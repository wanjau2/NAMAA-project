/**
 * Transition-rule checks for lib/case-actions.ts.
 *
 * Run: npm run verify:actions
 *
 * These are SOFTWARE checks on the local transition layer, not clinical
 * validation. They exist so that the safety rules in the work plan and design
 * specification are asserted rather than assumed — and so that when this layer
 * is replaced by Ismail's server at F4, the same scenarios can be pointed at
 * the real API.
 *
 * No test runner on purpose: Node 22 executes this directly via type stripping,
 * which keeps the sprint dependency list short.
 */

import {
  applyAction,
  type ActionRequest,
  type CaseState,
} from "../lib/case-actions.ts";

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

const base: CaseState = {
  id: "case-test", care_gap_id: "gap-test", patient_label: "Test (synthetic)",
  age_band: "2-4 years", pathway: "child_wcv", rule_id_version: "DEMO_WCV_01",
  flag_status: "gap", stage: "identified", disposition: "active",
  owner: "Coordinator 1", next_action: "x", due_time: null, overdue: false,
  revision: 1,
};
const NOW = "2026-11-17T10:00:00Z";
const req = (o: Partial<ActionRequest>): ActionRequest => ({
  action: "approve_pathway", expected_revision: 1,
  request_id: "11111111-2222-3333-4444-555555555555", data: {}, ...o,
});

// --- role boundary ---
let r = applyAction(base, req({ data: { attestation: true } }), "coordinator", NOW);
check("coordinator cannot approve a pathway", !r.ok && r.error.code === "forbidden_role");

// --- needs_review blocks approval ---
r = applyAction({ ...base, flag_status: "needs_review" },
  req({ data: { attestation: true } }), "clinical_reviewer", NOW);
check("needs_review blocks pathway approval", !r.ok && r.error.code === "precondition_failed");

// --- attestation is required ---
r = applyAction(base, req({ data: {} }), "clinical_reviewer", NOW);
check("approval requires attestation", !r.ok && r.error.code === "validation_failed"
  && Boolean(r.error.field_errors.attestation));

// --- happy approval ---
r = applyAction(base, req({ data: { attestation: true } }), "clinical_reviewer", NOW);
check("reviewer approves: identified -> reviewed, rev+1",
  r.ok && r.next.stage === "reviewed" && r.next.revision === 2);
const reviewed = r.ok ? r.next : base;

// --- stale revision ---
r = applyAction(reviewed, req({ action: "send_invitation", expected_revision: 1,
  data: { template: "wcv_invite_v1" } }), "coordinator", NOW);
check("stale expected_revision is rejected", !r.ok && r.error.code === "stale_revision");

// --- invitation needs a recorded preference ---
r = applyAction(reviewed, req({ action: "send_invitation", expected_revision: 2,
  data: { template: "wcv_invite_v1" } }), "coordinator", NOW);
check("invitation blocked without contact preference",
  !r.ok && r.error.code === "precondition_failed");

// --- record preference, then invite ---
r = applyAction(reviewed, req({ action: "record_contact_preference", expected_revision: 2,
  data: { channel: "sms", language: "en", preferred_time: "afternoon" } }), "coordinator", NOW);
check("contact preference recorded", r.ok && Boolean(r.next.contact_preference));
const withPref = r.ok ? r.next : reviewed;

r = applyAction(withPref, req({ action: "send_invitation", expected_revision: 3,
  data: { template: "wcv_invite_v1" } }), "coordinator", NOW);
check("invitation sent: reviewed -> invited", r.ok && r.next.stage === "invited");
const invited = r.ok ? r.next : withPref;

// --- decline keeps the stage and never completes ---
r = applyAction(invited, req({ action: "record_decline", expected_revision: 4,
  data: { reason: "Declined by caregiver" } }), "coordinator", NOW);
check("decline sets disposition only, stage unchanged",
  r.ok && r.next.disposition === "declined" && r.next.stage === "invited");
check("decline is never relabelled completed", r.ok && r.next.disposition !== "completed");

// --- booking -> attendance ---
r = applyAction(invited, req({ action: "book_appointment", expected_revision: 4,
  data: { appointment_time: "2026-11-20", location: "Clinic A (synthetic)" } }), "coordinator", NOW);
check("booking: invited -> booked", r.ok && r.next.stage === "booked");
const booked = r.ok ? r.next : invited;

r = applyAction(booked, req({ action: "close_as_completed", expected_revision: 5,
  data: { evidence_type: "Encounter", evidence_reference: "Encounter/e1", attestation: true } }),
  "clinical_reviewer", NOW);
check("booking alone cannot close as completed",
  !r.ok && r.error.code === "invalid_transition");

