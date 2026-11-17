"use client";

/**
 * RoleGatedAction — an action that belongs to another simulated role.
 *
 * D002 §2: the theme requires these to be visible-but-disabled with an
 * explanation. A native `disabled` button is REMOVED FROM THE FOCUS ORDER, so a
 * keyboard or screen-reader user could never reach that explanation — and "all
 * controls are keyboard accessible" is in the work plan's definition of done.
 *
 * Therefore:
 *  - aria-disabled="true", control stays focusable, handler returns early
 *  - the reason is VISIBLE helper text, not a tooltip only
 *  - aria-describedby associates the two, so it is announced on focus
 *  - the label keeps --text-secondary (6.9:1 on subtle); it is meant to be
 *    read, so it is never washed out to a conventional disabled grey
 */

import { useId } from "react";
import { Info } from "lucide-react";
import { cn } from "@/lib/utils";

export function RoleGatedAction({
  children,
  allowed,
  reason,
  onClick,
  variant = "primary",
  className,
}: {
  children: React.ReactNode;
  /** Whether the current simulated role may invoke this action. */
  allowed: boolean;
  /** Why not — shown whenever `allowed` is false. Plain language. */
  reason: string;
  onClick?: () => void;
  variant?: "primary" | "secondary";
  className?: string;
}) {
  const reasonId = useId();

  const base =
    "inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition-colors";
  const enabled =
    variant === "primary"
      ? "bg-brand text-white hover:bg-brand-hover"
      : "bg-surface text-ink border border-border hover:bg-subtle";
  const gated =
    "bg-subtle text-ink-muted border border-border cursor-not-allowed";

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <button
        type="button"
        aria-disabled={!allowed}
        aria-describedby={allowed ? undefined : reasonId}
        onClick={() => {
          if (!allowed) return; // focusable, but inert
          onClick?.();
        }}
        className={cn(base, allowed ? enabled : gated)}
      >
        {children}
      </button>

      {!allowed ? (
        <p
          id={reasonId}
          className="flex items-start gap-1.5 text-xs text-ink-muted"
        >
          <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          <span>{reason}</span>
        </p>
      ) : null}
    </div>
  );
}
