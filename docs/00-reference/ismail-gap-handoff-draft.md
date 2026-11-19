# Draft handoff to Ismail — remaining backend gaps

**Prepared:** 19 November 2026  
**Baseline:** repository commit `167b797`; inspection of checked-in code, tests, and handoffs. No fresh API, browser, or concurrency test run was performed for this draft.  
**Status:** proposed work and acceptance criteria, not a claim that the team has agreed new contracts. Companion: [Mark's gap handoff](mark-gap-handoff-draft.md).

Ismail — the synthetic backend now exposes the security, review, evaluation, Relate, and verified-context bridges. The next work is to make their contracts, persistence, authorization, and recovery behavior match the assurances given to Alfred and Mark.

Already delivered: session-scoped storage, workflow actions, structured application errors, AuthZEN-shaped decisions, note/model authorization hooks, nested proposal serialization, a review journal and outbox, canonical evaluation responses, fixed Relate operations, verified context, and prototype suppression. These are existing foundations, not requests to rebuild the endpoints.

**Priority:** P0 = correctness/security/contract defect affecting the current synthetic integration; P1 = required completion and evidence; P2 = supporting delivery or a conditional enhancement. Production IdP/PDP, external audit storage, and live HAPI remain separate deferred work.

## 1. Outcome contract and rule integration

### I00 — Record the outcome contract and case behavior · P0 · shared with Alfred and Mark

Use Alfred's four canonical names for `rule_evaluation.outcome`: `gap_identified`, `no_gap_identified_in_available_data`, `needs_review`, and `not_eligible`. Preserve `legacy_flag_status` and `api_compatibility` as explicit compatibility projections.

**Gap:** the canonical response exists, but `CaseRow.flag_status` still carries only `gap | needs_review`. Evaluations without a gap/review result return `case: null`; an existing case is not reconciled in that branch. The team has not recorded how the latest evaluation and an existing workflow should coexist.

**Deliver/done:** publish the agreed schema and case lifecycle behavior, including where Mark retrieves no-case results and how a changed eligibility outcome affects existing work. Do not silently coerce an outcome or automatically mark preventive care completed. Widening a TypeScript case enum alone is not a backend contract change.

### I01 — Persist and expose the complete canonical evaluation · P0 · Ismail

**Gap:** `run_evaluation()` persists only `flag_status`, `factors`, and `missing` in `RuleEvaluation.result_json`; it constructs `rule_evaluation` afterward for the response. The saved input snapshot lists observation IDs rather than a complete reproducible set of versioned inputs. There is no evaluation read/history endpoint in the patient router.

**Deliver/done:** persist the validated canonical object and the exact input/version snapshot atomically, with evaluation ID, rule version, scope, and effective evaluation date. Provide an authorized readback/latest/history contract appropriate for Mark. A reload must recover the same four-value result, including `not_eligible`, without reconstructing it from a lossy flag. Use real application version semantics rather than a permanently unchanged `app-1` when inputs change.

### I02 — Connect reviewed facts to Alfred's evaluator · P0 · Ismail integrates; Alfred owns rule semantics

**Gap:** review updates proposals and enqueues a stub FHIR transaction; evaluation reads the separate `Observation` table and calls the placeholder `app.rules` evaluator. There is no demonstrated reviewed-fact-to-rule path. The placeholder has no no-gap branch, accepts a false eligibility observation without checking its verification/conflict state, and marks an adult gap factor verified even when the screening input is absent. Its age-prefix heuristic can also classify an adult band beginning with 4 or 5 as a child.

**Deliver/done:** integrate Alfred's agreed evaluator through an authorized, versioned snapshot of eligible reviewed inputs. Agree when a journaled review becomes available to evaluation relative to outbox commit. Demonstrate accept/correct affecting a later evaluation, reject/pending remaining excluded, and unverified/conflicting inputs producing the agreed uncertainty behavior. Exercise all four outcomes using Alfred's fixtures; do not repair clinical rule semantics independently in a second implementation.

Evidence for I00–I02: [schemas](../../api/app/schemas.py), [evaluation persistence](../../api/app/services/evaluations.py), [patient routes](../../api/app/routers/patients.py), [placeholder evaluator](../../api/app/rules/evaluator.py), [Alfred contracts](../../ai/src/namaa_ai/contracts.py), [review service](../../api/app/services/review.py).

## 2. Review contracts, identity, and persistence

### I03 — Make wire responses validate against Alfred's actual contracts · P0 · Ismail with Alfred

**Gap:** nested shape is not yet full compatibility. Extraction proposals include additional review fields and use the job's `extract-v0.3` prompt version, while Alfred's strict proposal/model contracts forbid extra fields and require `extract-v1.0.1`. Review responses omit the command's correction and the reviewed fact's `review`; their embedded proposal is serialized after its state/version changed, while Alfred binds the decision to the original proposed version.

**Deliver/done:** agree canonical objects versus API envelope extensions, preserve the original proposal snapshot and complete command, and emit the actual model/prompt provenance. Do not relabel an old prompt merely to pass validation. Validate real extraction and accept/correct/reject responses through Alfred's `BackendExtractionJob` and `BackendReviewResult`, including command/proposal equality. Keep outbox/stub metadata outside strict canonical objects unless the shared contract explicitly includes it.

### I04 — Enforce source and correction validation on the server · P0 · Ismail with Alfred's validator

**Gap:** the endpoint checks the source hash/version and review-severity acknowledgements, but does not reject blocking issues or rerun quote/offset/subject/resource validation. Corrections are arbitrary dictionaries, can omit required content, and can change the excerpt while retaining old offsets. A correction is not forbidden on accept/reject. Review can also be applied again to a terminal proposal if the caller supplies its newer version.

**Deliver/done:** reuse Alfred's review/source validation behind a backend authorizer, with strict command/fact types and an agreed transition policy. Revalidate the selected fact against the exact source, recompute its code-point span, retain cross-proposal conflicts, require acknowledgements, and reject invalid family-member/patient mappings. Unsupported or blocked facts must never enter the reviewed store/outbox. Explicitly support or reject subsequent amendments/retractions; do not leave earlier committed facts active after a later rejection without reconciliation.

### I05 — Bind reviewer identity and reauthorize journal replay · P0 · Ismail

**Gap:** `reviewer_reference` is accepted from the request body; the clinical role check does not bind that identity to the principal. An existing journal response is returned before proposal lookup, role checks, and authorization. Workflow commands similarly return cached responses before their role check.

**Deliver/done:** resolve reviewer identity from trusted server state, or require the supplied reference to match an explicit server mapping. Recheck the current caller's access before disclosing replayed results, without applying the mutation twice. Test changed role, revoked principal, wrong patient/workspace, and an attempted reviewer substitution. Keep the guest role switch labelled synthetic; it is not production identity verification.

### I06 — Enforce atomic concurrency and complete idempotency binding · P0 · Ismail

**Gap:** review reads a version, mutates the ORM object, and commits without a database compare-and-swap/version guard. Journal uniqueness alone does not protect two different request IDs reviewing the same version. Replay hashes do not reliably bind the path target: review body `proposal_id` is optional, and workflow hashing excludes the case path. Review and workflow journals also share the outbox's workspace/request-ID namespace without a common command identity check.

**Deliver/done:** atomically claim the expected proposal/case revision, return 409 for losing writers, and bind idempotency to workspace, target, operation, command content, and the agreed principal semantics. Handle duplicate-key races as replay/conflict, not 500. Test same-key/same-command, changed payload, changed path target, cross-command key reuse, and simultaneous distinct commands. One successful decision must produce one journal event and the intended outbox entry.

### I07 — Make proposal identity safe across re-extraction · P0 · Ismail

**Gap:** every extraction reuses fixture IDs such as `prop-1101`; `Proposal` has no workspace/ID uniqueness constraint. Re-running a completed extraction inserts another row with the same lookup ID, while fact/review endpoints use `.one_or_none()` on workspace and ID.

**Deliver/done:** define immutable proposal identity per extraction/source version, enforce it in storage, and preserve review history when re-extracting. Two successful runs must remain individually addressable; fact lookup/review must not become ambiguous, overwrite earlier evidence, or reset a previously reviewed fact. Use collision-safe FHIR logical IDs derived from the agreed identity as well.

Evidence for I03–I07: [review route/body](../../api/app/routers/facts.py), [review service](../../api/app/services/review.py), [proposal serialization](../../api/app/services/proposals.py), [extraction creation](../../api/app/services/extractions.py), [fixture IDs](../../api/app/services/extraction_fixtures.py), [models](../../api/app/models.py), [workflow replay](../../api/app/workflow/engine.py), [Alfred review validation](../../ai/src/namaa_ai/review.py), [Alfred transport validation](../../ai/src/namaa_ai/backend.py).

## 3. Authorization and audit gaps in the current prototype

### I08 — Apply revocation at execution and disclosure boundaries · P0 · Ismail

**Gap:** revocation is checked when rebuilding a job's execution context. It is not checked by the general trusted-context builder or `authorize_proposal_disclosure()`, and the worker does not repeat it before publishing results. A stream retains its initial request context. The revocation endpoint itself has no explicit role/policy gate beyond a session.

**Deliver/done:** enforce current principal/membership/permission state on protected reads, review/evaluation, replay, worker execution, and result disclosure. Refresh the relevant subscriber context at disclosure rather than relying on its opening snapshot. Define who may revoke a principal. A revocation after queueing, during execution, or before terminal delivery must prevent the prohibited work/disclosure and produce an auditable terminal outcome.

### I09 — Correct trusted assignment construction · P0 · Ismail

**Gap:** `build_trusted_context()` sets an empty assignment for an explicitly out-of-scope patient, then restores all workspace patient IDs with `assigned if assigned else patient_ids`. Assignments are derived from existing cases, which also prevents a legitimate patient without a case from participating in the new evaluation-only flow. Membership is always active; permission revision is constant.

**Deliver/done:** keep an explicit empty scope empty; establish synthetic assignments independently of whether a care-gap case already exists; bind purpose and other authority fields to the agreed server policy. Test no-case patients, removed assignments, changed authority, and missing scope. Static synthetic membership/revision behavior must be accurately documented until a real lifecycle is implemented.

### I10 — Complete the role/resource policy matrix and endpoint coverage · P0 · Ismail

**Gap:** the PDP has no aggregate-only restriction for `population_analyst` and can permit recognized actions when required patient/resource scope is omitted. The service-review branch skips the initiating-reviewer requirement because `service` is already excluded from its outer condition. Case reads, audit reads, and outbox operations do not all use the same authorization boundary. The design explicitly limits analysts to approved aggregates.

**Deliver/done:** define and enforce an action/resource/role matrix for the synthetic contract. Resolve target scope from authoritative stored records, require missing scope to fail closed, and do not treat body-supplied patient/workspace claims as proof about a resource. Bind any service delegation to a preserved authorized initiator. Cover notes, proposals, context, cases, evaluations, audit reads/writes, and ops retry. A permitted AuthZEN answer must agree with the protected endpoint's decision.

### I11 — Make denied actions auditable and audit payloads safe · P0 · Ismail

**Gap:** `authorize()` flushes an audit event and then raises on denial; ordinary request cleanup closes the uncommitted session, so the deny event is not reliably retained. Sanitization checks only top-level keys, allowing forbidden nested content. Client-submitted audit assertions and authoritative server decisions need a clear distinction; command and transport request IDs can also diverge.

**Deliver/done:** retain denial/security audit records without committing failed clinical mutations, sanitize nested dictionaries/lists or use a bounded allowlist, and correlate decision, command, job, reviewer, and source versions. Restrict audit writers/readers according to I10. Test a real protected-route denial followed by audit readback, nested forbidden metadata, and rollback of the underlying action. Do not describe application-table audit as an external append-only store.

### I12 — Complete the shared error and disclosure contract · P1 · Ismail

**Gap:** only `AppError` has a shared-envelope handler. FastAPI request-validation errors still use its default shape; several errors omit request IDs, and not-found/denied responses can expose different details before authorization. Unexpected storage conflicts are not consistently translated.

**Deliver/done:** return documented `code`, `message`, `field_errors`, and request correlation for malformed input and expected 401/403/404/409/422 conditions. Publish recoverable rate-limit/service-failure behavior where supported. Use the agreed unavailable/denied disclosure policy without revealing sensitive existence or scope details. Mark must be able to distinguish retry, refresh, validation repair, and uncertain mutation outcome without parsing exception text.

Evidence for I08–I12: [trusted context](../../api/app/security/context.py), [request dependencies](../../api/app/security/deps.py), [PDP](../../api/app/security/pdp.py), [enforcement](../../api/app/security/enforce.py), [audit writer](../../api/app/security/audit.py), [security routes](../../api/app/routers/security.py), [extraction disclosure](../../api/app/routers/extractions.py), [job checks](../../api/app/services/extractions.py), [database lifetime](../../api/app/db.py), [error handler](../../api/app/errors.py), [app handlers](../../api/app/main.py), [role requirements](namaa_software_design_specification.md).

## 4. Verified context, Relate, and FHIR boundary

### I13 — Make verified-context claims match checked versions and lifecycle · P0 · Ismail; assembly contract shared

**Gap:** verified context checks workspace and actual patient links, but then marks matching FHIR rows authorized/source-verified without excluding compensated/revoked resources. Application observations always use `app-1`; the document version map is built from all versions without an explicit latest-version selection. Generation can be supplied by the caller, `built_at` is synthesized as five minutes ago, and permission revision is static. These are not evidence of a checked index generation or permission lifecycle.

**Deliver/done:** bind verification to current authoritative scope, resource lifecycle, and exact versions; exclude revoked/compensated/unreviewed material as required by the agreed policy. Publish truthful build/verification/expiry metadata and validate the meaning of generation IDs. Retain partial completeness and no-absence-claim semantics. Agree with Alfred and Mark whether the API supplies verified `records` or assembled `items`; never invent missing assembly/review provenance.

### I14 — Scope Relate candidates by structured patient links · P1 · Ismail

**Gap:** Relate discovery searches for a patient reference substring anywhere in resource JSON and applies its SQL limit before filtering by patient. It can return misleading references from narrative text or omit valid candidates. Permission/generation labels are fixed, and `limit` is not bounded by the endpoint schema.

**Deliver/done:** use the resource's actual patient link, filter before limiting, bound requests, and give candidates accurate lifecycle/version metadata. Keep operations fixed and parameterized. Test patient-reference prefixes, narrative-only mentions, foreign resources, empty results, and pagination/limits. Discovery remains hints only; every consumed result must pass authoritative verification, including stale/empty discovery paths.

### I15 — Preserve reviewed fact semantics in the FHIR mapping · P0 · Ismail with Alfred

**Gap:** the review bundle is a generic resource with status, subject, and note text; it loses much of the structured reviewed fact and provenance. It uses `subject` for `FamilyMemberHistory`, while the repository's verified-context reader expects that resource's `patient` link. Thus a successfully stored reviewed family-history resource can disappear from verified context.

**Deliver/done:** integrate the agreed per-resource mapping and validation, preserving assertion, subject/relationship, dates, codes/values, reviewer, source reference/version, and provenance. Test reviewed family history through stub commit and verified retrieval. Expose journaled, pending, committed-to-stub, failed, and compensated states clearly; a 200 review response is not a HAPI commit. Live HAPI remains deferred unless separately approved into scope.

### I16 — Complete outbox atomicity, replay, and compensation semantics · P1 · Ismail

**Gap:** outbox/retry scaffolding exists, but the stub gateway tracks only the latest request ID on each mutable resource. Older replay history can be lost after another update. A bundle can mutate earlier entries before a later failure, and compensation leaves an existing normal status unchanged while adding a tag that verified context does not filter. Command-to-outbox status reconciliation and uncertain-outcome behavior need stronger evidence.

**Deliver/done:** retain a durable transaction result per command, apply each bundle atomically in the stub, and define compensation/reconciliation that cannot expose invalidated facts as current. Preserve conditional-version checks and bound retries. Exercise a crash after application commit, uncertain gateway outcome, partial bundle failure, later resource update followed by old replay, compensation, and DLQ retry. Report the eventual result to consumers without duplicating or silently losing a write.

### I17 — Make workers terminate and recover predictably · P1 · Ismail

**Gap:** a denied or failing extraction escapes to the outer worker logger after the job was claimed; it can remain running until another lease attempt rather than receiving a failure/cancellation result. Claims are select-then-update rather than atomic lease claims. SSE snapshots and queued terminal frames need protection against stale job/scope state. Configured non-fixture extraction still executes fixtures, while the wire `inference_mode` comes from configuration.

**Deliver/done:** persist explicit failure/cancellation and release leases for rejected jobs, isolate one job's failure from others, and prevent concurrent claims in the supported deployment. Reconcile stream state with durable state across reconnect/restart. Report the mode that actually ran, including fallback. Test worker restart, denial, timeout, two claimants, reset during work, and a dropped stream. Keep the documented single-replica SSE limit until a shared transport is deliberately added.

Evidence for I13–I17: [verified context](../../api/app/security/verified_context.py), [Relate lookups](../../api/app/services/relate_index.py), [review bundle](../../api/app/services/review.py), [gateway stub](../../api/app/fhir/gateway.py), [outbox](../../api/app/services/outbox.py), [worker runtime](../../api/app/workers/runtime.py), [extraction lifecycle](../../api/app/services/extractions.py), [SSE route](../../api/app/routers/extractions.py), [D004](../02-decisions/D004-sse-and-outbox.md).

## 5. Backend contracts that unblock Mark

### I18 — Publish authoritative document and authority fields · P1 · Ismail

Mark still uses fixture fallback links because there is no case-to-document listing. Case detail lacks a supported caregiver-authority field, even though authority exists in patient/trusted-context data.

**Deliver/done:** provide authorized source associations with document/patient/case IDs and versions, and a patient/case view that distinguishes caregiver relationship, authority status, and contact preferences. Correct inconsistent seed citations. Define unknown/not-applicable states instead of making the UI invent verification. Add resource/audit read contracts only for the inspector scope the team retains.

### I19 — Correct aggregate definitions before expanding the reporting cohort · P0 · Ismail with Alfred

**Gap:** analytics infers invitation, booking, attendance, and follow-up from current stage and counts every `closed` case in all four. Closing for another reason can therefore manufacture milestones. The eligible-total cell applies complementary suppression with numerator equal to denominator, so its complement is always zero for a nonempty cohort; merely increasing cohort size will not make that cell publishable.

**Deliver/done:** compute milestones from recorded evidence/events or an agreed durable projection, keep completion separate from other closures, and agree total-cell/complementary suppression rules with Alfred. Test closure before attendance, decline/unreachable, deferred work, repeated cases, empty cohorts, and both small and publishable cohorts. Then supply a larger synthetic reporting cohort if the team chooses one, or explicitly retain a fully suppressed demo. Never weaken suppression only to make a dashboard look populated.

### I20 — Publish typed consumer contracts and optional action availability · P1; action availability P2 · Ismail

Several bridge responses are untyped dictionaries or lists of dictionaries, so OpenAPI does not describe the strict objects Alfred and Mark need. The action catalog exists, but case-level available actions/blocked reasons remain duplicated in the frontend.

**Deliver/done:** publish typed proposal, review, evaluation, context, and compatibility schemas with representative examples and versioning expectations. Keep IDs, roles, error envelopes, and nullability consistent. If Q9 is retained, return authoritative `available_actions` and blocked reasons; otherwise maintain catalog contract checks and explicitly leave frontend predicates as display hints. Richer metric/inspector fields should be agreed additions, not silently assumed by Mark.

Evidence for I18–I20: [case serialization](../../api/app/services/serializers.py), [schemas](../../api/app/schemas.py), [extraction schemas](../../api/app/schemas_extraction.py), [analytics](../../api/app/services/analytics.py), [source fixtures](../../api/app/services/extraction_fixtures.py), [open questions Q9/Q11](../02-decisions/OPEN-QUESTIONS.md), [Mark's draft](mark-gap-handoff-draft.md).

## 6. Verification and runnable handoff

### I21 — Expand tests to prove the integrated guarantees · P1 · Ismail; joint consumer run

Current tests cover useful happy paths, role refusal, suppression, SSE, and outbox retries. Review tests do not establish correction/rejection/source-validation parity; the revocation test only checks that a revocation row is created. An enum-membership assertion on one evaluation does not exercise all four outcomes, and synchronous helper-driven extraction tests do not prove the full worker/stream lifecycle.

**Deliver/done:** add focused regression tests for I01–I20, prioritizing strict Alfred codecs, original-proposal review binding, replay authorization, concurrent writes, repeated extraction, durable denial audit, revocation after queue/claim, same-workspace out-of-scope access, analyst restrictions, context freshness, and all four evaluation outcomes. Include persistence readback/restart and worker/SSE integration. Run the backend suite, Alfred's real-API bridge checks/AuthZEN codec checks, and Mark's updated API/browser contract checks against the same build. Record actual results and remaining skips; do not substitute endpoint existence for behavior.

### I22 — Make upgrades, reset, and deployment reproducible · P1 · Ismail with Mark

**Gap:** startup uses `create_all()`, which does not migrate existing tables after schema changes. Reset deletes audit/revocation and clinical demo rows within the same session; worker/cache invalidation across that reset needs a defined generation boundary. Docker/Compose configure `NEXT_PUBLIC_API_URL`, while the web client reads `NEXT_PUBLIC_API_BASE_URL`.

**Deliver/done:** document and test the supported schema-upgrade or explicitly disposable-demo database path, isolate test state from an existing demo database, and define reset semantics for active jobs, caches, journals, and audit evidence. Preserve other workspaces. Align the browser build URL variable/CORS with Mark and verify fresh Compose and local startup, including restart with existing data. No destructive reset of a user's existing database should be implicit in startup.

### I23 — Update milestone claims and the final backend handoff · P2 · Ismail

Replace endpoint-presence claims with verified behavior: distinguish canonical response from durable canonical persistence, clinical role checking from reviewer identity binding, and job-claim revocation from disclosure revocation. Update M05, API setup/limitations, shared contracts, and the stale README/DOCKER mock-only statements with Mark. Provide architecture, data handling, test evidence, runtime limitations, and exact startup configuration for the demo/deck.

**Done when:** Alfred and Mark can identify what is connected, which checks passed on which build, what remains blocked, and the supported single-instance synthetic deployment. Keep historical evidence dated rather than rewriting old results as current.

Evidence for I21–I23: [review/handoff tests](../../api/tests/test_review_and_handoff.py), [security tests](../../api/tests/test_security.py), [API/worker tests](../../api/tests/test_api.py), [database initialization](../../api/app/db.py), [reset service](../../api/app/services/demo.py), [API README](../../api/README.md), [Compose](../../docker-compose.yml), [web client](../../web/lib/api.ts), [M05](../01-milestones/M05-ismail-i4-i7-bridge.md), [current Ismail handoff](team-handoff-from-ismail.md).

## Deferred work and ownership boundary

Live HAPI/profile validation/partition gateway, production IdP/PDP and membership management, an external append-only audit sink, production database/operations hardening, and multi-replica SSE transport remain explicit later milestones. Live model hosting is separately gated. They should not be presented as completed or quietly added to the current synthetic release's critical path.

Ismail owns API authority, transactional persistence, concurrency, backend enforcement/audit, worker/outbox behavior, typed backend contracts, and the runnable release. Alfred owns evaluator/validation semantics, fixtures, mapping collaboration, and AI-side codecs; Mark owns frontend consumption, user-visible states, browser/accessibility evidence, and demo assembly. Neither consumer should compensate for missing backend guarantees by inventing state or permissions.

Suggested order: settle I00 while fixing review identity/validation/replay, proposal identity, and revocation; complete strict consumer compatibility and durable rule integration; reconcile context/FHIR/outbox behavior and frontend data dependencies; then run the shared integration matrix and publish the corrected release handoff. Supporting UI work can continue while these backend defects are addressed.
