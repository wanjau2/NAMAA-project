"use client";

/**
 * Source review — API-backed read and review path.
 *
 * Proposals, note text and offsets come from the server. Review commands post
 * to POST /api/v1/facts/{id}/review. Badges and counts update only from a
 * validated server response or GET-fact readback. FHIR commit is a stub.
 */

import { useId, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertOctagon,
  ArrowLeft,
  Check,
  Info,
  Pencil,
  RotateCcw,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/status-badge";
import type { EpistemicState } from "@/components/status-badge";
import { CaseSubnav } from "@/components/case-subnav";
import { chrome } from "@/lib/copy";
import { useDemoSession } from "@/lib/demo-session";
import { useCase, useCaseStore } from "@/lib/case-store";
import { useSourceReview } from "@/lib/use-source-review";
import { traceability, type Traceability } from "@/lib/text-offsets";
import {
  ASSERTIONS,
  FACT_SUBJECTS,
  RELATIONSHIPS,
  buildCorrection,
  buildReviewCommand,
  commandFingerprint,
  decisionMatchesCommand,
  factIsComplete,
  hasBlockingIssue,
  mergeReviewedProposal,
  normalizeProposal,
  reviewSeverityIssues,
  type Assertion,
  type ContractProposal,
  type FactSubject,
  type ProposedFact,
  type Relationship,
  type ReviewAction,
  type ReviewCommand,
  type ReviewDecision,
  type ValidationIssue,
} from "@/lib/contracts";
import {
  ApiError,
  api,
  errorCode,
  errorFieldErrors,
  errorHttpStatus,
  newRequestId,
} from "@/lib/api";
import {
  describeSecurityOutcome,
  type SecurityOutcome,
} from "@/lib/security-states";
import {
  ASSERTION_LABELS,
  SUBJECT_LABELS,
  type ReviewState,
} from "@/lib/api-types";

type CorrectedFields = {
  value_text: string;
  subject: FactSubject;
  assertion: Assertion;
  effective_date: string;
  relationship: Relationship | null;
};

type ReviewAttempt = {
  requestId: string;
  fingerprint: string;
  action: ReviewAction;
  status:
    | "submitting"
    | "confirmed"
    | "cannot_build"
    | "refused"
    | "stale"
    | "invalid"
    | "uncertain";
  reason?: string;
  outcome?: SecurityOutcome;
  code?: string;
  fieldErrors?: Record<string, string>;
  version?: number;
  reviewer?: string | null;
  fhirGateway?: string | null;
  notice?: string | null;
};

const REVIEW_BADGE: Record<ReviewState, { state: EpistemicState; label: string }> =
  {
    proposed: { state: "proposed", label: "Proposed — not yet reviewed" },
    accepted: { state: "verified", label: "Accepted by reviewer" },
    corrected: { state: "verified", label: "Corrected and accepted" },
    rejected: { state: "review", label: "Rejected — excluded from rules" },
  };

const RELATIONSHIP_LABELS: Record<Relationship, string> = {
  mother: "Mother",
  father: "Father",
  sister: "Sister",
  brother: "Brother",
  sibling: "Sibling",
  grandmother: "Grandmother",
  grandfather: "Grandfather",
};

export function SourceReviewView({ id }: { id: string }) {
  const { role, sessionEpoch, locale } = useDemoSession();
  const { sessionId } = useCaseStore();
  const { case: row } = useCase(id);
  const review = useSourceReview(row, sessionId, role, sessionEpoch);

  const [attempts, setAttempts] = useState<Record<string, ReviewAttempt>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const inFlight = useRef<Set<string>>(new Set());
  const requestIds = useRef<Record<string, string>>({});

  async function submitReview(input: {
    proposal: ContractProposal;
    action: ReviewAction;
    reason: string;
    correction: ProposedFact | null;
    acknowledgedIssues: string[];
  }): Promise<void> {
    const { proposal, action, reason, correction, acknowledgedIssues } = input;
    if (!sessionId || inFlight.current.has(proposal.id)) return;

    const fingerprint = commandFingerprint({
      action,
      reason,
      correction,
      acknowledgedIssues,
    });
    const requestKey = `${proposal.id}:${proposal.version ?? "none"}:${fingerprint}`;
    if (!requestIds.current[requestKey]) {
      requestIds.current[requestKey] = newRequestId();
    }
    const requestId = requestIds.current[requestKey];

    const built = buildReviewCommand({
      requestId,
      proposal,
      action,
      reason,
      correction,
      acknowledgedIssues,
    });
    if (!built.ok) {
      setAttempts((prev) => ({
        ...prev,
        [proposal.id]: {
          requestId,
          fingerprint,
          action,
          status: "cannot_build",
          reason: built.reason,
        },
      }));
      return;
    }

    inFlight.current.add(proposal.id);
    setAttempts((prev) => ({
      ...prev,
      [proposal.id]: {
        requestId,
        fingerprint,
        action,
        status: "submitting",
      },
    }));

    try {
      const decision = await api.reviewFact(
        sessionId,
        role,
        proposal.id,
        built.command,
      );
      await confirmDecision(proposal, built.command, decision);
    } catch (caught) {
      const httpStatus = errorHttpStatus(caught);
      const code = errorCode(caught);
      const fields = errorFieldErrors(caught);
      if (httpStatus === 409) {
        try {
          const fresh = await api.getFact(sessionId, role, proposal.id);
          review.replaceProposal(normalizeOrKeep(proposal, fresh));
        } catch {
          // Readback failed; the 409 copy still asks the reviewer to reload.
        }
        setAttempts((prev) => ({
          ...prev,
          [proposal.id]: {
            requestId,
            fingerprint,
            action,
            status: "stale",
            outcome: describeSecurityOutcome(409, "fact_review"),
            code,
            fieldErrors: fields,
          },
        }));
        return;
      }
      if (httpStatus === 422) {
        setAttempts((prev) => ({
          ...prev,
          [proposal.id]: {
            requestId,
            fingerprint,
            action,
            status: "invalid",
            outcome: describeSecurityOutcome(422, "fact_review"),
            code,
            fieldErrors: fields,
            reason: caught instanceof ApiError ? caught.message : undefined,
          },
        }));
        return;
      }
      if (httpStatus === 0 || httpStatus >= 500) {
        setAttempts((prev) => ({
          ...prev,
          [proposal.id]: {
            requestId,
            fingerprint,
            action,
            status: "uncertain",
            outcome: describeSecurityOutcome(httpStatus, "fact_review"),
            code,
          },
        }));
        return;
      }
      setAttempts((prev) => ({
        ...prev,
        [proposal.id]: {
          requestId,
          fingerprint,
          action,
          status: "refused",
          outcome: describeSecurityOutcome(httpStatus, "fact_review"),
          code,
        },
      }));
    } finally {
      inFlight.current.delete(proposal.id);
    }
  }

  async function confirmDecision(
    proposal: ContractProposal,
    command: ReviewCommand,
    decision: ReviewDecision,
  ) {
    if (!decisionMatchesCommand(decision, command)) {
      setAttempts((prev) => ({
        ...prev,
        [proposal.id]: {
          requestId: command.request_id,
          fingerprint: commandFingerprint({
            action: command.action,
            reason: command.reason,
            correction: command.correction,
            acknowledgedIssues: command.acknowledged_issues,
          }),
          action: command.action,
          status: "uncertain",
          outcome: describeSecurityOutcome(0, "fact_review"),
          code: "identity_mismatch",
          reason:
            "The server response did not match the command that was sent, so this is not treated as a confirmed review.",
        },
      }));
      return;
    }

    let readback: unknown | null = null;
    if (sessionId) {
      try {
        readback = await api.getFact(sessionId, role, proposal.id);
      } catch {
        readback = null;
      }
    }
    review.replaceProposal(mergeReviewedProposal(proposal, decision, readback));
    setAttempts((prev) => ({
      ...prev,
      [proposal.id]: {
        requestId: command.request_id,
        fingerprint: commandFingerprint({
          action: command.action,
          reason: command.reason,
          correction: command.correction,
          acknowledgedIssues: command.acknowledged_issues,
        }),
        action: command.action,
        status: "confirmed",
        version: decision.resulting_proposal_version,
        reviewer: decision.command.reviewer_reference ?? null,
        fhirGateway: decision.fhir_gateway ?? "stub",
        notice: decision.notice ?? null,
      },
    }));
  }

  const isReviewer = role === "clinical_reviewer";
  const gateId = useId();

  const counts = useMemo(() => {
    const tally = { proposed: 0, accepted: 0, corrected: 0, rejected: 0 };
    for (const proposal of review.proposals) {
      tally[proposal.state] += 1;
    }
    return tally;
  }, [review.proposals]);

  const noteText = review.document?.text ?? "";
  const selectedProposal =
    review.proposals.find((p) => p.id === selected) ??
    review.proposals[0] ??
    null;
  const influencing = counts.accepted + counts.corrected;

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      <Link
        href={`/cases/${id}`}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted hover:text-ink"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        {chrome(locale, "backToCase")}
      </Link>
      <CaseSubnav caseId={id} />

      <header className="mt-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl text-ink">Source review</h1>
          <p className="mt-1 max-w-3xl text-sm text-ink-muted">
            {row ? `${row.patient_label} · ` : ""}Facts proposed from one source
            note. Nothing here influences the demonstration rule until it is
            accepted or corrected by a clinical reviewer.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setAttempts({});
            review.rerun();
          }}
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-3 py-2 text-sm font-semibold text-ink hover:bg-subtle"
        >
          <RotateCcw aria-hidden="true" className="size-3.5" />
          Re-run extraction
        </button>
      </header>

      <p className="mt-3 flex items-start gap-1.5 rounded-lg border border-dashed border-status-proposed bg-status-proposed-bg p-3 text-xs text-status-proposed">
        <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
        <span>
          Review decisions are <strong>journaled in this synthetic workspace</strong>.
          FHIR commit uses a <strong>gateway stub</strong> — this is not a HAPI
          write and is not an authorization receipt. Accepted facts are
          available for a later server evaluation; this screen does not
          re-evaluate the rule.
        </span>
      </p>

      <ExtractionStatus review={review} />

      {review.phase === "unavailable" ||
      ((review.phase === "failed" ||
        review.phase === "timed_out" ||
        review.phase === "cancelled") &&
        !review.document) ? (
        <SecurityPanel
          outcome={
            review.readOutcome ??
            describeSecurityOutcome(0, "note_retrieve")
          }
          onRetry={review.rerun}
        />
      ) : null}

      {review.phase === "empty" && !review.document ? (
        <div className="mt-4 rounded-lg border border-border bg-subtle p-6">
          <p className="text-base font-semibold text-ink">
            No source note is available for this case
          </p>
          <p className="mt-1 text-sm text-ink-muted">
            This is an authorized empty result, not evidence that nothing was
            documented, and not an access denial.
          </p>
        </div>
      ) : null}

      {review.document ? (
        <>
          <section
            aria-label="Review progress"
            className="mt-4 rounded-lg border border-border bg-surface p-4"
          >
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
              <Tally label="Pending" value={counts.proposed} />
              <Tally label="Accepted" value={counts.accepted} />
              <Tally label="Corrected" value={counts.corrected} />
              <Tally label="Rejected" value={counts.rejected} />
            </div>
            <p className="mt-3 flex items-start gap-1.5 text-xs text-ink-muted">
              <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
              <span>
                <span className="tabular font-medium text-ink">
                  {influencing}
                </span>{" "}
                reviewed fact{influencing === 1 ? "" : "s"}{" "}
                {influencing === 1 ? "is" : "are"} available for a later server
                evaluation.{" "}
                <span className="tabular font-medium text-ink">
                  {counts.proposed}
                </span>{" "}
                pending proposal{counts.proposed === 1 ? " is" : "s are"}{" "}
                excluded. Counts come from the server after each decision. This
                screen does not compute clinical logic.
              </span>
            </p>
            <p className="mt-2 flex items-start gap-1.5 text-xs text-ink-muted">
              <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
              <span>
                Instruction-like sentences in the source note are treated as
                data. No proposal was created from them.
              </span>
            </p>
          </section>

          {!isReviewer ? (
            <p
              id={gateId}
              className="mt-4 flex items-start gap-2 rounded-lg border border-status-review bg-status-review-bg p-3 text-sm text-status-review"
            >
              <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              <span>
                Requires the Clinical Reviewer role to accept, correct or reject
                a proposed fact. Switch role in the simulation bar to
                demonstrate review. Role switching is a labelled simulation, not
                authorization.
              </span>
            </p>
          ) : null}

          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <section className="lg:sticky lg:top-16 lg:self-start">
              <h2 className="text-lg text-ink">Source note</h2>
              <p className="mt-1 text-xs text-ink-muted">
                <span className="font-mono-tech">{review.document.id}</span> ·
                version{" "}
                <span className="font-mono-tech">
                  {review.document.version}
                </span>{" "}
                ·{" "}
                <span className="font-mono-tech">
                  {review.document.document_date}
                </span>
              </p>
              <div className="mt-2 rounded-lg border border-border bg-subtle p-4">
                <p className="text-base leading-relaxed text-ink">
                  <NoteText text={noteText} proposal={selectedProposal} />
                </p>
              </div>
              <p className="mt-2 text-xs text-ink-muted">
                Retrieved under policy adapter{" "}
                <span className="font-mono-tech">
                  {review.document.policy_adapter}
                </span>
                {review.document.production_authorization
                  ? ""
                  : " · not production-authorized"}
                . Extracted with{" "}
                <span className="font-mono-tech">
                  {review.modelRevision ?? "unknown"}
                </span>
                {review.inferenceMode ? (
                  <>
                    {" "}
                    ·{" "}
                    <span className="font-mono-tech">
                      {review.inferenceMode}
                    </span>
                  </>
                ) : null}
                . The reviewer is recorded separately from the extractor, and
                only by the server.
              </p>
            </section>

            <section>
              <h2 className="text-lg text-ink">
                Proposed facts{" "}
                <span className="tabular text-sm font-normal text-ink-muted">
                  ({review.proposals.length})
                </span>
              </h2>
              {review.proposals.length === 0 && review.phase === "ready" ? (
                <p className="mt-2 rounded-lg border border-border bg-subtle p-4 text-sm text-ink-muted">
                  The extractor proposed nothing from this note. That is not a
                  finding of no care gap.
                </p>
              ) : null}
              {review.phase === "empty" && review.document ? (
                <p className="mt-2 rounded-lg border border-border bg-subtle p-4 text-sm text-ink-muted">
                  Extraction succeeded and proposed nothing. That is not a
                  finding of no care gap.
                </p>
              ) : null}
              <ul className="mt-2 space-y-3">
                {review.proposals.map((proposal) => (
                  <li key={proposal.id}>
                    <ProposalCard
                      noteText={noteText}
                      proposal={proposal}
                      adapted={review.adapted[proposal.id]}
                      attempt={attempts[proposal.id]}
                      selected={selectedProposal?.id === proposal.id}
                      onSelect={() => setSelected(proposal.id)}
                      isReviewer={isReviewer}
                      gateId={isReviewer ? undefined : gateId}
                      onSubmit={(payload) =>
                        void submitReview({ proposal, ...payload })
                      }
                    />
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </>
      ) : null}
    </div>
  );
}

function normalizeOrKeep(
  current: ContractProposal,
  raw: unknown,
): ContractProposal {
  const adapted = normalizeProposal(raw);
  if (!adapted.proposal.id) return current;
  return {
    ...adapted.proposal,
    state:
      adapted.proposal.state === "proposed" ? current.state : adapted.proposal.state,
  };
}

function ExtractionStatus({
  review,
}: {
  review: ReturnType<typeof useSourceReview>;
}) {
  if (review.phase === "idle") return null;

  const stopped =
    review.phase === "failed" ||
    review.phase === "timed_out" ||
    review.phase === "cancelled";

  if (stopped && review.document) {
    const title =
      review.phase === "timed_out"
        ? "Extraction timed out"
        : review.phase === "cancelled"
          ? "Extraction was cancelled"
          : "Extraction did not complete";
    return (
      <div className="mt-4 rounded-lg border border-status-overdue bg-status-overdue-bg p-4">
        <p className="flex items-start gap-2 text-sm font-semibold text-status-overdue">
          <AlertOctagon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <span>{title}</span>
        </p>
        <p className="mt-2 text-sm text-ink">
          {review.message ?? review.progressLine ?? "The job did not finish."}
        </p>
        {review.readOutcome ? (
          <p className="mt-2 text-sm text-ink">{review.readOutcome.body}</p>
        ) : null}
        <p className="mt-2 text-xs text-ink-muted">
          A failed, cancelled or timed-out extraction is <strong>not</strong> a
          finding of no care gap. The note remains unreviewed.
        </p>
        <button
          type="button"
          onClick={review.rerun}
          className="mt-3 inline-flex items-center gap-1.5 rounded border border-status-overdue px-2 py-1 text-xs font-semibold text-status-overdue"
        >
          <RotateCcw aria-hidden="true" className="size-3" />
          Retry extraction
        </button>
      </div>
    );
  }

  if (review.phase === "resolving" || review.phase === "extracting") {
    return (
      <div
        className="mt-4 rounded-lg border border-border bg-surface p-4"
        aria-busy="true"
        aria-live="polite"
      >
        <p className="text-sm text-ink">
          {review.phase === "resolving"
            ? "Locating the source note…"
            : review.progressLine || "Queued…"}
        </p>
        {review.message ? (
          <p className="mt-1 text-xs text-ink-muted">{review.message}</p>
        ) : null}
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-subtle">
          <div
            className="h-full rounded-full bg-brand transition-[width]"
            style={{ width: `${Math.max(review.progressPercent, 5)}%` }}
          />
        </div>
        {review.jobId ? (
          <p className="mt-2 font-mono-tech text-xs text-ink-muted">
            {review.jobId} · {review.extractionState}
          </p>
        ) : null}
      </div>
    );
  }

  return null;
}

function SecurityPanel({
  outcome,
  onRetry,
}: {
  outcome: SecurityOutcome;
  onRetry: () => void;
}) {
  return (
    <div className="mt-4 rounded-lg border border-status-overdue bg-status-overdue-bg p-4">
      <p className="flex items-start gap-2 text-sm font-semibold text-status-overdue">
        <AlertOctagon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        <span>{outcome.title}</span>
      </p>
      <p className="mt-2 text-sm text-ink">{outcome.body}</p>
      {outcome.caveat ? (
        <p className="mt-2 text-xs text-ink-muted">{outcome.caveat}</p>
      ) : null}
      {outcome.action ? (
        <p className="mt-2 text-xs text-ink-muted">{outcome.action}</p>
      ) : null}
      {outcome.state === "failed" || outcome.state === "no_session" ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 inline-flex items-center gap-1.5 rounded border border-status-overdue px-2 py-1 text-xs font-semibold text-status-overdue"
        >
          <RotateCcw aria-hidden="true" className="size-3" />
          Retry
        </button>
      ) : null}
    </div>
  );
}

