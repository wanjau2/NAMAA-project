# Alfred's safety implementation — 19 November 2026

## Analysis before implementation

The repository already separates `api/` (Ismail), `ai/` (Alfred), and `web/`
(Mark). The ownership table in the software design specification assigns Alfred
MedGemma, extraction schemas, mapping/provenance, deterministic rules and
evaluation. The user's instruction to do Alfred's role only governs this work.

The AI package already has protected HTTPS inference, a 6,000-code-point note
limit, greedy decoding, 2,048 output tokens, bounded retries, exact quote checks,
explicit authorized review, proposed FHIR transactions and synthetic rules.
The baseline offline suite passes 217 tests. This is software evidence only.

Inspected gaps: dates accept Pydantic coercions; the authorized extraction path
does not bind the returned source ID; context IDs collide for passages from the
same resource version; arbitrary retriever IDs are trusted by assembly; graph
failure has no structured refresh result; no separate approved guideline corpus
exists; adult factors omit family history; suppression exists only as metric
definitions in this package. Completion-rate wording incorrectly equates
attendance with completed care.

## File layout and order

1. Harden `contracts.py`, `adapters.py`, `security.py`, `review.py`: reject
   ambiguous dates, revalidate internal boundary objects, bind source identity,
   preserve format-only repair and review gating.
2. Extend `context.py` and `context_engineering.py`; add `context_assembler.py`
   for approved guidelines and patient passages under shared retrieval budgets.
3. Add `relate_graph.py`: call the backend verification boundary on every
   resolution, suppress unavailable/stale/unauthorized results as unknown, and
   request refresh through an injected backend callback.
4. Extend `rules.py`: retain the versioned fictional schedule, include reviewed
   family-history factors and expose deterministic post-commit rule routing.
5. Add pure `analytics.py` suppression functions and correct the completion
   metric definition. Add unit and integration boundary tests under `ai/tests/`.
6. Publish schemas/examples and record actual verification and backend handoff.

## Integration boundaries

No API routes, database models/migrations, lease worker, HAPI client, clinical
workflow commands, frontend or infrastructure are implemented by Alfred here.
Ismail must connect the existing endpoints to these functions, authenticate
session-derived workspace/partition, persist proposals/evaluations, perform
transactional lease/CAS/idempotency handling, verify current HAPI resources and
permissions, and execute reviewed FHIR Bundles. A successful local mapping or
mocked verification is never represented as a HAPI commit.

Rules consume only backend-authorized reviewed committed snapshots. A family
history commit schedules adult re-evaluation; it does not establish eligibility,
a missing screening date, urgency, or an order. The 37/73-day intervals remain
explicitly fictional. QuestionnaireResponse mapping requires a supplied approved
Questionnaire and answer mapping; this slice refuses to invent one.

FHIR behavior is checked against the pinned [R4 REST specification](https://hl7.org/fhir/R4/http.html)
and [R4 FamilyMemberHistory](https://hl7.org/fhir/R4/familymemberhistory.html).
Strict date parsing follows the distinction between JSON and Python validation
in [Pydantic's strict-mode documentation](https://docs.pydantic.dev/latest/concepts/strict_mode/).
Official profile validation and real HAPI/MedGemma integration remain separate
deployment gates.

## Delivered and verified

The file layout above is implemented. All changes to executable code are under
`ai/`; `api/`, `web/` and infrastructure are unchanged. JSON schemas for the new
contracts are published under `ai/examples/schemas/{analytics,context_assembler,relate_graph}`.
Existing examples were regenerated, including the corrected `demo-1.1.0`
completion metric and passage-specific context IDs.

On base commit `bf754f1` plus this working-tree change:

- Offline AI suite: **273 passed**.
- Required isolated API integration selection: **13 passed, 16 deselected**.
- Combined suite: **286 passed, 16 skipped**. Skips are explicitly configured
  live-backend checks without an external URL/seed mapping, not skipped local
  safety tests. See [verification evidence](../../docs/03-evidence/alfred-safety/checks.md).

The ASGI integration tests initially stalled in the sandbox's AnyIO event loop.
The approved run outside the sandbox passed against isolated in-memory SQLite
and the existing synthetic API. No real patient data or hosted model was used.

## Concrete handoff to Ismail

| Boundary | Alfred's callable/contract | Backend work still required |
| --- | --- | --- |
| Extraction endpoint and durable worker | `AuthorizedExtractionPipeline`, `HostedAdapter`, `extraction.decode_response` | Authenticated initiating principal; session-derived workspace/partition; PostgreSQL atomic lease claim, fencing token and heartbeat covering the 90-second inference budget; bounded job retries; version-bound DocumentReference read; proposals persisted only in the application DB. Do not use the current fixture fallback when hosted inference fails. |
| Fact review | `apply_review`, `propose_transaction` | Session-bound reviewer; command journal and proposal CAS; HAPI transaction with update preconditions; append-only Provenance; reconcile uncertain commits before retry. Local Bundles remain non-executable proposals pending validation. |
| Evaluation | `evaluate`, `rules_for_reviewed_commit` | Replace the API evaluator stub with reviewed HAPI snapshots; invoke routing after confirmed commit; persist complete immutable results and input versions. Family history schedules review, not an order or a diagnosis. |
| Context and guidelines | `ScopedContextAssembler`, `VerifiedGuidelines` | Per-request PEP/PDP and current HAPI verification; approval tied to the exact guideline version; supply verified text/offsets; reauthorize before disclosure or dispatch. No approved real guideline corpus is included. |
| Optional graph | `RelateResolver(verify, request_refresh)` | Implement current-source/permission verification and idempotent authorized refresh enqueue. Legacy tuple-returning clients do not yet use this new boundary. |
| Overview and segments | `suppress_population` | Build one complete fixed publication family, suppress it once, then select endpoint views. Wire `/segments` (absent in this checkout), rebuild projections and enforce cross-release privacy. |
| Care workflow | Existing API acceptance tests and corrected metric definition | Draft CarePlan/Task, reviewer activation and ServiceRequest authorization, verified completion evidence, minute-based escalation, durable command concurrency. Existing API uses `expected_revision`, whereas the requested contract names `expected_version`; resolve this in the API contract. |

The strict PostgreSQL/HAPI production architecture is **not delivered** by this
Alfred-only change. Current endpoint tests establish bounded synthetic behavior,
not FHIR authority, database durability, production access control or clinical
validation. An explicit QuestionnaireResponse mapping remains unsupported until
an approved versioned Questionnaire and answer mapping are supplied.
