"use client";

/**
 * Population dashboard (theme §5, work plan F5, design specification §10).
 *
 * Funnel, dispositions and segments are the live API release. This session's
 * worklist activity is reported separately so a dashboard does not invent a
 * projection refresh. Timeliness cards are labelled design examples — they
 * are not in the analytics API.
 */

import { useMemo } from "react";
import { AlertTriangle, Info } from "lucide-react";
import { ApiAnalyticsPanel } from "@/components/api-analytics-panel";
import { useCaseStore } from "@/lib/case-store";
import { useDemoSession } from "@/lib/demo-session";
import { sessionActivity } from "@/lib/metrics";

const TIMELINESS_EXAMPLES = [
  "Median time to invitation",
  "Median time to attendance",
  "Overdue task rate",
] as const;

export default function MetricsPage() {
  const { rows } = useCaseStore();
  const { role } = useDemoSession();
  const activity = useMemo(() => sessionActivity(rows, []), [rows]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <header>
        <h1 className="text-2xl text-ink">Population view</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-muted">
          Fixed synthetic cohorts over a fixed observation window. Operational
          counts only — nothing here is a measure of clinical effectiveness,
          calibration or diagnostic accuracy.
        </p>
      </header>

      <p className="mt-4 flex items-start gap-2 rounded-lg border border-status-review bg-status-review-bg p-3 text-sm font-semibold text-status-review">
        <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        <span>
          Synthetic Demo Metrics — fictional population, not real-world outcomes
        </span>
      </p>

      {role === "population_analyst" ? (
        <p className="mt-3 flex items-start gap-2 rounded-lg border border-border bg-subtle p-3 text-xs text-ink-muted">
          <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          <span>
            Analyst view: approved aggregates only. Fixed segment views, no
            overlapping filters and no individual-level export, so small groups
            cannot be reconstructed by combining views.
          </span>
        </p>
      ) : null}

      <div className="mt-6">
        <ApiAnalyticsPanel />
      </div>

      <section className="mt-6 rounded-lg border border-dashed border-border bg-surface p-5">
        <h2 className="text-lg text-ink">Timeliness</h2>
        <p className="mt-1 text-sm text-ink-muted">
          Design example — not in this API. Not computed from this worklist and
          not a live metric. These views wait on an equivalent API aggregate.
        </p>
        <ul className="mt-4 divide-y divide-border rounded-md border border-border">
          {TIMELINESS_EXAMPLES.map((label) => (
            <li
              key={label}
              className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm"
            >
              <span className="text-ink">{label}</span>
              <span className="font-mono-tech text-xs text-ink-muted">
                Not published
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-6 rounded-lg border border-border bg-surface p-5">
        <h2 className="text-lg text-ink">This worklist session</h2>
        <p className="mt-1 text-sm text-ink-muted">
          Operational counts from the six-case coordinator worklist in this
          guest session. They are not the population publication family, are
          not small-cell suppressed, and must not be folded into the live
          funnel as if a projection refresh happened.
        </p>
        <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Stat
            label="Open cases assigned"
            value={rows.filter((c) => c.stage !== "closed").length}
          />
          <Stat label="Overdue / escalated" value={activity.rejected_referrals} />
          <Stat label="Owners with open work" value={activity.by_owner.length} />
        </dl>
        {activity.by_owner.length > 0 ? (
          <ul className="mt-4 space-y-1 text-sm">
            {activity.by_owner.map((owner) => (
              <li key={owner.owner} className="flex justify-between gap-4">
                <span className="text-ink">{owner.owner}</span>
                <span className="tabular text-ink-muted">
                  {owner.open_cases} open
                </span>
              </li>
            ))}
          </ul>
        ) : null}
        <p className="mt-3 text-xs text-ink-muted">
          Coordinator workload and rejected handoffs are operational measures.
          They carry no claim of clinical benefit.
        </p>
      </section>
    </div>
  );
}

function Stat({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div>
      <dt className="text-xs font-medium text-ink-muted">{label}</dt>
      <dd className="tabular mt-1 text-lg font-semibold text-ink">{value}</dd>
    </div>
  );
}