function Tally({ label, value }: { label: string; value: number }) {
  return (
    <span className="flex items-baseline gap-1.5">
      <span className="tabular text-lg font-semibold text-ink">{value}</span>
      <span className="text-xs text-ink-muted">{label}</span>
    </span>
  );
}

function NoteText({
  text,
  proposal,
}: {
  text: string;
  proposal: ContractProposal | null;
}) {
  const span = proposal
    ? {
        excerpt: proposal.fact.excerpt,
        offset_start: proposal.offset_start,
        offset_end: proposal.offset_end,
      }
    : null;
  const trace = span ? traceability(text, span) : null;
  if (!trace || trace.state !== "verified") {
    return <>{text}</>;
  }
  return (
    <>
      {trace.before}
      <mark className="rounded bg-status-proposed-bg px-0.5 text-status-proposed underline decoration-dashed decoration-1 underline-offset-2">
        {trace.match}
      </mark>
      {trace.after}
    </>
  );
}

function ProposalCard({
  noteText,
  proposal,
  adapted,
  attempt,
  selected,
  onSelect,
  isReviewer,
  gateId,
  onSubmit,
}: {
  noteText: string;
  proposal: ContractProposal;
  adapted?: ReturnType<typeof useSourceReview>["adapted"][string];
  attempt?: ReviewAttempt;
  selected: boolean;
  onSelect: () => void;
  isReviewer: boolean;
  gateId?: string;
  onSubmit: (payload: {
    action: ReviewAction;
    reason: string;
    correction: ProposedFact | null;
    acknowledgedIssues: string[];
  }) => void;
}) {
  const fact = proposal.fact;
  const [mode, setMode] = useState<"idle" | "correct" | "reject">("idle");
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState<string | null>(null);
  const [acked, setAcked] = useState<Set<string>>(new Set());
  const [fields, setFields] = useState<CorrectedFields>({
    value_text: fact.value_text,
    subject: fact.subject ?? "patient",
    assertion: fact.assertion ?? "present",
    effective_date: fact.effective_date ?? "",
    relationship: fact.relationship,
  });

  const trace = traceability(noteText, {
    excerpt: fact.excerpt,
    offset_start: proposal.offset_start,
    offset_end: proposal.offset_end,
  });
  const issues = adapted?.proposal.issues ?? proposal.issues;
  const missing = adapted?.missing ?? [];
  const malformed = adapted?.malformed ?? [];
  const blocked = hasBlockingIssue(issues);
  const reviewIssues = reviewSeverityIssues(issues);
  const allReviewAcked = reviewIssues.every((issue) => acked.has(issue.code));
  const traceable = trace.state === "verified" && !blocked && malformed.length === 0;
  const alreadyReviewed = proposal.state !== "proposed";
  const submitting = attempt?.status === "submitting";
  const badge = REVIEW_BADGE[proposal.state];
  const reasonId = useId();
  const complete = factIsComplete(fact);
  const actionable =
    isReviewer &&
    traceable &&
    complete &&
    !alreadyReviewed &&
    !submitting &&
    allReviewAcked;

  const displayed = fact;

  function submitCorrection() {
    if (!reason.trim()) {
      setReasonError("A reason is required so the change is auditable.");
      return;
    }
    const correction = buildCorrection(fact, fields);
    if (!correction) {
      setReasonError(
        "A correction must be a complete replacement fact with valid subject, assertion and resource type.",
      );
      return;
    }
    setReasonError(null);
    onSubmit({
      action: "correct",
      reason: reason.trim(),
      correction,
      acknowledgedIssues: [...acked],
    });
    setMode("idle");
  }

  function submitRejection() {
    if (!reason.trim()) {
      setReasonError("A reason is required so the rejection is auditable.");
      return;
    }
    setReasonError(null);
    onSubmit({
      action: "reject",
      reason: reason.trim(),
      correction: null,
      acknowledgedIssues: [...acked],
    });
    setMode("idle");
  }

  const subjectLabel = displayed.subject
    ? SUBJECT_LABELS[displayed.subject]
    : "Not supplied";
  const assertionLabel = displayed.assertion
    ? ASSERTION_LABELS[displayed.assertion]
    : "Not supplied";

  return (
    <article
      onFocus={onSelect}
      onMouseEnter={onSelect}
      className={cn(
        "rounded-lg border bg-surface p-4 transition-colors",
        selected ? "border-brand-focus" : "border-border",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs font-medium tracking-wide text-ink-muted">
            {displayed.concept.replaceAll("_", " ") || "Unnamed concept"}
          </p>
          <p className="mt-0.5 text-sm font-semibold text-ink">
            {displayed.value_text || "No statement supplied"}
          </p>
        </div>
        <StatusBadge state={badge.state} label={badge.label} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
        <Chip label="Subject" value={subjectLabel} />
        <Chip label="Assertion" value={assertionLabel} />
        <Chip
          label="Date"
          value={displayed.effective_date || "Not stated in note"}
          mono={Boolean(displayed.effective_date)}
        />
        <Chip
          label="Maps to"
          value={displayed.proposed_resource_type ?? "Not supplied"}
          mono
        />
      </div>

      {displayed.subject === "family_member" ? (
        <p className="mt-2 text-xs text-ink-muted">
          Recorded as family history, never as a diagnosis for this patient.
          {displayed.relationship ? (
            <> Relationship: {RELATIONSHIP_LABELS[displayed.relationship]}.</>
          ) : (
            <> Relationship not supplied.</>
          )}
        </p>
      ) : null}

      <figure className="mt-3 rounded-md border-s-4 border-s-border bg-subtle p-3">
        <blockquote className="text-sm text-ink">
          &ldquo;{displayed.excerpt}&rdquo;
        </blockquote>
        <figcaption className="mt-1.5 text-xs text-ink-muted">
          <span className="font-mono-tech">
            {proposal.source_document_id} {proposal.source_document_version}
          </span>{" "}
          ·{" "}
          {proposal.offset_start === null || proposal.offset_end === null ? (
            <span>no source offsets</span>
          ) : (
            <>
              code points{" "}
              <span className="font-mono-tech">
                {proposal.offset_start}–{proposal.offset_end}
              </span>
            </>
          )}
        </figcaption>
      </figure>

      {!traceable && trace.state !== "verified" ? (
        <TraceabilityProblem trace={trace} />
      ) : null}

      {malformed.length > 0 ? (
        <p className="mt-2 flex items-start gap-1.5 rounded-md border border-status-overdue bg-status-overdue-bg p-2 text-xs text-status-overdue">
          <AlertOctagon aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          <span>
            This proposal is missing or has illegal required fields (
            {malformed.join(", ")}). Those values were not filled in. It cannot
            be accepted or corrected.
          </span>
        </p>
      ) : null}

      <ContractProvenance
        issues={issues}
        missing={missing}
        model={proposal.model}
        sourceVersion={proposal.source_document_version}
        sourceSha={proposal.source_sha256}
      />

      {proposal.reviewer_reference || attempt?.reviewer ? (
        <p className="mt-2 text-xs text-ink-muted">
          Server-bound reviewer{" "}
          <span className="font-mono-tech">
            {proposal.reviewer_reference ?? attempt?.reviewer}
          </span>
          {proposal.review_reason ? ` · ${proposal.review_reason}` : null}. This
          identity is synthetic and was not chosen in the browser.
        </p>
      ) : isReviewer ? (
        <p className="mt-2 text-xs text-ink-muted">
          Reviewer identity is bound by the server for this synthetic session.
          The browser does not send a practitioner reference.
        </p>
      ) : null}

      {reviewIssues.length > 0 && !alreadyReviewed ? (
        <fieldset className="mt-3 space-y-2 rounded-md border border-status-review bg-status-review-bg p-3">
          <legend className="text-xs font-semibold text-status-review">
            Review issues to acknowledge
          </legend>
          <p className="text-xs text-ink-muted">
            Each issue must be acknowledged explicitly. They are not marked
            acknowledged on your behalf.
          </p>
          {reviewIssues.map((issue) => (
            <label
              key={issue.code}
              className="flex items-start gap-2 text-xs text-ink"
            >
              <input
                type="checkbox"
                className="mt-0.5"
                checked={acked.has(issue.code)}
                disabled={!isReviewer || submitting}
                aria-label={`Acknowledge issue ${issue.code}`}
                onChange={(event) => {
                  setAcked((prev) => {
                    const next = new Set(prev);
                    if (event.target.checked) next.add(issue.code);
                    else next.delete(issue.code);
                    return next;
                  });
                }}
              />
              <span>
                {issue.message}{" "}
                <span className="font-mono-tech">[{issue.code}]</span>
              </span>
            </label>
          ))}
        </fieldset>
      ) : null}

      {attempt ? <AttemptNote attempt={attempt} onRetry={() => {
        if (attempt.status === "uncertain") {
          onSubmit({
            action: attempt.action,
            reason: reason.trim() || "Accepted as proposed.",
            correction: attempt.action === "correct" ? buildCorrection(fact, fields) : null,
            acknowledgedIssues: [...acked],
          });
        }
      }} /> : null}

      {mode === "idle" && !alreadyReviewed ? (
        <div className="mt-4 flex flex-wrap gap-2">
          <ReviewButton
            allowed={actionable}
            describedBy={gateId}
            onClick={() =>
              onSubmit({
                action: "accept",
                reason: "Accepted as proposed.",
                correction: null,
                acknowledgedIssues: [...acked],
              })
            }
            tone="primary"
          >
            <Check aria-hidden="true" className="size-3.5" />
            Accept
          </ReviewButton>
          <ReviewButton
            allowed={actionable}
            describedBy={gateId}
            onClick={() => {
              setReason("");
              setReasonError(null);
              setMode("correct");
            }}
          >
            <Pencil aria-hidden="true" className="size-3.5" />
            Correct
          </ReviewButton>
          <ReviewButton
            allowed={isReviewer && !submitting && !alreadyReviewed}
            describedBy={gateId}
            onClick={() => {
              setReason("");
              setReasonError(null);
              setMode("reject");
            }}
          >
            <X aria-hidden="true" className="size-3.5" />
            Reject
          </ReviewButton>
        </div>
      ) : null}

      {mode === "correct" ? (
        <form
          className="mt-4 space-y-3 rounded-md border border-border bg-canvas p-3"
          onSubmit={(event) => {
            event.preventDefault();
            submitCorrection();
          }}
        >
          <Field label="Statement" htmlFor={`${proposal.id}-value`}>
            <textarea
              id={`${proposal.id}-value`}
              value={fields.value_text}
              onChange={(event) =>
                setFields((f) => ({ ...f, value_text: event.target.value }))
              }
              rows={2}
              className="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-ink"
            />
          </Field>

          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Subject" htmlFor={`${proposal.id}-subject`}>
              <select
                id={`${proposal.id}-subject`}
                value={fields.subject}
                onChange={(event) =>
                  setFields((f) => ({
                    ...f,
                    subject: event.target.value as FactSubject,
                  }))
                }
                className="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-ink"
              >
                {FACT_SUBJECTS.map((value) => (
                  <option key={value} value={value}>
                    {SUBJECT_LABELS[value]}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Assertion" htmlFor={`${proposal.id}-assertion`}>
              <select
                id={`${proposal.id}-assertion`}
                value={fields.assertion}
                onChange={(event) =>
                  setFields((f) => ({
                    ...f,
                    assertion: event.target.value as Assertion,
                  }))
                }
                className="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-ink"
              >
                {ASSERTIONS.map((value) => (
                  <option key={value} value={value}>
                    {ASSERTION_LABELS[value]}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Date (explicit only)" htmlFor={`${proposal.id}-date`}>
              <input
                id={`${proposal.id}-date`}
                type="date"
                value={fields.effective_date}
                onChange={(event) =>
                  setFields((f) => ({
                    ...f,
                    effective_date: event.target.value,
                  }))
                }
                className="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-ink"
              />
            </Field>
          </div>

          {fields.subject === "family_member" ? (
            <Field label="Relationship" htmlFor={`${proposal.id}-relationship`}>
              <select
                id={`${proposal.id}-relationship`}
                value={fields.relationship ?? ""}
                onChange={(event) =>
                  setFields((f) => ({
                    ...f,
                    relationship: (event.target.value || null) as Relationship | null,
                  }))
                }
                className="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-ink"
              >
                <option value="">Not supplied</option>
                {RELATIONSHIPS.map((value) => (
                  <option key={value} value={value}>
                    {RELATIONSHIP_LABELS[value]}
                  </option>
                ))}
              </select>
            </Field>
          ) : null}

          <ReasonField
            id={reasonId}
            value={reason}
            onChange={setReason}
            error={reasonError}
            label="Reason for the correction"
          />

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={submitting || !allReviewAcked}
              className="rounded-md bg-brand px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-hover disabled:opacity-50"
            >
              Save correction
            </button>
            <button
              type="button"
              onClick={() => setMode("idle")}
              className="rounded-md border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-ink hover:bg-subtle"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : null}

      {mode === "reject" ? (
        <form
          className="mt-4 space-y-3 rounded-md border border-border bg-canvas p-3"
          onSubmit={(event) => {
            event.preventDefault();
            submitRejection();
          }}
        >
          <ReasonField
            id={reasonId}
            value={reason}
            onChange={setReason}
            error={reasonError}
            label="Reason for rejecting this proposal"
          />
          <p className="text-xs text-ink-muted">
            A rejected proposal is excluded from rule evaluation. It is retained
            with its reason and reviewer, not deleted.
          </p>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-status-overdue px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
            >
              Reject proposal
            </button>
            <button
              type="button"
              onClick={() => setMode("idle")}
              className="rounded-md border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-ink hover:bg-subtle"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : null}
    </article>
  );
}

function AttemptNote({
  attempt,
  onRetry,
}: {
  attempt: ReviewAttempt;
  onRetry: () => void;
}) {
  if (attempt.status === "submitting") {
    return (
      <p className="mt-2 text-xs text-ink-muted" aria-live="polite">
        Sending review command{" "}
        <span className="font-mono-tech">{attempt.requestId}</span>…
      </p>
    );
  }

  if (attempt.status === "confirmed") {
    return (
      <p className="mt-2 rounded-md border border-status-verified bg-status-verified-bg p-2 text-xs text-status-verified">
        Recorded in this synthetic workspace. Proposal now at version{" "}
        <span className="font-mono-tech">{attempt.version}</span>
        . FHIR gateway:{" "}
        <span className="font-mono-tech">{attempt.fhirGateway ?? "stub"}</span>{" "}
        — not a HAPI commit.
      </p>
    );
  }

  if (attempt.status === "cannot_build") {
    return (
      <p className="mt-2 rounded-md border border-status-review bg-status-review-bg p-2 text-xs text-status-review">
        Not sent: {attempt.reason}
      </p>
    );
  }

  return (
    <div className="mt-2 rounded-md border border-status-overdue bg-status-overdue-bg p-2 text-xs text-status-overdue">
      <p className="font-semibold">
        {attempt.outcome?.title ?? "The request was not applied"}
      </p>
      <p className="mt-1">
        {attempt.reason ?? attempt.outcome?.body}
      </p>
      {attempt.outcome?.action ? (
        <p className="mt-1">{attempt.outcome.action}</p>
      ) : null}
      {attempt.fieldErrors && Object.keys(attempt.fieldErrors).length > 0 ? (
        <ul className="mt-1 list-disc ps-4">
          {Object.entries(attempt.fieldErrors).map(([field, message]) => (
            <li key={field}>
              <span className="font-mono-tech">{field}</span>: {message}
            </li>
          ))}
        </ul>
      ) : null}
      <p className="mt-1 font-mono-tech">
        [{attempt.code}] request {attempt.requestId}
      </p>
      {attempt.status === "uncertain" ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 inline-flex items-center gap-1.5 rounded border border-status-overdue px-2 py-1 text-xs font-semibold"
        >
          Retry the same command
        </button>
      ) : null}
    </div>
  );
}

function ContractProvenance({
  issues,
  missing,
  model,
  sourceVersion,
  sourceSha,
}: {
  issues: ValidationIssue[];
  missing: string[];
  model: { model_revision: string; prompt_version: string; simulated: boolean } | null;
  sourceVersion: string;
  sourceSha: string | null;
}) {
  const issuesUnavailable = missing.includes("issues");

  return (
    <div className="mt-3 border-t border-border pt-3">
      {issues.length > 0 ? (
        <ul className="space-y-1">
          {issues.map((issue) => (
            <li
              key={issue.code}
              className={cn(
                "flex items-start gap-1.5 rounded-md border p-2 text-xs",
                issue.severity === "block"
                  ? "border-status-overdue bg-status-overdue-bg text-status-overdue"
                  : "border-status-review bg-status-review-bg text-status-review",
              )}
            >
              <AlertOctagon aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
              <span>
                <b>{issue.severity === "block" ? "Blocking" : "Review"}:</b>{" "}
                {issue.message}{" "}
                <span className="font-mono-tech">[{issue.code}]</span>
              </span>
            </li>
          ))}
        </ul>
      ) : issuesUnavailable ? (
        <p className="text-xs text-ink-muted">
          Validation issues are not reported by this API. An empty list here
          means <b>not reported</b>, not &ldquo;none found&rdquo;.
        </p>
      ) : null}

      <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted">
        <span>
          source version{" "}
          <span className="font-mono-tech">{sourceVersion}</span>
        </span>
        <span>
          source hash{" "}
          {sourceSha ? (
            <span className="font-mono-tech">{sourceSha.slice(0, 12)}…</span>
          ) : (
            <span>not supplied</span>
          )}
        </span>
        {model ? (
          <span>
            model <span className="font-mono-tech">{model.model_revision}</span>
            {model.simulated ? (
              <span className="ms-1 rounded border border-dashed border-status-proposed px-1.5 py-0.5 text-status-proposed">
                simulated
              </span>
            ) : null}
          </span>
        ) : (
          <span>model identity not supplied</span>
        )}
      </p>
    </div>
  );
}

function TraceabilityProblem({ trace }: { trace: Traceability }) {
  const copy =
    trace.state === "no_offsets"
      ? "No source offsets were returned, so this excerpt cannot be located in the note. The extractor did not claim a position for it, and the interface will not guess one."
      : trace.state === "out_of_range"
        ? "The stated offsets fall outside this note, so the excerpt cannot be verified against its source."
        : `The text at these offsets does not match the excerpt. The note reads \u201c${
            "found" in trace ? trace.found : ""
          }\u201d.`;

  return (
    <p className="mt-2 flex items-start gap-1.5 rounded-md border border-status-overdue bg-status-overdue-bg p-2 text-xs text-status-overdue">
      <AlertOctagon aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
      <span>
        {copy} Not reviewable — this proposal cannot be accepted. Return it for
        re-extraction.
      </span>
    </p>
  );
}

function ReviewButton({
  children,
  allowed,
  describedBy,
  onClick,
  tone = "secondary",
}: {
  children: React.ReactNode;
  allowed: boolean;
  describedBy?: string;
  onClick: () => void;
  tone?: "primary" | "secondary";
}) {
  return (
    <button
      type="button"
      aria-disabled={!allowed}
      aria-describedby={allowed ? undefined : describedBy}
      onClick={() => {
        if (!allowed) return;
        onClick();
      }}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold",
        !allowed
          ? "cursor-not-allowed border border-border bg-subtle text-ink-muted"
          : tone === "primary"
            ? "bg-brand text-white hover:bg-brand-hover"
            : "border border-border bg-surface text-ink hover:bg-subtle",
      )}
    >
      {children}
    </button>
  );
}

function ReasonField({
  id,
  value,
  onChange,
  error,
  label,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  error: string | null;
  label: string;
}) {
  return (
    <div>
      <label htmlFor={id} className="text-xs font-medium text-ink-muted">
        {label}
      </label>
      <textarea
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={2}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className={cn(
          "mt-1 w-full rounded-md border bg-surface px-2 py-1.5 text-sm text-ink",
          error ? "border-status-overdue" : "border-border",
        )}
      />
      {error ? (
        <p
          id={`${id}-error`}
          className="mt-1 flex items-start gap-1.5 text-xs text-status-overdue"
        >
          <AlertOctagon aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          <span>{error}</span>
        </p>
      ) : null}
    </div>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="text-xs font-medium text-ink-muted">
        {label}
      </label>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function Chip({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-border bg-canvas px-2 py-0.5">
      <span className="text-ink-muted">{label}:</span>
      <span className={cn("text-ink", mono && "font-mono-tech")}>{value}</span>
    </span>
  );
}
