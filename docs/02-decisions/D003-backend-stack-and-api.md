# D003 — Backend stack, API paths, and metrics suppression

**Date:** 2026-11-18
**Status:** Accepted
**Decided by:** Ismail (backend owner), for team confirmation at next check-in
**Resolves:** OPEN-QUESTIONS Q1 (partial), Q5, Q8

## Context

The three-day work plan and the full design specification disagree on backend stack
(SQLite vs PostgreSQL + HAPI), API path prefixes, and where small-cell suppression runs.
Mark’s frontend already ships against contract-matching mocks and a local action registry
in `web/lib/case-actions.ts`. The release gate requires both synthetic journeys on one
build with a server-authoritative workflow — not a full FHIR platform in 18 hours.

## Decision

We will ship the **demo-critical path** as **FastAPI + SQLite** under
**`/api/v1/...`**, with **server-side small-cell suppression** on analytics responses.
Clinical payloads keep FHIR-shaped identifiers and resource references so a later HAPI
gate remains possible. MedGemma and a live HAPI server are **out of the critical path**
for this sprint (see Q3). Action names and roles match Mark’s `ActionId` registry
verbatim.

Authoritative endpoints:

| Method | Path |
| --- | --- |
| GET | `/health` |
| POST | `/api/v1/demo/sessions` |
| POST | `/api/v1/demo/reset` |
| GET | `/api/v1/cases` |
| GET | `/api/v1/cases/{id}` |
| POST | `/api/v1/patients/{id}/evaluations` |
| POST | `/api/v1/cases/{id}/actions` |
| GET | `/api/v1/analytics/overview` |

Mutations carry `action`, `expected_revision`, `request_id`, and `data`. Errors return
`code`, `message`, `field_errors`, and `request_id`.

## Options considered

| Option | Pro | Con | Why not chosen |
| --- | --- | --- | --- |
| Full design-spec stack (Postgres + HAPI + worker) | Matches long-term architecture | Exceeds three-day budget; blocks Mark | Deferred; FHIR shapes retained in seed/API |
| Work-plan paths without `/api/v1` | Shorter URLs | Conflicts with design spec; harder to version | Rejected in favour of versioned prefix |
| Frontend-only metrics suppression | Faster to paint | Leaks true counts in network responses | Rejected; suppression is an API duty |

## Consequences

- Mark can configure one API base URL and delete the local action stand-in at F4.
- Submission must state: **HAPI not deployed**; clinical store is application SQLite with
  FHIR-shaped synthetic IDs.
- Alfred’s rules module is imported in-process; no separate AI service on the critical path.
- Complementary `n < 10` suppression is computed in the API; the UI renders only what it receives.

## Revisit when

A confirmed deadline longer than three focused days, or a clinical sponsor requiring real
FHIR persistence for the demo, would reopen Q1 toward HAPI + PostgreSQL.
