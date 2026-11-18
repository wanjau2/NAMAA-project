/**
 * Checks for lib/text-offsets.ts and lib/rule-outcomes.ts.
 *
 * Run: npm run verify:contracts
 *
 * These two modules encode requirements from Alfred's handoff
 * (ai/docs/CONTRACTS.md): Unicode code-point offsets, null offsets that must
 * never be guessed at, and four rule outcomes that must not be collapsed.
 * Both fail silently if wrong, which is why they are tested rather than
 * eyeballed.
 */

import {
  codePointLength,
  isTraceable,
  sliceCodePoints,
  traceability,
} from "../lib/text-offsets.ts";
import {
  OUTCOME_DISPLAY,
  RULE_OUTCOMES,
  blocksPathway,
  resolveOutcome,
} from "../lib/rule-outcomes.ts";

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

/* ------------------------------------------------------------------ offsets */

const ascii = "Caregiver cannot recall the date of the last check-up.";
check(
  "ASCII: code-point slice equals the naive JS slice",
  sliceCodePoints(ascii, 10, 23) === ascii.slice(10, 23),
);

// Arabic is inside the BMP: one UTF-16 unit per character, so the two agree.
const arabic = "المراجع السريري أكد التاريخ";
check(
  "Arabic (BMP): code-point length equals JS length",
  codePointLength(arabic) === arabic.length,
);

// Astral characters are where Python and JavaScript part company.
const astral = "Caregiver 🧒 asked about the visit 🗓 last year.";
check(
  "astral: code-point length is SHORTER than JS length",
  codePointLength(astral) < astral.length,
  `${codePointLength(astral)} vs ${astral.length}`,
);

const target = "asked about the visit";
const cpStart = Array.from(astral).join("").indexOf(target); // not reliable; compute properly
const points = Array.from(astral);
let start = -1;
for (let i = 0; i < points.length; i++) {
  if (points.slice(i, i + Array.from(target).length).join("") === target) {
    start = i;
    break;
  }
}
const end = start + Array.from(target).length;

check(
  "astral: code-point slice recovers the excerpt",
  sliceCodePoints(astral, start, end) === target,
  sliceCodePoints(astral, start, end),
);
check(
  "astral: the naive JS slice at the SAME offsets does NOT — the bug this prevents",
  astral.slice(start, end) !== target,
  `naive gave "${astral.slice(start, end)}"`,
);
void cpStart;

check(
  "a verified span splits the note into before / match / after",
  (() => {
    const t = traceability(astral, {
      offset_start: start,
      offset_end: end,
      excerpt: target,
    });
    return (
      t.state === "verified" &&
      t.before + t.match + t.after === astral &&
      t.match === target
    );
  })(),
);

check(
  "null offsets are reported as no_offsets, never highlighted",
  traceability(ascii, {
    offset_start: null,
    offset_end: null,
    excerpt: "cannot recall",
  }).state === "no_offsets",
);

check(
  "a half-null offset pair is still no_offsets",
  traceability(ascii, {
    offset_start: 3,
    offset_end: null,
    excerpt: "x",
  }).state === "no_offsets",
);

check(
  "offsets beyond the note are out_of_range",
  traceability(ascii, {
    offset_start: 10,
    offset_end: 9999,
    excerpt: "whatever",
  }).state === "out_of_range",
);

check(
  "an inverted span is out_of_range, not a silent empty match",
  traceability(ascii, { offset_start: 20, offset_end: 10, excerpt: "" })
    .state === "out_of_range",
);

check(
  "offsets naming different text are a mismatch, and report what was found",
  (() => {
    const t = traceability(ascii, {
      offset_start: 0,
      offset_end: 9,
      excerpt: "Clinician",
    });
    return t.state === "mismatch" && t.found === "Caregiver";
  })(),
);

check(
  "isTraceable is true only for a verified span",
  isTraceable(ascii, { offset_start: 0, offset_end: 9, excerpt: "Caregiver" }) &&
    !isTraceable(ascii, {
      offset_start: null,
      offset_end: null,
      excerpt: "Caregiver",
    }),
);

/* ----------------------------------------------------------------- outcomes */

check("all four rule outcomes exist", RULE_OUTCOMES.length === 4);
check(
  "every outcome has a label, a meaning and a limitation",
  RULE_OUTCOMES.every((o) => {
    const d = OUTCOME_DISPLAY[o];
    return Boolean(d.label) && Boolean(d.meaning) && Boolean(d.limitation);
  }),
);
check(
  "no-gap carries an explicit non-assurance limitation",
  /not an assurance of health/i.test(
    OUTCOME_DISPLAY.no_gap_identified_in_available_data.limitation ?? "",
  ),
);
check(
  "needs-review states that unknown is not up to date",
  /unknown is not the same as up to date/i.test(
    OUTCOME_DISPLAY.needs_review.limitation ?? "",
  ),
);
check(
  "gap-identified is labelled a prioritization signal, not a diagnosis",
  /not a diagnosis/i.test(OUTCOME_DISPLAY.gap_identified.limitation ?? ""),
);
check(
  "not-eligible is scoped to its own pathway",
  /this pathway/i.test(OUTCOME_DISPLAY.not_eligible.limitation ?? ""),
);
check(
  "no two outcomes share a label (none is collapsed into another)",
  new Set(RULE_OUTCOMES.map((o) => OUTCOME_DISPLAY[o].label)).size === 4,
);

check(
  "canonical values pass through unchanged",
  RULE_OUTCOMES.every((o) => {
    const r = resolveOutcome(o);
    return r.outcome === o && r.source === "canonical";
  }),
);
check(
  "the API's short spellings are aliased, and say so",
  resolveOutcome("gap").outcome === "gap_identified" &&
    resolveOutcome("gap").source === "aliased" &&
    resolveOutcome("no_gap").outcome ===
      "no_gap_identified_in_available_data" &&
    resolveOutcome("no_gap").source === "aliased",
);
check(
  "needs_review is canonical in both vocabularies",
  resolveOutcome("needs_review").source === "canonical",
);
check(
  "an unrecognised outcome falls back to needs_review AND is flagged",
  (() => {
    const r = resolveOutcome("definitely_fine_no_action");
    return (
      r.outcome === "needs_review" &&
      r.source === "unknown" &&
      r.raw === "definitely_fine_no_action"
    );
  })(),
);
check(
  "only needs_review blocks the pathway",
  blocksPathway("needs_review") &&
    !blocksPathway("gap_identified") &&
    !blocksPathway("not_eligible") &&
    !blocksPathway("no_gap_identified_in_available_data"),
);

console.log(`\n${pass} passed, ${fail} failed`);
if (fail > 0) process.exit(1);
