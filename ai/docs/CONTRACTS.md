# Backend and frontend handoff

Contract version: package `0.1.0`, prompt `extract-v1.0.1`. Schemas are in
[`../examples/schemas`](../examples/schemas). Python's Pydantic 2 dependency matches
the API's pinned major and version. This package has no dependency on FastAPI,
SQLAlchemy, React or the backend's application models.

## Public data and internal authority

| Contract | Example | Direction |
| --- | --- | --- |
| ExtractionRequest | `extraction-request.json` | Backend-authorized immutable source → worker |
| ExtractionProposal / ExtractionResult | `extraction-proposal.json`, `extraction-result.json` | Worker → application proposal store → review UI |
| ReviewCommand | `review-accept.json`, `review-correct.json`, `review-reject.json` | UI intention → authenticated backend |
| ReviewedFact | `reviewed-fact.json` | Trusted review logic → deterministic mapper |
| RuleSnapshot | `rule-input-snapshot.json` | Authorized committed FHIR gateway → evaluator |
| RuleEvaluation | `rule-evaluation.json`, `rule-needs-review.json` | Evaluator → backend → UI |
| RuleEvaluationHandoff | `rule-evaluation-handoff.json` | Lossless canonical result with an explicitly limited legacy flag projection |
| VerifiedContext | `verified-context.json` | Backend verification layer → optional explanation boundary |
| ContextItem / ContextQuery / AssembledContext | Typed contracts | Verified sources → optional explanation context assembler |

All examples are under `examples/`. Authorization fields in **internal** snapshot
and context contracts are assertions made by Ismail's trusted adapter. They are
not evidence of authentication and must never be accepted as user or model input.
Likewise, a serialized ReviewedFact is not a bearer authorization token. Load it
from the trusted review store; do not accept it from a client as proof of review.

## Extraction

The backend must bind workspace and patient to the authenticated session, fetch
the permitted source text/version and populate the extraction request. Model
output contains only `facts`; it cannot control IDs, source metadata, offsets,
review state or model identity. Server-generated proposals bind the immutable
source ID/version, SHA-256 text hash, patient/workspace, model revision and prompt.
Store proposals and failed jobs in the application database, outside FHIR.

`value_text` is the original verbatim statement. `excerpt` includes full supporting
sentence/line context. Concepts are `last_wcv`, `last_adult_screening`,
`caregiver_concern`, `tobacco_use`, `family_condition` and
`documented_condition`. Subject, assertion,
proposed resource type and relationship have closed enums. Effective date is an
explicit full date or null; document date never supplies a missing event date.

Results distinguish `success`, `no_supported_facts`, `invalid_output`, and
`transport_failure`. Source-invalid proposals can be returned with blocking issues
for correction/rejection. A no-facts success is about these supported extraction
categories only, never “no care gap.” No result authorizes an action.

## Review and transactions

`apply_review(request, proposal, command, current_version=..., reviewed_at=...,
authorizer=...)` defaults to deny. Implement `ReviewAuthorizer.require_review` using
the backend's current session, patient/workspace access, clinical-review permission
and reviewer identity. An administrator role alone is insufficient.

Review commands require a request ID, proposal ID, expected integer proposal
version, reviewer reference and nonempty reason. `correct` supplies a complete
replacement ProposedFact and undergoes the same source checks. `accept` cannot
override a blocking issue. Review-level issues (missing date, uncertainty,
historical or conflicting statements) must be explicitly acknowledged by code.
Acknowledgment preserves uncertainty; it does not repair a missing date or resolve
conflicting committed resources for rules. Reject returns no ReviewedFact and no
FHIR resource. Record rejected commands in the backend command/audit store.

The pure function checks the supplied current version; **Ismail must load, lock,
compare-and-swap and journal that version atomically**. Repeated request IDs with
the same payload must return the saved result; reuse with a different payload must
fail. The module does not implement persistence, concurrent review serialization
or distributed transaction recovery.

`propose_transaction(reviewed_fact)` returns two entries: reviewed resource and
Provenance. Stable UUIDs derive from workspace, patient, proposal and review
request. Clinical concept text is preserved without invented terminology codes.
An Observation carries assertion in a labelled component, its verbatim value and
an optional explicit event date. `final` status is not proof of human review.
Positive/historical relative statements become FamilyMemberHistory conditions;
absent/uncertain family statements stay in its note and do not assert a condition.
FamilyMemberHistory remains `partial`; reviewing one statement does not establish
complete family history. A patient `Condition` proposal is permitted only when
the source explicitly says the patient is currently diagnosed; it preserves the
verbatim statement as `code.text` without inferring a clinical/verification
status or terminology code. It remains outside FHIR until human review and is
not consumed by either demonstration rule. This does not authorize MedGemma to
diagnose.

