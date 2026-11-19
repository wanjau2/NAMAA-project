"use client";

/**
 * Context view — a separate route on purpose.
 *
 * Alfred's handoff asks that the AI explanation and context view stay distinct
 * from review decisions and rule results. Putting retrieved context on the case
 * detail screen, beside the rule outcome and the action panel, would invite
 * exactly the conflation he is guarding against.
 *
 * Default state is the truth: no verified-context service exists yet. The
 * contract examples are available behind an explicit, labelled toggle so the
 * rendering can be reviewed before M2 lands.
 */

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import { ContextPanel, type ContextState } from "@/components/context-panel";
import { useCase } from "@/lib/case-store";
import {
  ALFRED_CONTEXT_EXAMPLE,
  EMPTY_CONTEXT_EXAMPLE,
} from "@/lib/context-example";

type Mode = "live" | "example" | "example_empty";

const MODES: { id: Mode; label: string }[] = [
  { id: "live", label: "Live backend" },
  { id: "example", label: "Contract example" },
  { id: "example_empty", label: "Empty result" },
];

export function ContextView({ id }: { id: string }) {
  const { case: row } = useCase(id);
  const [mode, setMode] = useState<Mode>("live");

  const state: ContextState =
    mode === "live"
      ? { kind: "unavailable" }
      : {
          kind: "loaded",
          context:
            mode === "example"
              ? ALFRED_CONTEXT_EXAMPLE
              : EMPTY_CONTEXT_EXAMPLE,
          provenance: "Contract example — not backend data",
        };

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
      <Link
        href={`/cases/${id}`}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted hover:text-ink"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        Back to case detail
      </Link>

      <header className="mt-4">
        <h1 className="text-2xl text-ink">Retrieved context</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-muted">
          {row ? `${row.patient_label} · ` : ""}Authorized source records
          assembled for a human to read. Kept separate from review decisions and
          from the rule result, because it is neither.
        </p>
      </header>

      <p className="mt-3 flex items-start gap-1.5 rounded-lg border border-border bg-subtle p-3 text-xs text-ink-muted">
        <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
        <span>
          Retrieved context is <strong>not</strong> a diagnosis, a permission, a
          clinical risk or an eligibility decision. It cannot change a rule
          result, and a relationship appearing here has not been verified as
          clinically meaningful.
        </span>
      </p>

      <div
        className="mt-4 flex flex-wrap items-center gap-2"
        role="group"
        aria-label="Context source"
      >
        <span className="text-xs font-medium text-ink-muted">Showing</span>
        {MODES.map((option) => (
          <button
            key={option.id}
            type="button"
            onClick={() => setMode(option.id)}
            aria-pressed={mode === option.id}
            className={cn(
              "rounded-full border px-3 py-1 text-xs font-medium",
              mode === option.id
                ? "border-brand bg-brand text-white"
                : "border-border bg-surface text-ink hover:bg-subtle",
            )}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="mt-4">
        <ContextPanel state={state} />
      </div>
    </div>
  );
}
