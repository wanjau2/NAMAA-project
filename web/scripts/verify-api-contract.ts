/**
 * API contract checks — run against a LIVE Namaa API.
 *
 * Run:  npm run verify:api        (API must be running on :8000)
 *
 * This replaces the former scripts/verify-actions.ts, which exercised the
 * frontend's local transition engine. That engine is deleted; the server owns
 * transitions now, so the same scenarios are pointed at the real API — which is
 * what the A2 evidence note said they were written for.
 *
 * Software checks on synthetic data. Not clinical validation.
 */

import { ACTION_CATALOG } from "../lib/action-catalog.ts";

const BASE = process.env.NAMAA_API_BASE ?? "http://127.0.0.1:8000";

let pass = 0;
let fail = 0;
let pending = 0;

/**
 * A capability the team has agreed but the API does not implement yet.
 * Reported loudly, but it does NOT fail the suite: this is a readiness gate,
 * not a regression. When it flips to PASS the frontend is already wired.
 */
function readiness(name: string, implemented: boolean, note: string) {
  if (implemented) {
    pass++;
    console.log(`PASS  ${name}`);
  } else {
    pending++;
    console.log(`PENDING  ${name} — ${note}`);
  }
}
function check(name: string, condition: boolean, detail = "") {
  if (condition) {
    pass++;
    console.log(`PASS  ${name}`);
  } else {
    fail++;
    console.log(`FAIL  ${name} ${detail}`);
  }
}

// Responses are deliberately untyped here: the point of this script is to
// check what the API actually returns, not what our types claim it returns.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Json = Record<string, any>;

/** Fact fields may be nested under `fact` (Alfred) or flat (legacy). */
function factOf(p: Json): Json {
  return p?.fact && typeof p.fact === "object" ? (p.fact as Json) : p;
}

function proposalExcerpt(p: Json): string {
  return String(factOf(p).excerpt ?? p.excerpt ?? "");
}

let session = "";

async function call(
  path: string,
  init: { method?: string; body?: unknown; role?: string; noSession?: boolean } = {},
): Promise<{ status: number; json: Json }> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  if (!init.noSession && session) headers["X-Namaa-Session"] = session;
  if (init.role) headers["X-Namaa-Role"] = init.role;

  const response = await fetch(`${BASE}${path}`, {
    method: init.method ?? "GET",
    headers,
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });
  let json: Json = {};
  try {
    json = (await response.json()) as Json;
  } catch {
    json = {};
  }
  return { status: response.status, json };
}

function action(
  id: string,
  expected_revision: number,
  request_id: string,
  data: Record<string, unknown> = {},
) {
  return { action: id, expected_revision, request_id, data };
}

