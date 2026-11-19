# Draft handover — Alfred to Ismail

**Prepared:** 19 November 2026  
**Scope:** AI extraction, context, reviewed-fact evaluation and reporting safeguards  
**Change set:** working-tree changes based on `bf754f1`; no delivery commit or PR recorded yet  
**Status:** ready for backend integration; synthetic testing only

Ismail — Alfred's package is ready for the next integration pass. This session
hardened extraction and review boundaries, added approved-guideline context and
graph refresh contracts, added family-history evaluation routing, and implemented
a reusable population suppression policy. The work is in `ai/`; your API,
database, workflow and infrastructure implementations were not changed.

Please connect these components to the existing backend foundations rather than
duplicate the extraction validation or rule logic. An accepted proposal, a
generated Bundle and a successful synthetic API response are distinct from a
confirmed clinical commit. Rules must use reviewed resources reloaded from HAPI.

The current backend remains SQLite with a stub FHIR gateway. PostgreSQL leases,
partitioned HAPI authority and production identity are still required to meet
the requested target architecture.

## 1. What is available

Paths below are relative to `ai/`. Existing components are marked separately
from additions made this session.

| Component | This session's delivery | Integration entry point |
| --- | --- | --- |
| Model response decoding | New decoder rejects duplicate JSON keys, non-JSON numeric constants and mismatched deployment identity | [`extraction.decode_response`](../src/namaa_ai/extraction.py), called by the existing `HostedAdapter` |
| Extraction boundary | Hardened existing schemas and pipeline: explicit dates, input revalidation, source-ID binding before dispatch | [`AuthorizedExtractionPipeline.run`](../src/namaa_ai/security.py), [`HostedAdapter`](../src/namaa_ai/adapters.py) |
| Human review | Existing accept/correct/reject logic now revalidates its input objects | [`apply_review`](../src/namaa_ai/review.py), `apply_review_authorized` in `security.py` |
| FHIR mapping | Existing reviewed-fact mapper retained; no live gateway added | [`propose_transaction`](../src/namaa_ai/fhir.py) |
| Patient context | Fixed passage-ID collisions, duplicate ranker output and conflicting source versions | [`ContextAssembler`](../src/namaa_ai/context_engineering.py) |
| Approved guidance | New typed guideline corpus and shared patient/guideline retrieval budget | [`ScopedContextAssembler`, `VerifiedGuidelines`, `render_bounded_context`](../src/namaa_ai/context_assembler.py) |
| Optional graph | New per-request verifier and refresh callback composition | [`RelateResolver`](../src/namaa_ai/relate_graph.py) |
| Deterministic rules | Added family-history explanation factors and post-commit routing | [`evaluate`, `rules_for_reviewed_commit`](../src/namaa_ai/rules.py) |
| Population disclosure | New pure small-cell and complementary suppression function | [`MetricCount`, `suppress_population`](../src/namaa_ai/analytics.py) |
| Completion definition | Corrected numerator to require evidence-backed, reviewer-authorized completion; version `demo-1.1.0` | [`METRICS`](../src/namaa_ai/engagement.py) |

Contracts and examples are in [`examples/`](../examples/). New JSON schemas are
under [`schemas/analytics/`](../examples/schemas/analytics/),
[`schemas/context_assembler/`](../examples/schemas/context_assembler/) and
[`schemas/relate_graph/`](../examples/schemas/relate_graph/).

## 2. Recommended integration order

The order below is a proposed backend work sequence, not a claim that these
steps are already integrated.

