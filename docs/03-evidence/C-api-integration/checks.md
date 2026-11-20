# Phase C — API integration: acceptance checks

**Date:** 2026-11-18
**Owner:** Mark (frontend), against Ismail's API ([D003](../../02-decisions/D003-backend-stack-and-api.md))
**Reproduce:**

```bash
cd api && ./.venv/bin/uvicorn app.main:app --port 8000   # terminal 1
cd web && npm run verify:api                             # terminal 2
```

All data is synthetic. Software checks on the API contract, not clinical validation.

## What changed

The frontend's local transition layer is **deleted**. `lib/case-actions.ts` (the 13-action
engine, validation, state mutation, event fabrication) and the seeded `lib/case-store.tsx` are
gone. The server is now authoritative for every transition.

| Removed | Replaced by |
| --- | --- |
| `lib/case-actions.ts` — transition engine + validation | `api/app/workflow/` (server) |
| `lib/case-store.tsx` — local seeded store | `lib/case-store.tsx` — API transport only |
| `lib/mock-data.ts` — cases, details, timelines | `GET /api/v1/cases`, `GET /api/v1/cases/{id}` |
| `scripts/verify-actions.ts` — tested the local engine | `scripts/verify-api-contract.ts` — same scenarios, live API |

What legitimately stayed client-side is `lib/action-catalog.ts`: **presentation metadata only**
(labels, field kinds, option lists, safety caveats) plus a `displayWhen` stage hint, documented
as a hint rather than a rule. All validation was deleted from it.

## Contract checks — 34/34 pass against the live API

| Group | Check | Result |
| --- | --- | --- |
| Reachability | `/health` returns ok and declares synthetic | ✅ |
| Session | A call without `X-Namaa-Session` is rejected | ✅ `401 unauthorized` |
| Session | Guest session created; response carries the `NOT FOR CLINICAL USE` notice | ✅ |
| Seed | 6 synthetic cases; `case-0001` is `identified/needs_review` at rev 1 | ✅ |
| Shape | Case detail nests explanation, factors, missing and events | ✅ |
| **Drift** | **UI catalog and API publish the same 13 action ids** | ✅ |
| **Drift** | **UI catalog and API agree on the role for every action** | ✅ |
| Contract | API publishes the mutation envelope and error shape at `/meta/actions` | ✅ |
| Role | Coordinator cannot approve a pathway | ✅ `forbidden_role` |
| Missing data | `needs_review` blocks pathway approval | ✅ `precondition_failed` |
| Concurrency | Stale `expected_revision` rejected | ✅ `stale_revision` |
| **Closure** | **Booking alone cannot close as completed** | ✅ `invalid_transition` |
| Validation | Missing required field returns `field_errors` | ✅ |
| Happy path | `booked → attended`, revision bumped | ✅ rev 4 → 5 |
| Audit | Event records prior → new state and the request id | ✅ |
| **Idempotency** | **Replayed `request_id` returns the first result, no second event** | ✅ same event id |
| **Idempotency** | **Same `request_id`, different payload is rejected** | ✅ `idempotency_conflict` |
| Closure | Without evidence reference → `validation_failed` | ✅ |
| Closure | Without reviewer attestation → `validation_failed` | ✅ |
| Closure | With evidence + attestation → `closed/completed`, evidence retained | ✅ |
| Counting | A declined case keeps its stage and is not completed | ✅ |
| Counting | `close_other` closes as `clinically_closed_other` | ✅ |
| Reopening | Reopen requires a reason | ✅ |
| Robustness | Unknown action id rejected | ✅ `422` |
| **Suppression** | **Suppressed analytics cells carry no numerator or denominator** | ✅ |
| Suppression | Suppressed cells state a reason and threshold | ✅ |
| Reset | Restores the seed; `case-0002` back to `booked` rev 4 | ✅ |
| Reset | Affects only the calling session | ✅ `cases_restored: 6` |

Ismail's own suite also passes: `cd api && ./.venv/bin/python -m pytest tests/ -q` → 6 passed.

## Frontend verification

| Check | Observed |
| --- | --- |
| Build, both typechecks, lint | All clean |
| `/cases/[id]` is now a dynamic route | Build output shows Partial Prerender, not enumerated params (roadmap C4) |
| Mock worklist data gone from the bundle | `Child B (synthetic)`, `Adult E (synthetic)`, `Three contact attempts failed` — all **GONE** from `/cases` chunks |
| Live API panel on `/metrics` | Renders `GET /api/v1/analytics/overview` results with per-cell suppression |
| Source review labelled | `This screen is not yet server-backed` banner present |
| API status in the simulation bar | Connected / connecting / unreachable indicator |

### Bug found and fixed during verification

The worklist's first paint rendered **"No cases match these filters"** before the first fetch had
started, because `rowsLoading` is false until the request begins. For this product that is not a
cosmetic bug: it reads as an absence of care gaps, which is the one claim the UI must never make.
The skeleton now covers `status === "connecting"` as well. Verified: first paint is
`Loading synthetic cases…`.

## Deliberate choices

| Choice | Why |
| --- | --- |
| `displayWhen` stage hints kept client-side | Avoids offering obviously irrelevant controls. Documented as a hint; the server answers `invalid_transition` if it is wrong, and the UI shows that. Q9 asks for `available_actions` so even this can go |
| Role is the only client-side gate | It prevents offering a control certain to be refused. Preconditions are the server's, and its reason text is what the form displays |
| Session held in memory only | A reload starts a fresh synthetic workspace, matching the guest-session model |
| Server echo is the only state source | A successful action replaces local state with the returned case; nothing is advanced optimistically |
| `/metrics` cards still on a local cohort | The API suppresses all 16 cells at this seed size (below). The cards are labelled as a local fixture and a design reference, not data |

## Open gaps

1. **Analytics seed too small.** `GET /api/v1/analytics/overview` returns **16/16 cells
   suppressed** — correct logic, cohort of 3 per pathway against a threshold of 10. Needs a
   larger synthetic reporting cohort or a stated demonstration threshold. Until then the funnel,
   segments and timeliness views have no server source.
2. **No proposal endpoints**, so source review (A1) stays on fixtures and review decisions are
   not persisted — no `Provenance`, no reviewer identity. Raised as **Q10**.
3. **Analytics shape is thinner than the dashboard renders**: no segment groups, no timeliness,
   no cohort window or refresh time, and no `deferred` / `clinically_closed_other` counts.
4. **Not yet run:** axe-core, keyboard-only journey completion, RTL snapshot, and a
   browser-driven end-to-end pass. Client rendering was verified from served markup and the
   contract suite, not from a real browser session — that is D4/D5/E1.
5. HAPI is not deployed (D003). The submission must say so: the clinical store is application
   SQLite with FHIR-shaped synthetic identifiers.

---

# Addendum — 2026-11-20

The 34/34 table and the open-gap list above are 18 November evidence. Do not rewrite them.

| Later change | Status |
| --- | --- |
| `available_actions` on `GET /cases/{id}` | Live display path; `displayWhen` is last-resort only |
| `GET /cases/{id}/documents` | Authoritative listing; fallback map deleted |
| Fact review persist | Live in the application store; FHIR Provenance still stub |
| Analytics reporting cohort | Publishes; threshold stays ≥ 10 |
| `/metrics` | Live overview + segments; local fixture removed |
| Source review | API + SSE; the “not yet server-backed” banner is gone |

HAPI is still not deployed.
