"use client";

/**
 * Context view — a separate route on purpose.
 *
 * Alfred's handoff asks that the AI explanation and context view stay distinct
 * from review decisions and rule results. Putting retrieved context on the case
 * detail screen, beside the rule outcome and the action panel, would invite
 * exactly the conflation he is guarding against.
 *
 * Live data uses Relate discovery then POST /api/v1/security/verified-context.
 * Contract examples remain labelled examples of AssembledContext and are not
 * mixed with verified records.
 */

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import { ContextPanel, type ContextState } from "@/components/context-panel";
import { CaseSubnav } from "@/components/case-subnav";
import { chrome } from "@/lib/copy";
import { useCase, useCaseStore } from "@/lib/case-store";
import { useDemoSession } from "@/lib/demo-session";
import {
  ALFRED_CONTEXT_EXAMPLE,
  EMPTY_CONTEXT_EXAMPLE,
} from "@/lib/context-example";
import { useVerifiedContext } from "@/lib/use-verified-context";

type Mode = "live" | "example" | "example_empty";

const MODES: { id: Mode; label: string }[] = [
  { id: "live", label: "Live backend" },
  { id: "example", label: "Contract example" },
  { id: "example_empty", label: "Empty result" },
];

export function ContextView({ id }: { id: string }) {
  const { role, sessionEpoch, locale } = useDemoSession();
  const { sessionId } = useCaseStore();
  const { case: row, error } = useCase(id);
  const [mode, setMode] = useState<Mode>("live");
  const live = useVerifiedContext(
    row?.patient_id,
    sessionId,
    role,
    sessionEpoch,
    Boolean(row) || Boolean(error),
    Boolean(error) && !row,
  );

  const state: ContextState =
    mode === "example"
      ? {
          kind: "loaded",
          context: ALFRED_CONTEXT_EXAMPLE,
          provenance: "Contract example — not backend data",
        }
      : mode === "example_empty"
        ? {
            kind: "loaded",
            context: EMPTY_CONTEXT_EXAMPLE,
            provenance: "Contract example — not backend data",
          }
        : liveToPanel(live);

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
      <Link
        href={`/cases/${id}`}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted hover:text-ink"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        {chrome(locale, "backToCase")}
      </Link>
      <CaseSubnav caseId={id} />

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
                ? "border-brand bg-subtle text-ink"
                : "border-border bg-surface text-ink hover:bg-canvas",
            )}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="mt-4">
        <ContextPanel state={state} onRefresh={live.refresh} />
      </div>
    </div>
  );
}

function liveToPanel(
  live: ReturnType<typeof useVerifiedContext>,
): ContextState {
  if (live.kind === "loading") return { kind: "loading" };
  if (live.kind === "unavailable") return { kind: "no_patient" };
  if (live.kind === "denied") return { kind: "denied", outcome: live.outcome };
  if (live.kind === "failed") return { kind: "failed", outcome: live.outcome };
  return {
    kind: "verified",
    variant: live.kind,
    context: live.context,
    family: live.family,
    carePlans: live.carePlans,
    relateFailed: live.relateFailed,
  };
}