| Order | Ismail's work | Acceptance checkpoint |
| --- | --- | --- |
| 1 | Establish authenticated session-to-workspace/partition mapping and current authorization at each boundary | Client-supplied partition claims and out-of-scope patient access cannot select clinical data |
| 2 | Connect durable extraction jobs to the authorized pipeline | Two workers cannot finalize the same lease; failures never become successful empty results |
| 3 | Connect strict review to journaled, version-checked HAPI transactions | One accepted/corrected command produces one intended clinical change plus Provenance; rejection produces no clinical write |
| 4 | Build reviewed HAPI snapshots and replace the evaluator stub | Review-to-commit-to-evaluation works; all four outcomes survive persistence/readback |
| 5 | Supply verified patient/guideline context and optional graph callbacks | Stale or denied sources are withheld; graph failure produces unknown and a refresh outcome |
| 6 | Wire one suppressed reporting release to overview and segments | Related responses cannot reveal a hidden count through subtraction |
| 7 | Complete accountable workflow and recovery verification | Booking cannot close care; authorized closure requires verified evidence; overdue work retains its owner |

## 3. Extraction endpoint and durable worker

Use the existing `POST /api/v1/documents/{id}/extractions` entry point for
authorization and enqueueing; return `202` with `job_id`. Invoke the hosted model
only from the durable Python worker.

The existing composition is:

```python
pipeline = AuthorizedExtractionPipeline(enforcer, source_provider, hosted_adapter)
result = await pipeline.run(
    context=current_initiating_context,
    patient_id=job_patient_id,
    source_id=job_document_id,
    job_id=job_id,
)
```

These variables are backend-owned objects. The source provider's async
`fetch(context=..., patient_id=..., source_id=...)` must return an
`ExtractionRequest` for the authorized, version-bound DocumentReference.
Explicitly compare the fetched version with the version captured by the job;
the pipeline binds document ID, workspace and patient but does not load the job
or enforce its stored version itself.

The pipeline checks `note.retrieve`, separately checks `model.dispatch`, and
checks `proposal.disclose` after inference. Reconstruct the initiating principal's
current authority on claim; a worker's service identity must not replace it.
Reauthorize subsequent status/SSE/excerpt disclosure as well.

You own PostgreSQL transactional claims, lease tokens, heartbeat/expiry, fencing
of stale workers, bounded retries and atomic persistence of the final job result
with its staged proposals. The adapter's total inference deadline is 90 seconds;
the lease must remain valid through inference and finalization. Persist enough
attempt information to bound retries across crashes. Adapter budgets reset per
invocation, so job retries must not accidentally create an unlimited repair loop.

Existing adapter limits remain: 6,000 Unicode code points per note, rejection
without truncation, `do_sample=false`, 2,048 new tokens, one transient retry and
one formatting repair, at most three HTTP attempts per invocation. Deployment
identity mismatch and source-grounding errors are terminal for that invocation.
Exact excerpts and offsets are computed server-side; offsets are zero-based,
end-exclusive Unicode code points.

Retain `success`, `no_supported_facts`, `invalid_output` and `transport_failure`
as distinct extraction outcomes. None is a clinical risk conclusion. An invalid
source-grounded result can contain blocked proposals for explicit correction or
rejection; it must not be silently relabelled successful. Store proposals only
in the application database. Hosted failures must not fall back to fixture output.

Endpoint credentials and the immutable model revision belong in worker-only
configuration. The serving protocol and required environment variables are in
[`ENDPOINT.md`](ENDPOINT.md). No endpoint was provisioned or called in this work.

## 4. Review, clinical commit and evaluation

At `POST /api/v1/facts/{id}/review`, validate `ReviewCommand`, bind the path target
and reviewer identity to the authenticated session, and call the shared review
logic. `correct` requires a complete replacement `ProposedFact`; correction on
accept/reject is invalid. Reasons are required. Recheck the source version/hash,
exact selected excerpt, offsets, subject mapping and required acknowledgements.
Acknowledging an issue must never override a blocking validation failure.

Use an atomic proposal-version check and a command journal bound to workspace,
target, operation and payload. Replays must be reauthorized before disclosing a
cached response. Return the original proposal snapshot and complete review
command in the canonical decision, with API/outbox metadata outside strict
canonical objects. [`BackendReviewResult`](../src/namaa_ai/backend.py) is the
consumer-side validation contract.

