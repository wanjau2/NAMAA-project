/**
 * Population metrics from a fixed cohort snapshot.
 *
 * ############################################################################
 * # LOCAL STAND-IN. Suppression MUST move server-side at F4 — see Q8.        #
 * ############################################################################
 *
 * Structure matters more than the numbers here. Suppression is applied in THIS
 * layer and suppressed cells are returned with the value ABSENT, so the
 * component can only render what it was given. That is the shape the API has to
 * return. It is not yet the security property: a client-side layer still has
 * the underlying counts in the bundle, which is precisely why Q8 asks for this
 * to be computed and suppressed on the server.
 *
 * Definitions follow the work plan and design specification §10:
 *  - Completion = people with a VERIFIED completed action / eligible people due
 *    in a fixed cohort. Reported separately for child and adult pathways.
 *  - Declined, deferred and unreachable people REMAIN in the denominator.
 *  - `clinically_closed_other` never counts as completed care.
 *  - Invitation reach, booking, attendance and follow-up are distinct counts.
 *  - No claim of false-positive rate, calibration or clinical effectiveness is
 *    derivable from any of this. These are synthetic operational counts.
 */

import type { CaseRow, EventOut, Pathway } from "@/lib/api-types";

/** Demonstration suppression threshold. A real pilot needs a governance-approved value. */
export const SUPPRESSION_THRESHOLD = 10;

export type Segment =
  | { label: string; suppressed: false; count: number }
  /** Value omitted on purpose. The component has nothing else to render. */
  | { label: string; suppressed: true; reason: "small_cell" | "complementary" };

export type SegmentGroup = {
  key: string;
  title: string;
  /** Stated so a reader can see the denominator the segments divide. */
  total: number;
  segments: Segment[];
  anySuppressed: boolean;
};

export type PathwayMetrics = {
  pathway: Pathway;
  label: string;
  cohort_label: string;
  window_start: string;
  window_end: string;
  refreshed_at: string;
  /** Denominator: eligible people due in the fixed cohort. */
  eligible_due: number;
  /** Numerator: verified completed preventive action. */
  verified_completed: number;
  funnel: { label: string; count: number; note?: string }[];
  dispositions: { label: string; count: number; counts_as_completed: boolean }[];
  timeliness: {
    median_days_to_attendance: number | null;
    overdue_tasks: number;
    missing_timestamps: number;
  };
  segment_groups: SegmentGroup[];
};

type RawSegment = { label: string; count: number };

type Baseline = {
  pathway: Pathway;
  label: string;
  cohort_label: string;
  window_start: string;
  window_end: string;
  refreshed_at: string;
  eligible_due: number;
  invited: number;
  booked: number;
  attended: number;
  follow_up_due: number;
  follow_up_completed: number;
  verified_completed: number;
  declined: number;
  deferred: number;
  unreachable: number;
  closed_other: number;
  median_days_to_attendance: number | null;
  overdue_tasks: number;
  missing_timestamps: number;
  segment_groups: { key: string; title: string; segments: RawSegment[] }[];
};

/**
 * Fixed synthetic cohort snapshot. Every number is fictional.
 * A projection has a refresh time by design (§10): actions taken during a demo
 * session are reported separately until the next refresh rather than silently
 * folded in, because a dashboard that invents precision is worse than one that
 * admits latency.
 */
