"use client";

/**
 * Population dashboard (theme §5, work plan F5, design specification §10).
 *
 * Rules this screen implements:
 *  - Every rate shows its NUMERATOR and DENOMINATOR, never a bare percentage.
 *  - Declined, deferred and unreachable people stay in the denominator and are
 *    listed explicitly as non-completions.
 *  - `clinically_closed_other` is shown as a closure that does NOT complete care.
 *  - Invitation, booking, attendance and follow-up are distinct counts.
 *  - Small cells are suppressed, including complementary cells.
 *  - Everything is labelled synthetic, and no figure implies a real-world
 *    outcome or any clinical performance claim.
 *
 * No charting library (theme scope guardrail): the funnel is CSS bars.
 */

import { useMemo } from "react";
import { AlertTriangle, Info, Lock } from "lucide-react";
import { cn } from "@/lib/utils";
import { ApiAnalyticsPanel } from "@/components/api-analytics-panel";
import { useCaseStore } from "@/lib/case-store";
import { useDemoSession } from "@/lib/demo-session";
import {
  SUPPRESSION_THRESHOLD,
  buildMetrics,
  rate,
  sessionActivity,
  type PathwayMetrics,
  type SegmentGroup,
} from "@/lib/metrics";

export default function MetricsPage() {
  const { rows } = useCaseStore();
  const { role } = useDemoSession();
  const metrics = useMemo(() => buildMetrics(), []);
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

      {/* Mandatory banner. */}
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

      <p className="mt-6 flex items-start gap-2 rounded-lg border border-border bg-subtle p-3 text-xs text-ink-muted">
        <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
        <span>
          The cards below use a larger <strong>local cohort fixture</strong> so the
          funnel, segments and timeliness views can be demonstrated. They are not
          served by the API. Treat them as a design reference, not as data.
        </span>
      </p>

      <div className="mt-4 space-y-6">
        {metrics.map((pathway) => (
          <PathwayCard key={pathway.pathway} metrics={pathway} />
        ))}
      </div>

      {/* Session activity, kept out of the projection on purpose. */}
      <section className="mt-6 rounded-lg border border-border bg-surface p-5">
        <h2 className="text-lg text-ink">This session</h2>
        <p className="mt-1 text-sm text-ink-muted">
          Actions taken in this guest session are reported separately until the
          next projection refresh. A dashboard that folds them in silently would
          imply a refresh that did not happen.
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

function PathwayCard({ metrics }: { metrics: PathwayMetrics }) {
  const completionRate = rate(metrics.verified_completed, metrics.eligible_due);
  const maxCount = Math.max(...metrics.funnel.map((step) => step.count));

  return (
    <section className="rounded-lg border border-border bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg text-ink">{metrics.label}</h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            {metrics.cohort_label}
          </p>
        </div>
        <p className="text-xs text-ink-muted">
          Window{" "}
          <span className="font-mono-tech">{metrics.window_start}</span> to{" "}
          <span className="font-mono-tech">{metrics.window_end}</span>
          <br />
          Refreshed{" "}
          <span className="font-mono-tech">{metrics.refreshed_at}</span>
        </p>
      </div>

      {/* Primary completion: numerator and denominator always visible. */}
      <div className="mt-4 rounded-lg border border-border bg-canvas p-4">
        <h3 className="text-sm font-semibold text-ink">Primary completion</h3>
        <p className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="tabular text-2xl font-semibold text-ink">
            {metrics.verified_completed}
          </span>
          <span className="text-ink-muted">/</span>
          <span className="tabular text-2xl font-semibold text-ink">
            {metrics.eligible_due}
          </span>
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

      {/* Funnel — distinct counts, CSS bars. */}
      <h3 className="mt-5 text-sm font-semibold text-ink">
        Engagement and progression
      </h3>
      <ul className="mt-2 space-y-2">
        {metrics.funnel.map((step) => (
          <li key={step.label}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="text-ink">{step.label}</span>
              <span className="tabular font-medium text-ink">{step.count}</span>
            </div>
            <div
              className="mt-1 h-2 w-full overflow-hidden rounded-full bg-subtle"
              role="presentation"
            >
              <div
                className="h-full rounded-full bg-brand"
                style={{
                  width: `${maxCount > 0 ? (step.count / maxCount) * 100 : 0}%`,
                }}
              />
            </div>
            {step.note ? (
              <p className="mt-1 text-xs text-ink-muted">{step.note}</p>
            ) : null}
          </li>
        ))}
      </ul>

      {/* Dispositions, with completion status stated per row. */}
      <h3 className="mt-5 text-sm font-semibold text-ink">Dispositions</h3>
      <ul className="mt-2 divide-y divide-border rounded-md border border-border">
        {metrics.dispositions.map((disposition) => (
          <li
            key={disposition.label}
            className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm"
          >
            <span className="text-ink">{disposition.label}</span>
            <span className="flex items-center gap-3">
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 text-xs font-medium",
                  disposition.counts_as_completed
                    ? "bg-status-verified-bg text-status-verified"
                    : "bg-subtle text-ink-muted",
                )}
              >
                {disposition.counts_as_completed
                  ? "Counts as completed"
                  : "Not a completion"}
              </span>
              <span className="tabular font-medium text-ink">
                {disposition.count}
              </span>
            </span>
          </li>
        ))}
      </ul>

      {/* Timeliness, including what is missing. */}
      <h3 className="mt-5 text-sm font-semibold text-ink">Timeliness</h3>
      <dl className="mt-2 grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Stat
          label="Median days to attendance"
          value={metrics.timeliness.median_days_to_attendance ?? "Not reportable"}
        />
        <Stat label="Overdue tasks" value={metrics.timeliness.overdue_tasks} />
        <Stat
          label="Records with missing timestamps"
          value={metrics.timeliness.missing_timestamps}
        />
      </dl>
      <p className="mt-2 text-xs text-ink-muted">
        Missing timestamps are reported rather than excluded, so the median is
        read against what is actually known.
      </p>

      {/* Fixed segment views with suppression. */}
      <h3 className="mt-5 text-sm font-semibold text-ink">Segments</h3>
      <div className="mt-2 grid gap-4 md:grid-cols-3">
        {metrics.segment_groups.map((group) => (
          <SegmentCard key={group.key} group={group} />
        ))}
      </div>
    </section>
  );
}

function SegmentCard({ group }: { group: SegmentGroup }) {
  return (
    <div className="rounded-md border border-border p-3">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
        {group.title}
      </h4>
      <p className="mt-1 text-xs text-ink-muted">
        Total <span className="tabular font-medium text-ink">{group.total}</span>
      </p>
      <ul className="mt-2 space-y-1">
        {group.segments.map((segment) => (
          <li
            key={segment.label}
            className={cn(
              "flex items-center justify-between gap-2 rounded px-2 py-1 text-sm",
              segment.suppressed && "suppressed-cell",
            )}
          >
            <span className="text-ink">{segment.label}</span>
            {segment.suppressed ? (
              <span className="flex items-center gap-1 text-xs text-ink-muted">
                <Lock aria-hidden="true" className="size-3" />
                <span className="font-mono-tech">
                  Suppressed (n &lt; {SUPPRESSION_THRESHOLD})
                </span>
              </span>
            ) : (
              <span className="tabular font-medium text-ink">
                {segment.count}
              </span>
            )}
          </li>
        ))}
      </ul>
      {group.anySuppressed ? (
        <p className="mt-2 text-xs text-ink-muted">
          Cells below {SUPPRESSION_THRESHOLD} are suppressed. A second cell is
          suppressed where the published total would otherwise reveal the first.
        </p>
      ) : null}
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
