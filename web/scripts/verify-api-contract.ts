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
import { sliceCodePoints } from "../lib/text-offsets.ts";

const BASE = process.env.NAMAA_API_BASE ?? "http://127.0.0.1:8000";

const CANONICAL_OUTCOMES = [
  "gap_identified",
  "no_gap_identified_in_available_data",
  "needs_review",
  "not_eligible",
] as const;

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
  init: {
    method?: string;
    body?: unknown;
    role?: string;
    noSession?: boolean;
    omitRole?: boolean;
    session?: string;
  } = {},
): Promise<{ status: number; json: Json }> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  const sid = init.session ?? session;
  if (!init.noSession && sid) headers["X-Namaa-Session"] = sid;
  if (init.role) headers["X-Namaa-Role"] = init.role;
  else if (!init.noSession && sid && init.omitRole !== true) {
    headers["X-Namaa-Role"] = "coordinator";
  }

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

function issueCodes(p: Json): string[] {
  return (Array.isArray(p.issues) ? p.issues : []).map((i: Json) =>
    String(i.code),
  );
}

function excerptMatchesNote(note: string, p: Json): boolean {
  const start = p.offset_start;
  const end = p.offset_end;
  if (typeof start !== "number" || typeof end !== "number") return false;
  return sliceCodePoints(note, start, end) === proposalExcerpt(p);
}

function nestedFact(p: Json): Json | null {
  return p?.fact && typeof p.fact === "object" ? (p.fact as Json) : null;
}

function reviewBody(
  proposal: Json,
  action: "accept" | "correct" | "reject",
  extra: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    request_id: extra.request_id ?? `rev-${action}-${proposal.id}`,
    proposal_id: proposal.id,
    expected_proposal_version: extra.expected_proposal_version ?? proposal.version,
    action,
    reviewer_reference: "Practitioner/demo-reviewer",
    reason:
      extra.reason ??
      "Synthetic reviewer decision for the API contract check.",
    correction: extra.correction ?? null,
    acknowledged_issues: extra.acknowledged_issues ?? issueCodes(proposal),
  };
}

