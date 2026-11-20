# Handoff — Alfred to Ismail

**Prepared:** 19 November 2026  
**From:** Alfred (`ai/`)  
**To:** Ismail (`api/`, FHIR, workers, workflow)  
**On `main`:** `1e694e3` (`test(ai): align audit assertions with backend decision fields`)  
**Also on this line:** `514d93f` (Alfred safety package), `dc962da` (your review/acceptance work)  
**Status:** Alfred's package is ready to connect. Synthetic only. Not a deployment approval.

Ismail — please integrate the callables below into the endpoints you already
own. Do not copy extraction validation, quote offsets, review mapping, or rule
semantics into a second implementation. `api/` was not changed for this
handoff. SQLite, the FHIR stub, guest identity, and fixture extraction remain
your current runtime.

An accepted proposal, a generated Bundle, an outbox row, and a 200 from the
stub gateway are not a HAPI commit. Rules must consume reviewed resources
reloaded from the clinical store, with versions.

Copy for Mark: keep `legacy_flag_status` / `api_compatibility` as explicit
projections. Do not collapse `not_eligible` into `no_gap`.

---

## 1. What to import

Paths are relative to `ai/src/namaa_ai/`. Assemblers and resolvers are on.
Pass `enabled=False` at a composition boundary that must stay dark.

| Boundary | Call | Notes |
| --- | --- | --- |
| Extraction | `AuthorizedExtractionPipeline.run`, `HostedAdapter`, `decode_response` | Worker-only. HTTPS endpoint, no DB access in the model process. |
| Source grounding | `make_proposals` / `check_fact` | Server-side excerpts; zero-based, end-exclusive Unicode offsets. |
| Review | `apply_review` or `apply_review_authorized` | Accept / correct / reject. Bind reviewer from the session. |
| FHIR mapping | `propose_transaction` | Returns a non-executable Bundle (`executable=false`) plus Provenance. |
| Rules | `evaluate`, `rules_for_reviewed_commit` | `DEMO_WCV_01`, `DEMO_ADULT_01`. Fictional 37/73-day intervals. |
| Compatibility | `prepare_rule_handoff` | Lossy flag for Mark. Persist the nested `rule_evaluation`. |
| Context | `ScopedContextAssembler`, `VerifiedGuidelines`, `render_bounded_context` | Enabled. Pass server-minted scope. `enabled=False` remains a kill switch. Hybrid BM25 + hashed dense is default. |
| Graph | `RelateResolver(verify, request_refresh)` | Enabled. Every resolve re-verifies. Failure → `unknown`, no items. `BackendApiClient.family_history_resolution` uses this path. |
| Analytics | `suppress_population`, `publish_population`, `funnel_cells` | One publication family; overview and segments are views of that release. Eligible is a denominator, never a self-complement cell. |
| Completion metric | `METRICS` in `engagement.py` | Version `demo-1.1.0`. |
| Wire checks | `BackendApiClient`, `BackendReviewResult`, `BackendExtractionJob` | Consumer-side codecs, not a second API. |

JSON examples and schemas: `ai/examples/` including
`schemas/analytics/`, `schemas/context_assembler/`, `schemas/relate_graph/`.

Serving protocol: [`ENDPOINT.md`](ENDPOINT.md). Worker env:
`NAMAA_HF_ENDPOINT_URL`, `NAMAA_HF_TOKEN`, `NAMAA_MODEL_REVISION` (40-char
commit), `NAMAA_ENDPOINT_PROTOCOL=namaa-extraction-v1`. No endpoint was
provisioned or called.

The API image currently copies only `api/`. To import `namaa_ai`, add the
package to the API environment (editable install from `ai/` or an equivalent
image layer). Do not vendor a truncated copy of the validators.

---

## 2. Suggested order

Keep the existing routes. Change what they call.

| Step | Your work | Done when |
| --- | --- | --- |
| 1 | Session → workspace/partition; never trust a client partition id | Out-of-scope patients cannot select clinical data |
| 2 | Durable extraction worker → `AuthorizedExtractionPipeline` | Two workers cannot finalize one lease; hosted failure is not a successful empty/fixture job |
| 3 | Review → `apply_review` + journaled HAPI transaction | One accept/correct → one typed resource + Provenance; reject writes nothing clinical |
| 4 | Replace `app.rules.evaluator` with `evaluate` on a reviewed HAPI snapshot | All four outcomes persist and read back; unreviewed/rejected facts are absent |
| 5 | Verified context + `RelateResolver` callbacks | Stale/denied graph hints become `unknown` + refresh; no leaked references |
| 6 | One `suppress_population()` release feeding `/overview` and `/segments` | Related responses cannot recover a hidden count by subtraction |
| 7 | Accountable workflow (your module) | Booking ≠ completion; overdue escalation keeps the owner |

PostgreSQL leases, partitioned HAPI, and production identity remain required
for the target architecture. They are not delivered by this package.

