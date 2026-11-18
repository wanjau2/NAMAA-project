"use client";

/**
 * Case detail — API-backed.
 *
 * The load-bearing pattern is the EQUAL-WEIGHT UNCERTAINTY LAYOUT (theme §4.3):
 * "Missing & unverified information" sits beside "Suggested pathway" at the same
 * visual weight, because an absent record means incomplete information, never
 * low risk.
 *
 * Everything shown here comes from `GET /api/v1/cases/{id}`. The action panel
 * submits to the server and renders the server's answer; it never advances a
 * stage locally.
 */

import { useEffect } from "react";
import Link from "next/link";
import { AlertOctagon, ArrowLeft, RotateCcw } from "lucide-react";
import { StatusBadge, StatusCard } from "@/components/status-badge";
import { ActionPanel } from "@/components/action-panel";
import { useCase, useCaseStore } from "@/lib/case-store";
import {
  DISPOSITION_LABELS,
  PATHWAY_LABELS,
  STAGE_LABELS,
} from "@/lib/api-types";
import { getSourceReview } from "@/lib/source-review-fixtures";

export function CaseDetailView({ id }: { id: string }) {
  const { case: row, loading, error, reload } = useCase(id);
  const { status, connectionMessage } = useCaseStore();

  // Source review still runs on fixtures: the API has no proposal endpoints yet.
  const review = getSourceReview(id);

  useEffect(() => {
    if (row) document.title = `${row.patient_label} — Namaa`;
  }, [row]);

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

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <Link
        href="/cases"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted hover:text-ink"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        Back to worklist
      </Link>

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
            {row.flag_status === "needs_review" ? (
              <StatusBadge state="review" label="Needs review" />
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

        <dl className="mt-4 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <Meta label="Stage" value={STAGE_LABELS[row.stage]} />
          <Meta
            label="Disposition"
            value={DISPOSITION_LABELS[row.disposition]}
          />
          <Meta
            label="Preferred contact"
            value={
              detail.contact_preference
                ? `${detail.contact_preference.channel.toUpperCase()} · ${detail.contact_preference.language.toUpperCase()} · ${detail.contact_preference.preferred_time}`
                : "Not recorded"
            }
          />
          <Meta label="Caregiver authority" value="Verified (synthetic)" />
        </dl>

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
          {/* Equal-weight pair: recommendation and uncertainty, same size. */}
          <div className="grid gap-4 md:grid-cols-2">
            <StatusCard
              state={row.flag_status === "needs_review" ? "review" : "verified"}
              title="Suggested pathway"
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
              {review ? (
                <Link
                  href={`/cases/${id}/review`}
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-border bg-surface px-3 py-2 text-sm font-semibold text-ink hover:bg-subtle"
                >
                  Review source facts
                  <span className="tabular text-xs text-ink-muted">
                    ({review.proposals.length})
                  </span>
                </Link>
              ) : null}
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

          <section className="rounded-lg border border-border bg-subtle p-4">
            <h2 className="text-sm font-semibold text-ink">
              FHIR / audit inspector
            </h2>
            <p className="mt-1 text-xs text-ink-muted">
              Resource references and versions. HAPI is not deployed for this
              sprint (D003) — identifiers are FHIR-shaped synthetic ids held in
              the application store.
            </p>
            <p className="mt-2 font-mono-tech text-xs text-ink-muted">
              CarePlan/{row.care_gap_id} · rev {row.revision}
              {row.patient_id ? (
                <>
                  <br />
                  Patient/{row.patient_id}
                </>
              ) : null}
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <Link
        href="/cases"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted hover:text-ink"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        Back to worklist
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
      <p className="flex items-start gap-2 text-sm font-semibold text-status-overdue">
        <AlertOctagon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        <span>{title}</span>
      </p>
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

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium text-ink-muted">{label}</dt>
      <dd className="mt-1 text-ink">{value}</dd>
    </div>
  );
}