async function readSseTerminal(jobId: string, sid: string): Promise<Json | null> {
  const url =
    `${BASE}/api/v1/extractions/${encodeURIComponent(jobId)}/events` +
    `?session=${encodeURIComponent(sid)}&role=clinical_reviewer`;
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), 20_000);
  try {
    const res = await fetch(url, {
      headers: {
        Accept: "text/event-stream",
        "X-Namaa-Session": sid,
        "X-Namaa-Role": "clinical_reviewer",
      },
      signal: ac.signal,
    });
    if (!res.ok || !res.body) return { __http: res.status };
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop() ?? "";
      for (const block of parts) {
        const dataLine = block
          .split("\n")
          .find((line) => line.startsWith("data:"));
        if (!dataLine) continue;
        let payload: Json = {};
        try {
          payload = JSON.parse(dataLine.slice(5).trim()) as Json;
        } catch {
          return { __malformed: true, raw: dataLine };
        }
        if (
          ["succeeded", "failed", "cancelled", "timed_out"].includes(
            payload.state,
          )
        ) {
          return payload;
        }
      }
    }
    return null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
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
  const isolated = await call("/api/v1/demo/sessions", {
    method: "POST",
    noSession: true,
  });
  const session2 = String(isolated.json.session_id ?? "");
  check(
    "a second guest session is created for isolation checks",
    isolated.status === 200 && Boolean(session2) && session2 !== session,
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
  check(
    "case detail publishes available_actions from the server",
    Array.isArray(detail.json.available_actions) &&
      detail.json.available_actions.every(
        (a: Json) => typeof a.id === "string" && typeof a.permitted_role === "string",
      ),
  );
  const listedDocs = await call("/api/v1/cases/case-0001/documents");
  check(
    "case-0001 document listing is authoritative (no client fallback map)",
    listedDocs.status === 200 &&
      Array.isArray(listedDocs.json) &&
      listedDocs.json.some((d: Json) => d.id === "doc-synthetic-11"),
    `status ${listedDocs.status}`,
  );
  const booked = await call("/api/v1/cases/case-0002");
  const available = new Set(
    (booked.json.available_actions ?? []).map((a: Json) => a.id),
  );
  check(
    "case-0002 publishes record_attendance in available_actions",
    available.has("record_attendance") && !available.has("book_appointment"),
    `got ${[...available].join(",")}`,
  );
  const audit = await call("/api/v1/audit/events");
  check(
    "coordinator can list audit events",
    audit.status === 200 && Array.isArray(audit.json),
    `status ${audit.status}`,
  );
  const outbox = await call("/api/v1/ops/outbox");
  check(
    "coordinator can list the stub FHIR outbox",
    outbox.status === 200 && Array.isArray(outbox.json),
    `status ${outbox.status}`,
  );
  const reviewerOutbox = await call("/api/v1/ops/outbox", {
    role: "clinical_reviewer",
  });
  check(
    "clinical reviewer is denied outbox.read",
    reviewerOutbox.status === 403,
    `status ${reviewerOutbox.status}`,
  );
  const reviewerAudit = await call("/api/v1/audit/events", {
    role: "clinical_reviewer",
  });
  check(
    "clinical reviewer can list audit events",
    reviewerAudit.status === 200 && Array.isArray(reviewerAudit.json),
    `status ${reviewerAudit.status}`,
  );
  const noRole = await call("/api/v1/cases", { omitRole: true });
  check(
    "a call without X-Namaa-Role is rejected",
    noRole.status === 400 && noRole.json.code === "invalid_role",
    `got ${noRole.status}/${noRole.json.code}`,
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
      evidence_type: "Encounter",
      evidence_reference: "Encounter/enc-synthetic-02",
      attestation: true,
    }),
  });
  check(
    "closure with evidence queues outbox completion (not an immediate close)",
    completed.status === 200 &&
      completed.json.case?.stage === "attended" &&
      completed.json.case?.completion_status === "pending" &&
      completed.json.case?.detail?.completion_evidence?.evidence_reference ===
        "Encounter/enc-synthetic-02",
    `${completed.status}/${completed.json.case?.stage}/${completed.json.case?.completion_status}/${completed.json.code}`,
  );
  let closedCase: Json = completed.json.case ?? {};
  for (let i = 0; i < 20; i++) {
    if (
      closedCase.stage === "closed" &&
      closedCase.disposition === "completed"
    ) {
      break;
    }
    await new Promise((r) => setTimeout(r, 250));
    closedCase = (await call("/api/v1/cases/case-0002")).json;
  }
  check(
    "outbox commit closes the case as completed",
    closedCase.stage === "closed" &&
      closedCase.disposition === "completed" &&
      closedCase.completion_status === "committed",
    `${closedCase.stage}/${closedCase.disposition}/${closedCase.completion_status}`,
  );
  check(
    "completion retains the evidence reference",
    closedCase.detail?.completion_evidence?.evidence_reference ===
      "Encounter/enc-synthetic-02",
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

  const listedNote = await call("/api/v1/documents/doc-synthetic-01");
  check(
    "the cited case-0002 note is a real document, not an empty 404",
    listedNote.status === 200 &&
      listedNote.json.case_id === "case-0002" &&
      typeof listedNote.json.text === "string" &&
      listedNote.json.text.length > 0,
    `status ${listedNote.status}`,
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
  const sse = await readSseTerminal(String(queued.json.job_id), session);
  const sseProps: Json[] = Array.isArray(sse?.proposals) ? sse.proposals : [];
  check(
    "SSE terminal event carries nested proposals",
    Boolean(sse) &&
      sse?.__malformed !== true &&
      sse?.state === "succeeded" &&
      sseProps.length > 0 &&
      sseProps.every((p: Json) => nestedFact(p) !== null),
    sse?.__malformed
      ? "malformed SSE frame"
      : `state=${sse?.state} n=${sseProps.length}`,
  );
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
  const noteText = String(doc.json.text);
  check(
    "every excerpt matches the note at Unicode code-point offsets",
    props.every((p: Json) => excerptMatchesNote(noteText, p)),
    JSON.stringify(
      props.filter((p: Json) => !excerptMatchesNote(noteText, p)).map((p: Json) => p.id),
    ),
  );
  const astral = "A😀B";
  check(
    "code-point slice diverges from UTF-16 String.slice on an astral character",
    sliceCodePoints(astral, 1, 2) === "😀" && astral.slice(1, 2) !== "😀",
    `cp=${sliceCodePoints(astral, 1, 2)} utf16=${astral.slice(1, 2)}`,
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

  // --- nested proposal contract (required, not a readiness probe) ---
  check(
    "proposals use the nested `fact` contract",
    props.length > 0 && nestedFact(props[0]) !== null,
    props[0] ? "fact missing" : "no proposals",
  );
  check(
    "proposals carry an integer concurrency version",
    props.length > 0 && typeof props[0].version === "number",
  );
  check(
    "proposals carry validation issues as an array (empty is not 'none found')",
    props.length > 0 && Array.isArray(props[0].issues),
  );
  check(
    "proposals carry a source hash binding them to an exact note",
    props.length > 0 &&
      typeof props[0].source_sha256 === "string" &&
      /^[a-f0-9]{64}$/.test(String(props[0].source_sha256)),
  );
  check(
    "malformed nested proposals fail the suite rather than a readiness gate",
    props.every(
      (p: Json) =>
        nestedFact(p) !== null &&
        typeof p.version === "number" &&
        Array.isArray(p.issues) &&
        typeof p.source_sha256 === "string",
    ),
  );

  const first = props[0];
  const second = props[1];
  const firstIssues = issueCodes(first);
  check(
    "at least one child proposal carries a review-severity issue to acknowledge",
    firstIssues.length > 0,
    JSON.stringify(first?.issues ?? null),
  );

  const unacked = await call(`/api/v1/facts/${first.id}/review`, {
    method: "POST",
    role: "clinical_reviewer",
    body: reviewBody(first, "accept", {
      request_id: "rev-unacked",
      acknowledged_issues: [],
    }),
  });
  check(
    "unacknowledged review-severity issues are refused",
    unacked.status === 422 &&
      (unacked.json.code === "validation_failed" ||
        String(unacked.json.message ?? "").includes("review_issues_not_acknowledged")),
    `${unacked.status}/${unacked.json.code}`,
  );

  const acceptId = "rev-accept-persist";
  const accepted = await call(`/api/v1/facts/${first.id}/review`, {
    method: "POST",
    role: "clinical_reviewer",
    body: reviewBody(first, "accept", { request_id: acceptId }),
  });
  check(
    "accept persists with nested fact and stub FHIR gateway",
    accepted.status === 200 &&
      accepted.json.state === "accepted" &&
      accepted.json.fhir_gateway === "stub" &&
      typeof accepted.json.resulting_proposal_version === "number",
    `${accepted.status}/${accepted.json.state}/${accepted.json.code}`,
  );

  const acceptReplay = await call(`/api/v1/facts/${first.id}/review`, {
    method: "POST",
    role: "clinical_reviewer",
    body: reviewBody(first, "accept", { request_id: acceptId }),
  });
  check(
    "lost-response replay of the same review request_id returns the first result",
    acceptReplay.status === 200 &&
      acceptReplay.json.state === "accepted" &&
      acceptReplay.json.resulting_proposal_version ===
        accepted.json.resulting_proposal_version,
    `${acceptReplay.status}/${acceptReplay.json.state}`,
  );

  const acceptConflict = await call(`/api/v1/facts/${first.id}/review`, {
    method: "POST",
    role: "clinical_reviewer",
    body: reviewBody(first, "accept", {
      request_id: acceptId,
      reason: "Different payload for the same request_id must conflict.",
    }),
  });
  check(
    "a review request_id reused with a different payload is rejected",
    acceptConflict.status === 409 &&
      acceptConflict.json.code === "idempotency_conflict",
    `${acceptConflict.status}/${acceptConflict.json.code}`,
  );

  const staleReview = await call(`/api/v1/facts/${first.id}/review`, {
    method: "POST",
    role: "clinical_reviewer",
    body: reviewBody(first, "accept", {
      request_id: "rev-stale-version",
      expected_proposal_version: 1,
    }),
  });
  check(
    "a stale proposal version is refused",
    staleReview.status === 409 && staleReview.json.code === "stale_revision",
    `${staleReview.status}/${staleReview.json.code}`,
  );

  const acceptRead = await call(`/api/v1/facts/${first.id}`, {
    role: "clinical_reviewer",
  });
  check(
    "GET fact readback shows accepted state and bumped version",
    acceptRead.status === 200 &&
      acceptRead.json.review_state === "accepted" &&
      acceptRead.json.version === accepted.json.resulting_proposal_version &&
      nestedFact(acceptRead.json) !== null,
    `${acceptRead.status}/${acceptRead.json.review_state}/v${acceptRead.json.version}`,
  );

  const rejected = await call(`/api/v1/facts/${second.id}/review`, {
    method: "POST",
    role: "clinical_reviewer",
    body: reviewBody(second, "reject", { request_id: "rev-reject-persist" }),
  });
  check(
    "reject persists",
    rejected.status === 200 && rejected.json.state === "rejected",
    `${rejected.status}/${rejected.json.state}/${rejected.json.code}`,
  );
  const rejectRead = await call(`/api/v1/facts/${second.id}`, {
    role: "clinical_reviewer",
  });
  check(
    "GET fact readback shows rejected state",
    rejectRead.status === 200 && rejectRead.json.review_state === "rejected",
    `${rejectRead.status}/${rejectRead.json.review_state}`,
  );

  const family = adultProps.find(
    (p: Json) => nestedFact(p)?.subject === "family_member",
  );
  const screening = adultProps.find(
    (p: Json) => nestedFact(p)?.subject === "patient",
  );
  check("adult extraction produced a family-member proposal", Boolean(family));
  const familyFact = nestedFact(family ?? {});
  const corrected = await call(`/api/v1/facts/${family?.id}/review`, {
    method: "POST",
    role: "clinical_reviewer",
    body: reviewBody(family ?? {}, "correct", {
      request_id: "rev-correct-persist",
      correction: familyFact
        ? {
            concept: familyFact.concept,
            value_text: "a sibling was diagnosed with bowel cancer",
            subject: familyFact.subject,
            assertion: familyFact.assertion,
            effective_date: familyFact.effective_date ?? null,
            excerpt: familyFact.excerpt,
            proposed_resource_type: familyFact.proposed_resource_type,
            relationship: familyFact.relationship ?? "sibling",
          }
        : null,
    }),
  });
  check(
    "correct persists a replacement fact",
    corrected.status === 200 &&
      corrected.json.state === "corrected" &&
      corrected.json.fhir_gateway === "stub",
    `${corrected.status}/${corrected.json.state}/${corrected.json.code}`,
  );
  const correctRead = await call(`/api/v1/facts/${family?.id}`, {
    role: "clinical_reviewer",
  });
  check(
    "GET fact readback shows the corrected value",
    correctRead.status === 200 &&
      correctRead.json.review_state === "corrected" &&
      nestedFact(correctRead.json)?.value_text ===
        "a sibling was diagnosed with bowel cancer",
    `${correctRead.status}/${correctRead.json.review_state}/${nestedFact(correctRead.json)?.value_text}`,
  );

  const coordinatorReview = await call(`/api/v1/facts/${screening?.id}/review`, {
    method: "POST",
    role: "coordinator",
    body: reviewBody(screening ?? {}, "reject", {
      request_id: "rev-coordinator-forbidden",
    }),
  });
  check(
    "coordinator cannot apply review",
    coordinatorReview.status === 403,
    `${coordinatorReview.status}/${coordinatorReview.json.code}`,
  );

  // --- four canonical outcomes, including case: null ---
  const noLatest = await call(
    "/api/v1/patients/pat-synthetic-11/evaluations/latest",
    { role: "clinical_reviewer" },
  );
  check(
    "GET latest evaluation is 404 when none is stored",
    noLatest.status === 404,
    `${noLatest.status}`,
  );

  const expectedEvals: Record<
    string,
    { outcome: (typeof CANONICAL_OUTCOMES)[number]; caseNull: boolean }
  > = {
    "pat-synthetic-11": { outcome: "needs_review", caseNull: false },
    "pat-synthetic-12": { outcome: "gap_identified", caseNull: false },
    "pat-synthetic-13": {
      outcome: "no_gap_identified_in_available_data",
      caseNull: true,
    },
    "pat-synthetic-32": { outcome: "not_eligible", caseNull: true },
  };
  for (const [patientId, expect] of Object.entries(expectedEvals)) {
    const posted = await call(`/api/v1/patients/${patientId}/evaluations`, {
      method: "POST",
      role: "clinical_reviewer",
      body: {},
    });
    const outcome = posted.json.rule_evaluation?.outcome;
    check(
      `${patientId} returns canonical outcome ${expect.outcome}`,
      posted.status === 200 &&
        outcome === expect.outcome &&
        CANONICAL_OUTCOMES.includes(outcome),
      `status=${posted.status} outcome=${outcome} flag=${posted.json.flag_status}`,
    );
    check(
      `${patientId} case is ${expect.caseNull ? "null" : "present"}`,
      expect.caseNull ? posted.json.case === null : posted.json.case != null,
      `case=${posted.json.case === null ? "null" : typeof posted.json.case}`,
    );
    const latest = await call(
      `/api/v1/patients/${patientId}/evaluations/latest`,
      { role: "clinical_reviewer" },
    );
    check(
      `${patientId} latest evaluation readback matches`,
      latest.status === 200 &&
        latest.json.rule_evaluation?.outcome === expect.outcome,
      `${latest.status}/${latest.json.rule_evaluation?.outcome}`,
    );
  }

  // --- verified context: records, not AssembledContext ---
  const verified = await call("/api/v1/security/verified-context", {
    method: "POST",
    role: "clinical_reviewer",
    body: { patient_id: "pat-synthetic-11" },
  });
  check(
    "verified-context returns records with scope and expiry",
    verified.status === 200 &&
      Array.isArray(verified.json.records) &&
      verified.json.exhaustive === false &&
      verified.json.absence_claims_allowed === false &&
      typeof verified.json.expires_at === "string" &&
      typeof verified.json.checked_scope === "string" &&
      verified.json.authorized === true,
    `${verified.status} exhaustive=${verified.json.exhaustive}`,
  );
  check(
    "verified-context does not invent AssembledContext items/query/tiers",
    !Array.isArray(verified.json.items) &&
      verified.json.query == null &&
      verified.json.tiers == null,
  );
  const staleContext = await call("/api/v1/security/verified-context", {
    method: "POST",
    role: "clinical_reviewer",
    body: {
      patient_id: "pat-synthetic-11",
      generation_id: "not-the-current-generation",
    },
  });
  check(
    "a mismatched generation_id is marked stale, not current",
    staleContext.status === 200 && staleContext.json.state === "stale",
    `${staleContext.status}/${staleContext.json.state}`,
  );

  const relateFamily = await call(
    "/api/v1/relate/family-history?patient_id=pat-synthetic-11",
    { role: "clinical_reviewer" },
  );
  const relatePlans = await call(
    "/api/v1/relate/care-plans?patient_id=pat-synthetic-11",
    { role: "clinical_reviewer" },
  );
  check(
    "Relate family-history and care-plans return candidates without authorizing",
    relateFamily.status === 200 &&
      Array.isArray(relateFamily.json.candidates) &&
      relatePlans.status === 200 &&
      Array.isArray(relatePlans.json.candidates),
    `${relateFamily.status}/${relatePlans.status}`,
  );
  const relateForeign = await call(
    "/api/v1/relate/care-plans?patient_id=pat-not-in-workspace",
    { role: "clinical_reviewer" },
  );
  check(
    "Relate does not authorize a foreign patient",
    relateForeign.status === 403,
    `${relateForeign.status}`,
  );

  // --- security: 403 and 404 must be indistinguishable to a client ---
  const foreignDoc = await call("/api/v1/documents/doc-does-not-exist");
  check(
    "an unknown document does not disclose whether it exists",
    foreignDoc.status === 403 || foreignDoc.status === 404,
    `status ${foreignDoc.status}`,
  );

  // --- analytics: one suppression family for overview and segments ---
  const overview = await call("/api/v1/analytics/overview");
  const cells: Json[] = (overview.json.pathways ?? []).flatMap((p: Json) =>
    Object.entries(p)
      .filter(([k]) => k !== "pathway")
      .map(([, v]) => v as Json),
  );
  check("analytics reports both pathways", overview.json.pathways?.length === 2);
  check("analytics declares synthetic", overview.json.synthetic === true);
  check(
    "suppressed overview cells carry no numerator or denominator",
    cells
      .filter((c: Json) => c.suppressed)
      .every((c: Json) => c.numerator === null && c.denominator === null),
  );
  check(
    "suppressed overview cells state a reason and threshold ≥ 10",
    cells
      .filter((c: Json) => c.suppressed)
      .every(
        (c: Json) => Boolean(c.reason) && typeof c.threshold === "number" && c.threshold >= 10,
      ),
  );
  const suppressed = cells.filter((c: Json) => c.suppressed).length;
  const published = cells.filter((c: Json) => !c.suppressed);
  check(
    "reporting cohort publishes at least one unsuppressed cell",
    published.length > 0,
    `${suppressed}/${cells.length} suppressed`,
  );
  const segments = await call("/api/v1/analytics/segments");
  const segmentCells: Json[] = Array.isArray(segments.json.segments)
    ? segments.json.segments
    : [];
  check(
    "segments share the overview publication family",
    segments.status === 200 &&
      segments.json.synthetic === true &&
      segments.json.as_of === overview.json.as_of &&
      segments.json.threshold === overview.json.threshold &&
      typeof segments.json.projection_version === "string" &&
      segmentCells.length > 0,
    `${segments.status} n=${segmentCells.length}`,
  );
  check(
    "suppressed segment cells carry no count, denominator or rate",
    segmentCells
      .filter((c: Json) => c.suppressed)
      .every(
        (c: Json) =>
          c.count === null && c.denominator === null && c.rate === null,
      ),
  );
  const overviewByPathway = Object.fromEntries(
    (overview.json.pathways ?? []).map((p: Json) => [p.pathway, p]),
  );
  const segmentFlagsMatch = segmentCells.every((cell: Json) => {
    const pathway = overviewByPathway[cell.segment];
    if (!pathway) return false;
    const key = cell.metric_id === "follow-up" ? "follow_up" : cell.metric_id;
    const overviewCell = pathway[key] as Json | undefined;
    if (!overviewCell) return false;
    return Boolean(overviewCell.suppressed) === Boolean(cell.suppressed);
  });
  check(
    "segment suppression flags match the overview cells of the same family",
    segmentFlagsMatch,
  );
  console.log(
    `NOTE  ${suppressed}/${cells.length} analytics cells suppressed at this seed size`,
  );

  // --- reset restores the seed for this session only ---
  const otherBeforeReset = await call("/api/v1/cases/case-0002", {
    session: session2,
  });
  check(
    "a second session still has the unmutated seed before reset",
    otherBeforeReset.json.stage === "booked" &&
      otherBeforeReset.json.revision === 4,
    `${otherBeforeReset.json.stage}/rev${otherBeforeReset.json.revision}`,
  );

  const reset = await call("/api/v1/demo/reset", { method: "POST" });
  check("reset restores the seed", reset.json.cases_restored === 6);
  const afterReset = await call("/api/v1/cases/case-0002");
  check(
    "reset returns case-0002 to booked at rev 4",
    afterReset.json.stage === "booked" && afterReset.json.revision === 4,
  );
  const otherAfterReset = await call("/api/v1/cases/case-0002", {
    session: session2,
  });
  check(
    "reset of this session does not rewrite the second session",
    otherAfterReset.json.stage === "booked" &&
      otherAfterReset.json.revision === 4,
  );

  console.log(`\n${pass} passed, ${fail} failed`);
  if (fail > 0) process.exit(1);
}

void main();