The older itemized backend register is still useful for defects on the
synthetic API: [`docs/00-reference/ismail-gap-handoff-draft.md`](../../docs/00-reference/ismail-gap-handoff-draft.md)
(I00–I23, baseline `167b797`). This document is the current Alfred integration
contract on `1e694e3`.

---

## 3. Extraction

Keep `POST /api/v1/documents/{id}/extractions` → `202` + `job_id`. Call the
model only from the durable worker, after re-authorizing the **initiating**
principal. A worker service identity must not replace that principal.

```python
pipeline = AuthorizedExtractionPipeline(enforcer, source_provider, hosted_adapter)
result = await pipeline.run(
    context=current_initiating_context,
    patient_id=job_patient_id,
    source_id=job_document_id,
    job_id=job_id,
)
```

`source_provider.fetch(context=..., patient_id=..., source_id=...)` must return
an `ExtractionRequest` for the authorized, version-bound DocumentReference.
Compare that version with the version stored on the job. The pipeline binds
document, workspace and patient; it does not load your job row.

Pipeline checks: `note.retrieve`, then `model.dispatch`, then
`proposal.disclose`. Re-check disclosure on status/SSE/excerpt reads.

Your ownership: PostgreSQL claim (`FOR UPDATE SKIP LOCKED` or equivalent),
lease token, heartbeat, fencing of stale workers, bounded job retries, atomic
persist of the terminal result and staged proposals. Adapter wall clock is
90 seconds; the lease must cover inference and finalization. Adapter budgets
reset per invocation — job retries must not create an unbounded repair loop.

Hard limits already in the adapter:

- 6,000 Unicode code points; reject, never truncate
- `do_sample=false`, `max_new_tokens=2048`
- one transient HTTP retry, one format repair, at most three HTTP attempts
- deployment identity mismatch and source-grounding errors are terminal for
  that invocation

Persist distinct statuses: `success`, `no_supported_facts`, `invalid_output`,
`transport_failure`. None of these is a care-gap or “no risk” conclusion.
Blocked proposals may be returned for human correct/reject; do not relabel
them as successful. Store proposals only in the application DB.

**Current API gap on this checkout:** `advance_job` still materializes
fixtures. If `extraction_mode != "offline_fixture"` it still succeeds and
sets `offline-fixture-v1 (fallback — live model unavailable)`. That path
must go. Job column default `extract-v0.3` is stale; wire `extract-v1.0.1`.

---

## 4. Review, commit, evaluation

`POST /api/v1/facts/{id}/review`:

1. Bind `proposal_id` and reviewer identity from the session (do not trust
   `reviewer_reference` unless it matches the server mapping).
2. Validate a `ReviewCommand`. `correct` requires a complete replacement
   `ProposedFact`. Correction on accept/reject is invalid. Reason is required.
3. Re-check source version/hash, excerpt, offsets, subject mapping, and
   acknowledgements. An acknowledgement must not override a blocking issue.
4. CAS the expected proposal version. Journal workspace + target + operation
   + payload. Reauthorize before returning a cached replay.
5. Call `apply_review` (or `apply_review_authorized`). Echo the **original**
   proposal snapshot and the full command. Put outbox/stub metadata outside
   the canonical object. Consumer check: `BackendReviewResult`.

Then `propose_transaction(reviewed_fact)` for the Bundle. You attach
`If-Match`, resolve create vs update, validate references, enforce immutable
Provenance, and execute through HAPI. Local mapping checks are not HL7
validator output.

Timeouts: the HAPI write may have succeeded. Reconcile before retry. Do not
feed journaled acceptance to rules until commit/readback is confirmed.

After a confirmed commit:

```python
for rule_id in rules_for_reviewed_commit(snapshot, changed_resource_version):
    evaluation = evaluate(snapshot, rule_id)
    # persist evaluation + input versions immutably
```

`FamilyMemberHistory` routes to `DEMO_ADULT_01`. It must not become a patient
`Condition` or fill last-screening history. Missing history is `needs_review`,
never `no_gap_identified_in_available_data`. Context retrieval does not
establish eligibility or authorize an order.

Canonical outcomes to persist (not only `flag_status`):

- `gap_identified`
- `no_gap_identified_in_available_data`
- `needs_review`
- `not_eligible` — `legacy_flag_status` is null; must not become `no_gap`

**Current API gaps:** review still upserts every accepted fact as a patient
`Observation`, including family history. The placeholder evaluator does not
call `namaa_ai.rules.evaluate`; adult missing screening is treated as a gap;
age bands starting with 4 or 5 can be classified as children. Replace the
stub rather than patching those heuristics in place.

---

## 5. Context, guidelines, Relate

Mint `VerifiedContext` only after current resource and permission checks.
`ScopedContextAssembler()` needs workspace, patient,
generation, permission revision and clocks from **server** state.

Patient passages and approved guidelines share `ContextQuery` item/text
limits. Omit whole passages; do not truncate. Character budget is source
text, not JSON overhead. Passage IDs are now distinct per document span —
rebuild any vectors keyed by the old IDs. Default ranking is hybrid BM25
plus a hashed-token dense ranker; inject a production `DenseRetriever` when
you have an authorized vector destination.

