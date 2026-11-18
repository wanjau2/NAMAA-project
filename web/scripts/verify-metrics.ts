/**
 * Metric-definition and suppression checks for lib/metrics.ts.
 *
 * Run: npm run verify:metrics
 *
 * Software checks on synthetic counts. They assert the DEFINITIONS the work
 * plan and design specification §10 require — not clinical accuracy, which
 * none of this evidences.
 */

import {
  SUPPRESSION_THRESHOLD,
  buildMetrics,
  rate,
  suppressSegments,
} from "../lib/metrics.ts";

let pass = 0;
let fail = 0;
function check(name: string, condition: boolean, detail = "") {
  if (condition) {
    pass++;
    console.log(`PASS  ${name}`);
  } else {
    fail++;
    console.log(`FAIL  ${name} ${detail}`);
  }
}

const metrics = buildMetrics();

check("both pathways reported separately", metrics.length === 2);
check(
  "child and adult are distinct cohorts",
  metrics[0].pathway === "child_wcv" && metrics[1].pathway === "adult_screening",
);

for (const m of metrics) {
  const tag = m.pathway;

  // --- denominator integrity ---
  const dispositionTotal = m.dispositions.reduce((sum, d) => sum + d.count, 0);
  check(
    `[${tag}] non-completions are reported, not dropped`,
    m.dispositions.filter((d) => !d.counts_as_completed).length === 4,
  );
  check(
    `[${tag}] declined/deferred/unreachable/other fit inside the denominator`,
    dispositionTotal <= m.eligible_due,
    `${dispositionTotal} > ${m.eligible_due}`,
  );
  check(
    `[${tag}] only one disposition counts as completed`,
    m.dispositions.filter((d) => d.counts_as_completed).length === 1,
  );
  check(
    `[${tag}] the completing disposition equals the numerator`,
    m.dispositions.find((d) => d.counts_as_completed)?.count ===
      m.verified_completed,
  );
  check(
    `[${tag}] clinically_closed_other does not count as completed`,
    m.dispositions.find((d) => d.label.startsWith("Clinically closed"))
      ?.counts_as_completed === false,
  );

  // --- funnel integrity ---
  const step = (label: string) =>
    m.funnel.find((f) => f.label === label)?.count ?? -1;
  check(
    `[${tag}] funnel is monotonic: eligible >= invited >= booked >= attended`,
    step("Eligible due") >= step("Invited") &&
      step("Invited") >= step("Booked") &&
      step("Booked") >= step("Attended"),
  );
  check(
    `[${tag}] verified completed never exceeds attended`,
    m.verified_completed <= step("Attended"),
  );
  check(
    `[${tag}] follow-up completed never exceeds follow-up due`,
    step("Follow-up completed") <= step("Follow-up due"),
  );
  check(
    `[${tag}] eligible-due step equals the published denominator`,
    step("Eligible due") === m.eligible_due,
  );
  check(
    `[${tag}] booking and attendance carry their caveats`,
    Boolean(m.funnel.find((f) => f.label === "Booked")?.note) &&
      Boolean(m.funnel.find((f) => f.label === "Attended")?.note),
  );

  // --- timeliness reports what is missing ---
  check(
    `[${tag}] missing timestamps are reported`,
    typeof m.timeliness.missing_timestamps === "number",
  );

  // --- suppression ---
  for (const group of m.segment_groups) {
    const published = group.segments.filter((s) => !s.suppressed);
    const hidden = group.segments.filter((s) => s.suppressed);

    check(
      `[${tag}/${group.key}] no published cell is below the threshold`,
      published.every((s) => !s.suppressed && s.count >= SUPPRESSION_THRESHOLD),
    );
    check(
      `[${tag}/${group.key}] suppressed cells carry no value`,
      hidden.every((s) => !("count" in s)),
    );
    if (hidden.length > 0) {
      check(
        `[${tag}/${group.key}] never exactly one suppressed cell (reconstructable)`,
        hidden.length >= 2,
        `only ${hidden.length} suppressed`,
      );
      const publishedSum = published.reduce(
        (sum, s) => sum + (s.suppressed ? 0 : s.count),
        0,
      );
      check(
        `[${tag}/${group.key}] residual cannot be attributed to one cell`,
        group.total - publishedSum > 0 && hidden.length >= 2,
      );
    }
  }
}

// --- suppression unit behaviour ---
const oneSmall = suppressSegments(
  [
    { label: "A", count: 96 },
    { label: "B", count: 39 },
    { label: "C", count: 7 },
  ],
  142,
);
check(
  "a lone small cell triggers complementary suppression of the next smallest",
  oneSmall.filter((s) => s.suppressed).length === 2 &&
    oneSmall.find((s) => s.label === "C")?.suppressed === true &&
    oneSmall.find((s) => s.label === "B")?.suppressed === true,
);
check(
  "complementary suppression is labelled with its reason",
  oneSmall.find((s) => s.label === "B" && s.suppressed)?.suppressed === true &&
    (oneSmall.find((s) => s.label === "B") as { reason?: string })?.reason ===
      "complementary",
);
check(
  "the largest cell survives suppression",
  oneSmall.find((s) => s.label === "A")?.suppressed === false,
);

const twoSmall = suppressSegments(
  [
    { label: "A", count: 58 },
    { label: "B", count: 6 },
    { label: "C", count: 3 },
  ],
  67,
);
check(
  "two small cells need no complementary suppression",
  twoSmall.filter((s) => s.suppressed).length === 2,
);

const noneSmall = suppressSegments(
  [
    { label: "A", count: 54 },
    { label: "B", count: 31 },
    { label: "C", count: 12 },
  ],
  97,
);
check(
  "no suppression when every cell clears the threshold",
  noneSmall.every((s) => !s.suppressed),
);

// --- rate ---
check("rate returns null on a zero denominator", rate(0, 0) === null);
check("rate is a percentage", rate(68, 142)?.toFixed(1) === "47.9");

console.log(`\n${pass} passed, ${fail} failed`);
if (fail > 0) process.exit(1);
