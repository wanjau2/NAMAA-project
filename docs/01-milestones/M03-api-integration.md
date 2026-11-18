# M03 — Frontend pointed at the API; local transition layer deleted

**Date:** 2026-11-18
**Owner:** Mark, integrating Ismail's [M02](M02-backend-foundation.md) backend
**Status:** Partial — workflow fully integrated, analytics and source review not
**Gate:** Work plan F4 (backend connection), roadmap Phase C

## What changed

The frontend no longer decides anything about case state. Ismail's FastAPI service is now the
authority for every transition, validation, event and disposition, and the frontend's local
stand-in has been deleted rather than left dormant.

Both synthetic journeys now run against one server-authoritative build, which is the release
gate's central requirement.

## Scope delivered

| Item | Built | Mocked | Not started | Note |
| --- | --- | --- | --- | --- |
| Typed API client with structured errors | ✅ | | | `lib/api.ts`, `lib/api-types.ts` (roadmap B1) |
| Guest session lifecycle + `X-Namaa-Session` / `X-Namaa-Role` | ✅ | | | In-memory; reload starts a fresh workspace |
| Worklist from `GET /api/v1/cases` | ✅ | | | Loading, empty, error and retry states |
| Case detail from `GET /api/v1/cases/{id}` | ✅ | | | Server event timeline; 404 handled |
| Actions via `POST /api/v1/cases/{id}/actions` | ✅ | | | Envelope, stale-revision recovery, field errors |
| Reset via `POST /api/v1/demo/reset` | ✅ | | | Roadmap B6 |
| Dynamic `/cases/[id]` route | ✅ | | | Roadmap C4 |
| API status indicator in the simulation bar | ✅ | | | Connected / connecting / unreachable |
| Live analytics panel with server suppression | ✅ | | | Shows all-suppressed state honestly |
| Population dashboard cards | | ✅ | | Local cohort fixture — API seed too small |
| Source review (A1) | | ✅ | | No proposal endpoints exist (Q10) |
| Browser-driven journey evidence | | | ❌ | D4 / D5 / E1 |

## Deleted

- `lib/case-actions.ts` — the 13-action transition engine, validation and state mutation
- the seeded local store inside `lib/case-store.tsx`
- `lib/mock-data.ts` — cases, details and timelines (trimmed to
  `lib/source-review-fixtures.ts`, which holds only what the API does not model)
- `scripts/verify-actions.ts` — replaced by `scripts/verify-api-contract.ts`

`lib/action-catalog.ts` retains presentation metadata only. Its `displayWhen` predicates are
documented as display hints; the server decides validity.

## Acceptance checks

**34/34 contract checks pass against the live API** — see
[evidence](../03-evidence/C-api-integration/checks.md). Ismail's 6 pytest checks also pass.

Two checks are worth calling out because they close earlier risks:

- **Catalog drift detection.** The suite compares `lib/action-catalog.ts` against
  `GET /api/v1/meta/actions` and asserts the same 13 action ids with the same roles. Divergence
  now fails a check instead of surfacing as a runtime refusal.
- **Server-side suppression confirmed.** Suppressed analytics cells arrive with
  `numerator: null, denominator: null`, so the hidden counts never reach the browser. The A4
  evidence had demonstrated the opposite for the client-side version.

## Non-negotiables re-verified

- [x] Synthetic-data notice on every screen
- [x] **Server rejects invalid transitions** — now genuinely true, verified for role,
      precondition, stale revision, invalid transition and field validation
- [x] Stage and disposition remain separate; no silent relabel to completed
- [x] Completion requires evidence plus reviewer authorization — enforced server-side
- [x] Missing data produces needs-review with equal visual weight
- [x] No unreviewed AI output influences rules (no AI path; rules are deterministic)
- [x] No unsupported clinical performance claims
- [~] Small-cell suppression — server-side and correct, but **all 16 cells suppressed** at the
      current seed size, so nothing is publishable yet

## Known limitations

- **Analytics has no usable server source.** Correct logic, cohort too small. The dashboard
  cards remain a labelled local fixture.
- **Source review is not persisted.** No proposal endpoints, so no `Provenance` and no reviewer
  identity. The screen says so on-screen.
- **HAPI is not deployed** (D003). Clinical store is application SQLite with FHIR-shaped
  synthetic identifiers. The submission must state this.
- Client rendering verified from served markup plus the contract suite, not a real browser.
- The `displayWhen` hints duplicate a little server knowledge; Q9 would remove them.

## Next

1. **Q9 / Q10 with Ismail** — `available_actions` per case, and whether proposal endpoints land
   this sprint.
2. **Analytics seed decision** — blocks any honest population view.
3. Phase B remainder: 409 recovery polish, remaining empty states.
4. Phase D: keyboard, axe, RTL, responsive.