r = applyAction(booked, req({ action: "record_attendance", expected_revision: 5,
  data: { attended: "did_not_attend" } }), "coordinator", NOW);
check("did-not-attend does not advance the stage", r.ok && r.next.stage === "booked");

r = applyAction(booked, req({ action: "record_attendance", expected_revision: 5,
  data: { attended: "attended" } }), "coordinator", NOW);
check("attendance: booked -> attended", r.ok && r.next.stage === "attended");
const attended = r.ok ? r.next : booked;

// --- closure requires evidence ---
r = applyAction(attended, req({ action: "close_as_completed", expected_revision: 6,
  data: { evidence_type: "Encounter", attestation: true } }), "clinical_reviewer", NOW);
check("closure without an evidence reference fails validation",
  !r.ok && r.error.code === "validation_failed"
  && Boolean(r.error.field_errors.evidence_reference));

r = applyAction(attended, req({ action: "close_as_completed", expected_revision: 6,
  data: { evidence_type: "Encounter", evidence_reference: "Encounter/enc-1" } }),
  "clinical_reviewer", NOW);
check("closure without reviewer attestation fails validation",
  !r.ok && Boolean(r.error.field_errors.attestation));

r = applyAction(attended, req({ action: "close_as_completed", expected_revision: 6,
  data: { evidence_type: "Procedure", evidence_reference: "Procedure/proc-1", attestation: true } }),
  "clinical_reviewer", NOW);
check("closure with evidence + attestation completes",
  r.ok && r.next.stage === "closed" && r.next.disposition === "completed"
  && r.next.completion_evidence?.evidence_reference === "Procedure/proc-1");
check("completion records an evidence reference on the event",
  r.ok && r.event.evidence_reference === "Procedure/proc-1");

// --- coordinator cannot authorize clinical closure ---
r = applyAction(attended, req({ action: "close_as_completed", expected_revision: 6,
  data: { evidence_type: "Procedure", evidence_reference: "Procedure/p", attestation: true } }),
  "coordinator", NOW);
check("coordinator cannot authorize clinical closure",
  !r.ok && r.error.code === "forbidden_role");

// --- other closure must not count as completed ---
r = applyAction(attended, req({ action: "close_other", expected_revision: 6,
  data: { reason: "Moved out of area (synthetic)" } }), "clinical_reviewer", NOW);
check("close_other closes without completing",
  r.ok && r.next.stage === "closed" && r.next.disposition === "clinically_closed_other");
const closedOther = r.ok ? r.next : attended;

// --- reopen requires a reason ---
r = applyAction(closedOther, req({ action: "reopen", expected_revision: 7, data: {} }),
  "clinical_reviewer", NOW);
check("reopen requires a reason", !r.ok && Boolean(r.error.field_errors.reason));

r = applyAction(closedOther, req({ action: "reopen", expected_revision: 7,
  data: { reason: "New information received" } }), "clinical_reviewer", NOW);
check("reopen returns the case to follow-up and active",
  r.ok && r.next.stage === "follow_up" && r.next.disposition === "active");

// --- referral rejection keeps it owned and escalated ---
r = applyAction(attended, req({ action: "record_referral_outcome", expected_revision: 6,
  data: { outcome: "rejected", reason: "Capacity unavailable" } }), "coordinator", NOW);
check("rejected referral stays open, owned and overdue",
  r.ok && r.next.stage === "follow_up" && r.next.overdue === true
  && r.next.disposition === "active" && r.next.owner === attended.owner);
const rejected = r.ok ? r.next : attended;

r = applyAction(rejected, req({ action: "close_as_completed", expected_revision: 7,
  data: { evidence_type: "Encounter", evidence_reference: "Encounter/e", attestation: true } }),
  "clinical_reviewer", NOW);
check("rejected referral blocks completion until reassigned",
  !r.ok && r.error.code === "precondition_failed");

// --- deferral retains a recall date ---
r = applyAction(invited, req({ action: "defer_with_recall", expected_revision: 4,
  data: { recall_date: "2027-02-01", reason: "Family travelling" } }), "coordinator", NOW);
check("deferral retains a recall date and is not a completion",
  r.ok && r.next.disposition === "deferred" && r.next.recall_date === "2027-02-01");

// --- every event carries prior/new state and the request id ---
r = applyAction(base, req({ data: { attestation: true } }), "clinical_reviewer", NOW);
check("event records prior -> new state and request id",
  r.ok && r.event.prior_state === "identified/active"
  && r.event.new_state === "reviewed/active"
  && r.event.request_id === "11111111-2222-3333-4444-555555555555");

console.log(`\n${pass} passed, ${fail} failed`);
if (fail > 0) process.exit(1);