`propose_transaction(reviewed_fact)` returns a stable-ID transaction proposal
containing a typed resource and Provenance. It does not execute a write or add
backend-resolved update preconditions. You own current-version checks, `If-Match`
for updates, reference validation, immutable Provenance enforcement and HAPI
execution. Local mapping checks are not official R4/profile validation; the
proposal is deliberately marked `executable=false` until backend validation.

Keep the application journal/outbox recoverable across the separate HAPI commit.
A timeout can mean the clinical transaction succeeded but its response was lost;
reconcile that outcome before retrying. Do not expose journaled acceptance as
committed clinical truth or feed it to rules before confirmed commit/readback.

After commit, build a `RuleSnapshot` from current, authorized, reviewed HAPI
resources with exact resource versions and review attestations. Then:

```python
for rule_id in rules_for_reviewed_commit(snapshot, changed_resource_version):
    evaluation = evaluate(snapshot, rule_id)
    # Backend persists the complete immutable evaluation and input versions.
```

The routing function returns rule IDs; it does not enqueue work or write data.
FamilyMemberHistory routes to `DEMO_ADULT_01` without becoming a patient
Condition. Missing screening history remains `needs_review`. Neither family
history nor retrieved context establishes eligibility or authorizes an order.

Persist the complete canonical evaluation, not just a legacy flag. Preserve:

- `gap_identified`
- `no_gap_identified_in_available_data`
- `needs_review`
- `not_eligible`

Use `prepare_rule_handoff()` for the explicit compatibility projection.
`not_eligible` has a null legacy flag and must not become `no_gap`.
The rules remain `synthetic-1.0.0`, with fictional eligibility cards and 37/73-day
intervals. They are not clinical screening schedules.

## 5. Patient context, approved guidelines and optional Relate

Supply `VerifiedContext` only after current resource and permission verification.
`ScopedContextAssembler` is disabled by default and must be explicitly enabled
at the backend composition boundary. Its trusted workspace, patient, generation,
permission revision and timestamps must come from server state.

Patient passages and approved guideline passages share `ContextQuery` item/text
limits; whole passages are omitted rather than truncated. The character budget
counts source text, not serialization overhead. Distinct passages of a document
now have distinct IDs, so any cached vectors keyed by old context IDs must be
rebuilt. BM25 is available; dense ranking is an injectable interface, not a
deployed embedding service.

For `VerifiedGuidelines`, verify approval of the exact Library/DocumentReference
version and supply source-verified text and offsets. A boolean supplied by a
browser or retrieved note is not approval. Guidelines remain a separate
collection from patient facts. No real approved guideline corpus is included.
Use `render_bounded_context()` for the untrusted-data representation; any model
dispatch or response disclosure still requires its own authorization boundary.

For the optional graph, construct `RelateResolver(verify, request_refresh,
enabled=True)`. Supply these async callbacks:

| Callback | Required signature and behavior |
| --- | --- |
| `verify` | Keyword arguments `workspace_id`, `patient_reference`, `references`; returns `VerifiedContext` after current PEP/PDP checks and HAPI verification. Bind/check the supplied scope against the actual authenticated principal. Verify relational supports, not merely resource existence. |
| `request_refresh` | Keyword arguments `workspace_id`, `patient_reference`; independently authorizes and idempotently enqueues refresh for that scope. No graph text or caller-selected partition is trusted. |

Every resolution calls verification, including stale or empty batches. Successful
resolution returns `state="verified"`. Failed, missing, expired or unauthorized
support produces `state="unknown"`, no items, and `refresh="requested"` or
`"failed"`. Empty graph results never establish absence of care. Existing
tuple-returning bridge methods have not been rewired to this new resolver; no
refresh endpoint is assumed to exist.

## 6. Analytics and accountable workflow

Build fixed, workspace-scoped reporting projections from confirmed clinical and
workflow evidence. Pass the complete related overview/segment publication family
to `suppress_population()` once, then select views from that returned release.
Do not invoke it independently on each requested segment.

