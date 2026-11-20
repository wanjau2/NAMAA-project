"use client";

/**
 * Live `GET /api/v1/analytics/overview`.
 *
 * Suppression is a server duty (Q8 / D003). Suppressed cells arrive with
 * `numerator: null, denominator: null`, so the browser never holds hidden
 * counts. Funnel numbers include a labelled reporting cohort that is not on
 * the coordinator worklist.
 */

import { useCallback, useEffect, useState } from "react";
import { AlertOctagon, Info, Lock, RotateCcw } from "lucide-react";
import { api } from "@/lib/api";
import type { AnalyticsOverview, MetricCell } from "@/lib/api-types";
import { PATHWAY_LABELS } from "@/lib/api-types";
import { useDemoSession } from "@/lib/demo-session";
import { useCaseStore } from "@/lib/case-store";
import { rate } from "@/lib/metrics";
import { cn } from "@/lib/utils";

const FUNNEL = [
  "eligible",
  "invited",
  "booked",
  "attended",
  "follow_up",
  "completed",
] as const;

const DISPOSITIONS = ["completed", "declined", "unreachable"] as const;

export function ApiAnalyticsPanel() {
  const { role, sessionEpoch } = useDemoSession();
  return <ApiAnalyticsPanelInner key={`${role}:${sessionEpoch}`} />;
}

