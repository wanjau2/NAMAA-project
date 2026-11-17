/**
 * StatusBadge — the ONLY sanctioned way to render an epistemic or workflow state.
 *
 * D002 §7: always emits token + icon + plain-language text together, so a bare
 * coloured dot is not reachable through this API. Review rule: a raw hex or a
 * lone coloured element in a PR is a blocker.
 *
 * Borders use each state's FOREGROUND colour (D002 §1). The originally
 * specified -300 pastels sat at ~1.3-1.8:1 against their own backgrounds and
 * failed WCAG 1.4.11, which would have broken the solid-vs-dashed channel that
 * distinguishes unreviewed AI output from verified fact.
 */

import { AlertOctagon, AlertTriangle, CheckCircle2, Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Four states on two orthogonal axes: WHO asserted it (verified vs proposed)
 * and HOW urgent it is (review vs overdue). Keeping them separate is what lets
 * the UI carry the design specification's clinical safety boundary.
 */
export type EpistemicState = "verified" | "proposed" | "review" | "overdue";

type StateConfig = {
  Icon: LucideIcon;
  /** Default plain-language text. Never render the badge without text. */
  defaultLabel: string;
  className: string;
};

const STATE_CONFIG: Record<EpistemicState, StateConfig> = {
  verified: {
    Icon: CheckCircle2,
    defaultLabel: "Verified",
    className:
      "border-solid bg-status-verified-bg text-status-verified border-status-verified",
  },
  proposed: {
    // Dashed border is a non-colour channel: it survives greyscale, colour
    // vision deficiency and a bad projector.
    Icon: Sparkles,
    defaultLabel: "Proposed — not yet reviewed",
    className:
      "border-dashed bg-status-proposed-bg text-status-proposed border-status-proposed",
  },
  review: {
    Icon: AlertTriangle,
    defaultLabel: "Needs review",
    className:
      "border-solid bg-status-review-bg text-status-review border-status-review",
  },
  overdue: {
    Icon: AlertOctagon,
    defaultLabel: "Overdue",
    className:
      "border-solid bg-status-overdue-bg text-status-overdue border-status-overdue",
  },
};

export function StatusBadge({
  state,
  label,
  className,
}: {
  state: EpistemicState;
  /** Overrides the default text. Must stay plain language — never a bare code. */
  label?: string;
  className?: string;
}) {
  const { Icon, defaultLabel, className: stateClass } = STATE_CONFIG[state];

  return (
    <span
      className={cn(
        // text-xs is the 12px floor from the D002 ramp; weight 500 compensates
        // for status foregrounds that clear AA with little headroom.
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium",
        stateClass,
        className,
      )}
    >
      <Icon aria-hidden="true" className="size-3.5 shrink-0" />
      <span>{label ?? defaultLabel}</span>
    </span>
  );
}

/**
 * StatusCard — the same token set at card scale, with a start-edge spine
 * instead of a uniform saturated outline (D002 §1). border-s-4 is a logical
 * property, so it mirrors correctly under dir="rtl" for free.
 */
export function StatusCard({
  state,
  title,
  children,
  className,
}: {
  state: EpistemicState;
  title: string;
  children?: React.ReactNode;
  className?: string;
}) {
  const { Icon, className: stateClass } = STATE_CONFIG[state];
  const spine = {
    verified: "border-s-status-verified",
    proposed: "border-s-status-proposed",
    review: "border-s-status-review",
    overdue: "border-s-status-overdue",
  }[state];

  return (
    <section
      className={cn(
        "rounded-lg border border-s-4 p-4",
        stateClass,
        spine,
        className,
      )}
    >
      <h3 className="flex items-center gap-2 text-base font-semibold">
        <Icon aria-hidden="true" className="size-4 shrink-0" />
        {title}
      </h3>
      {children ? (
        <div className="mt-2 text-sm text-ink">{children}</div>
      ) : null}
    </section>
  );
}
