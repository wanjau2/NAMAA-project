# M02 — Backend foundation (Ismail)

**Date:** 2026-11-18
**Owner:** Ismail
**Status:** Built (demo path)

## Summary

Ship a runnable FastAPI + SQLite demo API that is the authoritative source of truth
for case workflow, matching Mark’s action registry and seed case IDs.

## Built

- Decision [D003](../02-decisions/D003-backend-stack-and-api.md): stack, `/api/v1` paths, server-side suppression
- `api/` FastAPI app with health, guest sessions, reset, cases, actions, evaluations, analytics
- Seed fixtures aligned with `web/lib/mock-data.ts` (`case-0001`…`case-0006`)
- Workflow engine: role gates, revision checks, idempotent `request_id`, evidence-backed completion
- Deterministic rules stub in `api/app/rules/` (replaceable by Alfred)
- Setup guide: [api/README.md](../../api/README.md)
- Action/role handoff: [api-actions-and-roles.md](../00-reference/api-actions-and-roles.md)
- Automated checks: `api/tests/test_api.py` (6 passing)

## Mocked / deferred

- HAPI FHIR server and PostgreSQL (designed-not-built for this sprint)
- MedGemma extraction worker
- Production authentication (guest session header only)
- Alfred’s final rules package (stub in place)

## Evidence

Run from `api/`:

```text
pytest -q
# 6 passed
```

## Unblocks

- Mark Phase C (swap mocks for real API) once client points at `/api/v1`
- Alfred fixture wiring via `POST /api/v1/patients/{id}/evaluations`