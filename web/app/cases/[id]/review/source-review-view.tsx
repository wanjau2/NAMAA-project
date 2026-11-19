"use client";

/**
 * Source review — API-backed read path.
 *
 * Proposals, note text, offsets and extraction progress all come from the
 * server now (`GET /api/v1/documents/{id}`, `POST .../extractions`, SSE at
 * `/api/v1/extractions/{id}/events`). The fixtures are gone.
 *
 * Review decisions are the one thing still local: the API exposes no write
 * endpoint for them (Q10), so accept / correct / reject are held in component
 * state and the screen says plainly that nothing is persisted. They must not be
 * read as an authorization receipt.
 *
 * The boundary this screen exists to enforce is unchanged: a proposed fact has
 * no influence on rule evaluation until a clinical reviewer accepts or corrects
 * it, the excerpt is verified against the source, and a failed extraction is
 * never rendered as "no care gap".
 */

import { useId, useMemo, useState } from "react";
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
import { useDemoSession } from "@/lib/demo-session";
import { useCase, useCaseStore } from "@/lib/case-store";
import { useSourceReview } from "@/lib/use-source-review";
import { traceability, type Traceability } from "@/lib/text-offsets";
import {
  buildReviewCommand,
  hasBlockingIssue,
  normalizeProposal,
  type ProposedFact,
  type ReviewAction,
  type ValidationIssue,
} from "@/lib/contracts";
import { ApiError, ApiUnreachableError, api, newRequestId } from "@/lib/api";
import { describeSecurityOutcome, type SecurityOutcome } from "@/lib/security-states";
import {
  ASSERTION_LABELS,
  SUBJECT_LABELS,
  type ApiProposal,
  type Assertion,
  type ProposalSubject,
  type ReviewState,
} from "@/lib/api-types";

type CorrectedFields = {
  value_text: string;
  subject: ProposalSubject;
  assertion: Assertion;
  effective_date: string;
};

type Decision =
  | { state: "proposed" }
  | { state: "accepted" }
  | { state: "corrected"; corrected: CorrectedFields; reason: string }
  | { state: "rejected"; reason: string };

const REVIEW_BADGE: Record<ReviewState, { state: EpistemicState; label: string }> =
  {
    proposed: { state: "proposed", label: "Proposed — not yet reviewed" },
    accepted: { state: "verified", label: "Accepted by reviewer" },
    corrected: { state: "verified", label: "Corrected and accepted" },
    rejected: { state: "review", label: "Rejected — excluded from rules" },
  };

/** What happened when a review decision was sent to the server. */
type Persistence =
  | { kind: "persisted"; version: number }
  | { kind: "endpoint_absent" }
  | { kind: "cannot_build"; reason: string }
  | { kind: "refused"; outcome: SecurityOutcome; code: string };

