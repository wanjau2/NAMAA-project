/**
 * Suppression helper checks. Population counts are asserted against the API,
 * not a local fixture.
 *
 * Run: npm run verify:metrics
 */

import {
  SUPPRESSION_THRESHOLD,
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

check("suppression threshold is at least 10", SUPPRESSION_THRESHOLD >= 10);

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

check("rate returns null on a zero denominator", rate(0, 0) === null);
check("rate is a percentage", rate(68, 142)?.toFixed(1) === "47.9");

console.log(`\n${pass} passed, ${fail} failed`);
if (fail > 0) process.exit(1);
