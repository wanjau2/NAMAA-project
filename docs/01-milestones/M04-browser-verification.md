# M04 — Browser verification: both journeys, accessibility, RTL and responsive

**Date:** 2026-11-18
**Owner:** Mark
**Status:** Done
**Gate:** Roadmap D3–D6 and E1–E2

## What changed

Until now every claim about the frontend rested on served markup, typechecks and API contract
checks. Nothing had been driven in a real browser. It has now: **36/36 Playwright checks pass**
across Desktop Chrome and a 390px Pixel 7, against the live API, and the suite starts both
services itself so a run is reproducible from a clean checkout.

Six real defects were found and fixed in the process — none of them detectable by the checks
that already existed.

## Scope delivered

| Item | Built | Note |
| --- | --- | --- |
| E1 — both journeys end to end | ✅ | Child from `booked`; adult through rejected referral and reassignment |
| E2 — clean browser session | ✅ | Fresh context per test; no credentials needed |
| D4 — keyboard operability | ✅ | Tab-to-link, Enter activation, focus visibility, `aria-disabled` reachability |
| D5 — axe-core | ✅ | 4 pages × 2 viewports, zero critical or serious |
| D6 — responsive | ✅ | No horizontal scroll at 390px; simulation bar collapse |
| D3 — RTL | ✅ | `dir`/`lang` mirroring; every `.font-mono-tech` node isolated |

Run with `npm run e2e` (both projects) or `npm run e2e:desktop`.

## Defects fixed

1. **WCAG 2.5.3 label-in-name** on the language toggle — axe *serious*, on every page.
2. **Duplicate `id="sim-role"`** — the label resolved to a hidden control once the mobile panel
   was open.
3. **The success confirmation vanished** after a successful action, because the row that
   produced it was no longer valid and unmounted with the message inside it.
4. **A page refresh discarded the entire guest session**, silently losing all demo progress.
5. **Case detail never displayed the owner**, due time or next action, which §8 requires.
6. **The API status indicator was desktop-only**, so a phone user got no connection feedback.

Details and the two self-inflicted regressions caught by the same suite are in the
[evidence](../03-evidence/D-browser-pass/checks.md).

## Non-negotiables re-verified — in a browser this time

- [x] Synthetic-data notice on every screen
- [x] Server rejects invalid transitions, and the UI surfaces the reason
- [x] Stage and disposition remain distinct
- [x] Completion requires evidence **and** a reviewer; booking alone is not offered
- [x] Missing data blocks approval with an explicit reason
- [x] No unreviewed proposal influences rules; extraction is labelled a fixture
- [x] No unsupported clinical performance claims
- [~] Small-cell suppression renders correctly, but the API still suppresses all 16 cells at the
      current seed size

## Known limitations

- The child pathway cannot be demonstrated from `identified`: `case-0001` is `needs_review`, and
  clearing that needs the fact-review endpoint that does not exist (Q10). The child journey runs
  from `case-0002` at `booked`.
- Screen-reader narration is not covered; axe inspects the tree, not the experience.
- Arabic UI copy is still absent (Q2) — only mirroring and bidi isolation are verified.
- Two environment issues need the team: the API CORS allowlist covers port 3000 only, and
  `output: "standalone"` makes `next start` unsupported for deployment.

## Next

1. **E3** record the demonstration, **E4** assemble deck and screenshots — both now unblocked.
2. Resolve the CORS allowlist and the standalone/`next start` question before **E5**.
3. Still blocked on the team: analytics cohort (C3), fact-review endpoint (Q10), rule-outcome
   enum, documents-by-case listing (Q11).
