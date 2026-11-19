"use client";

/**
 * Assembled-context panel (Alfred's M3; contract: AssembledContext).
 *
 * Deliberately separate from review decisions and rule results. Retrieved
 * context is material a human may read; it is not a finding, not a permission
 * and not an eligibility decision, and this panel must never let it look like
 * one.
 *
 * The three rules that shape everything here:
 *  - `exhaustive` is always false, so absence of an item is never evidence of
 *    absence. The notice saying so is not dismissible.
 *  - An empty result is rendered as UNKNOWN, never as "nothing found".
 *  - Completeness and the checked scope travel with every result.
 */

import {
  AlertTriangle,
  CircleSlash,
  Info,
  Layers,
  Lock,
  ShieldCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { traceability } from "@/lib/text-offsets";
import {
  COMPLETENESS_DISPLAY,
  TIER_LABELS,
  type AssembledContext,
  type ContextItem,
} from "@/lib/contracts";

export type ContextState =
  /** No verified-context service exists yet (M2 not delivered). */
  | { kind: "unavailable" }
  | { kind: "loaded"; context: AssembledContext; provenance: string };

export function ContextPanel({ state }: { state: ContextState }) {
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

  const { context, provenance } = state;
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

      {/* Completeness and checked scope travel with every result. */}
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

      {/* Not dismissible: the context is never a complete view. */}
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

function ContextItemCard({ item }: { item: ContextItem }) {
  // Offsets are code points; an unverifiable span is stated, never guessed.
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