function ApiAnalyticsPanelInner() {
  const { role } = useDemoSession();
  const { sessionId, status } = useCaseStore();
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      setData(await api.analyticsOverview(sessionId, role));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Request failed.");
    } finally {
      setLoading(false);
    }
  }, [sessionId, role]);

  useEffect(() => {
    if (status !== "ready" || !sessionId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await api.analyticsOverview(sessionId, role);
        if (!cancelled) setData(result);
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "Request failed.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [status, sessionId, role]);

  const allCells = data
    ? data.pathways.flatMap((p) => [
        p.eligible,
        p.invited,
        p.booked,
        p.attended,
        p.follow_up,
        p.completed,
        p.declined,
        p.unreachable,
      ])
    : [];
  const suppressedCount = allCells.filter((c) => c.suppressed).length;

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg text-ink">Live API analytics</h2>
          <p className="mt-1 text-sm text-ink-muted">
            Straight from{" "}
            <span className="font-mono-tech">
              GET /api/v1/analytics/overview
            </span>
            . Suppression is applied by the server, so hidden counts never reach
            this page.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="inline-flex items-center gap-1.5 rounded border border-border px-2 py-1 text-xs font-medium text-ink hover:bg-subtle"
        >
          <RotateCcw aria-hidden="true" className="size-3" />
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {error ? (
        <p className="flex items-start gap-1.5 rounded-md border border-status-overdue bg-status-overdue-bg p-2 text-xs text-status-overdue">
          <AlertOctagon aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          <span>{error}</span>
        </p>
      ) : null}

      {data ? (
        <>
          <p className="text-xs text-ink-muted">
            As of <span className="font-mono-tech">{data.as_of}</span> ·
            threshold{" "}
            <span className="font-mono-tech">n &lt; {data.threshold}</span> ·{" "}
            <span className="tabular font-medium text-ink">
              {suppressedCount}
            </span>
            /
            <span className="tabular font-medium text-ink">
              {allCells.length}
            </span>{" "}
            cells suppressed
          </p>
          <p className="flex items-start gap-1.5 rounded-md border border-border bg-subtle p-2 text-xs text-ink-muted">
            <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
            <span>{data.notice}</span>
          </p>

          {data.pathways.map((pathway) => (
            <PathwayCard
              key={pathway.pathway}
              label={PATHWAY_LABELS[pathway.pathway]}
              eligible={pathway.eligible}
              invited={pathway.invited}
              booked={pathway.booked}
              attended={pathway.attended}
              follow_up={pathway.follow_up}
              completed={pathway.completed}
              declined={pathway.declined}
              unreachable={pathway.unreachable}
            />
          ))}
        </>
      ) : !error && !loading ? (
        <p className="text-sm text-ink-muted">Waiting for a guest session.</p>
      ) : null}
    </section>
  );
}

function PathwayCard({
  label,
  eligible,
  invited,
  booked,
  attended,
  follow_up,
  completed,
  declined,
  unreachable,
}: {
  label: string;
  eligible: MetricCell;
  invited: MetricCell;
  booked: MetricCell;
  attended: MetricCell;
  follow_up: MetricCell;
  completed: MetricCell;
  declined: MetricCell;
  unreachable: MetricCell;
}) {
  const cells = {
    eligible,
    invited,
    booked,
    attended,
    follow_up,
    completed,
    declined,
    unreachable,
  };
  const published = FUNNEL.map((key) => cells[key].numerator).filter(
    (n): n is number => n !== null,
  );
  const maxCount = Math.max(0, ...published);
  const completionRate =
    completed.numerator !== null && completed.denominator
      ? rate(completed.numerator, completed.denominator)
      : completed.value !== null
        ? completed.value * 100
        : null;

  return (
    <section className="rounded-lg border border-border bg-surface p-5">
      <h3 className="text-lg text-ink">{label}</h3>
      <p className="mt-0.5 text-xs text-ink-muted">
        Synthetic reporting cohort plus the six journey cases. Worklist cases
        stay on Cases.
      </p>

      <div className="mt-4 rounded-lg border border-border bg-canvas p-4">
        <h4 className="text-sm font-semibold text-ink">Primary completion</h4>
        <p className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <CellValue cell={{ ...completed, denominator: null }} large />
          <span className="text-ink-muted">/</span>
          <CellValue cell={eligible} large />
          <span className="text-sm text-ink-muted">
            verified completed / eligible due
          </span>
          {completionRate !== null ? (
            <span className="tabular rounded-md bg-subtle px-2 py-0.5 text-sm font-medium text-ink">
              {completionRate.toFixed(1)}%
            </span>
          ) : null}
        </p>
        <p className="mt-2 text-xs text-ink-muted">
          Declined, deferred and unreachable people remain in this denominator.
          Only an authorized closure with evidence counts in the numerator.
        </p>
      </div>

      <h4 className="mt-5 text-sm font-semibold text-ink">
        Engagement and progression
      </h4>
      <ul className="mt-2 space-y-2">
        {FUNNEL.map((key) => {
          const cell = cells[key];
          const width =
            !cell.suppressed && cell.numerator !== null && maxCount > 0
              ? (cell.numerator / maxCount) * 100
              : 0;
          return (
            <li key={key}>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="text-ink">{cell.label}</span>
                <CellValue cell={cell} />
              </div>
              <div
                className="mt-1 h-2 w-full overflow-hidden rounded-full bg-subtle"
                role="presentation"
              >
                <div
                  className="h-full rounded-full bg-brand"
                  style={{ width: `${width}%` }}
                />
              </div>
            </li>
          );
        })}
      </ul>

      <h4 className="mt-5 text-sm font-semibold text-ink">Dispositions</h4>
      <ul className="mt-2 divide-y divide-border rounded-md border border-border">
        {DISPOSITIONS.map((key) => {
          const cell = cells[key];
          const countsAsCompleted = key === "completed";
          return (
            <li
              key={key}
              className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm"
            >
              <span className="text-ink">{cell.label}</span>
              <span className="flex items-center gap-3">
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 text-xs font-medium",
                    countsAsCompleted
                      ? "bg-status-verified-bg text-status-verified"
                      : "bg-subtle text-ink-muted",
                  )}
                >
                  {countsAsCompleted ? "Counts as completed" : "Not a completion"}
                </span>
                <CellValue cell={cell} />
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function CellValue({ cell, large }: { cell: MetricCell; large?: boolean }) {
  if (cell.suppressed) {
    return (
      <span className="flex items-center gap-1 text-xs text-ink-muted">
        <Lock aria-hidden="true" className="size-3" />
        <span className="font-mono-tech">
          Suppressed (n &lt; {cell.threshold})
        </span>
      </span>
    );
  }
  const shown =
    cell.numerator !== null
      ? cell.denominator !== null
        ? `${cell.numerator} / ${cell.denominator}`
        : String(cell.numerator)
      : "—";
  return (
    <span
      className={cn(
        "tabular font-medium text-ink",
        large && "text-2xl font-semibold",
      )}
    >
      {shown}
    </span>
  );
}
