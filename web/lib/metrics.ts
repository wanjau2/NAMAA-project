/**
 * Session-local operational counts and suppression helpers.
 *
 * Population funnel numbers come from GET /api/v1/analytics/overview.
 * Do not recompute them in the browser — hidden counts must never travel
 * in the bundle (Q8 / D003).
 */

import type { CaseRow, EventOut } from "@/lib/api-types";

/** Demonstration suppression threshold. A real pilot needs a governance-approved value. */
export const SUPPRESSION_THRESHOLD = 10;

export type Segment =
  | { label: string; suppressed: false; count: number }
  | { label: string; suppressed: true; reason: "small_cell" | "complementary" };

type RawSegment = { label: string; count: number };

/**
 * Small-cell suppression with complementary suppression.
 *
 * A cell below the threshold is suppressed. If exactly one cell would be
 * hidden while the group total is published, a second cell is suppressed so
 * the missing value cannot be recovered by subtraction.
 */
export function suppressSegments(
  raw: RawSegment[],
  total: number,
  threshold = SUPPRESSION_THRESHOLD,
): Segment[] {
  void total;
  const suppressed = new Set<string>();
  for (const segment of raw) {
    if (segment.count < threshold) suppressed.add(segment.label);
  }

  if (suppressed.size === 1) {
    const next = raw
      .filter((segment) => !suppressed.has(segment.label))
      .sort((a, b) => a.count - b.count)[0];
    if (next) suppressed.add(next.label);
  }

  return raw.map((segment) =>
    suppressed.has(segment.label)
      ? {
          label: segment.label,
          suppressed: true as const,
          reason:
            segment.count < threshold
              ? ("small_cell" as const)
              : ("complementary" as const),
        }
      : { label: segment.label, suppressed: false as const, count: segment.count },
  );
}

/**
 * Activity in the current demo session, reported SEPARATELY from the snapshot.
 * Folding it into the projection would imply a refresh that did not happen.
 */
export type SessionActivity = {
  actions_taken: number;
  completions: number;
  non_completion_closures: number;
  declines: number;
  unreachable: number;
  rejected_referrals: number;
  by_owner: { owner: string; open_cases: number }[];
};

export function sessionActivity(
  cases: CaseRow[],
  events: EventOut[],
): SessionActivity {
  const byOwner = new Map<string, number>();
  for (const c of cases) {
    if (c.stage === "closed") continue;
    byOwner.set(c.owner, (byOwner.get(c.owner) ?? 0) + 1);
  }

  return {
    actions_taken: events.length,
    completions: events.filter((e) => e.action === "close_as_completed").length,
    non_completion_closures: events.filter((e) => e.action === "close_other")
      .length,
    declines: events.filter((e) => e.action === "record_decline").length,
    unreachable: events.filter((e) => e.action === "record_unreachable").length,
    rejected_referrals: cases.filter((c) => c.overdue).length,
    by_owner: [...byOwner.entries()]
      .map(([owner, open_cases]) => ({ owner, open_cases }))
      .sort((a, b) => b.open_cases - a.open_cases),
  };
}

/** Rate as a percentage, or null when the denominator is zero. */
export function rate(numerator: number, denominator: number): number | null {
  if (denominator <= 0) return null;
  return (numerator / denominator) * 100;
}
