# D005 — Trusted context, AuthZEN PDP, enforcement hooks, audit sink

**Date:** 2026-11-18
**Status:** Accepted
**Decided by:** Ismail (backend), for Alfred’s AI security adapter
**Related:** D003 (demo stack), D004 (SSE/outbox), Alfred `namaa_ai` contracts

## Context

Alfred’s AI module defaults to deny and expects AuthZEN 1.0 evaluation, trusted
request context, enforcement before note/model/proposal/review disclosure, and a
protected audit sink. Those values must come from Ismail’s services — never from
request bodies, prompts, or browser flags. The guest demo must remain clearly
**synthetic-only** authorization.

## Decision

1. **Trusted request context** is minted only by the API from the guest/team
   session and membership tables (`GET /api/v1/security/context` and the
   `app.security.context` Python builder). Clients cannot supply authority fields.
2. **PDP** is Ismail’s AuthZEN-shaped endpoint
   `POST /api/v1/authz/evaluation` (and batch `/evaluations`), authenticated by
   session for interactive calls or `X-Namaa-Service-Token` for workers.
   Missing/indeterminate → **deny**. Policy revision `synthetic-policy-v1`;
   every decision returns a `decision_id`.
3. **Enforcement** is the Python interface `authorize(action, …)` used by routers
   and workers before note retrieval, model dispatch, context retrieval, proposal
   disclosure, excerpt export, and human review. Queued jobs store the initiating
   principal snapshot and re-authorize at claim and before result return.
4. **Audit sink** is `POST /api/v1/audit/events` (service-auth) plus durable
   `audit_events` rows — no note text, tokens, or full prompts.
5. **Relate/FHIR boundary** is
   `POST /api/v1/security/verified-context`: backend re-checks patient scope and
   source versions; graph-derived hints never grant access; stale/revoked
   suppressed.
6. Guest adapter identity is always
   `policy_adapter=synthetic_guest_v1` with `production_authorization=false`.

## Consequences

Alfred wires `namaa_ai.security` to these endpoints/interfaces and adds security
acceptance tests. Submission must state guest authz is synthetic demonstration
only.
