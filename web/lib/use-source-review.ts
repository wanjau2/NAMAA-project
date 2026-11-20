"use client";

/**
 * Drives the source-review read path against the API:
 *   list case documents -> get note -> queue extraction -> SSE -> proposals.
 *
 * Proposals are normalized once at this boundary. Review writes live in the
 * view so a refused decision cannot look reviewed before the server answers.
 *
 * SSE is the progress channel. Status GET is a bounded fallback after a drop
 * or malformed frame. A still-running, failed, cancelled or timed-out job is
 * never turned into extraction-empty just because it has no proposals yet.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, api, errorHttpStatus } from "@/lib/api";
import type {
  CaseOut,
  DocumentOut,
  ExtractionJobOut,
  ExtractionState,
  Role,
} from "@/lib/api-types";
import {
  normalizeProposal,
  type AdaptedProposal,
  type ContractProposal,
} from "@/lib/contracts";
import { resolveCaseDocument } from "@/lib/source-documents";
import {
  formatExtractionElapsed,
  isTerminalExtraction,
  subscribeExtractionProgress,
  type ExtractionProgressEvent,
} from "@/lib/extraction-sse";
import {
  interpretExtractionJob,
  MAX_MALFORMED_FRAMES,
  MAX_SSE_ERRORS,
  MAX_STATUS_POLLS,
  STATUS_POLL_MS,
} from "@/lib/extraction-recovery";
import {
  describeSecurityOutcome,
  type SecurityOutcome,
} from "@/lib/security-states";

export type SourceReviewPhase =
  | "idle"
  | "resolving"
  | "extracting"
  | "ready"
  | "empty"
  | "unavailable"
  | "failed"
  | "timed_out"
  | "cancelled";

export type NormalizedProposal = AdaptedProposal & { shape: "nested" | "flat" };

export type SourceReviewState = {
  phase: SourceReviewPhase;
  document: DocumentOut | null;
  proposals: ContractProposal[];
  adapted: Record<string, NormalizedProposal>;
  jobId: string | null;
  extractionState: ExtractionState | null;
  progressPercent: number;
  /** "Extracting… 12s (90s timeout)" — the theme's required elapsed line. */
  progressLine: string;
  modelRevision: string | null;
  inferenceMode: string | null;
  message: string | null;
  readOutcome: SecurityOutcome | null;
  replaceProposal: (next: ContractProposal) => void;
  rerun: () => void;
};

function adaptAll(raw: unknown[]): {
  proposals: ContractProposal[];
  adapted: Record<string, NormalizedProposal>;
} {
  const adapted: Record<string, NormalizedProposal> = {};
  const proposals: ContractProposal[] = [];
  for (const item of raw) {
    const result = normalizeProposal(item);
    if (!result.proposal.id) continue;
    adapted[result.proposal.id] = result;
    proposals.push(result.proposal);
  }
  return { proposals, adapted };
}

function lineFromJob(job: ExtractionJobOut): string {
  return formatExtractionElapsed({
    event: isTerminalExtraction(job.state) ? "terminal" : "progress",
    job_id: job.job_id,
    document_id: job.document_id,
    document_version: job.document_version,
    state: job.state,
    progress_percent: job.progress_percent,
    message: job.message,
    elapsed_ms: job.elapsed_ms,
    timeout_ms: job.timeout_ms,
    model_revision: job.model_revision,
    prompt_version: job.prompt_version,
    error_code: job.error_code,
    error_message: job.error_message,
    synthetic: job.synthetic,
    inference_mode: job.inference_mode,
    proposals: job.proposals,
  });
}

const NOT_A_GAP =
  "This is not a finding of no care gap. The note remains unreviewed.";

