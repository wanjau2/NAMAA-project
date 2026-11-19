/**
 * Checks for lib/contracts.ts and the context rendering rules.
 *
 * Run: npm run verify:shapes
 *
 * Covers the parts of Alfred's handoff that are easy to get subtly wrong:
 * adapting the API's flat proposal without inventing fields, blocking issues,
 * and the completeness / absence semantics the context panel must preserve.
 */

import {
  COMPLETENESS_DISPLAY,
  TIER_LABELS,
  fromApiProposal,
  hasBlockingIssue,
} from "../lib/contracts.ts";
import {
  buildReviewCommand,
  normalizeProposal,
} from "../lib/contracts.ts";
import {
  ALFRED_CONTEXT_EXAMPLE,
  EMPTY_CONTEXT_EXAMPLE,
} from "../lib/context-example.ts";
import {
  describeSecurityOutcome,
  leaksExistence,
} from "../lib/security-states.ts";

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

/* ----------------------------------------------------------- the adapter */

const api = {
  id: "prop-1",
  concept: "Last well-child visit",
  value_text: "Caregiver cannot recall the date",
  subject: "patient" as const,
  assertion: "uncertain" as const,
  effective_date: null,
  proposed_resource_type: "Observation",
  source_document_id: "doc-synthetic-11",
  source_document_version: 2,
  excerpt: "cannot recall the date",
  offset_start: 114,
  offset_end: 136,
  review_state: "proposed" as const,
};

const adapted = fromApiProposal(api, {
  revision: "offline-fixture-v1",
  inferenceMode: "offline_fixture",
});

check(
  "extracted fields are nested under `fact`",
  adapted.proposal.fact.concept === api.concept &&
    adapted.proposal.fact.value_text === api.value_text &&
    adapted.proposal.fact.excerpt === api.excerpt,
);
check(
  "metadata stays outside `fact`",
  adapted.proposal.source_document_id === api.source_document_id &&
    adapted.proposal.offset_start === api.offset_start,
);
check(
  "the source version is carried as an OPAQUE string, never a number",
  typeof adapted.proposal.source_document_version === "string" &&
    adapted.proposal.source_document_version === "2",
);
check(
  "offsets declare their unit",
  adapted.proposal.offset_unit === "unicode_code_points",
);

check(
  "fields the API cannot supply are null, not invented",
  adapted.proposal.source_sha256 === null &&
    adapted.proposal.fact.relationship === null &&
    adapted.proposal.version === null,
);
check(
  "and every one of them is named in `missing`",
  ["source_sha256", "issues", "relationship", "version"].every((f) =>
    adapted.missing.includes(f as never),
  ),
);
check(
  "an empty issues list is reported as unavailable, not as 'none found'",
  adapted.proposal.issues.length === 0 && adapted.missing.includes("issues"),
);

check(
  "an offline fixture is marked simulated",
  adapted.proposal.model?.simulated === true,
);
check(
  "a live inference mode would NOT be marked simulated",
  fromApiProposal(api, { revision: "r1", inferenceMode: "live" }).proposal.model
    ?.simulated === false,
);
check(
  "with no model identity the field is null rather than fabricated",
  fromApiProposal(api, null).proposal.model === null,
);

check(
  "null offsets survive the adapter as null",
  fromApiProposal(
    { ...api, offset_start: null, offset_end: null },
    null,
  ).proposal.offset_start === null,
);

/* ------------------------------------------------------------- issues */

check("no issues means nothing is blocked", !hasBlockingIssue([]));
check(
  "a review-severity issue does not block acceptance",
  !hasBlockingIssue([
    { code: "date_ambiguous", severity: "review", message: "Ambiguous date" },
  ]),
);
check(
  "a block-severity issue blocks acceptance",
  hasBlockingIssue([
    { code: "quote_mismatch", severity: "block", message: "Quote mismatch" },
  ]),
);
check(
  "one blocking issue among several still blocks",
  hasBlockingIssue([
    { code: "a", severity: "review", message: "x" },
    { code: "b", severity: "block", message: "y" },
  ]),
);

/* ------------------------------------------------------------- context */

check(
  "every completeness value has a label and a meaning",
  (["complete_in_checked_scope", "partial", "unknown"] as const).every((k) => {
    const d = COMPLETENESS_DISPLAY[k];
    return Boolean(d.label) && Boolean(d.meaning);
  }),
);
check(
  "'complete' is scoped to what was CHECKED, never to the record",
  /checked|outside that scope/i.test(
    COMPLETENESS_DISPLAY.complete_in_checked_scope.meaning,
  ),
);
check(
  "'unknown' forbids any statement about absence",
  /absent/i.test(COMPLETENESS_DISPLAY.unknown.meaning),
);
check(
  "all three retrieval tiers are labelled",
  Object.keys(TIER_LABELS).length === 3,
);

check(
  "the contract example is never exhaustive",
  ALFRED_CONTEXT_EXAMPLE.exhaustive === false,
);
check(
  "the contract example forbids absence claims",
  ALFRED_CONTEXT_EXAMPLE.absence_claims_allowed === false,
);
check(
  "the contract example carries a checked-scope notice",
  /checked scope/i.test(ALFRED_CONTEXT_EXAMPLE.notice),
);
check(
  "an unreviewed context item is marked unreviewed",
  ALFRED_CONTEXT_EXAMPLE.items[0].reviewed === false,
);
check(
  "an empty envelope is empty_unknown with unknown completeness",
  EMPTY_CONTEXT_EXAMPLE.state === "empty_unknown" &&
    EMPTY_CONTEXT_EXAMPLE.completeness === "unknown" &&
    EMPTY_CONTEXT_EXAMPLE.items.length === 0,
);

