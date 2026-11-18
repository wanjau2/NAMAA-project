"use client";

/**
 * Rule outcome display — deliberately NOT the StatusBadge vocabulary.
 *
 * Alfred's handoff asks that the AI explanation and context view stay distinct
 * from review decisions and rule results. StatusBadge speaks about epistemic
 * state (proposed / verified / needs review / overdue); a rule outcome is a
 * different kind of claim, so it gets its own component and its own shapes.
 *
 * All four outcomes render as themselves. The limitation line is never
 * optional: "no gap identified in available data" and "not eligible" are the
 * two most likely to be misread as reassurance, so their limits travel with
 * them everywhere they appear.
 */

import { AlertTriangle, CircleSlash, Info, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  OUTCOME_DISPLAY,
  resolveOutcome,
  type OutcomeResolution,
  type RuleOutcome,
} from "@/lib/rule-outcomes";

const TONE_CLASS: Record<string, string> = {
  finding: "bg-status-proposed-bg text-status-proposed border-status-proposed",
  review: "bg-status-review-bg text-status-review border-status-review",
  neutral: "bg-subtle text-ink border-border",
};

const TONE_ICON = {
  finding: Search,
  review: AlertTriangle,
  neutral: CircleSlash,
} as const;

export function RuleOutcomeBadge({
  outcome,
  className,
}: {
  outcome: RuleOutcome;
  className?: string;
}) {
  const display = OUTCOME_DISPLAY[outcome];
  const Icon = TONE_ICON[display.tone];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium",
        TONE_CLASS[display.tone],
        className,
      )}
    >
      <Icon aria-hidden="true" className="size-3.5 shrink-0" />
      <span>{display.label}</span>
    </span>
  );
}

/**
 * The outcome with its meaning and its limitation. Use wherever the rule
 * result is being explained rather than merely labelled.
 */
export function RuleOutcomeCard({
  resolution,
  className,
}: {
  resolution: OutcomeResolution;
  className?: string;
}) {
  const display = OUTCOME_DISPLAY[resolution.outcome];
  const Icon = TONE_ICON[display.tone];

  return (
    <section
      className={cn(
        "rounded-lg border border-s-4 p-4",
        TONE_CLASS[display.tone],
        className,
      )}
    >
      <h3 className="flex items-center gap-2 text-base font-semibold">
        <Icon aria-hidden="true" className="size-4 shrink-0" />
        {display.label}
      </h3>
      <p className="mt-2 text-sm text-ink">{display.meaning}</p>
      <p className="mt-2 flex items-start gap-1.5 text-xs text-ink-muted">
        <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
        <span>{display.limitation}</span>
      </p>

      {/* A value nobody agreed on is surfaced, never silently coerced. */}
      {resolution.source === "unknown" ? (
        <p className="mt-2 rounded-md border border-status-overdue bg-status-overdue-bg p-2 text-xs text-status-overdue">
          The server reported an outcome this interface does not recognise:{" "}
          <span className="font-mono-tech">{resolution.raw}</span>. It is shown
          as needs review until the contract is agreed. Do not read it as a
          conclusion.
        </p>
      ) : null}

      {resolution.source === "aliased" ? (
        <p className="mt-2 text-xs text-ink-muted">
          Reported by the API as{" "}
          <span className="font-mono-tech">{resolution.raw}</span>; shown using
          the agreed vocabulary.
        </p>
      ) : null}
    </section>
  );
}

/** Convenience for list rows, where only a label fits. */
export function OutcomeFromApi({ value }: { value: string }) {
  return <RuleOutcomeBadge outcome={resolveOutcome(value).outcome} />;
}
