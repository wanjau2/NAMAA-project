"use client";

/**
 * Live `GET /api/v1/analytics/overview`, shown beside the local cohort cards.
 *
 * Two honest purposes:
 *  1. Evidence that suppression is now a SERVER duty (Q8 / D003). Suppressed
 *     cells arrive with `numerator: null, denominator: null`, so the browser
 *     never holds the hidden counts.
 *  2. It shows the residual problem plainly: with the API seed at 3 cases per
 *     pathway and a threshold of 10, every cell is suppressed. The logic is
 *     right; the reporting cohort is too small to publish anything.
 */

import { useCallback, useEffect, useState } from "react";
import { AlertOctagon, Info, Lock, RotateCcw } from "lucide-react";
import { api } from "@/lib/api";
import type { AnalyticsOverview, MetricCell } from "@/lib/api-types";
import { PATHWAY_LABELS } from "@/lib/api-types";
import { useCaseStore } from "@/lib/case-store";

const CELL_ORDER = [
  "eligible",
  "invited",
  "booked",
  "attended",
  "follow_up",
  "completed",
  "declined",
  "unreachable",
] as const;

export function ApiAnalyticsPanel() {
  const { sessionId, status } = useCaseStore();
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      setData(await api.analyticsOverview(sessionId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Request failed.");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    if (status !== "ready" || !sessionId || data) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await api.analyticsOverview(sessionId);
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
  }, [status, sessionId, data]);

  const allCells = data
    ? data.pathways.flatMap((p) => CELL_ORDER.map((k) => p[k]))
    : [];
  const suppressedCount = allCells.filter((c) => c.suppressed).length;

  return (
    <section className="rounded-lg border border-border bg-surface p-5">
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
        <p className="mt-3 flex items-start gap-1.5 rounded-md border border-status-overdue bg-status-overdue-bg p-2 text-xs text-status-overdue">
          <AlertOctagon aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          <span>{error}</span>
        </p>
      ) : null}

      {data ? (
        <>
          <p className="mt-3 text-xs text-ink-muted">
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

          {suppressedCount === allCells.length ? (
            <p className="mt-3 flex items-start gap-1.5 rounded-md border border-status-review bg-status-review-bg p-2 text-xs text-status-review">
              <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
              <span>
                Every cell is suppressed. The suppression logic is correct — the
                seeded reporting cohort (3 cases per pathway) is simply smaller
                than the threshold. The cards above therefore use a larger local
                cohort fixture, clearly labelled, until the API seed grows.
              </span>
            </p>
          ) : null}

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {data.pathways.map((pathway) => (
              <div
                key={pathway.pathway}
                className="rounded-md border border-border p-3"
              >
                <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
                  {PATHWAY_LABELS[pathway.pathway]}
                </h3>
                <ul className="mt-2 space-y-1">
                  {CELL_ORDER.map((key) => (
                    <Cell key={key} cell={pathway[key]} />
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </>
      ) : !error && !loading ? (
        <p className="mt-3 text-sm text-ink-muted">
          Waiting for a guest session.
        </p>
      ) : null}
    </section>
  );
}

function Cell({ cell }: { cell: MetricCell }) {
  return (
    <li
      className={cn(
        "flex items-center justify-between gap-2 rounded px-2 py-1 text-sm",
        cell.suppressed && "suppressed-cell",
      )}
    >
      <span className="text-ink">{cell.label}</span>
      {cell.suppressed ? (
        <span className="flex items-center gap-1 text-xs text-ink-muted">
          <Lock aria-hidden="true" className="size-3" />
          <span className="font-mono-tech">
            Suppressed (n &lt; {cell.threshold})
          </span>
        </span>
      ) : (
        <span className="tabular font-medium text-ink">
          {cell.numerator}
          {cell.denominator !== null ? ` / ${cell.denominator}` : ""}
        </span>
      )}
    </li>
  );
}

function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}
