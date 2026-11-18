# M03 — Extraction SSE and FHIR outbox compensation

**Date:** 2026-11-18
**Owner:** Ismail
**Status:** Built (against offline fixture + FHIR gateway stub)

## Summary

Replace planned 2s extraction polling with SSE, and formalize the application DB ↔ FHIR
boundary with a transactional outbox, automated retries, compensation, and dead-letter
handling ([D004](../02-decisions/D004-sse-and-outbox.md)).

## Built

- `POST /api/v1/documents/{id}/extractions` → 202 + job id
- `GET /api/v1/extractions/{id}/events` — SSE `progress` / `terminal` (session via header or `?session=`)
- Background extraction worker with sparse DB writes + in-process event hub
- Offline-fixture proposals labelled `offline-fixture-v1 (no live inference)`
- Outbox entries for `close_as_completed` / `approve_pathway`
- FHIR gateway stub with idempotent `request_id` replay
- Compensating state + DLQ + `POST /api/v1/ops/outbox/{id}/retry`
- Frontend helper `web/lib/extraction-sse.ts`
- Tests: 8 passing including SSE terminal frame and DLQ retry

## Mocked / deferred

- Live MedGemma endpoint
- Real HAPI FHIR server (stub store only)
- Multi-replica SSE fan-out (Redis/NATS)

## Evidence

```text
cd api && pytest -q
# 8 passed
```
