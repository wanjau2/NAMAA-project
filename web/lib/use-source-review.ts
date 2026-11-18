"use client";

/**
 * Drives the source-review read path against the API:
 *   resolve document -> queue extraction -> subscribe to SSE -> proposals.
 *
 * SSE replaces the 2-second polling the theme originally specified (D004); a
 * status GET is kept only as a fallback when the stream yields no proposals.
 *
 * Review decisions are NOT handled here. The API has no write endpoint for
 * them (Q10), so the screen keeps them in local state and says so.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, api } from "@/lib/api";
import type {
  ApiProposal,
  CaseOut,
  DocumentOut,
  ExtractionState,
  Role,
} from "@/lib/api-types";
import { resolveCaseDocument } from "@/lib/source-documents";
import {
  formatExtractionElapsed,
  isTerminalExtraction,
  subscribeExtractionProgress,
  type ExtractionProgressEvent,
} from "@/lib/extraction-sse";

export type SourceReviewState = {
  phase: "idle" | "resolving" | "extracting" | "ready" | "empty" | "error";
  document: DocumentOut | null;
  proposals: ApiProposal[];
  jobId: string | null;
  extractionState: ExtractionState | null;
  progressPercent: number;
  /** "Extracting… 12s (90s timeout)" — the theme's required elapsed line. */
  progressLine: string;
  modelRevision: string | null;
  inferenceMode: string | null;
  message: string | null;
  triedDocumentIds: string[];
  rerun: () => void;
};

export function useSourceReview(
  caseOut: CaseOut | undefined,
  sessionId: string | null,
  role: Role,
): SourceReviewState {
  const [phase, setPhase] = useState<SourceReviewState["phase"]>("idle");
  const [document, setDocument] = useState<DocumentOut | null>(null);
  const [proposals, setProposals] = useState<ApiProposal[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [extractionState, setExtractionState] =
    useState<ExtractionState | null>(null);
  const [progressPercent, setProgressPercent] = useState(0);
  const [progressLine, setProgressLine] = useState("");
  const [modelRevision, setModelRevision] = useState<string | null>(null);
  const [inferenceMode, setInferenceMode] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [tried, setTried] = useState<string[]>([]);
  const [runToken, setRunToken] = useState(0);

  const unsubscribe = useRef<null | (() => void)>(null);

  const rerun = useCallback(() => setRunToken((n) => n + 1), []);

  useEffect(() => {
    if (!caseOut || !sessionId) return;
    let cancelled = false;

    (async () => {
      setPhase("resolving");
      setProposals([]);
      setMessage(null);
      setExtractionState(null);
      setProgressPercent(0);
      setProgressLine("");

      const resolved = await resolveCaseDocument(sessionId, role, caseOut);
      if (cancelled) return;

      if (!resolved.found) {
        setTried(resolved.tried);
        setDocument(null);
        setPhase("empty");
        return;
      }

      setDocument(resolved.document);
      setPhase("extracting");

      let accepted;
      try {
        accepted = await api.startExtraction(
          sessionId,
          role,
          resolved.document.id,
        );
      } catch (caught) {
        if (cancelled) return;
        setMessage(
          caught instanceof Error ? caught.message : "Could not queue extraction.",
        );
        setPhase("error");
        return;
      }
      if (cancelled) return;

      setJobId(accepted.job_id);
      setExtractionState(accepted.state);

      const finish = async (event?: ExtractionProgressEvent) => {
        if (cancelled) return;
        // Proposals ride the terminal SSE frame when disclosure is permitted;
        // otherwise fall back to the status endpoint.
        const fromEvent = (event?.proposals ?? []) as ApiProposal[];
        if (fromEvent.length > 0) {
          setProposals(fromEvent);
          setPhase("ready");
          return;
        }
        try {
          const status = await api.getExtraction(
            sessionId,
            role,
            accepted.job_id,
          );
          if (cancelled) return;
          setProposals(status.proposals ?? []);
          setModelRevision(status.model_revision);
          setInferenceMode(status.inference_mode);
          setPhase(status.proposals?.length ? "ready" : "empty");
        } catch {
          if (!cancelled) setPhase("error");
        }
      };

      unsubscribe.current = subscribeExtractionProgress({
        apiBaseUrl: API_BASE,
        jobId: accepted.job_id,
        sessionId,
        onEvent: (event) => {
          if (cancelled) return;
          setExtractionState(event.state);
          setProgressPercent(event.progress_percent);
          setProgressLine(formatExtractionElapsed(event));
          setModelRevision(event.model_revision);
          setInferenceMode(event.inference_mode);
          if (event.error_message) setMessage(event.error_message);
          if (isTerminalExtraction(event.state)) {
            if (event.state === "succeeded") {
              void finish(event);
            } else {
              // A failed or timed-out extraction is NEVER "no care gap".
              setPhase("error");
            }
          }
        },
        onError: () => {
          // Stream dropped — fall back to the status endpoint once.
          if (!cancelled) void finish();
        },
      });
    })();

    return () => {
      cancelled = true;
      unsubscribe.current?.();
      unsubscribe.current = null;
    };
  }, [caseOut, sessionId, role, runToken]);

  return {
    phase,
    document,
    proposals,
    jobId,
    extractionState,
    progressPercent,
    progressLine,
    modelRevision,
    inferenceMode,
    message,
    triedDocumentIds: tried,
    rerun,
  };
}
