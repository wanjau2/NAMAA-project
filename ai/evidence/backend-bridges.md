# Backend bridge verification — 2026-11-19

## Continued Alfred validation

- Added a review guard that rejects a supplied proposal from a different
  session workspace before making any mutation request.
- Expanded HTTP-client Relate checks for cross-workspace discovery, unverified
  and mixed supporting references, generation/patient mismatch, unauthorized
  records and incorrectly typed or production authorization flags.
- Focused client tests: **86 passed**. Final full AI suite: **225 passed,
  16 skipped** (opt-in live checks lack target/fixture configuration).
- Added `ai/scripts/check_backend.py`: a reproducible isolated-local or
  explicitly targeted deployment runner with required checks, temporary server
  cleanup, a failing exit code on rejection, and payload-free JSON reporting.
- Executed the local runner: **1 passed, 11 failed, 4 deselected**, exit 1.
  The selected failures have the same causes recorded below. Compact evidence
  is in [backend-acceptance-local.json](backend-acceptance-local.json).
- Confirmed missing target configuration exits 2 without running the suite.
  `git diff --check` passed. GitHub branch listing contains only unchanged
  `main`; no newer backend branch or deployed URL has been supplied.

## Alfred follow-up: strict review responses and acceptance coverage

Scope of this follow-up: AI clients, tests and documentation only. No additional
backend or frontend changes were made. GitHub main still reports `a9b9e1e`; no
synthetic deployment URL is configured. The backend revision/URL request remains
unanswered, so deployed compatibility is not claimed.

`BackendReviewResult` now validates the existing canonical `ReviewDecision`
shape: exact submitted command, action/state correspondence, integer version
increment, required accepted/corrected fact, null rejected fact, and consistent
nested review. Passing the original proposal binds its full source and scope.
API extensions are retained without inferring HAPI commit. Command replay is
explicit; transport failures never trigger an automatic review retry.

| Follow-up check | Observed result |
| --- | --- |
| Focused backend client suite | 67 passed |
| Full AI suite, including real API integration | 206 passed, 16 skipped (unconfigured opt-in live checks) |
| Required in-process API integration command | 8 passed, 16 deselected |
| Required live-security checks without a URL | 2 configuration errors, exit 1; confirms required runs cannot pass on skips |
| Expanded HTTP acceptance against temporary localhost Uvicorn | 1 passed, 11 failed, 4 deselected |

The HTTP failures identify these current backend blockers:

- Six review acceptance/replay/conflict/role checks stop before review because
  extraction returns flat proposals rather than the required nested contract.
  They do not prove anything about review endpoint behavior. OpenAPI separately
  confirms that the review route is missing.
- Two evaluation checks fail because `rule_evaluation`, `legacy_flag_status`,
  and `api_compatibility` are absent from the response.
- Both Relate discovery operations return HTTP 404.
- The audit boundary event's exposed `decision_id` is null. The old live test
  incorrectly allowed a different PDP event to satisfy the decision-link check;
  the replacement checks the boundary event itself and fails visibly.

Actual HTTP AuthZEN Permit/Deny decoding, revision metadata and verified-context
parsing pass. The server used a disposable database and was shut down afterward.

Four additional live rule-outcome tests are ready but require Ismail's seed
mapping (`NAMAA_AI_TEST_RULE_CASES`) for all outcomes, including `not_eligible`,
in fresh guest sessions. All four outcomes and inconsistent/lossy response
rejection are already covered by client unit tests. Live correction tests a
complete replacement of the same source fact; the unit suite exercises a
changed-value correction through the real AI review module.

Remaining external acceptance evidence: actual deployed review/Relate response
shapes, passing live accept/correct/reject and conflict tests, four seeded rule
outcomes, and backend durable read-back/restart checks. HAPI commit stays stubbed.

## Initial bridge verification

Base checkout: `a9b9e1e`. All data and authorization were synthetic. No model
endpoint or HAPI transaction was used.

| Check | Observed result |
| --- | --- |
| `python -m pytest -q ai/tests` | 183 passed, 2 skipped (opt-in HTTP tests had no URL) |
| Real API integration subset, included above | 8 passed using FastAPI, its PDP/audit routes, and isolated SQLite |
| `PYTHONPATH=api:ai/src python -m pytest -q api/tests` | 14 passed; one upstream AnyIO deprecation warning |
| Final focused bridge tests after adding URL dot-segment rejection | 46 passed |
| `live_security` against a temporary localhost Uvicorn server | 1 passed, 1 deselected; actual HTTP context, Permit/Deny decoding, audit persistence and verified context |
| Running server OpenAPI preflight | Review and both Relate discovery routes absent; canonical evaluation fields absent |
| `git diff --check` | Passed |

API tests needed execution outside the filesystem/network sandbox because its
socket restrictions stalled FastAPI's worker-thread event-loop wakeup. The
temporary HTTP server used a disposable SQLite database and was stopped after
the check. No connected deployment URL was supplied.

The new unit wire tests verify nested extraction proposals, complete review
commands and propagated errors, all four canonical rule outcomes (including
`not_eligible`), and discovery followed by authoritative context verification.
Those mock-transport tests are not evidence that the announced newer backend
deployment accepts the client contracts.

The real API tests exposed and now cover two verified-context defects: graph
hints/narrative could include another patient's FHIR resource, and truncated
verification timestamps could reject freshly stored resources. The API now
requires an exact supported FHIR patient link and preserves timestamp precision.

Pending: run `live_bridges` against the branch or URL containing the announced
review, nested extraction, canonical rule and Relate operations. Confirm the
Relate batch and review response contracts there. HAPI commit remains stubbed.