export function useSourceReview(
  caseOut: CaseOut | undefined,
  sessionId: string | null,
  role: Role,
  sessionEpoch: number,
): SourceReviewState {
  const [phase, setPhase] = useState<SourceReviewPhase>("idle");
  const [document, setDocument] = useState<DocumentOut | null>(null);
  const [proposals, setProposals] = useState<ContractProposal[]>([]);
  const [adapted, setAdapted] = useState<Record<string, NormalizedProposal>>(
    {},
  );
  const [jobId, setJobId] = useState<string | null>(null);
  const [extractionState, setExtractionState] =
    useState<ExtractionState | null>(null);
  const [progressPercent, setProgressPercent] = useState(0);
  const [progressLine, setProgressLine] = useState("");
  const [modelRevision, setModelRevision] = useState<string | null>(null);
  const [inferenceMode, setInferenceMode] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [readOutcome, setReadOutcome] = useState<SecurityOutcome | null>(null);
  const [runToken, setRunToken] = useState(0);

  const unsubscribe = useRef<null | (() => void)>(null);
  const generation = useRef(0);

  const caseId = caseOut?.id;
  const caseRef = useRef(caseOut);
  caseRef.current = caseOut;

  const rerun = useCallback(() => setRunToken((n) => n + 1), []);

  const replaceProposal = useCallback((next: ContractProposal) => {
    setProposals((prev) =>
      prev.map((proposal) => (proposal.id === next.id ? next : proposal)),
    );
    setAdapted((prev) => {
      const current = prev[next.id];
      if (!current) return prev;
      return {
        ...prev,
        [next.id]: { ...current, proposal: next },
      };
    });
  }, []);

  useEffect(() => {
    const currentCase = caseRef.current;
    if (!currentCase || !sessionId) return;
    const gen = ++generation.current;
    let cancelled = false;
    let pollTimer: ReturnType<typeof setTimeout> | null = null;
    let polls = 0;
    let sseErrors = 0;
    let malformed = 0;
    let terminalHandled = false;

    unsubscribe.current?.();
    unsubscribe.current = null;

    setPhase("resolving");
    setDocument(null);
    setProposals([]);
    setAdapted({});
    setJobId(null);
    setExtractionState(null);
    setProgressPercent(0);
    setProgressLine("");
    setModelRevision(null);
    setInferenceMode(null);
    setMessage(null);
    setReadOutcome(null);

    const applyIfCurrent = (fn: () => void) => {
      if (!cancelled && generation.current === gen) fn();
    };

    const clearPoll = () => {
      if (pollTimer) {
        clearTimeout(pollTimer);
        pollTimer = null;
      }
    };

    const stopStream = () => {
      unsubscribe.current?.();
      unsubscribe.current = null;
      clearPoll();
    };

    (async () => {
      const resolved = await resolveCaseDocument(sessionId, role, currentCase);
      applyIfCurrent(() => {
        if (resolved.status === "unavailable") {
          setReadOutcome(resolved.outcome);
          setPhase(
            resolved.outcome.state === "not_available" ||
              resolved.outcome.state === "no_session"
              ? "unavailable"
              : "failed",
          );
          return;
        }
        if (resolved.status === "empty") {
          setPhase("empty");
        }
      });
      if (cancelled || generation.current !== gen) return;
      if (resolved.status !== "found") return;

      applyIfCurrent(() => {
        setDocument(resolved.document);
        setPhase("extracting");
      });

      let accepted;
      try {
        accepted = await api.startExtraction(
          sessionId,
          role,
          resolved.document.id,
        );
      } catch (caught) {
        const httpStatus = errorHttpStatus(caught);
        applyIfCurrent(() => {
          setReadOutcome(
            describeSecurityOutcome(httpStatus, "extraction_stream"),
          );
          setMessage(
            caught instanceof Error ? caught.message : "Could not queue extraction.",
          );
          setPhase(
            httpStatus === 401 || httpStatus === 403 || httpStatus === 404
              ? "unavailable"
              : "failed",
          );
        });
        return;
      }
      if (cancelled || generation.current !== gen) return;

      applyIfCurrent(() => {
        setJobId(accepted.job_id);
        setExtractionState(accepted.state);
      });

      const applySucceeded = (raw: unknown[]) => {
        if (terminalHandled || cancelled || generation.current !== gen) return;
        terminalHandled = true;
        stopStream();
        const next = adaptAll(raw);
        applyIfCurrent(() => {
          setProposals(next.proposals);
          setAdapted(next.adapted);
          setExtractionState("succeeded");
          setPhase(next.proposals.length ? "ready" : "empty");
        });
      };

      const applyStop = (
        kind: "failed" | "timed_out" | "cancelled",
        stopMessage: string,
      ) => {
        if (terminalHandled || cancelled || generation.current !== gen) return;
        terminalHandled = true;
        stopStream();
        applyIfCurrent(() => {
          setMessage(stopMessage);
          setExtractionState(kind);
          setPhase(kind);
        });
      };

      const recoverFromStatus = async () => {
        if (cancelled || generation.current !== gen || terminalHandled) return;
        try {
          const status = await api.getExtraction(
            sessionId,
            role,
            accepted.job_id,
          );
          if (cancelled || generation.current !== gen || terminalHandled) return;
          const interpreted = interpretExtractionJob(status);
          applyIfCurrent(() => {
            setModelRevision(status.model_revision);
            setInferenceMode(status.inference_mode);
            setExtractionState(status.state);
            setProgressPercent(status.progress_percent);
            setProgressLine(lineFromJob(status));
            if (status.error_message) setMessage(status.error_message);
          });
          if (interpreted.kind === "succeeded") {
            applySucceeded(interpreted.proposals);
            return;
          }
          if (
            interpreted.kind === "failed" ||
            interpreted.kind === "timed_out" ||
            interpreted.kind === "cancelled"
          ) {
            applyStop(interpreted.kind, interpreted.message);
            return;
          }
          polls += 1;
          if (polls >= MAX_STATUS_POLLS) {
            applyStop(
              "failed",
              `Extraction progress could not be confirmed. ${NOT_A_GAP}`,
            );
            return;
          }
          pollTimer = setTimeout(() => {
            void recoverFromStatus();
          }, STATUS_POLL_MS);
        } catch (caught) {
          if (cancelled || generation.current !== gen || terminalHandled) return;
          const httpStatus = errorHttpStatus(caught);
          if (httpStatus === 401 || httpStatus === 403 || httpStatus === 404) {
            terminalHandled = true;
            stopStream();
            applyIfCurrent(() => {
              setReadOutcome(
                describeSecurityOutcome(httpStatus, "proposal_disclose"),
              );
              setPhase("unavailable");
            });
            return;
          }
          polls += 1;
          if (polls >= MAX_STATUS_POLLS) {
            applyStop(
              "failed",
              caught instanceof Error
                ? `${caught.message} ${NOT_A_GAP}`
                : `Could not read extraction status. ${NOT_A_GAP}`,
            );
            return;
          }
          pollTimer = setTimeout(() => {
            void recoverFromStatus();
          }, STATUS_POLL_MS);
        }
      };

      unsubscribe.current = subscribeExtractionProgress({
        apiBaseUrl: API_BASE,
        jobId: accepted.job_id,
        sessionId,
        role,
        onEvent: (event: ExtractionProgressEvent) => {
          if (cancelled || generation.current !== gen || terminalHandled) return;
          setExtractionState(event.state);
          setProgressPercent(event.progress_percent);
          setProgressLine(formatExtractionElapsed(event));
          setModelRevision(event.model_revision);
          setInferenceMode(event.inference_mode);
          if (event.error_message) setMessage(event.error_message);
          if (!isTerminalExtraction(event.state)) return;
          if (event.state === "succeeded") {
            const fromEvent = event.proposals ?? [];
            if (fromEvent.length > 0) {
              applySucceeded(fromEvent);
              return;
            }
            void recoverFromStatus();
            return;
          }
          if (event.state === "timed_out") {
            applyStop(
              "timed_out",
              event.error_message ||
                event.message ||
                `Extraction timed out. ${NOT_A_GAP}`,
            );
            return;
          }
          if (event.state === "cancelled") {
            applyStop(
              "cancelled",
              event.error_message ||
                event.message ||
                `Extraction was cancelled. ${NOT_A_GAP}`,
            );
            return;
          }
          applyStop(
            "failed",
            event.error_message ||
              event.message ||
              `Extraction failed. ${NOT_A_GAP}`,
          );
        },
        onError: () => {
          if (cancelled || generation.current !== gen || terminalHandled) return;
          sseErrors += 1;
          applyIfCurrent(() => {
            setMessage("Progress stream interrupted. Checking job status…");
          });
          if (sseErrors > MAX_SSE_ERRORS && polls >= MAX_STATUS_POLLS) {
            applyStop(
              "failed",
              `The progress stream closed before a terminal result. ${NOT_A_GAP}`,
            );
            return;
          }
          void recoverFromStatus();
        },
        onMalformed: (raw) => {
          if (cancelled || generation.current !== gen || terminalHandled) return;
          if (!raw.trim() || raw.trim().startsWith(":")) return;
          malformed += 1;
          applyIfCurrent(() => {
            setMessage(
              "A progress event could not be read. Checking job status…",
            );
          });
          if (malformed >= MAX_MALFORMED_FRAMES) {
            void recoverFromStatus();
          }
        },
      });
    })();

    return () => {
      cancelled = true;
      unsubscribe.current?.();
      unsubscribe.current = null;
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [caseId, sessionId, role, runToken, sessionEpoch]);

  return {
    phase,
    document,
    proposals,
    adapted,
    jobId,
    extractionState,
    progressPercent,
    progressLine,
    modelRevision,
    inferenceMode,
    message,
    readOutcome,
    replaceProposal,
    rerun,
  };
}
