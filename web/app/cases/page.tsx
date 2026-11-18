"use client";

/**
 * Coordinator worklist — API-backed.
 *
 * Rows come from `GET /api/v1/cases`. Disposition stays visually DISTINCT from
 * stage: `completed` is the only disposition that earns the verified token, and
 * declined / deferred / unreachable use review tokens with explicit text so
 * they can never read as a completion.
 */

import { useMemo, useState } from "react";
import Link from "next/link";
import { AlertOctagon, Clock, Filter, RotateCcw } from "lucide-react";
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
} from "@/lib/api-types";

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
  const { rows, rowsLoading, rowsError, reloadRows, status, connectionMessage } =
    useCaseStore();

  const [pathway, setPathway] = useState<Pathway | "all">("all");
  const [stage, setStage] = useState<Stage | "all">("all");
  const [overdueOnly, setOverdueOnly] = useState(false);

  const filtered = useMemo(
    () =>
      rows.filter((row) => {
        if (pathway !== "all" && row.pathway !== pathway) return false;
        if (stage !== "all" && row.stage !== stage) return false;
        if (overdueOnly && !row.overdue) return false;
        return true;
      }),
    [rows, pathway, stage, overdueOnly],
  );

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <header>
        <h1 className="text-2xl text-ink">Coordinator worklist</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Synthetic cases only. The server validates every transition — this view
          requests changes, it does not decide them.
        </p>
      </header>

      {status === "unreachable" ? (
        <ApiDown message={connectionMessage} onRetry={reloadRows} />
      ) : null}

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

      {/* While connecting, show the skeleton. Rendering "no cases match" before
          the first fetch has even started would read as an absence of care
          gaps, which is exactly the claim this UI must never make. */}
      {(status === "connecting" || rowsLoading) && rows.length === 0 ? (
        <WorklistSkeleton />
      ) : rowsError && rows.length === 0 ? (
        <ErrorPanel error={rowsError.message} code={rowsError.code} onRetry={reloadRows} />
      ) : (
        <>
          <p className="mt-4 flex flex-wrap items-center gap-x-2 text-sm text-ink-muted">
            <span>
              Showing{" "}
              <span className="tabular font-medium text-ink">
                {filtered.length}
              </span>{" "}
              of{" "}
              <span className="tabular font-medium text-ink">{rows.length}</span>{" "}
              synthetic cases
            </span>
            <button
              type="button"
              onClick={reloadRows}
              className="inline-flex items-center gap-1 rounded border border-border px-2 py-0.5 text-xs font-medium text-ink hover:bg-subtle"
            >
              <RotateCcw aria-hidden="true" className="size-3" />
              {rowsLoading ? "Refreshing…" : "Refresh"}
            </button>
          </p>

          {filtered.length === 0 ? (
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
              {filtered.map((row) => {
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
                          <span className="font-mono-tech">
                            {row.rule_id_version}
                          </span>{" "}
                          ·{" "}
                          <span className="font-mono-tech">
                            rev {row.revision}
                          </span>
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
                            <Clock
                              aria-hidden="true"
                              className="me-1 inline size-3"
                            />
                          ) : null}
                          {formatDue(row.due_time)}
                        </span>
                      </Field>
                    </dl>

                    <p className="mt-3 text-sm text-ink">
                      <span className="font-medium text-ink-muted">
                        Next action:{" "}
                      </span>
                      {row.next_action}
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

export function ApiDown({
  message,
  onRetry,
}: {
  message: string | null;
  onRetry: () => void;
}) {
  return (
    <div className="mt-4 rounded-lg border border-status-overdue bg-status-overdue-bg p-4">
      <p className="flex items-start gap-2 text-sm font-semibold text-status-overdue">
        <AlertOctagon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        <span>The Namaa API is not reachable</span>
      </p>
      <p className="mt-2 text-sm text-ink">
        {message ?? "No connection to the API."}
      </p>
      <p className="mt-2 text-xs text-ink-muted">
        Nothing is shown rather than stale or invented data. No case state has
        changed.
      </p>
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

function ErrorPanel({
  error,
  code,
  onRetry,
}: {
  error: string;
  code: string;
  onRetry: () => void;
}) {
  return (
    <div className="mt-4 rounded-lg border border-status-overdue bg-status-overdue-bg p-4">
      <p className="flex items-start gap-2 text-sm text-status-overdue">
        <AlertOctagon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        <span>
          {error} <span className="font-mono-tech">[{code}]</span>
        </span>
      </p>
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

function WorklistSkeleton() {
  return (
    <div className="mt-4 space-y-3" aria-busy="true" aria-live="polite">
      <p className="text-sm text-ink-muted">Loading synthetic cases…</p>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="rounded-lg border border-border bg-surface p-4"
        >
          <div className="h-4 w-48 animate-pulse rounded bg-subtle" />
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[0, 1, 2, 3].map((j) => (
              <div key={j}>
                <div className="h-3 w-16 animate-pulse rounded bg-subtle" />
                <div className="mt-2 h-4 w-20 animate-pulse rounded bg-subtle" />
              </div>
            ))}
          </div>
        </div>
      ))}
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