/* ------------------------------------------- both proposal shapes are read */

const nestedPayload = {
  id: "07bde3ac",
  version: 1,
  state: "proposed",
  source_document_id: "demo-note",
  source_document_version: "v1",
  source_sha256:
    "8d82b6080687b7d387989c4fc404c7d038d06ce0ec274617138b7e1c67e8d8f2",
  fact: {
    concept: "last_wcv",
    value_text: "The patient attended a well-child visit on 2026-09-01.",
    subject: "patient",
    assertion: "present",
    effective_date: "2026-09-01",
    excerpt: "The patient attended a well-child visit on 2026-09-01.",
    proposed_resource_type: "Observation",
    relationship: null,
  },
  offset_start: 0,
  offset_end: 54,
  offset_unit: "unicode_code_points",
  issues: [],
  model: {
    model_id: "google/medgemma-1.5-4b-it",
    model_revision: "simulated-fixture-v1",
    prompt_version: "extract-v1.0.1",
    simulated: true,
  },
};

const fromNested = normalizeProposal(nestedPayload);
check("the nested contract shape is detected", fromNested.shape === "nested");
check(
  "nested: fact fields are read from `fact`",
  fromNested.proposal.fact.concept === "last_wcv" &&
    fromNested.proposal.fact.effective_date === "2026-09-01",
);
check(
  "nested: version, source hash and issues are present, so nothing is missing",
  fromNested.proposal.version === 1 &&
    fromNested.proposal.source_sha256 !== null &&
    fromNested.missing.length === 0,
);
check(
  "nested: model identity survives",
  fromNested.proposal.model?.simulated === true,
);

const fromFlat = normalizeProposal(api);
check("the flat API shape is still detected", fromFlat.shape === "flat");
check(
  "flat: the same fields arrive, with absences named",
  fromFlat.proposal.fact.concept === api.concept &&
    fromFlat.missing.includes("version"),
);

/* --------------------------------------------------- review command safety */

const noVersion = buildReviewCommand({
  requestId: "r1",
  proposal: fromFlat.proposal,
  action: "accept",
  reviewerReference: "Practitioner/demo-reviewer",
  reason: "Verified against the note.",
  correction: null,
  acknowledgedIssues: [],
});
check(
  "a review command is REFUSED when the proposal has no version",
  !noVersion.ok && /will not invent one/i.test(noVersion.reason),
);

const good = buildReviewCommand({
  requestId: "r2",
  proposal: fromNested.proposal,
  action: "accept",
  reviewerReference: "Practitioner/demo-reviewer",
  reason: "Verified against the note.",
  correction: null,
  acknowledgedIssues: ["missing_date"],
});
check(
  "a versioned proposal produces a valid accept command",
  good.ok &&
    good.command.expected_proposal_version === 1 &&
    good.command.correction === null &&
    good.command.acknowledged_issues[0] === "missing_date",
);
check(
  "correct without a replacement fact is refused",
  !buildReviewCommand({
    requestId: "r3",
    proposal: fromNested.proposal,
    action: "correct",
    reviewerReference: "Practitioner/demo-reviewer",
    reason: "x",
    correction: null,
    acknowledgedIssues: [],
  }).ok,
);
check(
  "accept WITH a replacement fact is refused",
  !buildReviewCommand({
    requestId: "r4",
    proposal: fromNested.proposal,
    action: "accept",
    reviewerReference: "Practitioner/demo-reviewer",
    reason: "x",
    correction: fromNested.proposal.fact,
    acknowledgedIssues: [],
  }).ok,
);
check(
  "an empty reason is refused",
  !buildReviewCommand({
    requestId: "r5",
    proposal: fromNested.proposal,
    action: "reject",
    reviewerReference: "Practitioner/demo-reviewer",
    reason: "   ",
    correction: null,
    acknowledgedIssues: [],
  }).ok,
);

/* ------------------------------------------------- existence is not leaked */

for (const op of [
  "note_retrieve",
  "extraction_stream",
  "proposal_disclose",
  "fact_review",
] as const) {
  check(
    `${op}: 403 and 404 are indistinguishable to the user`,
    !leaksExistence(403, 404, op),
  );
}
check(
  "the shared 403/404 wording says why it is the same answer",
  /same whether the record does not exist or is outside your authorization/i.test(
    describeSecurityOutcome(404, "note_retrieve").body,
  ),
);
check(
  "a denied disclosure is marked an access outcome, not a clinical finding",
  /not a clinical finding/i.test(
    describeSecurityOutcome(403, "proposal_disclose").caveat ?? "",
  ),
);
check(
  "409 is stale and offers a non-destructive recovery",
  describeSecurityOutcome(409, "fact_review").state === "stale" &&
    /entries are kept/i.test(describeSecurityOutcome(409, "fact_review").action ?? ""),
);
check(
  "a failed extraction is never rendered as 'no care gap'",
  /not a finding of no care gap/i.test(
    describeSecurityOutcome(500, "extraction_stream").caveat ?? "",
  ),
);
check(
  "401 is a session problem, distinct from authorization",
  describeSecurityOutcome(401, "note_retrieve").state === "no_session",
);
check(
  "a transport failure states that nothing was changed",
  /nothing was changed/i.test(describeSecurityOutcome(0, "fact_review").body),
);

console.log(`\n${pass} passed, ${fail} failed`);
if (fail > 0) process.exit(1);
