# D004 — Extraction SSE and FHIR outbox compensation

**Date:** 2026-11-18
**Status:** Accepted
**Decided by:** Ismail (backend owner)
**Resolves:** design-spec §5 polling UX; §7/§10 dual-store recovery

## Context

The UI theme and frontend roadmap assumed a **2-second poll** against extraction jobs
and a **90s timeout**. Polling every client hits the API (and thus the DB) for the same
job. Separately, the design specification requires journaling a command before a FHIR
transaction and reconciling after crashes — without an automated compensator, orphaned
journals accumulate until a human restarts the worker.

Live MedGemma and HAPI remain optional per [D003](D003-backend-stack-and-api.md); the
contracts and workers must still be real so Mark can drop polling and dual-write safety
is demonstrable against a FHIR gateway stub.

## Decision

1. **SSE (not WebSockets)** for extraction progress: `GET /api/v1/extractions/{id}/events`
   streams `progress` and `terminal` events. Clients open one `EventSource` per job;
   the API publishes from an in-process hub while the worker updates durable job state
   sparsely (state changes + heartbeat ≤ every 5s), not on every tick.
2. **Transactional outbox** on the application database for every mutation that intends a
   FHIR write. An outbox worker applies the journaled Bundle through the FHIR gateway
   stub (swap for HAPI later), with bounded retries, lease-based claiming, idempotent
   replay by `request_id`, automated compensation for uncertain outcomes, and a
   **dead-letter** state with an ops retry endpoint.

## Options considered

| Option | Pro | Con | Why not chosen |
| --- | --- | --- | --- |
| Keep 2s HTTP polling | Already sketched in UI docs | Hammers DB; worse under many guests | Replaced by SSE |
| WebSockets | Bidirectional | Overkill for one-way progress; harder with proxies | SSE sufficient |
| Manual restart reconciliation only | Simple | Orphans wait for humans | Automated compensator + DLQ required |

## Consequences

- Mark’s Phase B2 should subscribe to SSE instead of polling.
- Submission can claim real-time extraction progress and dual-store recovery **against the
  gateway stub**; live MedGemma/HAPI remain separately labelled when enabled.
- Ops surface: `GET /api/v1/ops/outbox`, `POST /api/v1/ops/outbox/{id}/retry`.

## Revisit when

A second API replica is required (in-process SSE hub must become Redis/NATS), or a real
HAPI partition replaces the gateway stub.