const BASELINES: Baseline[] = [
  {
    pathway: "child_wcv",
    label: "Child Well-Child",
    cohort_label: "Children due a well-child visit (synthetic)",
    window_start: "2026-05-01",
    window_end: "2026-10-31",
    refreshed_at: "2026-11-17T06:00:00Z",
    eligible_due: 142,
    invited: 118,
    booked: 86,
    attended: 74,
    follow_up_due: 31,
    follow_up_completed: 22,
    verified_completed: 68,
    declined: 14,
    deferred: 5,
    unreachable: 9,
    closed_other: 3,
    median_days_to_attendance: 12,
    overdue_tasks: 7,
    missing_timestamps: 4,
    segment_groups: [
      {
        key: "age_band",
        title: "Age band",
        segments: [
          { label: "0–1 years", count: 31 },
          { label: "2–4 years", count: 58 },
          { label: "5–9 years", count: 44 },
          { label: "10–14 years", count: 6 },
          { label: "15–17 years", count: 3 },
        ],
      },
      {
        key: "channel",
        title: "Contact channel",
        segments: [
          { label: "SMS", count: 96 },
          { label: "Phone (assisted)", count: 39 },
          { label: "Email", count: 7 },
        ],
      },
      {
        key: "geography",
        title: "Synthetic geography",
        segments: [
          { label: "Zone A", count: 61 },
          { label: "Zone B", count: 48 },
          { label: "Zone C", count: 25 },
          { label: "Zone D", count: 8 },
        ],
      },
    ],
  },
  {
    pathway: "adult_screening",
    label: "Adult Screening",
    cohort_label: "Adults due comprehensive screening review (synthetic)",
    window_start: "2026-05-01",
    window_end: "2026-10-31",
    refreshed_at: "2026-11-17T06:00:00Z",
    eligible_due: 97,
    invited: 71,
    booked: 48,
    attended: 39,
    follow_up_due: 26,
    follow_up_completed: 15,
    verified_completed: 33,
    declined: 11,
    deferred: 4,
    unreachable: 7,
    closed_other: 2,
    median_days_to_attendance: 19,
    overdue_tasks: 11,
    missing_timestamps: 6,
    segment_groups: [
      {
        key: "age_band",
        title: "Age band",
        segments: [
          { label: "40–44 years", count: 8 },
          { label: "45–49 years", count: 29 },
          { label: "50–54 years", count: 34 },
          { label: "55–59 years", count: 22 },
          { label: "60+ years", count: 4 },
        ],
      },
      {
        key: "channel",
        title: "Contact channel",
        segments: [
          { label: "SMS", count: 54 },
          { label: "Phone (assisted)", count: 31 },
          { label: "Email", count: 12 },
        ],
      },
      {
        key: "geography",
        title: "Synthetic geography",
        segments: [
          { label: "Zone A", count: 38 },
          { label: "Zone B", count: 34 },
          { label: "Zone C", count: 19 },
          { label: "Zone D", count: 6 },
        ],
      },
    ],
  },
];

/**
 * Small-cell suppression with complementary suppression.
 *
 * A cell below the threshold is suppressed. But if exactly ONE cell is
 * suppressed while the group total is published, the hidden value is simply
 * total minus the rest — so a second cell must be suppressed too. The next
 * smallest is chosen, which is sometimes an expensive cell to lose. That cost
 * is the point: it is what prevents reconstruction.
 */
export function suppressSegments(
  raw: RawSegment[],
  total: number,
  threshold = SUPPRESSION_THRESHOLD,
): SegmentGroup["segments"] {
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

function buildPathway(baseline: Baseline): PathwayMetrics {
  const groups: SegmentGroup[] = baseline.segment_groups.map((group) => {
    const total = group.segments.reduce((sum, s) => sum + s.count, 0);
    const segments = suppressSegments(group.segments, total);
    return {
      key: group.key,
      title: group.title,
      total,
      segments,
      anySuppressed: segments.some((s) => s.suppressed),
    };
  });

  return {
    pathway: baseline.pathway,
    label: baseline.label,
    cohort_label: baseline.cohort_label,
    window_start: baseline.window_start,
    window_end: baseline.window_end,
    refreshed_at: baseline.refreshed_at,
    eligible_due: baseline.eligible_due,
    verified_completed: baseline.verified_completed,
    funnel: [
      {
        label: "Eligible due",
        count: baseline.eligible_due,
        note: "Denominator. Includes declined, deferred and unreachable people.",
      },
      { label: "Invited", count: baseline.invited },
      {
        label: "Booked",
        count: baseline.booked,
        note: "A booking is not attendance.",
      },
      {
        label: "Attended",
        count: baseline.attended,
        note: "Attendance is not completion.",
      },
      { label: "Follow-up due", count: baseline.follow_up_due },
      { label: "Follow-up completed", count: baseline.follow_up_completed },
      {
        label: "Verified completed",
        count: baseline.verified_completed,
        note: "Requires evidence and reviewer authorization.",
      },
    ],
    dispositions: [
      {
        label: "Preventive action completed",
        count: baseline.verified_completed,
        counts_as_completed: true,
      },
      { label: "Declined", count: baseline.declined, counts_as_completed: false },
      { label: "Deferred", count: baseline.deferred, counts_as_completed: false },
      {
        label: "Unreachable",
        count: baseline.unreachable,
        counts_as_completed: false,
      },
      {
        label: "Clinically closed — other reason",
        count: baseline.closed_other,
        counts_as_completed: false,
      },
    ],
    timeliness: {
      median_days_to_attendance: baseline.median_days_to_attendance,
      overdue_tasks: baseline.overdue_tasks,
      missing_timestamps: baseline.missing_timestamps,
    },
    segment_groups: groups,
  };
}

export function buildMetrics(): PathwayMetrics[] {
  return BASELINES.map(buildPathway);
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
    // Referral outcome lives in case detail, which the worklist rows omit;
    // overdue is the row-level signal the API exposes for escalated work.
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
