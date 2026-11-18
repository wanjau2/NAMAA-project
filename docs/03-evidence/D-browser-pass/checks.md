# Browser verification pass — D3–D6, E1–E2

**Date:** 2026-11-18
**Owner:** Mark
**Tooling:** Playwright 1.x + Chromium headless, `@axe-core/playwright`
**Reproduce:** `cd web && npm run e2e` (starts the API and a production Next build itself)

**Result: 36/36 pass** across two projects — Desktop Chrome and Pixel 7 (390px).

Everything runs against the live API on synthetic data. These are software checks, not clinical
validation.

## Coverage

| Roadmap item | Covered by |
| --- | --- |
| **E1** both journeys end to end | `e2e/journeys.spec.ts` |
| **E2** clean browser session | fresh context per test; guest entry needs no credentials |
| **D4** keyboard operability | `e2e/accessibility.spec.ts` |
| **D5** axe-core | 4 pages × 2 viewports, WCAG 2.0/2.1 A + AA |
| **D6** responsive | both projects; no horizontal scroll at 390px; bar collapse |
| **D3** RTL | `e2e/responsive-rtl.spec.ts` |

## Safety properties verified in a real browser

These were previously asserted at the API or markup level. They are now verified as a reviewer
would actually experience them:

| Property | How |
| --- | --- |
| **Booking alone cannot complete care** | At `booked`, "Close as completed" is not offered at all |
| **Closure needs evidence** | Submitting with attestation but no evidence reference shows `This field is required.` |
| **Failed submits preserve input** | The attestation checkbox is still checked after the refusal |
| **Closure needs a reviewer** | As coordinator the control is `aria-disabled`, focusable, and its reason is announced |
| **Rejected referral blocks completion** | Reviewer attempt returns the precondition reason; completion only after reassignment |
| **Ownership survives escalation** | Owner becomes `Coordinator 3` and persists across a reload |
| **Missing data blocks approval** | `unknown is not the same as up to date` shown on `case-0001` |
| **Equal-weight uncertainty** | Both "Suggested pathway" and "Missing & unverified information" headings present |
| **Extraction is real** | SSE-driven job completes; proposals render `Proposed — not yet reviewed` |
| **Note text is data** | The instruction sentence is displayed; no proposal derives from it |
| **Untraceable quotes** | No `Quote does not match the source` present — every excerpt verified |
| **Suppression visible** | `Suppressed (n < 10)` and explicit numerator/denominator on `/metrics` |
| **Notice on every screen** | `sim-notice` visible on `/`, `/cases`, `/metrics`, `/cases/case-0001` |

## Accessibility

- **axe: zero critical or serious violations** on guest entry, worklist, case detail and
  population view, at both viewports.
- A role-gated control is **focusable** (`aria-disabled`, not `disabled`) and its
  `aria-describedby` target is visible and contains the reason.
- A case link is reachable by Tab and activatable with Enter.
- Focus is visibly outlined on the first focusable control.
- Technical strings under RTL: every `.font-mono-tech` node computes
  `direction: ltr; unicode-bidi: isolate`.
- No horizontal page scroll at 390px on any of the four pages.

## Defects found and fixed

The pass earned its keep: six real defects, none of which markup or contract checks could have
caught.

| # | Defect | Impact | Fix |
| --- | --- | --- | --- |
| 1 | **WCAG 2.5.3 label-in-name** on the language toggle, every page | Visible text `EN` / `عربي` was not part of the accessible name (`English`), so speech input could not target it. axe: *serious* | Accessible name now contains the visible text |
| 2 | **Duplicate `id="sim-role"`** | The bar renders its controls twice (desktop row + mobile panel); with the panel open the `<label>` resolved to the **hidden** desktop control | Per-instance ids via `useId()` |
| 3 | **Success confirmation vanished** | A successful action usually makes its own row invalid, so the row unmounted and took the "Recorded by the server" message with it — the user got no feedback that it worked | Confirmation lifted to panel level, inline duplicate removed |
| 4 | **A refresh discarded the whole session** | The guest session id lived in memory only, so reloading silently created a new workspace and threw away everything the reviewer had just done | Session persisted in `sessionStorage` (per tab, cleared on close) |
| 5 | **Case detail never showed the owner** | Design specification §8 requires owner and deadline on the case view, and the work plan requires the responsible person to be obvious. Only the worklist had it | Owner, Due and Next action added to the case header |
| 6 | **API status was desktop-only** | On a phone a reviewer had no way to tell the API was down | Chip visible at all widths, collapsing to a dot with the state in its accessible name |

Two further issues were introduced while fixing #6 and caught immediately by the same suite:
a 31px horizontal overflow at 390px, and `aria-prohibited-attr` from putting `aria-label` on a
role-less `<span>`. Both fixed (`role="status"`, text hidden below 640px).

## Environment findings for the team

1. **The API CORS allowlist only covers port 3000.** `NAMAA_CORS_ORIGINS` defaults to
   `http://localhost:3000,http://127.0.0.1:3000`, so the frontend on any other port gets every
   fetch blocked and correctly reports *API unreachable*. The Playwright config passes the
   origin explicitly. Worth widening or documenting before anyone demos on a different port.
2. **`next.config.ts` sets `output: "standalone"`** (added for Docker), and `next start` warns
   *"does not work with output: standalone"*. Pages served correctly in every test, but the
   supported command is `node .next/standalone/server.js`. This needs settling before E5
   deployment instructions are written.

## Not covered

- Screen-reader narration (axe checks the tree, not the experience).
- Colour-contrast at runtime beyond axe's automated check; the token ratios were computed in D002.
- The child pathway starting from `identified`: `case-0001` is `needs_review`, and clearing that
  requires the fact-review endpoint that does not exist (Q10). The child journey is therefore
  demonstrated from `case-0002` at `booked`.
- Arabic UI copy — only the toggle, `dir` mirroring and bidi isolation are verified (Q2).
