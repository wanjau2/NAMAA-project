# Alfred safety checks — 19 November 2026

Base: `bf754f1`, plus the accompanying working-tree changes. Python 3.14 virtual
environment at `ai/.venv`; all data synthetic. No live HAPI, MedGemma, graph,
guideline service or PostgreSQL deployment was exercised.

Run from `ai/`:

```text
.venv/bin/python -m pytest -q --ignore=tests/integration
273 passed in 0.72s

.venv/bin/python -m pytest -q --require-backend -m api_integration tests/integration
13 passed, 16 deselected in 1.91s

.venv/bin/python -m pytest -q
286 passed, 16 skipped in 2.77s
```

The final combined run includes the 273 unit/contract tests and 13 tests against
the real FastAPI application with an isolated in-memory SQLite database. The 16
skips require an explicitly selected external backend URL or rule fixture mapping.
Local API checks initially stalled in the sandbox's AnyIO event loop; the approved
run outside the sandbox passed. `git diff --check` passed.

| Safety requirement | Evidence and limit |
| --- | --- |
| Injection cannot authorize writes/review | `ai/tests/test_safety_boundaries.py`: instruction-like extracted facts are blocked; proposals cannot be mapped or evaluated directly. No actual model quality claim. |
| Unreviewed proposals do not affect rules | `ai/tests/integration/test_safety_acceptance.py`: queued fixture extraction creates staged proposals, leaves FHIR-stub rows unchanged and preserves the evaluation result. |
| Family remains family | Package integration test accepts a family fact, maps only FamilyMemberHistory plus Provenance, simulates a committed version and routes adult evaluation. Missing screening history remains needs-review. |
| Graph is never authority | `ai/tests/test_relate_graph.py`: verification is called on every request; current verified versions replace index hints; stale/denied/missing sources produce unknown and request refresh. Existing real-API tests reject cross-patient graph hints. HAPI itself is stubbed. |
| Booking cannot complete care | API acceptance rejects Appointment evidence, absent sign-off and coordinator closure; stage and revision remain unchanged. Full external evidence verification remains backend work. |
| Small-cell protection | Pure policy tests suppress small numerators/complements and every related numeric margin; API checks confirm small-cohort values and denominators are null. The new publication-family policy is not wired into the API. |
| Retrieval is bounded | Multiple passages of one document survive, exact duplicates collapse, conflicting versions fail closed, ranker-invented IDs are ignored, and approved guidance shares the item/text budget without becoming patient facts. |
| Extraction schema is strict | Explicit dates only, duplicate JSON keys rejected, wrong deployment identity receives no formatting retry, oversized source rejected before dispatch. |

No changes to `api/`, `web/`, runtime configuration or infrastructure. The
[implementation and handoff](../../../ai/docs/SAFETY_IMPLEMENTATION.md) names the
remaining owner-specific dependencies. No submission, deployment or message was sent.
