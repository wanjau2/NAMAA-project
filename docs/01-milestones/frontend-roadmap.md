# Frontend roadmap — remaining work to F6

**Owner:** Mark
**Created:** 2026-11-17
**Status:** Live document — update as steps complete
**Starting point:** [M01 — Frontend foundation](M01-frontend-foundation.md)

Covers every remaining frontend step from the current build to the delivery assets in work
plan F6. Ismail and Alfred: **Phase C is the only phase that needs you**, but read the
"What the frontend needs from the team" section — three decisions gate it.

## Already delivered (M01)

Token layer and shadcn bridge · persistent simulation bar · `StatusBadge` / `StatusCard` ·
`RoleGatedAction` · bidi handling for technical strings · guest entry · coordinator worklist ·
case detail (partial).

## Phase A — Finish the screen set

**Progress: A1, A2 complete.** Next: A3.

No backend required. Builds on contract-matching mocks, per the work plan's dependency-slip rule.

| # | Step | Acceptance | Est. |
| --- | --- | --- | --- |
| ~~A1~~ | ~~**Source review panel**~~ — **DONE 2026-11-17** · [evidence](../03-evidence/A1-source-review/checks.md) | 12/12 checks pass on the production build | 1.5h |
| ~~A2~~ | ~~**Action forms**~~ — **DONE 2026-11-17** · [evidence](../03-evidence/A2-action-forms/checks.md) | 26/26 transition checks pass (`npm run verify:actions`); offered actions verified per state | 1.5h |
| A3 | **Patient overview** — clinical history, caregiver information, contact preferences | Caregiver authority shown separately from relationship | 0.75h |
| A4 | **`/metrics` population dashboard** — separate child and adult cohort cards, explicit numerator/denominator, separate funnel counts for invited / booked / attended / follow-up, synthetic banner, suppressed cells | Denominators always visible; declined and unreachable people remain in the denominator; no figure implies a real-world outcome | 1.25h |
| A5 | **FHIR / audit inspector drawer** — resource JSON, references, versions, validation results | Scope depends on Q1. Currently a stub | 0.75h |
| A6 | **Navigation shell** — persistent nav across worklist / metrics / inspector, with selected state | Keyboard reachable; current page announced | 0.5h |

Suppression rendering in A4 can be *built* now but cannot be *claimed* until Q8 is decided.

## Phase B — States and resilience

Built against a stub client so Phase C becomes a swap, not a rewrite.

| # | Step | Acceptance | Est. |
| --- | --- | --- | --- |
| B1 | **Typed API client** — action envelope (action name, expected revision, request ID); structured error parsing (`code`, `message`, `field_errors`, `request_id`) | Every mutation carries all three; repeated request IDs are not generated twice | 1h |
| B2 | **Loading / skeleton states** + inference polling — 2s poll, elapsed text against the 90s timeout, terminal-state stop | A stalled job is visible as stalled; a timeout never renders as "no gap found" | 0.75h |
| B3 | **Error states per status code** — 401 / 403 / 404 / 409 / 422 / 429 / 503 | 409 shows the inline banner with **Reload Latest State** and **preserves all entered inputs** | 0.75h |
| B4 | **Empty states** on every list | Phrased as an empty result, never as an absence of care gaps | 0.25h |
| B5 | **No optimistic state** — the UI waits for the server echo | A failed call leaves the last confirmed state intact | 0.25h |
| B6 | **Reset wired** to the demo reset endpoint | Reset clears only its own synthetic session | 0.25h |

## Phase C — Connect to the backend (F4) — BLOCKED

Needs Q1 and Q5 answered. This is the phase that turns cosmetic gating into real enforcement.

| # | Step | Depends on |
| --- | --- | --- |
| C1 | Swap mocks for the real API; reconcile contract mismatches | Ismail's OpenAPI spec + action names |
| C2 | Verify revision conflicts and duplicate request IDs against the real server | Ismail (B5 reliability) |
| C3 | Render suppression from server flags | Q8 — Ismail + Alfred |
| C4 | Replace `generateStaticParams` on `/cases/[id]` with a dynamic route | C1 |

Estimated 3h once unblocked.

## Phase D — Bilingual and accessibility (F5)

| # | Step | Acceptance | Est. |
| --- | --- | --- | --- |
| D1 | Extract all strings into a dictionary | No hardcoded copy left in components | 1h |
| D2 | Integrate Arabic copy with `Unreviewed demo translation` badges | Gated on Q2. Unreviewed copy is never presented as clinically approved | 0.75h |
| D3 | RTL audit — lint rule banning physical direction classes, plus RTL snapshots | Timestamps, rule IDs and denominators do not scramble in Arabic | 0.75h |
| D4 | Keyboard pass — focus order, skip link, `aria-disabled` reachability | Both journeys complete with keyboard only; every gated control's reason is announced | 0.75h |
| D5 | axe-core via Playwright | Zero critical violations on every screen | 0.5h |
| D6 | Responsive pass, desktop and mobile, incl. simulation bar collapse | Both journeys work at both widths | 0.5h |
| D7 | Re-verify contrast on the final badge set; confirm reduced-motion | Ratios recomputed, not estimated | 0.25h |

## Phase E — Delivery assets (F6)

| # | Step | Acceptance | Est. |
| --- | --- | --- | --- |
| E1 | Playwright E2E for both journeys | Child and adult journeys pass on the same build | 1h |
| E2 | Guest journey on a clean browser session | No cached state; no unavailable credentials | 0.5h |
| E3 | Record the demonstration | No real credentials or sensitive information in frame | 0.75h |
| E4 | Assemble deck and screenshots | Built / mocked / future clearly separated | 0.5h |
| E5 | Deployment instructions and local fallback | A fresh reviewer can start the UI from the guide | 0.25h |

## Polish backlog

- **Hover treatment for the dark fill** — Mark asked (2026-11-17) that "that darkish base appear
  only at hover". Which element is not yet settled: the deep teal `#0F5C5C` fill on primary
  buttons and active filter pills, the worklist row background, or something else. Resolve
  before D7, since it changes the contrast values to re-verify.
- Row hover and selected-nav treatments (D002 §5).
- Reset confirmation visual refinement.

## What the frontend needs from the team

| Need | From | Blocks |
| --- | --- | --- |
| **Q1** stack decision | All three | Phase C, and the scope of A5 |
| **Q5** API paths, action names, role requirements | Ismail | B1, Phase C |
| **Q8** server-side small-cell suppression | Ismail + Alfred | C3, and the A4 suppression claim |
| **Q2** whether Arabic copy ships | All three | D2 |
| Reviewed patient-message copy and explanation labels | Alfred | A2 |
| Rule explanations and uncertainty wording | Alfred | A1 |

## Sequencing and the time budget

Phases A, B, D and E are unblocked today. Remaining estimate is roughly **A 5.75h · B 3.25h ·
C 3h · D 4.5h · E 3h ≈ 19.5h**, against about 15h left of the F1–F6 allocation. That is a real
overrun, not a rounding error.

If time compresses, cut in this order:

1. **A5** FHIR inspector drawer — the most deferrable screen
2. **A3** patient overview — its content can live inside case detail
3. **E4** deck polish
4. **D2** Arabic copy, keeping the RTL mechanics from D3

Protect: **D4, D5, D6** (the accessibility claims are in the definition of done) and **E1/E2**
(both journeys must demonstrably run on one build).

## Standing constraint

Until Phase C lands, every role check and blocked action in the UI is **client-side only** and is
not enforcement. The submission must describe the actual level of integration, including any
remaining mocks.
