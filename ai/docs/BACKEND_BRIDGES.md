# Synthetic backend bridges

`namaa_ai.backend.BackendApiClient` extends the security HTTP client. Construct
it with the API origin and `X-Namaa-Session`; optional `X-Namaa-Service-Token`
and `X-Namaa-Role` headers are forwarded. HTTPS is required except for local
development/test hosts. `from_env(headers)` reads `NAMAA_API_BASE_URL`. The
client does not load `.env`, retry mutations, or fall back to
`LocalSyntheticPolicy`, which remains a unit-test fixture only.

```python
from namaa_ai.backend import BackendApiClient
from namaa_ai.security import SecurityEnforcer

backend = BackendApiClient.from_env(session_headers)
context = await backend.trusted_context()
enforcer = SecurityEnforcer(backend, backend)
```

The enforcer calls `POST /api/v1/authz/evaluation` for every boundary and
`POST /api/v1/audit/events` for audit delivery. The AuthZEN codec requires an
actual boolean decision, a consistent Permit/Deny/Indeterminate extension,
nonempty decision/revision/reason identifiers, `synthetic_guest_v1`, and
`production_authorization=false`. The enforcer compares revisions with the
trusted context. Invalid decisions and audit failures deny access. Audit source
versions are a resource-reference-to-opaque-version map. The context request ID
is propagated to the policy and audit endpoints.

## Extraction, review and rules

- `backend.fetch(...)` supplies authorized document text to
  `AuthorizedExtractionPipeline(enforcer, backend, model_adapter)`.
- `backend.extraction_job(job_id)` reads one status snapshot and validates each
  nested `ExtractionProposal`, including `fact`, `model`, `source_sha256`,
  `offset_unit`, `issues`, source version, workspace and patient. Flat proposals
  are rejected. Use the API SSE stream for ongoing job progress.
- `await backend.review(command)` sends the complete explicit `ReviewCommand`
  to `POST /api/v1/facts/{proposal_id}/review`. The API owns reviewer binding,
  authorization, idempotency, version checks and persistence. HTTP errors,
  including stale-version conflicts, propagate without retry. It returns a
  typed `BackendReviewResult` based on Alfred's existing `ReviewDecision`:
  `command`, `resulting_proposal_version`, `state`, and `fact` are required.
  The response must echo the exact submitted command, increment its expected
  version by one, match the action to the resulting state, and contain a
  consistent reviewed fact for accept/correct (null for reject). Pass
  `proposal=proposal` to also bind the returned original proposal, source and
  workspace to the one reviewed. A supplied proposal from a different workspace
  is rejected before the mutation is sent. Extra API metadata is preserved in
  `result.model_extra`; it is not interpreted as proof of commit. This concrete
  contract still requires confirmation against Ismail's deployed response.
- `await backend.evaluate(patient_id)` calls the patient evaluations endpoint.
  The required `rule_evaluation` is validated losslessly, including
  `not_eligible`, versions, factors, missing information and due date. Legacy
  fields must agree with `prepare_rule_handoff`. Persist
  `result.rule_evaluation.model_dump(mode="json")` in the owning backend store;
  the AI module does not create a second persistence layer. Legacy-only
  responses are rejected.

**HAPI commit is still stubbed.** An accepted review, mapped Bundle, queued
outbox command or successful synthetic API response is not evidence of a real
HAPI transaction.

A timeout or invalid response after sending review leaves the remote outcome
unknown. Retain the original command/request ID for backend read-back or an
explicit idempotent replay. The client does not generate a new request ID or
retry automatically. A changed payload must not reuse an existing request ID.

## Relate discovery and verification

`family_history_context(patient_id)` and `care_plan_context(patient_id)` call
the fixed `/api/v1/relate/family-history` and `/api/v1/relate/care-plans` GET
operations with `patient_id` and bounded `limit`. The client uses the existing
`RelateCandidateBatch` contract; compatibility with the announced deployment
remains to be checked. No arbitrary graph query is accepted.

After every valid discovery response, including empty or stale batches, the
client runs `RelateResolver`. Verification uses `POST /api/v1/security/verified-context`
with scoped references as hints. Failed, stale or unauthorized support becomes
`state=unknown` with no items and `refresh=requested` (or `failed`).
`family_history_context` / `care_plan_context` return `.items` only. Prefer
`family_history_resolution` / `care_plan_resolution` so unknown is not mistaken
for absence. Relate never grants access.

