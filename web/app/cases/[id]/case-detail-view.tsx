"use client";

/**
 * Case detail — API-backed.
 *
 * The load-bearing pattern is the EQUAL-WEIGHT UNCERTAINTY LAYOUT (theme §4.3):
 * "Missing & unverified information" sits beside "Suggested pathway" at the same
 * visual weight, because an absent record means incomplete information, never
 * low risk.
 *
 * Workflow stage/disposition come from `GET /api/v1/cases/{id}`. The rule
 * outcome comes from the patient evaluation resource. The action panel
 * submits to the server and renders the server's answer; it never advances a
 * stage locally.
 */

import { useEffect } from "react";
import Link from "next/link";
import { AlertOctagon, ArrowLeft, RotateCcw } from "lucide-react";
import { StatusBadge, StatusCard } from "@/components/status-badge";
import { RuleOutcomeBadge } from "@/components/rule-outcome";
import { CanonicalEvaluationPanel } from "@/components/canonical-evaluation";
import { resolveOutcome } from "@/lib/rule-outcomes";
import { ActionPanel } from "@/components/action-panel";
import { CaseInspector } from "@/components/case-inspector";
import { CaseSubnav } from "@/components/case-subnav";
import { chrome } from "@/lib/copy";
import { useCase, useCaseStore } from "@/lib/case-store";
import { useDemoSession } from "@/lib/demo-session";
import { usePatientEvaluation } from "@/lib/use-patient-evaluation";
import {
  CAREGIVER_AUTHORITY_LABELS,
  DISPOSITION_LABELS,
  PATHWAY_LABELS,
  STAGE_LABELS,
  type CaregiverAuthority,
} from "@/lib/api-types";