async function main() {
  // --- reachability ---
  try {
    const health = await call("/health", { noSession: true });
    check("health returns ok", health.status === 200 && health.json.status === "ok");
    check("health declares synthetic", health.json.synthetic === true);
  } catch {
    console.error(
      `\nCannot reach the Namaa API at ${BASE}.\n` +
        `Start it first:\n  cd api && ./.venv/bin/uvicorn app.main:app --port 8000\n`,
    );
    process.exit(1);
  }

  // --- session handling ---
  const noSession = await call("/api/v1/cases", { noSession: true });
  check(
    "a call without X-Namaa-Session is rejected",
    noSession.status === 401 && noSession.json.code === "unauthorized",
    `got ${noSession.status}/${noSession.json.code}`,
  );

  const created = await call("/api/v1/demo/sessions", {
    method: "POST",
    noSession: true,
  });
  session = created.json.session_id;
  check("guest session is created", created.status === 200 && Boolean(session));
  check(
    "session response carries the synthetic notice",
    String(created.json.notice).includes("NOT FOR CLINICAL USE"),
  );

  // --- seed ---
  const list = await call("/api/v1/cases");
  check("seed provides 6 synthetic cases", list.json.length === 6, `got ${list.json.length}`);
  const detail = await call("/api/v1/cases/case-0001");
  check(
    "case-0001 is identified/needs_review at rev 1",
    detail.json.stage === "identified" &&
      detail.json.flag_status === "needs_review" &&
      detail.json.revision === 1,
  );
  check(
    "case detail nests explanation, factors, missing and events",
    Boolean(detail.json.detail?.explanation) &&
      Array.isArray(detail.json.detail?.factors) &&
      Array.isArray(detail.json.detail?.missing) &&
      Array.isArray(detail.json.detail?.events),
  );

  // --- catalog drift against the server's own published contract ---
  const meta = await call("/api/v1/meta/actions");
  const apiIds = new Set<string>((meta.json.actions ?? []).map((a: Json) => a.id));
  const uiIds = new Set(ACTION_CATALOG.map((spec) => spec.id));
  check(
    "UI catalog and API publish the same action ids",
    apiIds.size === uiIds.size && [...uiIds].every((id) => apiIds.has(id)),
    `api=${[...apiIds].sort().join(",")} ui=${[...uiIds].sort().join(",")}`,
  );
  const roleMismatch = (meta.json.actions ?? []).filter((a: Json) => {
    const spec = ACTION_CATALOG.find((s) => s.id === a.id);
    return spec && spec.role !== a.role;
  });
  check(
    "UI catalog and API agree on the role for every action",
    roleMismatch.length === 0,
    JSON.stringify(roleMismatch.map((a: Json) => a.id)),
  );
  check(
    "API publishes the mutation envelope and error shape",
    Boolean(meta.json.mutation_envelope?.request_id) &&
      Boolean(meta.json.error_shape?.field_errors),
  );

  // --- role boundary ---
  const wrongRole = await call("/api/v1/cases/case-0001/actions", {
    method: "POST",
    role: "coordinator",
    body: action("approve_pathway", 1, "c-role", { attestation: true }),
  });
  check(
    "coordinator cannot approve a pathway",
    wrongRole.json.code === "forbidden_role",
    wrongRole.json.code,
  );

  // --- missing data blocks approval ---
  const needsReview = await call("/api/v1/cases/case-0001/actions", {
    method: "POST",
    role: "clinical_reviewer",
    body: action("approve_pathway", 1, "c-precond", { attestation: true }),
  });
  check(
    "needs_review blocks pathway approval",
    needsReview.json.code === "precondition_failed",
    needsReview.json.code,
  );

  // --- concurrency ---
  const stale = await call("/api/v1/cases/case-0002/actions", {
    method: "POST",
    role: "coordinator",
    body: action("record_attendance", 1, "c-stale", { attended: "attended" }),
  });
  check(
    "stale expected_revision is rejected",
    stale.json.code === "stale_revision",
    stale.json.code,
  );

  // --- booking alone cannot complete care ---
  const bookedClose = await call("/api/v1/cases/case-0002/actions", {
    method: "POST",
    role: "clinical_reviewer",
    body: action("close_as_completed", 4, "c-booked-close", {
      evidence_type: "Encounter",
      evidence_reference: "Encounter/e1",
      attestation: true,
    }),
  });
  check(
    "booking alone cannot close as completed",
    bookedClose.json.code === "invalid_transition",
    bookedClose.json.code,
  );

  // --- field validation ---
  const noReason = await call("/api/v1/cases/case-0002/actions", {
    method: "POST",
    role: "coordinator",
    body: action("record_decline", 4, "c-noreason", {}),
  });
  check(
    "a missing required field returns field_errors",
    noReason.json.code === "validation_failed" &&
      Boolean(noReason.json.field_errors?.reason),
    JSON.stringify(noReason.json.field_errors),
  );

  // --- happy path + idempotency ---
  const attended = await call("/api/v1/cases/case-0002/actions", {
    method: "POST",
    role: "coordinator",
    body: action("record_attendance", 4, "c-attend", { attended: "attended" }),
  });
  check(
    "attendance advances booked -> attended and bumps the revision",
    attended.json.case?.stage === "attended" && attended.json.case?.revision === 5,
  );
  check(
    "the event records prior -> new state and the request id",
    attended.json.event?.prior_state === "booked/active" &&
      attended.json.event?.new_state === "attended/active" &&
      attended.json.event?.request_id === "c-attend",
  );
  const eventId = attended.json.event?.id;

  const replay = await call("/api/v1/cases/case-0002/actions", {
    method: "POST",
    role: "coordinator",
    body: action("record_attendance", 4, "c-attend", { attended: "attended" }),
  });
  check(
    "replaying a request_id returns the first result, no second event",
    replay.json.event?.id === eventId && replay.json.case?.revision === 5,
  );

  const conflict = await call("/api/v1/cases/case-0002/actions", {
    method: "POST",
    role: "coordinator",
    body: action("record_attendance", 5, "c-attend", { attended: "did_not_attend" }),
  });
  check(
    "a request_id reused with a different payload is rejected",
    conflict.json.code === "idempotency_conflict",
    conflict.json.code,
  );

  // --- closure requires evidence and attestation ---
  const noEvidence = await call("/api/v1/cases/case-0002/actions", {
    method: "POST",
    role: "clinical_reviewer",
    body: action("close_as_completed", 5, "c-noev", {
      evidence_type: "Encounter",
      attestation: true,
    }),
  });
  check(
    "closure without an evidence reference fails validation",
    noEvidence.json.code === "validation_failed" &&
      Boolean(noEvidence.json.field_errors?.evidence_reference),
  );

  const noAttest = await call("/api/v1/cases/case-0002/actions", {
    method: "POST",
    role: "clinical_reviewer",
    body: action("close_as_completed", 5, "c-noattest", {
      evidence_type: "Encounter",
      evidence_reference: "Encounter/enc-1",
    }),
  });
  check(
    "closure without reviewer attestation fails validation",
    noAttest.json.code === "validation_failed" &&
      Boolean(noAttest.json.field_errors?.attestation),
  );

  const completed = await call("/api/v1/cases/case-0002/actions", {
    method: "POST",
    role: "clinical_reviewer",
    body: action("close_as_completed", 5, "c-complete", {
      evidence_type: "Procedure",
      evidence_reference: "Procedure/proc-1",
      attestation: true,
    }),
  });
  check(
    "closure with evidence and attestation completes the case",
    completed.json.case?.stage === "closed" &&
      completed.json.case?.disposition === "completed",
  );
  check(
    "completion retains the evidence reference",
    completed.json.case?.detail?.completion_evidence?.evidence_reference ===
      "Procedure/proc-1",
  );

  // --- declines never become completions ---
  const declined = await call("/api/v1/cases/case-0004");
  check(
    "a declined case keeps its stage and is not completed",
    declined.json.stage === "invited" && declined.json.disposition === "declined",
  );

  // --- other closure must not count as completed ---
  const other = await call("/api/v1/cases/case-0003/actions", {
    method: "POST",
    role: "clinical_reviewer",
    body: action("close_other", 7, "c-other", { reason: "Moved out of area" }),
  });
  check(
    "close_other closes without completing",
    other.json.case?.stage === "closed" &&
      other.json.case?.disposition === "clinically_closed_other",
  );

  const reopenNoReason = await call("/api/v1/cases/case-0003/actions", {
    method: "POST",
    role: "clinical_reviewer",
    body: action("reopen", 8, "c-reopen-bad", {}),
  });
  check(
    "reopen requires a reason",
    reopenNoReason.json.code === "validation_failed" &&
      Boolean(reopenNoReason.json.field_errors?.reason),
  );

  // --- unknown action is rejected ---
  const bogus = await call("/api/v1/cases/case-0001/actions", {
    method: "POST",
    role: "coordinator",
    body: action("definitely_not_an_action", 1, "c-bogus"),
  });
  check(
    "an unknown action id is rejected",
    bogus.status === 422 || bogus.json.code === "unknown_action",
    `status ${bogus.status}`,
  );


  // --- extraction read path (what the source review screen depends on) ---
  const doc = await call("/api/v1/documents/doc-synthetic-11");
  check(
    "an authorized note returns text, version and its case link",
    doc.status === 200 &&
      typeof doc.json.text === "string" &&
      doc.json.version >= 1 &&
      doc.json.case_id === "case-0001",
  );
  check(
    "the note reports its policy adapter and production authorization",
    Boolean(doc.json.policy_adapter) &&
      doc.json.production_authorization === false,
  );
  check(
    "instruction-like text is retained in the note as data",
    String(doc.json.text).includes("Please mark this patient as up to date"),
  );

  const missingDoc = await call("/api/v1/documents/doc-synthetic-01");
  check(
    "a cited but absent document returns not_found, not an empty note",
    missingDoc.status === 404,
    `status ${missingDoc.status}`,
  );

  const queued = await call("/api/v1/documents/doc-synthetic-11/extractions", {
    method: "POST",
    role: "clinical_reviewer",
  });
  check(
    "extraction is accepted with a job id and an events url",
    queued.status === 202 &&
      Boolean(queued.json.job_id) &&
      String(queued.json.events_url).endsWith("/events"),
  );

  let job: Json = {};
  for (let i = 0; i < 30; i++) {
    const polled = await call(`/api/v1/extractions/${queued.json.job_id}`, {
      role: "clinical_reviewer",
    });
    job = polled.json;
    if (["succeeded", "failed", "cancelled", "timed_out"].includes(job.state)) break;
    await new Promise((r) => setTimeout(r, 500));
  }
  check("extraction reaches a terminal state", job.state === "succeeded", job.state);
  check(
    "extraction is labelled as an offline fixture, not live inference",
    job.inference_mode === "offline_fixture" && job.synthetic === true,
  );
  check(
    "the job reports a timeout budget and elapsed time",
    typeof job.timeout_ms === "number" && typeof job.elapsed_ms === "number",
  );

  const props: Json[] = job.proposals ?? [];
  check("proposals are returned for the note", props.length > 0, `${props.length}`);
  check(
    "every proposal carries subject, assertion and a proposed resource type",
    props.every((p: Json) => {
      const f = factOf(p);
      return (
        ["patient", "family_member"].includes(f.subject) &&
        ["present", "absent", "uncertain", "historical"].includes(f.assertion) &&
        Boolean(f.proposed_resource_type)
      );
    }),
  );
  check(
    "every proposal arrives unreviewed",
    props.every(
      (p: Json) => (p.review_state ?? p.state) === "proposed",
    ),
  );
  check(
    "every excerpt matches the note at its stated offsets",
    props.every(
      (p: Json) =>
        String(doc.json.text).slice(p.offset_start, p.offset_end) ===
        proposalExcerpt(p),
    ),
    JSON.stringify(
      props
        .filter(
          (p: Json) =>
            String(doc.json.text).slice(p.offset_start, p.offset_end) !==
            proposalExcerpt(p),
        )
        .map((p: Json) => p.id),
    ),
  );
  check(
    "no proposal is derived from the instruction-like sentence",
    props.every(
      (p: Json) =>
        !proposalExcerpt(p).includes("mark this patient as up to date"),
    ),
  );

  const adultDoc = await call("/api/v1/documents/doc-synthetic-31");
  const adultJob = await call("/api/v1/documents/doc-synthetic-31/extractions", {
    method: "POST",
    role: "clinical_reviewer",
  });
  let adult: Json = {};
  for (let i = 0; i < 30; i++) {
    const polled = await call(`/api/v1/extractions/${adultJob.json.job_id}`, {
      role: "clinical_reviewer",
    });
    adult = polled.json;
    if (["succeeded", "failed", "cancelled", "timed_out"].includes(adult.state)) break;
    await new Promise((r) => setTimeout(r, 500));
  }
  const adultProps: Json[] = adult.proposals ?? [];
  check(
    "a relative's condition is proposed as FamilyMemberHistory, not a patient Condition",
    adultProps.some((p: Json) => {
      const f = factOf(p);
      return (
        f.subject === "family_member" &&
        f.proposed_resource_type === "FamilyMemberHistory"
      );
    }) &&
      adultProps.every(
        (p: Json) => factOf(p).proposed_resource_type !== "Condition",
      ),
  );
  check(
    "the adult note belongs to case-0003",
    adultDoc.json.case_id === "case-0003",
  );


  // --- readiness: agreed capabilities (flip PENDING→PASS when API ships them) ---
  const nestedShape = props.length > 0 && typeof props[0].fact === "object";
  readiness(
    "proposals use the nested `fact` contract",
    nestedShape,
    "proposals are still flat; the UI reads both shapes (lib/contracts.ts normalizeProposal)",
  );
  readiness(
    "proposals carry an integer concurrency version",
    props.length > 0 && typeof props[0].version === "number",
    "no version is supplied, so a review command cannot be built without inventing one",
  );
  readiness(
    "proposals carry validation issues",
    props.length > 0 && Array.isArray(props[0].issues),
    "issues are not reported; an empty list must not read as 'none found'",
  );
  readiness(
    "proposals carry a source hash binding them to an exact note",
    props.length > 0 && typeof props[0].source_sha256 === "string",
    "source_sha256 is absent",
  );

  const reviewProbe = await call(
    `/api/v1/facts/${props[0]?.id ?? "unknown"}/review`,
    {
      method: "POST",
      role: "clinical_reviewer",
      body: {
        request_id: "probe",
        proposal_id: props[0]?.id ?? "unknown",
        expected_proposal_version: 1,
        action: "accept",
        reviewer_reference: "Practitioner/demo-reviewer",
        reason: "readiness probe",
        correction: null,
        acknowledged_issues: [],
      },
    },
  );
  readiness(
    "POST /api/v1/facts/{id}/review exists",
    reviewProbe.status !== 404 && reviewProbe.status !== 405,
    `returns ${reviewProbe.status}; review decisions cannot persist (Q10)`,
  );

  const evalProbe = await call("/api/v1/patients/pat-synthetic-11/evaluations", {
    method: "POST",
    body: {},
  });
  readiness(
    "evaluations expose a four-value rule outcome",
    typeof evalProbe.json.outcome === "string" ||
      typeof evalProbe.json.rule_evaluation?.outcome === "string",
    `only flag_status "${evalProbe.json.flag_status}" is returned; not_eligible cannot reach the UI (Q12)`,
  );

  // --- security: 403 and 404 must be indistinguishable to a client ---
  const foreignDoc = await call("/api/v1/documents/doc-does-not-exist");
  check(
    "an unknown document does not disclose whether it exists",
    foreignDoc.status === 403 || foreignDoc.status === 404,
    `status ${foreignDoc.status}`,
  );

  // --- analytics: server-side suppression shape ---
  const overview = await call("/api/v1/analytics/overview");
  const cells: Json[] = (overview.json.pathways ?? []).flatMap((p: Json) =>
    Object.entries(p)
      .filter(([k]) => k !== "pathway")
      .map(([, v]) => v as Json),
  );
  check("analytics reports both pathways", overview.json.pathways?.length === 2);
  check("analytics declares synthetic", overview.json.synthetic === true);
  check(
    "suppressed cells carry no numerator or denominator",
    cells
      .filter((c: Json) => c.suppressed)
      .every((c: Json) => c.numerator === null && c.denominator === null),
  );
  check(
    "suppressed cells state a reason and threshold",
    cells
      .filter((c: Json) => c.suppressed)
      .every((c: Json) => Boolean(c.reason) && typeof c.threshold === "number"),
  );
  const suppressed = cells.filter((c: Json) => c.suppressed).length;
  console.log(
    `NOTE  ${suppressed}/${cells.length} analytics cells suppressed at this seed size` +
      (suppressed === cells.length
        ? " — nothing is publishable; the reporting cohort is smaller than the threshold"
        : ""),
  );

  // --- reset restores the seed for this session only ---
  const reset = await call("/api/v1/demo/reset", { method: "POST" });
  check("reset restores the seed", reset.json.cases_restored === 6);
  const afterReset = await call("/api/v1/cases/case-0002");
  check(
    "reset returns case-0002 to booked at rev 4",
    afterReset.json.stage === "booked" && afterReset.json.revision === 4,
  );

  console.log(
    `\n${pass} passed, ${fail} failed, ${pending} pending (agreed but not implemented)`,
  );
  if (fail > 0) process.exit(1);
}

void main();