The API verified-context builder checks the exact FHIR `subject.reference` or
`patient.reference` for supported resource types. A graph hint or patient
mention in narrative cannot include another patient's record. It also preserves
subsecond verification timestamps so freshly stored resources do not fail the
freshness check because of truncation.

## Running checks

One command from the repository root starts an isolated local synthetic API,
runs the required HTTP checks, writes compact evidence, and shuts the server
down. Its database is temporary; fixture extraction and FHIR stub modes are
explicitly selected:

```bash
ai/.venv/bin/python ai/scripts/check_backend.py --local \
  --report ai/evidence/backend-acceptance-local.json
```

For Ismail's deployment, replace `--local` with `--api-url <synthetic-api-origin>`
or set `NAMAA_AI_TEST_API_URL`. Add `--rule-cases /path/to/backend-seed-cases.json`
to include all four canonical outcomes. The command requires a selected target,
preserves a failing exit code, and reports missing OpenAPI routes. It still runs
the HTTP checks if OpenAPI is unavailable. The saved report contains test names
and statuses, without response bodies, credentials, source text, or tracebacks.

The current local stack produces exit code 1: AuthZEN passes, and eleven
acceptance checks expose the older backend contracts and audit-link gap. These
are recorded failures, not expected-failure markers or skipped acceptance.

From `ai/`:

```bash
python -m pip install -e '.[test]' -r requirements-integration.txt
python -m pytest -q
python -m pytest -q --require-backend -m api_integration
```

`tests/integration/test_api_security.py` runs real FastAPI routes, PDP and audit
storage with an isolated SQLite database through ASGI. It does not mock policy
decisions or HTTP response bodies. These tests explicitly skip if API
dependencies are absent. `tests/test_backend.py` uses mock transports to check
the announced bridge contracts; those tests do not prove deployed integration.

To check a deliberately selected synthetic stack over HTTP:

```bash
NAMAA_AI_TEST_API_URL=http://127.0.0.1:8000 \
  python -m pytest -q --require-backend -m live_security tests/integration/test_live_backend.py

NAMAA_AI_TEST_API_URL=http://127.0.0.1:8000 \
  python -m pytest -q --require-backend -m live_bridges tests/integration/test_live_backend.py
```

An optional `NAMAA_AI_TEST_SERVICE_TOKEN` is forwarded without logging it.
`NAMAA_AI_TEST_REVIEWER` defaults to the existing synthetic UI identity,
`Practitioner/demo-reviewer`; set it to the reviewer bound by the target stack.
Every live test creates its own synthetic guest session and checks its trusted
context before review/evaluation mutations. Separate tests cover all three
review actions, exact-command replay, request-ID conflicts, stale versions,
coordinator denial, both seed patients' canonical evaluations, and both Relate
operations. Live correction restates the complete source fact to exercise the
replacement contract; changed-value correction uses the real AI review module
in the unit suite. The live audit check requires the boundary event itself to
expose the decision link, so a separate PDP audit record cannot satisfy it.

Bounded polling is an acceptance-test fallback; application progress uses SSE.
Without a URL, live checks skip explicitly in an ordinary development run.
`--require-backend` makes missing dependencies or selected live-test
configuration fail instead, so required acceptance jobs cannot pass on skips.
It does not enable unselected markers or create backend routes.

To test all four rule outcomes against backend fixtures, obtain Ismail's seed
mapping for patients created in every fresh guest session. Put it in a JSON
file with exactly these keys, each mapping to `patient_id` and optional
`pathway`: `gap_identified`, `no_gap_identified_in_available_data`,
`needs_review`, `not_eligible`. Then run:

```bash
NAMAA_AI_TEST_API_URL=http://127.0.0.1:8000 \
NAMAA_AI_TEST_RULE_CASES=/path/to/backend-seed-cases.json \
  python -m pytest -q --require-backend -m live_rule_outcomes tests/integration/test_live_backend.py
```

These checks assert the canonical outcome and retain `not_eligible` without a
legacy flag. No private backend database is edited to manufacture those cases.
Replay checks verify stable API decisions; restart durability and independent
database/read-back evidence remain backend acceptance work.

At checkout `a9b9e1e`, security/context/audit/verified-context endpoints are
present. The announced facts review and Relate discovery routes, nested
extraction response and canonical evaluation response are absent from the
local API. GitHub main matched that checkout during implementation. The newer
backend branch/commit or deployed URL is needed to confirm end-to-end
compatibility. Do not substitute legacy responses to make those checks pass.