Provenance targets the resource and records the source DocumentReference history
version, source hash, review action/reason, human reference and contained Device.
Device versions record the model revision and prompt version. The model Device is
separate from the human reviewer. The application journal retains original and
corrected proposals. Local reference checks are not workspace authorization.

Before transaction execution, resolve existing IDs and reference permissions,
validate base R4 and the applicable profiles, add version preconditions to updates,
and journal the intended transaction. Read committed resource versions back from
HAPI before making a RuleSnapshot. Never manufacture canonical versions from a
proposal Bundle. The demo performs this step through an explicitly named simulator.

Suggested backend API surfaces (Ismail — D005 security handoff):

| Endpoint | Backend action |
| --- | --- |
| `POST /api/v1/documents/{id}/extractions` | Authorize and queue; return 202/job ID |
| `GET /api/v1/extractions/{id}` | Return scoped job status and stored proposals |
| `POST /api/v1/facts/{id}/review` | Authenticate, bind identity, journal ReviewCommand and apply review |
| `POST /api/v1/patients/{id}/evaluations` | Retrieve authorized reviewed resource versions and evaluate |
| `GET /api/v1/security/context` | Trusted request context (backend-minted) |
| `POST /api/v1/authz/evaluation` | AuthZEN 1.0 PDP (synthetic_guest_v1) |
| `POST /api/v1/audit/events` | Protected audit sink |
| `POST /api/v1/security/verified-context` | Scope + version check before Relate/context disclosure |

Full wiring notes: [`../../docs/00-reference/authz-audit-integration-for-alfred.md`](../../docs/00-reference/authz-audit-integration-for-alfred.md).

Map PermissionError to 403; `stale_proposal_version` or changed source to 409;
schema/source/review errors to 422; exhausted transport to failed job/503. Preserve
the API's existing `code`, `message`, `field_errors`, `request_id` envelope. Do not
log raw Pydantic errors, notes, model payloads or HTTP exception details. Sanitize
errors before responding. No extraction HTTP routes were added to `api/`.

## Mark's UI adjustments

The existing source-review fixtures are flat; the new proposal's extracted fields
are under `fact`. Metadata uses `source_document_id`, `source_document_version`,
`offset_start`, `offset_end`, and `model`. Source/FHIR versions are opaque strings;
proposal concurrency versions are integers. Do not parse or sort FHIR versions.

Offsets are zero-based, end-exclusive **Unicode code points**. In JavaScript use
`Array.from(note.text).slice(start, end).join("")`, or convert explicitly to UTF-16
indices. Null offsets indicate a failed/ambiguous source match; never highlight an
arbitrary first occurrence. Display all issues, the complete source and simulated
badges. Render note text as text, not HTML. The UI may collect acknowledgments but
cannot override backend authorization or validation.

Display outcomes as “Gap identified”, “No gap identified in available data”,
“Needs review”, and “Not eligible”. The current API/frontend enum lacks the fourth
outcome; integration must preserve it rather than force it into `gap`/`no_gap`.
Display no-gap wording exactly with its available-data limitation. Existing UI
fact verification defaults are not accepted as authoritative review receipts.

`prepare_rule_handoff()` retains the complete canonical `RuleEvaluation` (rule
ID/version, all input resource versions, factors, missing information, due date
and simulation marker) and adds a legacy `flag_status` projection only for
outcomes representable by Ismail's current enum. `not_eligible` gets a null
projection and `api_outcome_extension_required`; it is never coerced to `no_gap`
or `needs_review`. This envelope is an Alfred-to-backend integration contract,
not a direct `EvaluationResult` response: that API response has additional
required fields and does not retain Alfred's complete provenance. Ismail must
persist the canonical nested result or extend the API schema before wiring the
evaluation into API persistence/UI flows.

## Optional context

`VerifiedContextAdapter` and `ContextAssembler` are disabled by default. Enabling
is an explicit backend composition choice only after Ismail supplies a tested
verification contract.
The adapter requires matching workspace/patient/generation/permission revision,
current authorized verified state, bounded verification times and valid per-record
authorization and source verification. It returns source references, versions,
generation information and completeness with `exhaustive: false` and
`absence_claims_allowed: false`, including for an empty context. Completeness means
only the backend's checked scope. Ismail must reauthorize and verify current HAPI
versions immediately before disclosure; the adapter cannot do those checks itself.
The offline assembler treats each FHIR resource as its own retrieval unit, uses
deterministic lexical ranking and accepts an optional dense-ranking adapter for
rank fusion. It does not select a vector vendor, create embeddings, or connect to
Relate. Retrieved context is only for optional explanation; it is not connected
to extraction or rules. Empty retrieval remains unknown, never a no-gap result.