export function SourceReviewView({ id }: { id: string }) {
  const { role } = useDemoSession();
  const { sessionId } = useCaseStore();
  const { case: row } = useCase(id);
  const review = useSourceReview(row, sessionId, role);

  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [persistence, setPersistence] = useState<Record<string, Persistence>>({});
  const [selected, setSelected] = useState<string | null>(null);

  /**
   * Send a review decision to POST /api/v1/facts/{id}/review.
   *
   * The endpoint does not exist yet. Rather than pretend, this attempts the
   * real call and reports exactly why it did not persist — so the day it ships,
   * review starts working with no further change here.
   */
  async function submitReview(
    proposalId: string,
    action: ReviewAction,
    reason: string,
    correction: ProposedFact | null,
  ): Promise<Persistence> {
    const raw = review.proposals.find((p) => p.id === proposalId);
    if (!raw || !sessionId) return { kind: "endpoint_absent" };

    const normalized = normalizeProposal(raw);
    const built = buildReviewCommand({
      requestId: newRequestId(),
      proposal: normalized.proposal,
      action,
      reviewerReference: "Practitioner/demo-reviewer",
      reason,
      correction,
      acknowledgedIssues: normalized.proposal.issues.map((i) => i.code),
    });
    if (!built.ok) return { kind: "cannot_build", reason: built.reason };

    try {
      const decision = await api.reviewFact(
        sessionId,
        "clinical_reviewer",
        proposalId,
        built.command,
      );
      return { kind: "persisted", version: decision.resulting_proposal_version };
    } catch (caught) {
      if (caught instanceof ApiError) {
        if (caught.status === 404 || caught.status === 405) {
          return { kind: "endpoint_absent" };
        }
        return {
          kind: "refused",
          outcome: describeSecurityOutcome(caught.status, "fact_review"),
          code: caught.code,
        };
      }
      if (caught instanceof ApiUnreachableError) {
        return {
          kind: "refused",
          outcome: describeSecurityOutcome(0, "fact_review"),
          code: "api_unreachable",
        };
      }
      return { kind: "endpoint_absent" };
    }
  }

  const isReviewer = role === "clinical_reviewer";
  const gateId = useId();

  const counts = useMemo(() => {
    const tally = { proposed: 0, accepted: 0, corrected: 0, rejected: 0 };
    for (const proposal of review.proposals) {
      tally[decisions[proposal.id]?.state ?? "proposed"] += 1;
    }
    return tally;
  }, [review.proposals, decisions]);

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
        Back to case detail
      </Link>

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
          onClick={review.rerun}
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-3 py-2 text-sm font-semibold text-ink hover:bg-subtle"
        >
          <RotateCcw aria-hidden="true" className="size-3.5" />
          Re-run extraction
        </button>
      </header>

      {/* Review decisions are not persisted — stated before anything else. */}
      <p className="mt-3 flex items-start gap-1.5 rounded-lg border border-dashed border-status-proposed bg-status-proposed-bg p-3 text-xs text-status-proposed">
        <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
        <span>
          Proposals, note text and offsets are served by the API. Review
          decisions are <strong>not persisted</strong>: the API has no
          fact-review endpoint yet, so accepting or correcting here records no
          reviewer identity and no provenance, and is not an authorization
          receipt.
        </span>
      </p>

      {/* Extraction progress. A failure is never "no care gap". */}
      <ExtractionStatus review={review} />

      {review.phase === "empty" && !review.document ? (
        <div className="mt-4 rounded-lg border border-border bg-subtle p-6">
          <p className="text-base font-semibold text-ink">
            No source note is available for this case
          </p>
          <p className="mt-1 text-sm text-ink-muted">
            This is an absence of an accessible note, not evidence that nothing
            was documented.
            {review.triedDocumentIds.length > 0 ? (
              <>
                {" "}
                Tried:{" "}
                <span className="font-mono-tech">
                  {review.triedDocumentIds.join(", ")}
                </span>
                .
              </>
            ) : null}
          </p>
        </div>
      ) : null}

      {review.document ? (
        <>
          {/* Boundary summary. */}
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
                The rule is evaluated from{" "}
                <span className="tabular font-medium text-ink">
                  {influencing}
                </span>{" "}
                reviewed fact{influencing === 1 ? "" : "s"}.{" "}
                <span className="tabular font-medium text-ink">
                  {counts.proposed}
                </span>{" "}
                pending proposal{counts.proposed === 1 ? " is" : "s are"}{" "}
                excluded. Re-evaluation happens on the server — this screen does
                not compute clinical logic.
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
            {/* Source note — read-only subtle pane. Untrusted input, rendered
                as text only, never markup. */}
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
                . The reviewer is recorded separately from the extractor.
              </p>
            </section>

            {/* Proposals */}
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
              <ul className="mt-2 space-y-3">
                {review.proposals.map((proposal) => (
                  <li key={proposal.id}>
                    <ProposalCard
                      noteText={noteText}
                      proposal={proposal}
                      model={{
                        revision: review.modelRevision,
                        inferenceMode: review.inferenceMode,
                      }}
                      decision={decisions[proposal.id] ?? { state: "proposed" }}
                      selected={selectedProposal?.id === proposal.id}
                      onSelect={() => setSelected(proposal.id)}
                      isReviewer={isReviewer}
                      gateId={isReviewer ? undefined : gateId}
                      persistence={persistence[proposal.id]}
                      onDecide={async (decision) => {
                        setDecisions((prev) => ({
                          ...prev,
                          [proposal.id]: decision,
                        }));
                        const action: ReviewAction =
                          decision.state === "accepted"
                            ? "accept"
                            : decision.state === "corrected"
                              ? "correct"
                              : "reject";
                        const reason =
                          "reason" in decision ? decision.reason : "Accepted as proposed.";
                        const result = await submitReview(
                          proposal.id,
                          action,
                          reason,
                          null,
                        );
                        setPersistence((prev) => ({
                          ...prev,
                          [proposal.id]: result,
                        }));
                      }}
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

function ExtractionStatus({
  review,
}: {
  review: ReturnType<typeof useSourceReview>;
}) {
  if (review.phase === "idle") return null;

  if (review.phase === "error") {
    return (
      <div className="mt-4 rounded-lg border border-status-overdue bg-status-overdue-bg p-4">
        <p className="flex items-start gap-2 text-sm font-semibold text-status-overdue">
          <AlertOctagon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <span>Extraction did not complete</span>
        </p>
        <p className="mt-2 text-sm text-ink">
          {review.message ?? review.progressLine ?? "The job did not finish."}
        </p>
        <p className="mt-2 text-xs text-ink-muted">
          A failed or timed-out extraction is <strong>not</strong> a finding of
          no care gap. The note remains unreviewed.
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
  proposal: ApiProposal | null;
}) {
  // Highlight only a verified span. With no offsets, or offsets that do not
  // match, nothing is highlighted — never the first occurrence of the excerpt,
  // which would invent a provenance the extractor did not claim.
  const trace = proposal ? traceability(text, proposal) : null;
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
  model,
  decision,
  persistence,
  selected,
  onSelect,
  isReviewer,
  gateId,
  onDecide,
}: {
  noteText: string;
  proposal: ApiProposal;
  model: { revision: string | null; inferenceMode: string | null };
  decision: Decision;
  persistence?: Persistence;
  selected: boolean;
  onSelect: () => void;
  isReviewer: boolean;
  gateId?: string;
  onDecide: (decision: Decision) => void;
}) {
  const [mode, setMode] = useState<"idle" | "correct" | "reject">("idle");
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState<string | null>(null);
  const [fields, setFields] = useState<CorrectedFields>({
    value_text: proposal.value_text,
    subject: proposal.subject,
    assertion: proposal.assertion,
    effective_date: proposal.effective_date ?? "",
  });

  const trace = traceability(noteText, proposal);
  // Alfred's contract shape, plus an honest list of what this API cannot send.
  const adapted = normalizeProposal(proposal);
  if (adapted.proposal.model === null && model.revision) {
    adapted.proposal.model = {
      model_id: "google/medgemma-1.5-4b-it",
      model_revision: model.revision,
      prompt_version: "unknown",
      simulated: model.inferenceMode !== "live",
    };
  }
  const blocked = hasBlockingIssue(adapted.proposal.issues);
  const traceable = trace.state === "verified" && !blocked;
  const badge = REVIEW_BADGE[decision.state];
  const reasonId = useId();

  // An untraceable quote is not reviewable: accepting it would put an
  // unsupported statement into the verified record.
  const actionable = isReviewer && traceable;

  const displayed =
    decision.state === "corrected"
      ? decision.corrected
      : {
          value_text: proposal.value_text,
          subject: proposal.subject,
          assertion: proposal.assertion,
          effective_date: proposal.effective_date ?? "",
        };

  function submitCorrection() {
    if (!reason.trim()) {
      setReasonError("A reason is required so the change is auditable.");
      return;
    }
    setReasonError(null);
    onDecide({ state: "corrected", corrected: fields, reason: reason.trim() });
    setMode("idle");
  }

  function submitRejection() {
    if (!reason.trim()) {
      setReasonError("A reason is required so the rejection is auditable.");
      return;
    }
    setReasonError(null);
    onDecide({ state: "rejected", reason: reason.trim() });
    setMode("idle");
  }

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
          <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">
            {proposal.concept}
          </p>
          <p className="mt-0.5 text-sm font-semibold text-ink">
            {displayed.value_text}
          </p>
        </div>
        <StatusBadge state={badge.state} label={badge.label} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
        <Chip label="Subject" value={SUBJECT_LABELS[displayed.subject]} />
        <Chip label="Assertion" value={ASSERTION_LABELS[displayed.assertion]} />
        <Chip
          label="Date"
          value={displayed.effective_date || "Not stated in note"}
          mono={Boolean(displayed.effective_date)}
        />
        <Chip label="Maps to" value={proposal.proposed_resource_type} mono />
      </div>

      {displayed.subject === "family_member" ? (
        <p className="mt-2 text-xs text-ink-muted">
          Recorded as family history, never as a diagnosis for this patient.
          {adapted.proposal.fact.relationship ? (
            <> Relationship: {adapted.proposal.fact.relationship}.</>
          ) : (
            <> Relationship not supplied by this API.</>
          )}
        </p>
      ) : null}

      <figure className="mt-3 rounded-md border-s-4 border-s-border bg-subtle p-3">
        <blockquote className="text-sm text-ink">
          &ldquo;{proposal.excerpt}&rdquo;
        </blockquote>
        <figcaption className="mt-1.5 text-xs text-ink-muted">
          <span className="font-mono-tech">
            {proposal.source_document_id} v{proposal.source_document_version}
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

      <ContractProvenance
        issues={adapted.proposal.issues}
        missing={adapted.missing}
        model={adapted.proposal.model}
        sourceVersion={adapted.proposal.source_document_version}
        sourceSha={adapted.proposal.source_sha256}
      />

      {decision.state === "corrected" ? (
        <div className="mt-3 rounded-md border border-border bg-canvas p-3 text-xs">
          <p className="font-semibold text-ink">What changed</p>
          <Diff
            label="Statement"
            was={proposal.value_text}
            now={decision.corrected.value_text}
          />
          <Diff
            label="Subject"
            was={SUBJECT_LABELS[proposal.subject]}
            now={SUBJECT_LABELS[decision.corrected.subject]}
          />
          <Diff
            label="Assertion"
            was={ASSERTION_LABELS[proposal.assertion]}
            now={ASSERTION_LABELS[decision.corrected.assertion]}
          />
          <Diff
            label="Date"
            was={proposal.effective_date ?? "Not stated"}
            now={decision.corrected.effective_date || "Not stated"}
          />
          <p className="mt-2 text-ink-muted">Reason: {decision.reason}</p>
        </div>
      ) : null}

      {decision.state === "rejected" ? (
        <p className="mt-3 text-xs text-ink-muted">Reason: {decision.reason}</p>
      ) : null}

      {persistence ? <PersistenceNote persistence={persistence} /> : null}

      {mode === "idle" ? (
        <div className="mt-4 flex flex-wrap gap-2">
          <ReviewButton
            allowed={actionable}
            describedBy={gateId}
            onClick={() => onDecide({ state: "accepted" })}
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
            allowed={isReviewer}
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
                    subject: event.target.value as ProposalSubject,
                  }))
                }
                className="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-ink"
              >
                <option value="patient">Patient</option>
                <option value="family_member">Family member</option>
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
                <option value="present">Present</option>
                <option value="absent">Absent</option>
                <option value="uncertain">Uncertain</option>
                <option value="historical">Historical</option>
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
              className="rounded-md bg-brand px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-hover"
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
              className="rounded-md bg-status-overdue px-3 py-1.5 text-xs font-semibold text-white"
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

/** What the server did with this decision — stated, never assumed. */
function PersistenceNote({ persistence }: { persistence: Persistence }) {
  if (persistence.kind === "persisted") {
    return (
      <p className="mt-2 rounded-md border border-status-verified bg-status-verified-bg p-2 text-xs text-status-verified">
        Recorded by the server. Proposal now at version{" "}
        <span className="font-mono-tech">{persistence.version}</span>.
      </p>
    );
  }

  if (persistence.kind === "endpoint_absent") {
    return (
      <p className="mt-2 rounded-md border border-dashed border-status-proposed bg-status-proposed-bg p-2 text-xs text-status-proposed">
        Held in this browser only. The API has no fact-review endpoint yet, so
        this decision has no reviewer identity and no provenance, and is not an
        authorization receipt.
      </p>
    );
  }

  if (persistence.kind === "cannot_build") {
    return (
      <p className="mt-2 rounded-md border border-status-review bg-status-review-bg p-2 text-xs text-status-review">
        Not sent: {persistence.reason}
      </p>
    );
  }

  return (
    <div className="mt-2 rounded-md border border-status-overdue bg-status-overdue-bg p-2 text-xs text-status-overdue">
      <p className="font-semibold">{persistence.outcome.title}</p>
      <p className="mt-1">{persistence.outcome.body}</p>
      {persistence.outcome.action ? (
        <p className="mt-1">{persistence.outcome.action}</p>
      ) : null}
      <p className="mt-1 font-mono-tech">[{persistence.code}]</p>
    </div>
  );
}

/**
 * Validation issues, model identity and source binding — Alfred's contract
 * fields. An empty issue list from an API that does not report issues is NOT a
 * clean bill of health, and this says so rather than showing a reassuring
 * blank.
 */
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
        ) : null}
      </p>
    </div>
  );
}

/**
 * The three ways traceability fails, told apart. "We could not locate it" is a
 * different statement from "the quote disagrees with the source", and a
 * reviewer needs to know which one they are looking at.
 */
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

function Diff({ label, was, now }: { label: string; was: string; now: string }) {
  if (was === now) return null;
  return (
    <p className="mt-1.5">
      <span className="text-ink-muted">{label}: </span>
      <span className="text-ink-muted line-through">{was}</span>
      <span aria-hidden="true" className="text-ink-muted"> → </span>
      <span className="sr-only">changed to</span>
      <span className="font-medium text-ink">{now}</span>
    </p>
  );
}
