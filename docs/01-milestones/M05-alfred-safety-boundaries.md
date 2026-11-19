# M05 — Alfred extraction and evaluation safety boundaries

**Date:** 2026-11-19
**Owner:** Alfred
**Status:** Partial
**Gate:** Reviewable intelligence and reliability/isolation, AI-package portion

Alfred's package now rejects ambiguous model wire data, preserves document
passages during bounded retrieval, separates approved guidance from patient
facts, and exposes explicit unknown/refresh outcomes for graph verification.
Reviewed family-history commits route adult re-evaluation without creating a
patient Condition. A pure population policy suppresses related numeric margins,
and completion metrics require evidence plus reviewer authorization.

| Item | Status |
| --- | --- |
| Extraction, context, rule routing, suppression code and Pydantic schemas | Built in `ai/` |
| Package test verifiers, guideline corpus and FHIR commits | Synthetic fixtures |
| PostgreSQL leases, real HAPI transactions, production identity, refresh queue and endpoint wiring | Ismail integration pending |

Verification: **286 tests passed; 16 optional live checks skipped**. See
[commands, scenarios and limits](../03-evidence/alfred-safety/checks.md).
No frontend or deployment checks are claimed. No existing API implementation
was changed.

The existing canonical outcome vocabulary and synthetic rule intervals remain.
The completion metric definition is `demo-1.1.0`; context item IDs now distinguish
passages. New guideline, graph-resolution and suppression schemas are published
alongside existing contracts. Nothing was sent to teammates; the
[concrete handoff](../../ai/docs/SAFETY_IMPLEMENTATION.md) is ready for review.