The current policy is deliberately conservative: if any count, denominator or
complement is below 10, all numeric values in that release are null, including
rates and denominators. Denominator labels and projection version remain. This
protects related margins within one release; cross-release differencing,
authorized cohorts, safe public segment labels and projection rebuilding are
backend responsibilities.

The helper models subset counts with complements. A row with
`count == denominator` has a zero complement and suppresses the release. Agree
with Alfred how standalone cohort totals should be represented before wiring
such rows; increasing the cohort alone will not resolve that behavior. Preserve
suppression while resolving the contract. `/segments` is absent in this checkout
and still needs an API implementation.

The completion metric is now `demo-1.1.0`: completed disposition plus verified
Encounter, Procedure or DiagnosticReport evidence and reviewer authorization.
Booking or attendance alone does not count. Do not infer completed milestones
from a generic closed case.

You retain ownership of draft CarePlan/review Task creation, owner and deadline,
reviewer activation, authorized ServiceRequest creation, Appointment handling,
verified closure evidence, and the one-minute overdue check that preserves
ownership and creates one escalation per missed deadline. Existing actions use
`expected_revision`; the requested target contract names `expected_version`.
Record the agreed API contract and coordinate any consumer change with Mark.

## 7. Verification and remaining acceptance gates

The recorded run for this change set was **286 passed, 16 skipped**: 273 AI
unit/contract tests and 13 integration tests against the real FastAPI application
using isolated in-memory SQLite and stub FHIR. The 16 optional external-backend
checks lacked a configured target/fixture mapping. These are prior execution
results, not a fresh run performed while drafting this document.

From `ai/`, with the documented test dependencies installed:

```bash
.venv/bin/python -m pytest -q --ignore=tests/integration
.venv/bin/python -m pytest -q --require-backend -m api_integration tests/integration
.venv/bin/python -m pytest -q
```

See [recorded evidence](../../docs/03-evidence/alfred-safety/checks.md) and
[`BACKEND_BRIDGES.md`](BACKEND_BRIDGES.md) for opt-in HTTP acceptance commands.
That guide also contains older checkout findings; do not treat those historical
results as proof for this build. No hosted model quality, real HAPI transaction,
PostgreSQL concurrency or production authorization was validated.

Before calling the integration complete, supply evidence for:

- Two competing workers, lease expiry, worker restart and rejected stale writes.
- Accept/correct/reject through authenticated endpoints, exact-command replay,
  changed-payload conflict, stale proposal version and reviewer substitution.
- Crash/timeout around HAPI commit with reconciliation and no duplicate facts.
- Reviewed commit changing a subsequent persisted/read-back evaluation; pending
  and rejected proposals excluded; all four canonical outcomes retained.
- Graph version/permission change between discovery and disclosure; refresh
  enqueue failure visible as unknown without leaked references.
- Appointment-only closure rejection, unauthorized closure rejection and
  successful closure only with verified evidence and reviewer sign-off.
- Suppression across overview, segments and exports, plus repeated-query checks.
- Overdue escalation retry/restart without duplicate escalation or lost owner.

## 8. Decisions and return handoff

Please record the integration commit/build, supported run mode and startup
command; the authenticated identity and partition-binding contract; actual
source/review/evaluation response examples; model endpoint protocol/revision;
context verifier/refresh callback implementation; analytics publication-family
definition; and test evidence with remaining failures/skips.

Alfred retains rule semantics, extraction validation, mapping collaboration and
AI-side contract changes. Mark owns frontend consumption. Production policy
integration will need a jointly reviewed codec: current HTTP security adapters
explicitly identify the synthetic guest policy and must not simply be relabelled
as production. QuestionnaireResponse mapping remains unsupported until an
approved versioned Questionnaire and answer mapping are supplied.

This draft is a repository handover, not a sent message or a deployment approval.
The broader existing [backend gap register](../../docs/00-reference/ismail-gap-handoff-draft.md)
remains useful historical context; the concrete delivery and test scope for this
session is recorded in [SAFETY_IMPLEMENTATION.md](SAFETY_IMPLEMENTATION.md).
