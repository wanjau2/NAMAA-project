# M01 — Frontend foundation and token layer

**Date:** 2026-11-17
**Owner:** Mark
**Status:** Partial — foundation done, journeys not yet complete
**Gate:** Work plan F1 (screen skeleton) and part of F2 (case detail)

## What changed

The frontend exists and runs. The Namaa design tokens are implemented as the single source of
truth with shadcn/ui aliased onto them, and the three safety-critical UI patterns — persistent
simulation bar, epistemic status rendering, and the equal-weight uncertainty layout — are built
and verified in a production build. Guest entry, the coordinator worklist and case detail are
navigable end to end on mock data.

## Stack as built

| Component | Version | Note |
| --- | --- | --- |
| Next.js | 16.4.6 | App Router, Cache Components + Partial Prefetching on by default |
| React | 19.3.0 | |
| TypeScript | ^5 | strict, `tsc --noEmit` clean |
| Tailwind CSS | 4.3.3 | CSS-first; **no `tailwind.config.ts` exists** |
| shadcn/ui | style `radix-nova`, RTL enabled | Radix primitives, lucide icons |
| lucide-react | ^1.74.0 | v1 renamed icons; theme's names resolve as aliases |

Scaffolded into `web/` so Ismail's `api/` can sit alongside it, matching the Compose topology in
the design specification §2.

## Scope delivered

| Item | Built | Mocked | Not started | Note |
| --- | --- | --- | --- | --- |
| Token layer, shadcn bridge, light-only | ✅ | | | `web/app/globals.css`, D002 §1/§4 applied |
| Four fonts via `next/font` (EN + Arabic + mono) | ✅ | | | Self-hosted, replaces the render-blocking `@import` |
| Type ramp + 4px spacing enforced by utilities | ✅ | | | D002 §6 |
| Persistent simulation bar, 44px sticky | ✅ | | | Role switcher, EN/عربي toggle, two-step reset, mobile collapse |
| `StatusBadge` / `StatusCard` | ✅ | | | Only sanctioned status renderer; icon + text + token always |
| `RoleGatedAction` (`aria-disabled`, focusable) | ✅ | | | D002 §2 |
| Bidi isolation on technical strings | ✅ | | | `.font-mono-tech` |
| Guest entry screen | ✅ | | | No credentials, explicit synthetic notice |
| Coordinator worklist | ✅ | ✅ | | Pathway / stage / overdue filters; stage kept distinct from disposition |
| Case detail | partial | ✅ | | Equal-weight uncertainty pair, contributing records, timeline, action panel |
| Language toggle wiring | ✅ | | | Flips `dir` on `<html>`; Arabic strings labelled unreviewed |
| Arabic UI copy | | | ❌ | Three role labels only. Pending Q2 and Alfred's reviewed copy |
| Population dashboard `/metrics` | | | ❌ | F5 |
| Source review (accept/correct/reject) | | | ❌ | Depends on Q3 |
| Backend connection | | | ❌ | F4, blocked on Q1 and Q5 |
| Loading / skeleton / conflict states | | | ❌ | D002 §5 — needs a real API to be meaningful |

**All case data is frontend mock data** in `web/lib/mock-data.ts`, clearly labelled as such, to
be replaced by Alfred's fixtures and Ismail's API.

## Acceptance checks

| Scenario | Expected | Observed | Pass | Evidence |
| --- | --- | --- | --- | --- |
| Production build | Compiles, types clean, lint clean | `next build` ✓, `tsc --noEmit` ✓, `eslint` ✓ | ✅ | build output |
| Simulation notice on every screen | Present on `/`, `/cases`, `/cases/[id]` | `SYNTHETIC DEMO DATA — NOT FOR CLINICAL USE` served in all three | ✅ | curl against `next start` |
| Dark mode absent | No `.dark` block, no `prefers-color-scheme` | 0 occurrences in compiled CSS | ✅ | compiled CSS grep |
| Status borders meet 3:1 | Border = state foreground | `--status-proposed-border: #6d28d9` compiled; dashed rule present | ✅ | compiled CSS grep |
| Bidi isolation compiled | `unicode-bidi: isolate` reaches output | present | ✅ | compiled CSS grep |
| Declined/unreachable ≠ completed | Distinct token and explicit text | `Unreachable` and `Preventive action completed` render differently | ✅ | `/cases` output |
| Closure blocked without evidence | Action refused with a reason | "Booking alone does not complete preventive care…" rendered | ✅ | `/cases/case-0001` |
| Needs-review blocks invitation | Invitation gated with explanation | gated on `flag_status === "needs_review"` | ✅ | `/cases/case-0001` |

Not yet checked: axe-core, keyboard-only journey completion, RTL snapshot, mobile widths.
Those are the M06 / F5 evidence set and need a browser, not curl.

## Non-negotiables re-verified

- [x] Synthetic-data notice present on every screen
- [ ] Server rejects invalid transitions — **no server yet**; gating is client-side only and must
      not be mistaken for enforcement
- [x] Stage and disposition remain separate; no silent relabel to completed
- [x] Completion requires evidence plus reviewer authorization *(enforced in the UI only)*
- [x] Missing data produces needs-review with equal visual weight
- [x] No unreviewed AI output influences rules *(no AI path built yet)*
- [x] No unsupported clinical performance claims in UI
- [ ] Small-cell suppression — **blocked on Q8**, and the metrics view is not built

## Contract changes

None agreed. `web/lib/mock-data.ts` encodes a **guess** at the shared records, following the work
plan's field lists. Treat it as a proposal to Ismail, not a contract. Specifically it assumes:
`stage`, `disposition`, `owner`, `next_action`, `due_time`, `revision`, `rule_id_version`,
`flag_status` with values `gap | needs_review`, and an explicit `overdue` boolean rather than a
client-side comparison against `due_time`.

## Known limitations

- **The gating is cosmetic.** Every role check and blocked action is client-side. A reviewer
  could reach the same state by editing the page. This is honest for F1 but must be stated in
  the submission until the server validates transitions.
- Reset clears client state only; `POST /demo/reset` is not wired.
- Case detail is static presentation — no action actually mutates anything.
- Arabic is three role labels plus the toggle. The RTL mechanics work; the copy does not exist.
- `generateStaticParams` enumerates the six mock cases. That has to be swapped for a dynamic
  route when the API lands.

## Next

1. `/metrics` with explicit numerators and denominators (F5) — renders suppressed cells, but
   cannot claim suppression works until Q8 is decided.
2. Loading, error, empty and 409-conflict states (D002 §5) against a stub API client, so the
   shapes are ready for F4.
3. Source review screen — gated on Q3.
4. Keyboard, axe and RTL passes once the screen set is complete.

Blocked on: **Q1** (stack), **Q5** (API paths), **Q8** (suppression). Mark can continue on mocks
per the work plan's dependency-slip rule, provided the result stays labelled a simulation.
