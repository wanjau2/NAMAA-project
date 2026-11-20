"use client";

/**
 * Retrieved-context panel.
 *
 * Live data is POST /api/v1/security/verified-context (`records`) plus Relate
 * discovery hints. That is not Alfred AssembledContext (query, tiers, items).
 * Contract examples stay on the assembled shape and are labelled as examples.
 *
 * Absence of a record is never evidence of absence. Relate candidates never
 * authorize access, imply caregiver authority, or establish eligibility.
 */

import {
  AlertTriangle,
  CircleSlash,
  Info,
  Layers,
  Lock,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { traceability } from "@/lib/text-offsets";
import {
  COMPLETENESS_DISPLAY,
  TIER_LABELS,
  type AssembledContext,
  type Completeness,
  type ContextItem,
} from "@/lib/contracts";
import type {
  RelateBatch,
  VerifiedContext,
  VerifiedContextRecord,
} from "@/lib/api-types";
import { relateCandidateCount } from "@/lib/relate";
import type { SecurityOutcome } from "@/lib/security-states";

export type ContextState =
  | { kind: "unavailable" }
  | { kind: "loading" }
  | { kind: "denied"; outcome: SecurityOutcome }
  | { kind: "failed"; outcome: SecurityOutcome }
  | { kind: "no_patient" }
  | { kind: "loaded"; context: AssembledContext; provenance: string }
  | {
      kind: "verified";
      variant: "live" | "empty" | "stale" | "expired";
      context: VerifiedContext;
      family: RelateBatch | null;
      carePlans: RelateBatch | null;
      relateFailed: boolean;
    };

export function ContextPanel({
  state,
  onRefresh,
}: {
  state: ContextState;
  onRefresh?: () => void;
}) {
  if (state.kind === "loading") {
    return (
      <section
        className="rounded-lg border border-border bg-surface p-5"
        aria-busy="true"
        aria-live="polite"
      >
        <h2 className="text-lg text-ink">Verified context</h2>
        <p className="mt-3 text-sm text-ink-muted">
          Retrieving authorized records for this patient…
        </p>
      </section>
    );
  }

  if (state.kind === "unavailable") {
    return (
      <section className="rounded-lg border border-border bg-surface p-5">
        <h2 className="text-lg text-ink">Assembled context</h2>
        <div className="mt-3 rounded-lg border border-status-review bg-status-review-bg p-4">
          <p className="flex items-start gap-2 text-sm font-semibold text-status-review">
            <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <span>No verified-context service is available</span>
          </p>
          <p className="mt-2 text-sm text-ink">
            The backend does not yet expose a verified-context endpoint, so no
            authorized records have been retrieved for this case.
          </p>
          <p className="mt-2 text-xs text-ink-muted">
            This is an absence of a service, <strong>not</strong> a finding that
            no records exist. Nothing here supports any statement about what is
            or is not in this patient’s record.
          </p>
        </div>
      </section>
    );
  }

  if (state.kind === "no_patient") {
    return (
      <section className="rounded-lg border border-border bg-surface p-5">
        <h2 className="text-lg text-ink">Verified context</h2>
        <p className="mt-3 text-sm text-ink">
          No patient is bound to this case, so verified context cannot be
          requested.
        </p>
        <p className="mt-2 text-xs text-ink-muted">
          That is not a finding that no records exist.
        </p>
      </section>
    );
  }

  if (state.kind === "denied" || state.kind === "failed") {
    return (
      <section className="rounded-lg border border-status-overdue bg-status-overdue-bg p-5">
        <h2 className="text-lg text-ink">Verified context</h2>
        <p className="mt-3 flex items-start gap-2 text-sm font-semibold text-status-overdue">
          <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <span>{state.outcome.title}</span>
        </p>
        <p className="mt-2 text-sm text-ink">{state.outcome.body}</p>
        {state.outcome.caveat ? (
          <p className="mt-2 text-xs text-ink-muted">{state.outcome.caveat}</p>
        ) : null}
        {onRefresh ? (
          <button
            type="button"
            onClick={onRefresh}
            className="mt-3 inline-flex items-center gap-1.5 rounded border border-status-overdue px-2 py-1 text-xs font-semibold text-status-overdue"
          >
            <RotateCcw aria-hidden="true" className="size-3" />
            Retry
          </button>
        ) : null}
      </section>
    );
  }

  if (state.kind === "verified") {
    return (
      <VerifiedRecordsPanel
        variant={state.variant}
        context={state.context}
        family={state.family}
        carePlans={state.carePlans}
        relateFailed={state.relateFailed}
        onRefresh={onRefresh}
      />
    );
  }

  return <AssembledExamplePanel context={state.context} provenance={state.provenance} />;
}

function AssembledExamplePanel({
  context,
  provenance,
}: {
  context: AssembledContext;
  provenance: string;
}) {
  const completeness = COMPLETENESS_DISPLAY[context.completeness];
  const empty = context.state === "empty_unknown" || context.items.length === 0;

  return (
    <section className="rounded-lg border border-border bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg text-ink">Assembled context</h2>
          <p className="mt-1 text-sm text-ink-muted">
            Authorized records retrieved for a human to read. Not a finding, not
            a permission, and not an eligibility decision.
          </p>
        </div>
        <p className="shrink-0 rounded border border-dashed border-status-proposed px-2 py-1 text-xs text-status-proposed">
          {provenance}
        </p>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-md border border-border bg-canvas p-3">
          <p className="text-xs font-medium text-ink-muted">Completeness</p>
          <p className="mt-1 text-sm font-semibold text-ink">
            {completeness.label}
          </p>
          <p className="mt-1 text-xs text-ink-muted">{completeness.meaning}</p>
        </div>
        <div className="rounded-md border border-border bg-canvas p-3">
          <p className="text-xs font-medium text-ink-muted">Checked scope</p>
          <p className="mt-1 text-sm text-ink">{context.notice}</p>
          <p className="mt-1 font-mono-tech text-xs text-ink-muted">
            generation {context.generation_id} · permissions{" "}
            {context.permission_revision}
          </p>
        </div>
      </div>

      <p className="mt-3 flex items-start gap-1.5 rounded-md border border-status-review bg-status-review-bg p-2 text-xs text-status-review">
        <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
        <span>
          This retrieval is <strong>not exhaustive</strong>, and absence of a
          record here is <strong>not</strong> evidence that it does not exist.
        </span>
      </p>

      {empty ? (
        <div className="mt-4 rounded-lg border border-border bg-subtle p-6">
          <p className="flex items-center gap-2 text-base font-semibold text-ink">
            <CircleSlash aria-hidden="true" className="size-4" />
            Unknown — nothing was returned
          </p>
          <p className="mt-1 text-sm text-ink-muted">
            No authorized record matched inside the checked scope. That is an
            empty result, not a finding of absence.
          </p>
        </div>
      ) : (
        <>
          <p className="mt-4 text-sm text-ink-muted">
            <span className="tabular font-medium text-ink">
              {context.items.length}
            </span>{" "}
            item{context.items.length === 1 ? "" : "s"} ·{" "}
            <span className="tabular">{context.character_count}</span>{" "}
            characters · query{" "}
            <span className="text-ink">&ldquo;{context.query}&rdquo;</span>
          </p>
          <ul className="mt-3 space-y-3">
            {context.items.map((item) => (
              <li key={item.item_id}>
                <ContextItemCard item={item} />
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function VerifiedRecordsPanel({
  variant,
  context,
  family,
  carePlans,
  relateFailed,
  onRefresh,
}: {
  variant: "live" | "empty" | "stale" | "expired";
  context: VerifiedContext;
  family: RelateBatch | null;
  carePlans: RelateBatch | null;
  relateFailed: boolean;
  onRefresh?: () => void;
}) {
  const completeness = completenessDisplay(context.completeness);
  const records = context.records ?? [];
  const empty = variant === "empty" || records.length === 0;

  return (
    <section className="rounded-lg border border-border bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg text-ink">Verified context</h2>
          <p className="mt-1 text-sm text-ink-muted">
            Authorized source records for a human to read. Not assembled-context
            metadata, not a finding, not a permission, and not an eligibility
            decision.
          </p>
        </div>
        {onRefresh ? (
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-3 py-2 text-sm font-semibold text-ink hover:bg-subtle"
          >
            <RotateCcw aria-hidden="true" className="size-3.5" />
            Refresh
          </button>
        ) : null}
      </div>

      {variant === "expired" ? (
        <p className="mt-3 rounded-md border border-status-overdue bg-status-overdue-bg p-2 text-sm text-status-overdue">
          This verification has expired. It is not current. Refresh to obtain a
          new verification; do not treat these records as still verified.
        </p>
      ) : null}
      {variant === "stale" ? (
        <p className="mt-3 rounded-md border border-status-review bg-status-review-bg p-2 text-sm text-status-review">
          This verification is stale relative to the current generation. It is
          not a current authorization to read these records as up to date.
        </p>
      ) : null}

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-md border border-border bg-canvas p-3">
          <p className="text-xs font-medium text-ink-muted">Completeness</p>
          <p className="mt-1 text-sm font-semibold text-ink">
            {completeness.label}
          </p>
          <p className="mt-1 text-xs text-ink-muted">{completeness.meaning}</p>
        </div>
        <div className="rounded-md border border-border bg-canvas p-3">
          <p className="text-xs font-medium text-ink-muted">Checked scope</p>
          <p className="mt-1 text-sm text-ink">{context.checked_scope}</p>
          <p className="mt-1 font-mono-tech text-xs text-ink-muted">
            generation {context.generation_id} · permissions{" "}
            {context.permission_revision}
          </p>
        </div>
      </div>

      <p className="mt-3 flex items-start gap-1.5 rounded-md border border-status-review bg-status-review-bg p-2 text-xs text-status-review">
        <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
        <span>
          This retrieval is <strong>not exhaustive</strong>
          {context.exhaustive ? " (the server field does not change that)" : ""}
          , and absence of a record here is <strong>not</strong> evidence that
          it does not exist
          {context.absence_claims_allowed
            ? " — absence claims are still not made here"
            : ""}
          .
        </span>
      </p>

      <p className="mt-2 font-mono-tech text-xs text-ink-muted">
        verified {context.verified_at} · expires {context.expires_at} · adapter{" "}
        {context.policy_adapter}
        {context.production_authorization ? "" : " · not production-authorized"}
      </p>
      {context.notice ? (
        <p className="mt-2 text-xs text-ink-muted">{context.notice}</p>
      ) : null}

      <RelateHints
        family={family}
        carePlans={carePlans}
        relateFailed={relateFailed}
      />

      <p className="mt-4 text-sm text-ink-muted">
        No query, tier or assembled-item metadata is invented for this
        response.
        {!empty ? (
          <>
            {" "}
            <span className="tabular font-medium text-ink">
              {records.length}
            </span>{" "}
            verified record{records.length === 1 ? "" : "s"}.
          </>
        ) : null}
      </p>

      {empty ? (
        <div className="mt-4 rounded-lg border border-border bg-subtle p-6">
          <p className="flex items-center gap-2 text-base font-semibold text-ink">
            <CircleSlash aria-hidden="true" className="size-4" />
            Unknown — nothing was returned
          </p>
          <p className="mt-1 text-sm text-ink-muted">
            No authorized record was returned inside the checked scope. That is
            an empty result, not a finding of absence.
          </p>
        </div>
      ) : (
        <>
          <ul className="mt-3 space-y-3">
            {records.map((record, index) => (
              <li
                key={`${record.source.reference}:${record.source.version}:${index}`}
              >
                <VerifiedRecordCard record={record} />
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function RelateHints({
  family,
  carePlans,
  relateFailed,
}: {
  family: RelateBatch | null;
  carePlans: RelateBatch | null;
  relateFailed: boolean;
}) {
  const count = relateCandidateCount(family, carePlans);
  return (
    <div className="mt-4 rounded-md border border-dashed border-border bg-canvas p-3">
      <p className="text-sm font-semibold text-ink">Relate discovery</p>
      <p className="mt-1 text-xs text-ink-muted">
        Graph-derived candidates are hints only. They do not authorize access,
        imply caregiver authority, or establish eligibility.
      </p>
      {relateFailed ? (
        <p className="mt-2 text-xs text-ink-muted">
          Relate discovery was not available. Verified records below were still
          requested without treating missing hints as permission.
        </p>
      ) : (
        <p className="mt-2 text-xs text-ink-muted">
          <span className="tabular font-medium text-ink">{count}</span>{" "}
          candidate{count === 1 ? "" : "s"} · family history{" "}
          {family?.candidates?.length ?? 0} · care plans{" "}
          {carePlans?.candidates?.length ?? 0}
        </p>
      )}
    </div>
  );
}

function VerifiedRecordCard({ record }: { record: VerifiedContextRecord }) {
  return (
    <article className="rounded-md border border-border bg-canvas p-3">
      <p className="font-mono-tech text-sm text-ink">
        {record.source.reference}
      </p>
      <p className="mt-2 text-sm text-ink">{record.text}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
        <Marker
          on={record.authorized}
          onLabel="Authorized"
          offLabel="Not authorized"
        />
        <Marker
          on={record.source_verified}
          onLabel="Source verified"
          offLabel="Source not verified"
        />
        <Marker
          on={record.reviewed}
          onLabel="Reviewed"
          offLabel="Not reviewed by a clinician"
        />
      </div>
      <p className="mt-2 font-mono-tech text-xs text-ink-muted">
        version {record.source.version} · updated {record.source_last_updated} ·
        verified {record.verified_at} · {record.patient_reference}
      </p>
    </article>
  );
}

function ContextItemCard({ item }: { item: ContextItem }) {
  const trace = traceability(item.text, {
    offset_start: item.offset_start,
    offset_end: item.offset_end,
    excerpt: item.text,
  });

  return (
    <article className="rounded-md border border-border bg-canvas p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-mono-tech text-sm text-ink">
          {item.source.reference}
        </p>
        <span className="inline-flex items-center gap-1 rounded-md border border-border bg-surface px-2 py-0.5 text-xs">
          <Layers aria-hidden="true" className="size-3" />
          {TIER_LABELS[item.tier]}
        </span>
      </div>

      <p className="mt-2 text-sm text-ink">{item.text}</p>

      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
        <Marker
          on={item.authorized}
          onLabel="Authorized"
          offLabel="Not authorized"
        />
        <Marker
          on={item.source_verified}
          onLabel="Source verified"
          offLabel="Source not verified"
        />
        <Marker
          on={item.reviewed}
          onLabel="Reviewed"
          offLabel="Not reviewed by a clinician"
        />
      </div>

      <p className="mt-2 font-mono-tech text-xs text-ink-muted">
        version {item.source.version} · updated {item.source_last_updated} ·
        verified {item.verified_at}
      </p>

      {item.offset_start === null ? (
        <p className="mt-1 text-xs text-ink-muted">
          No source offsets supplied for this passage.
        </p>
      ) : trace.state !== "verified" ? (
        <p className="mt-1 text-xs text-status-overdue">
          The supplied offsets do not verify against this passage.
        </p>
      ) : null}
    </article>
  );
}

function Marker({
  on,
  onLabel,
  offLabel,
}: {
  on: boolean;
  onLabel: string;
  offLabel: string;
}) {
  const Icon = on ? ShieldCheck : Lock;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-medium",
        on
          ? "border-status-verified bg-status-verified-bg text-status-verified"
          : "border-status-review bg-status-review-bg text-status-review",
      )}
    >
      <Icon aria-hidden="true" className="size-3" />
      {on ? onLabel : offLabel}
    </span>
  );
}

function completenessDisplay(value: string): { label: string; meaning: string } {
  if (value in COMPLETENESS_DISPLAY) {
    return COMPLETENESS_DISPLAY[value as Completeness];
  }
  return {
    label: value || "Unknown",
    meaning:
      "The extent of what was checked is not known. Nothing here supports a statement about what is absent.",
  };
}