export function CaseDetailView({ id }: { id: string }) {
  const { case: row, loading, error, reload } = useCase(id);
  const { status, connectionMessage, sessionId, loadCase } = useCaseStore();
  const { role, sessionEpoch, locale } = useDemoSession();
  const evaluation = usePatientEvaluation(
    row?.patient_id,
    row?.pathway,
    sessionId,
    role,
    sessionEpoch,
  );
  const returnedCaseId =
    evaluation.status === "ready" && evaluation.ranNow
      ? evaluation.result.case?.id ?? null
      : null;
  const evaluationId =
    evaluation.status === "ready" ? evaluation.result.evaluation_id : null;

  // Source review decides whether a note is actually available. This link does
  // not claim that a document exists.

  useEffect(() => {
    if (row) document.title = `${row.patient_label} — Namaa`;
  }, [row]);

  useEffect(() => {
    if (!returnedCaseId) return;
    loadCase(id);
  }, [returnedCaseId, evaluationId, loadCase, id]);

  if (status === "unreachable") {
    return (
      <Shell>
        <Problem
          title="The Namaa API is not reachable"
          body={connectionMessage ?? "No connection to the API."}
          hint="Nothing is shown rather than stale or invented data."
          onRetry={reload}
        />
      </Shell>
    );
  }

  if (loading && !row) {
    return (
      <Shell>
        <div aria-busy="true" aria-live="polite">
          <p className="text-sm text-ink-muted">Loading case…</p>
          <div className="mt-4 h-28 animate-pulse rounded-lg bg-subtle" />
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div className="h-40 animate-pulse rounded-lg bg-subtle" />
            <div className="h-40 animate-pulse rounded-lg bg-subtle" />
          </div>
        </div>
      </Shell>
    );
  }

  if (error || !row) {
    return (
      <Shell>
        <Problem
          title={error?.code === "not_found" ? "Case not found" : "Could not load this case"}
          body={
            error?.message ??
            "This case is not present in the current guest session."
          }
          code={error?.code}
          onRetry={reload}
        />
      </Shell>
    );
  }

  const detail = row.detail;
  const outcome =
    evaluation.status === "ready" && evaluation.result.rule_evaluation
      ? resolveOutcome(evaluation.result.rule_evaluation.outcome)
      : null;
  const headerOutcome = outcome ?? resolveOutcome(row.flag_status);

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <Link
        href="/cases"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted hover:text-ink"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        {chrome(locale, "backToWorklist")}
      </Link>
      <CaseSubnav caseId={id} />

      {/* Patient header. Caregiver authority is kept distinct from relationship. */}
      <header className="mt-4 rounded-lg border border-border bg-surface p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl text-ink">{row.patient_label}</h1>
            <p className="mt-1 text-sm text-ink-muted">
              {row.age_band} · {PATHWAY_LABELS[row.pathway]} ·{" "}
              <span className="font-mono-tech">{row.rule_id_version}</span> ·{" "}
              <span className="font-mono-tech">rev {row.revision}</span>
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <RuleOutcomeBadge outcome={headerOutcome.outcome} />
            {!outcome ? (
              <span className="text-xs text-ink-muted">
                Worklist flag{" "}
                <span className="font-mono-tech">{row.flag_status}</span>
                {" "}
                — not the canonical evaluation
              </span>
            ) : null}
            {row.overdue ? <StatusBadge state="overdue" label="Overdue" /> : null}
            {row.disposition === "completed" ? (
              <StatusBadge
                state="verified"
                label={DISPOSITION_LABELS[row.disposition]}
              />
            ) : null}
          </div>
        </div>

        {/* Owner, next action and deadline belong here, not only on the
            worklist: the design specification §8 requires the case view to
            show who is responsible and by when. */}
        <dl className="mt-4 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <Meta label="Stage" value={STAGE_LABELS[row.stage]} />
          <Meta
            label="Disposition"
            value={DISPOSITION_LABELS[row.disposition]}
          />
          <Meta label="Owner" value={row.owner} />
          <Meta label="Appointment date" value={detail.booking?.appointment_time ?? "Not recorded"} />
          <Meta label="Appointment location" value={detail.booking?.location ?? "Not recorded"} />
          <Meta
            label="Due"
            value={row.due_time ? row.due_time.replace("T", " ") : "—"}
            mono={Boolean(row.due_time)}
          />
          <Meta
            label="Preferred contact"
            value={
              detail.contact_preference
                ? `${detail.contact_preference.channel.toUpperCase()} · ${detail.contact_preference.language.toUpperCase()} · ${detail.contact_preference.preferred_time}`
                : "Not recorded"
            }
          />
          <Meta
            label="Caregiver authority"
            value={authorityLabel(detail.caregiver_authority)}
          />
          <Meta
            label="Caregiver relationship"
            value={detail.caregiver_relationship || "Not supplied"}
          />
        </dl>

        <p className="mt-2 text-xs text-ink-muted">
          Caregiver relationship is not authorization. Authority is the server
          field above, not inferred from relationship or contact preference.
        </p>

        <p className="mt-3 text-sm text-ink">
          <span className="font-medium text-ink-muted">Next action: </span>
          {row.next_action}
        </p>

        {detail.completion_evidence ? (
          <p className="mt-3 text-xs text-ink-muted">
            Closure evidence:{" "}
            <span className="font-mono-tech">
              {detail.completion_evidence.evidence_type}/
              {detail.completion_evidence.evidence_reference}
            </span>
          </p>
        ) : null}
        {detail.recall_date ? (
          <p className="mt-1 text-xs text-ink-muted">
            Recall date:{" "}
            <span className="font-mono-tech">{detail.recall_date}</span>
          </p>
        ) : null}
        {detail.referral_outcome ? (
          <p className="mt-1 text-xs text-ink-muted">
            Referral outcome:{" "}
            <span className="font-mono-tech">{detail.referral_outcome}</span>
          </p>
        ) : null}
      </header>

      <div className="mt-5 grid gap-5 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-5">
          <CanonicalEvaluationPanel
            state={evaluation}
            onRetry={evaluation.reevaluate}
          />

          {/* Equal-weight pair: recommendation and uncertainty, same size.
              This is the case record, not the canonical evaluation. */}
          <div className="grid gap-4 md:grid-cols-2">
            <StatusCard
              state={
                headerOutcome.outcome === "needs_review"
                  ? "review"
                  : "verified"
              }
              title="Suggested pathway (case record)"
            >
              <p>{detail.explanation}</p>
              <p className="mt-3 text-sm">
                <span className="font-medium">Suggested review action: </span>
                {detail.suggested_review_action}
              </p>
            </StatusCard>

            <StatusCard state="review" title="Missing & unverified information">
              {detail.missing.length === 0 ? (
                <p>No outstanding gaps recorded for this case.</p>
              ) : (
                <ul className="space-y-2">
                  {detail.missing.map((item) => (
                    <li key={item.label}>
                      <p className="font-medium">{item.label}</p>
                      <p className="text-ink-muted">{item.consequence}</p>
                    </li>
                  ))}
                </ul>
              )}
            </StatusCard>
          </div>

          <section className="rounded-lg border border-border bg-surface p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-lg text-ink">Contributing records</h2>
                <p className="mt-1 text-sm text-ink-muted">
                  Each row shows its source and when it was observed. Proposed
                  facts have not been accepted by a reviewer and do not
                  influence the rule.
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                <Link
                  href={`/cases/${id}/review`}
                  className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-3 py-2 text-sm font-semibold text-ink hover:bg-canvas"
                >
                  {chrome(locale, "reviewSource")}
                </Link>
                <Link
                  href={`/cases/${id}/context`}
                  className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-3 py-2 text-sm font-semibold text-ink hover:bg-canvas"
                >
                  {chrome(locale, "retrievedContext")}
                </Link>
              </div>
            </div>
            <ul className="mt-4 space-y-3">
              {detail.factors.map((fact) => (
                <li
                  key={`${fact.label}-${fact.source}`}
                  className="rounded-md border border-border bg-canvas p-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <p className="text-sm font-semibold text-ink">
                      {fact.label}
                    </p>
                    {fact.verified ? (
                      <StatusBadge state="verified" label="Verified" />
                    ) : (
                      <StatusBadge
                        state="proposed"
                        label="Proposed — not yet reviewed"
                      />
                    )}
                  </div>
                  <p className="mt-1 text-sm text-ink">{fact.value}</p>
                  <p className="mt-1 text-xs text-ink-muted">
                    <span className="font-mono-tech">{fact.source}</span> ·{" "}
                    <span className="font-mono-tech">{fact.observed_time}</span>
                  </p>
                </li>
              ))}
            </ul>
          </section>

          {/* Audit timeline — the server's event log, not a local one. */}
          <section className="rounded-lg border border-border bg-surface p-5">
            <h2 className="text-lg text-ink">Event timeline</h2>
            <p className="mt-1 text-xs text-ink-muted">
              Recorded server-side. Every transition is auditable.
            </p>
            <ol className="mt-4 space-y-3 border-s border-border ps-4">
              {detail.events.map((event) => (
                <li key={event.id}>
                  <p className="font-mono-tech text-xs text-ink-muted">
                    {event.timestamp}
                  </p>
                  <p className="text-sm text-ink">
                    {event.action}
                    {event.prior_state && event.new_state ? (
                      <span className="font-mono-tech ms-1 text-xs text-ink-muted">
                        {event.prior_state} → {event.new_state}
                      </span>
                    ) : null}
                  </p>
                  <p className="text-xs text-ink-muted">
                    Actor:{" "}
                    <span className="font-mono-tech">{event.actor_role}</span>
                    {event.reason ? ` · ${event.reason}` : ""}
                    {event.booking ? ` · Appointment ${event.booking.appointment_time} at ${event.booking.location}` : ""}
                    {event.evidence_reference
                      ? ` · evidence ${event.evidence_reference}`
                      : ""}
                  </p>
                </li>
              ))}
              {detail.events.length === 0 ? (
                <li className="text-xs text-ink-muted">
                  No events recorded yet.
                </li>
              ) : null}
            </ol>
          </section>
        </div>

        <aside className="space-y-4">
          <ActionPanel caseState={row} onChanged={reload} />

          <CaseInspector caseState={row} />
        </aside>
      </div>
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  const { locale } = useDemoSession();
  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <Link
        href="/cases"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted hover:text-ink"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        {chrome(locale, "backToWorklist")}
      </Link>
      <div className="mt-4">{children}</div>
    </div>
  );
}

