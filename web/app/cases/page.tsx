"use client";

/**
 * Coordinator worklist (theme §5).
 *
 * Filter pills for pathway and stage plus an "Overdue only" toggle. Each row
 * surfaces Current Stage, Disposition (kept visually DISTINCT from stage),
 * Assigned Owner, Next Action and Due Time.
 *
 * Disposition is not an epistemic state, so it does not reuse the four status
 * tokens loosely: `completed` is the only one that earns the verified token.
 * declined / deferred / unreachable use review tokens with explicit text,
 * because they must never read as a completion (work plan § Required behavior).
 */

import { useMemo, useState } from "react";
import Link from "next/link";
import { Clock, Filter } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/status-badge";
import type { EpistemicState } from "@/components/status-badge";
import { useCaseStore } from "@/lib/case-store";
import {
  DISPOSITION_LABELS,
  PATHWAYS,
  PATHWAY_LABELS,
  STAGES,
  STAGE_LABELS,
  type Disposition,
  type Pathway,
  type Stage,
} from "@/lib/mock-data";

function dispositionState(disposition: Disposition): EpistemicState | null {
  switch (disposition) {
    case "completed":
      return "verified";
    case "declined":
    case "deferred":
    case "unreachable":
    case "clinically_closed_other":
      return "review";
    case "active":
      return null; // neutral — work in progress is not a status claim
  }
}

function formatDue(due: string | null): string {
  if (!due) return "—";
  return due.replace("T", " ").replace(".000Z", "Z");
}

export default function WorklistPage() {
  const { cases } = useCaseStore();
  const allCases = useMemo(() => Object.values(cases), [cases]);

  const [pathway, setPathway] = useState<Pathway | "all">("all");
  const [stage, setStage] = useState<Stage | "all">("all");
  const [overdueOnly, setOverdueOnly] = useState(false);

  const rows = useMemo(
    () =>
      allCases.filter((row) => {
        if (pathway !== "all" && row.pathway !== pathway) return false;
        if (stage !== "all" && row.stage !== stage) return false;
        if (overdueOnly && !row.overdue) return false;
        return true;
      }),
    [allCases, pathway, stage, overdueOnly],
  );

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <header>
        <h1 className="text-2xl text-ink">Coordinator worklist</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Synthetic cases only. The server remains authoritative for every
          transition — this view requests changes, it does not decide them.
        </p>
      </header>

      {/* Filters */}
      <section
        aria-label="Filters"
        className="mt-5 flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
      >
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">
          <Filter aria-hidden="true" className="size-3.5" />
          Filters
        </div>

        <FilterGroup label="Pathway">
          <Pill active={pathway === "all"} onClick={() => setPathway("all")}>
            All
          </Pill>
          {PATHWAYS.map((value) => (
            <Pill
              key={value}
              active={pathway === value}
              onClick={() => setPathway(value)}
            >
              {PATHWAY_LABELS[value]}
            </Pill>
          ))}
        </FilterGroup>

        <FilterGroup label="Stage">
          <Pill active={stage === "all"} onClick={() => setStage("all")}>
            All
          </Pill>
          {STAGES.map((value) => (
            <Pill
              key={value}
              active={stage === value}
              onClick={() => setStage(value)}
            >
              {STAGE_LABELS[value]}
            </Pill>
          ))}
        </FilterGroup>

        <FilterGroup label="Overdue">
          <Pill active={overdueOnly} onClick={() => setOverdueOnly(!overdueOnly)}>
            Overdue only
          </Pill>
        </FilterGroup>
      </section>

      {/* Results */}
      <p className="mt-4 text-sm text-ink-muted">
        Showing <span className="tabular font-medium text-ink">{rows.length}</span>{" "}
        of <span className="tabular font-medium text-ink">{allCases.length}</span>{" "}
        synthetic cases
      </p>

      {rows.length === 0 ? (
        <div className="mt-3 rounded-lg border border-border bg-subtle p-8 text-center">
          <p className="text-base font-semibold text-ink">
            No cases match these filters
          </p>
          <p className="mt-1 text-sm text-ink-muted">
            This is an empty result, not an absence of care gaps.
          </p>
          <button
            type="button"
            onClick={() => {
              setPathway("all");
              setStage("all");
              setOverdueOnly(false);
            }}
            className="mt-4 rounded-md border border-border bg-surface px-3 py-2 text-sm font-semibold text-ink hover:bg-subtle"
          >
            Clear all filters
          </button>
        </div>
      ) : (
        <ul className="mt-3 space-y-3">
          {rows.map((row) => {
            const dispState = dispositionState(row.disposition);
            return (
              <li
                key={row.id}
                className="rounded-lg border border-border bg-surface p-4 hover:bg-canvas"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <Link
                      href={`/cases/${row.id}`}
                      className="text-base font-semibold text-ink underline-offset-2 hover:underline"
                    >
                      {row.patient_label}
                    </Link>
                    <p className="mt-0.5 text-xs text-ink-muted">
                      {PATHWAY_LABELS[row.pathway]} · {row.age_band} ·{" "}
                      <span className="font-mono-tech">{row.rule_id_version}</span>{" "}
                      · <span className="font-mono-tech">rev {row.revision}</span>
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {row.flag_status === "needs_review" ? (
                      <StatusBadge
                        state="review"
                        label="Needs review — information missing"
                      />
                    ) : null}
                    {row.overdue ? (
                      <StatusBadge state="overdue" label="Overdue" />
                    ) : null}
                  </div>
                </div>

                <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                  <Field label="Stage">
                    {/* Stage is neutral: it is a position in the lifecycle, not a claim. */}
                    <span className="inline-flex rounded-md bg-subtle px-2 py-0.5 text-xs font-medium text-ink">
                      {STAGE_LABELS[row.stage]}
                    </span>
                  </Field>

                  <Field label="Disposition">
                    {dispState ? (
                      <StatusBadge
                        state={dispState}
                        label={DISPOSITION_LABELS[row.disposition]}
                      />
                    ) : (
                      <span className="inline-flex rounded-md border border-border px-2 py-0.5 text-xs font-medium text-ink-muted">
                        {DISPOSITION_LABELS[row.disposition]}
                      </span>
                    )}
                  </Field>

                  <Field label="Owner">
                    <span className="text-ink">{row.owner}</span>
                  </Field>

                  <Field label="Due">
                    <span
                      className={cn(
                        "font-mono-tech text-xs",
                        row.overdue ? "text-status-overdue" : "text-ink",
                      )}
                    >
                      {row.overdue ? (
                        <Clock aria-hidden="true" className="me-1 inline size-3" />
                      ) : null}
                      {formatDue(row.due_time)}
                    </span>
                  </Field>
                </dl>

                <p className="mt-3 text-sm text-ink">
                  <span className="font-medium text-ink-muted">Next action: </span>
                  {row.next_action}
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function FilterGroup({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="w-16 shrink-0 text-xs font-medium text-ink-muted">
        {label}
      </span>
      {children}
    </div>
  );
}

function Pill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
        active
          ? "border-brand bg-brand text-white"
          : "border-border bg-surface text-ink hover:bg-subtle",
      )}
    >
      {children}
    </button>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs font-medium text-ink-muted">{label}</dt>
      <dd className="mt-1">{children}</dd>
    </div>
  );
}