`VerifiedGuidelines`: approval is the exact Library/DocumentReference
version, with source-verified text and offsets. A browser boolean or a note
is not approval. No real guideline corpus is in this repo. Use
`render_bounded_context()` for the untrusted payload. Model dispatch and
disclosure still need their own authorization checks.

Relate:

```python
resolver = RelateResolver(verify, request_refresh)
resolution = await resolver.resolve(
    batch,
    workspace_id=session.workspace_id,
    patient_reference=session.patient_reference,
    permission_revision=session.permission_revision,
)
```

| Callback | Contract |
| --- | --- |
| `verify` | `workspace_id`, `patient_reference`, `references` → `VerifiedContext` after PEP/PDP + current HAPI. Bind the authenticated principal. Check relational support, not mere existence. |
| `request_refresh` | `workspace_id`, `patient_reference`. Authorize independently. Idempotent enqueue. Ignore graph text and caller-selected partitions. |

`state="verified"` only when every candidate re-checks. Otherwise
`state="unknown"`, empty items, `refresh="requested"` or `"failed"`. Empty
results do not mean “no family history / no broken handoff”.

`BackendApiClient.family_history_resolution` / `care_plan_resolution` use
`RelateResolver`. The older `*_context` helpers return `.items` only (empty
when unknown — that is not evidence of absence). `request_refresh` POSTs
`/api/v1/relate/refresh`. Discovery remains hints only and must stay that way.

---

## 6. Analytics and workflow

Build workspace-scoped projections from **confirmed** clinical and workflow
evidence. Pass the whole related family (overview + segments) into
`suppress_population()` **once**, then pick views from that `AnalyticsRelease`.
Do not call it per endpoint.

If any count, denominator, or complement is `< 10`, every numeric value in
that release is null (rates and denominators included). Labels and
`projection_version` remain. Cross-release differencing and cohort
authorization are yours.

A cell with `count == denominator` has complement 0 and suppresses the
release. Agree the representation for standalone cohort totals before wiring
those rows. Raising N alone will not make `eligible/eligible` publishable.

`GET /api/v1/analytics/segments` is still missing on the API. Call
`publish_population()` once and serve both `/overview` and `/segments` from
that `AnalyticsViews` object. Overview currently suppresses per cell and does
not import these helpers.

Completion metric `demo-1.1.0`: completed disposition **and** verified
`Encounter` | `Procedure` | `DiagnosticReport` **and** reviewer
authorization. Booking, attendance, or a generic close is not completion.

Workflow remains yours: draft CarePlan + review Task (owner +
`Task.restriction.period.end`) on gap; activate plan + authorize
`ServiceRequest`; Appointment separate from completion; one escalation per
missed deadline without dropping ownership. Actions today use
`expected_revision`; the target name is `expected_version`. Agree with Mark
before renaming.

---

## 7. Checks

Recorded on this line (synthetic data, isolated SQLite, stub FHIR):

```bash
cd ai
.venv/bin/python -m pytest -q --ignore=tests/integration
.venv/bin/python -m pytest -q --require-backend -m api_integration tests/integration
.venv/bin/python -m pytest -q
```

Last combined run: **294 passed, 16 skipped**. Skips are live-URL / seed-map
checks, not local safety tests. Evidence:
[`docs/03-evidence/alfred-safety/checks.md`](../../docs/03-evidence/alfred-safety/checks.md).
[`BACKEND_BRIDGES.md`](BACKEND_BRIDGES.md) has older notes — do not treat those
as proof for this build.

Not validated here: hosted MedGemma quality, real HAPI, PostgreSQL
concurrency, production PDP.

Before calling the join complete, keep evidence for:

- Competing workers, lease expiry, restart, rejected stale writes
- Accept / correct / reject, exact replay, payload conflict, stale version,
  reviewer substitution
- HAPI crash/timeout reconciliation, no duplicate facts
- Confirmed commit changes a persisted evaluation; pending/rejected excluded;
  four outcomes survive reload
- Graph version or permission change between discovery and disclosure;
  refresh failure → unknown, no leaked refs
- Appointment-only close rejected; unauthorized close rejected; success only
  with verified evidence + reviewer
- Suppression on overview, segments, and exports; repeated queries
- Overdue escalation retry without a second escalation or lost owner

---

## 8. Please send back

- Integration commit, supported run mode, startup command
- Session → workspace/partition binding
- Example source, review, and evaluation responses from the live API
- Model endpoint protocol and actual revision (not the all-zero placeholder)
- `verify` / `request_refresh` implementation
- Analytics publication-family definition (especially cohort totals)
- Test log with remaining failures/skips

Alfred keeps rule semantics, extraction validation, mapping collaboration, and
AI-side contract changes. Mark owns UI consumption. Production policy must not
relabel `synthetic_guest_v1` as production. `QuestionnaireResponse` mapping
stays unsupported until you supply an approved versioned Questionnaire and
answer map.

This is a repository handoff, not a sent message.