function Problem({
  title,
  body,
  hint,
  code,
  onRetry,
}: {
  title: string;
  body: string;
  hint?: string;
  code?: string;
  onRetry: () => void;
}) {
  return (
    <div className="rounded-lg border border-status-overdue bg-status-overdue-bg p-4">
      <h2 className="flex items-start gap-2 text-sm font-semibold text-status-overdue">
        <AlertOctagon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        <span>{title}</span>
      </h2>
      <p className="mt-2 text-sm text-ink">
        {body} {code ? <span className="font-mono-tech">[{code}]</span> : null}
      </p>
      {hint ? <p className="mt-2 text-xs text-ink-muted">{hint}</p> : null}
      <button
        type="button"
        onClick={onRetry}
        className="mt-3 inline-flex items-center gap-1.5 rounded border border-status-overdue px-2 py-1 text-xs font-semibold text-status-overdue"
      >
        <RotateCcw aria-hidden="true" className="size-3" />
        Retry
      </button>
    </div>
  );
}

function authorityLabel(value: CaregiverAuthority | null | undefined): string {
  if (!value) return CAREGIVER_AUTHORITY_LABELS.not_supplied;
  return CAREGIVER_AUTHORITY_LABELS[value] ?? CAREGIVER_AUTHORITY_LABELS.unknown;
}

function Meta({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-xs font-medium text-ink-muted">{label}</dt>
      <dd className={`mt-1 text-ink${mono ? " font-mono-tech text-xs" : ""}`}>
        {value}
      </dd>
    </div>
  );
}
