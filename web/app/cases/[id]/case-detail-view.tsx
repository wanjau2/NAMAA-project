"use client";

/**
 * Case detail and source review (theme §5).
 *
 * The load-bearing pattern here is the EQUAL-WEIGHT UNCERTAINTY LAYOUT
 * (theme §4.3, D002): "Missing & Unverified Information" sits side by side with
 * "Suggested Pathway" at the same visual weight. Missing history must never
 * read as low risk — the design specification is explicit that an absent record
 * means incomplete information unless completeness has been verified.
 *
 * The action panel offers only valid transitions for the current simulated
 * role, and the server stays authoritative. Role switching grants nothing.
 */

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { StatusBadge, StatusCard } from "@/components/status-badge";
import { ActionPanel } from "@/components/action-panel";
import { useCaseStore } from "@/lib/case-store";
import {
  DISPOSITION_LABELS,
  PATHWAY_LABELS,
  STAGE_LABELS,
  getCaseDetail,
  getSourceReview,
} from "@/lib/mock-data";

export function CaseDetailView({ id }: { id: string }) {
  // Hooks first, unconditionally — the early return below must not sit
  // between them (react-hooks/rules-of-hooks).
  const { getCase, eventsFor } = useCaseStore();

  // Live state: actions taken in this session are reflected here, because the
  // store returned them, not because this component advanced anything itself.
  const row = getCase(id);
  const detail = getCaseDetail(id);
  const review = getSourceReview(id);
  const liveEvents = eventsFor(id);

  // The server shell already guaranteed this exists.
  if (!row) return null;

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <Link
        href="/cases"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted hover:text-ink"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        Back to worklist
      </Link>

      {/* Patient header. Caregiver authority is kept distinct from relationship,
          per the FHIR mapping rule for RelatedPerson. */}
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
          <div>
            <dt className="text-xs font-medium text-ink-muted">Stage</dt>
            <dd className="mt-1 text-ink">{STAGE_LABELS[row.stage]}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-ink-muted">Disposition</dt>
            <dd className="mt-1 text-ink">
              {DISPOSITION_LABELS[row.disposition]}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-ink-muted">Preferred contact</dt>
            <dd className="mt-1 text-ink">
              {row.contact_preference
                ? `${row.contact_preference.channel.toUpperCase()} · ${row.contact_preference.language.toUpperCase()} · ${row.contact_preference.preferred_time}`
                : "Not recorded"}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-ink-muted">
              Caregiver authority
            </dt>
            <dd className="mt-1 text-ink">Verified (synthetic)</dd>
          </div>
        </dl>
      </header>

      <div className="mt-5 grid gap-5 lg:grid-cols-[2fr_1fr]">
        {/* Start column */}
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
              <ul className="space-y-2">
                {detail.missing.map((item) => (
                  <li key={item.label}>
                    <p className="font-medium">{item.label}</p>
                    <p className="text-ink-muted">{item.consequence}</p>
                  </li>
                ))}
              </ul>
            </StatusCard>
          </div>

          {/* Contributing source facts, with proposed vs verified distinguished. */}
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
                  key={fact.label}
                  className="rounded-md border border-border bg-canvas p-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <p className="text-sm font-semibold text-ink">{fact.label}</p>
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

          {/* Chronological audit timeline. */}
          <section className="rounded-lg border border-border bg-surface p-5">
            <h2 className="text-lg text-ink">Event timeline</h2>
            <ol className="mt-4 space-y-3 border-s border-border ps-4">
              {detail.events.map((event) => (
                <li key={`${event.timestamp}-${event.action}`}>
                  <p className="font-mono-tech text-xs text-ink-muted">
                    {event.timestamp}
                  </p>
                  <p className="text-sm text-ink">{event.action}</p>
                  <p className="text-xs text-ink-muted">
                    Actor: <span className="font-mono-tech">{event.actor_role}</span>
                    {event.reason ? ` · ${event.reason}` : ""}
                  </p>
                </li>
              ))}
              {liveEvents.map((event) => (
                <li key={event.id}>
                  <p className="font-mono-tech text-xs text-ink-muted">
                    {event.timestamp}
                  </p>
                  <p className="text-sm text-ink">
                    {event.action}{" "}
                    <span className="font-mono-tech text-xs text-ink-muted">
                      {event.prior_state} → {event.new_state}
                    </span>
                  </p>
                  <p className="text-xs text-ink-muted">
                    Actor: <span className="font-mono-tech">{event.actor_role}</span>
                    {event.reason ? ` · ${event.reason}` : ""}
                    {event.evidence_reference
                      ? ` · evidence ${event.evidence_reference}`
                      : ""}
                  </p>
                </li>
              ))}
              {liveEvents.length === 0 ? (
                <li className="text-xs text-ink-muted">
                  No actions taken in this session yet.
                </li>
              ) : null}
            </ol>
          </section>
        </div>

        {/* End column: action panel */}
        <aside className="space-y-4">
          <ActionPanel caseState={row} />

          <section className="rounded-lg border border-border bg-subtle p-4">
            <h2 className="text-sm font-semibold text-ink">
              FHIR / audit inspector
            </h2>
            <p className="mt-1 text-xs text-ink-muted">
              Resource JSON, references and versions. Wired once Ismail&apos;s
              gateway lands (F4).
            </p>
            <p className="mt-2 font-mono-tech text-xs text-ink-muted">
              CarePlan/{row.care_gap_id} · rev {row.revision}
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
