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

**Progress: A1, A2, A4 complete** (plus a minimal nav from A6). Next: A3 or A5.

**Alfred's contract work started 2026-11-18** — code-point offsets and the four-outcome
display layer are done ([evidence](../03-evidence/F-contracts/checks.md)); the enum itself is Q12.

**Delivery assets 2026-11-18** — demo footage and the 12-slide deck are done (E3 footage, E4);
see [E-delivery](../03-evidence/E-delivery/README.md). E5 is blocked on the standalone question.

**Browser pass complete 2026-11-18** — see [M04](M04-browser-verification.md). D3–D6 and E1–E2
done; six defects found and fixed.

**A1 read path cut over to the API 2026-11-18** (proposals, note text, SSE progress).

**Phase C landed 2026-11-18** — see [M03](M03-api-integration.md). The local transition layer is
deleted; the server is authoritative. B1, B4, B5, B6 and C1/C2/C4 came with it.

No backend required. Builds on contract-matching mocks, per the work plan's dependency-slip rule.

| # | Step | Acceptance | Est. |
| --- | --- | --- | --- |
| ~~A1~~ | ~~**Source review panel**~~ — **DONE 2026-11-17**, **API read path 2026-11-18** · [evidence](../03-evidence/A1-source-review/checks.md) | 49/49 contract checks incl. 15 extraction checks; fixtures deleted. Review *writes* still blocked on Q10 | 1.5h |
| ~~A2~~ | ~~**Action forms**~~ — **DONE 2026-11-17** · [evidence](../03-evidence/A2-action-forms/checks.md) | 26/26 transition checks pass (`npm run verify:actions`); offered actions verified per state | 1.5h |
| A3 | **Patient overview** — clinical history, caregiver information, contact preferences | Caregiver authority shown separately from relationship | 0.75h |
| ~~A4~~ | ~~**`/metrics` population dashboard**~~ — **DONE 2026-11-17** · [evidence](../03-evidence/A4-population-dashboard/checks.md) | 53/53 definition + suppression checks pass (`npm run verify:metrics`). Q8 now **demonstrated**: hidden counts are readable in the JS bundle | 1.25h |
| A5 | **FHIR / audit inspector drawer** — resource JSON, references, versions, validation results | Scope depends on Q1. Currently a stub | 0.75h |
| A6 | **Navigation shell** — persistent nav across worklist / metrics / inspector, with selected state | Keyboard reachable; current page announced | 0.5h |

Suppression rendering in A4 can be *built* now but cannot be *claimed* until Q8 is decided.

## Phase B — States and resilience

Built against a stub client so Phase C becomes a swap, not a rewrite.

| # | Step | Acceptance | Est. |
| --- | --- | --- | --- |
| ~~B1~~ | ~~**Typed API client**~~ — **DONE 2026-11-18** · `lib/api.ts`, `lib/api-types.ts` | Envelope + structured errors verified live | 1h |
| B2 | **Loading / skeleton states** + **SSE extraction progress** (D004) — use `web/lib/extraction-sse.ts` / `GET /api/v1/extractions/{id}/events`; elapsed text against the 90s timeout; stop on terminal. HTTP status GET is fallback only — do **not** 2s-poll | A stalled job is visible as stalled; a timeout never renders as "no gap found" | 0.75h |
| B3 | **Error states per status code** — *partial*: 401/404/409/422 and unreachable handled with retry and input preservation; 403/429/503 untested | 409 banner + **Reload latest state** built | 0.75h |
| ~~B4~~ | ~~**Empty states**~~ — **DONE 2026-11-18** (worklist); fixed a first-paint bug that read as an absence of care gaps | Skeleton covers connecting state | 0.25h |
| ~~B5~~ | ~~**No optimistic state**~~ — **DONE 2026-11-18** | Server echo is the only state source | 0.25h |
| ~~B6~~ | ~~**Reset wired**~~ — **DONE 2026-11-18** · `POST /api/v1/demo/reset` | Session-scoped; seed restored | 0.25h |

## Phase C — Connect to the backend (F4) — BLOCKED

Q1 and Q5 were answered by [D003](../02-decisions/D003-backend-stack-and-api.md). The gating is
no longer cosmetic: the server validates every transition. C3 is the remaining item.

| # | Step | Depends on |
| --- | --- | --- |
| ~~C1~~ | ~~Swap mocks for the real API~~ — **DONE 2026-11-18**; `case-actions.ts` deleted | — |
| ~~C2~~ | ~~Verify revision conflicts and duplicate request IDs~~ — **DONE**; 34/34 contract checks | — |
| C3 | Render suppression from server flags — **API side done**, but 16/16 cells suppressed at the current seed. Blocked on a cohort decision | Ismail + Alfred |
| ~~C4~~ | ~~Replace `generateStaticParams` on `/cases/[id]`~~ — **DONE 2026-11-18** | — |

Estimated 3h once unblocked.

## Phase D — Bilingual and accessibility (F5)

| # | Step | Acceptance | Est. |
| --- | --- | --- | --- |
| D1 | Extract all strings into a dictionary | No hardcoded copy left in components | 1h |
| D2 | Integrate Arabic copy with `Unreviewed demo translation` badges | Gated on Q2. Unreviewed copy is never presented as clinically approved | 0.75h |
| ~~D3~~ | ~~RTL audit~~ — **DONE 2026-11-18** | Every `.font-mono-tech` node verified `direction: ltr; unicode-bidi: isolate` under `dir="rtl"` | 0.75h |
| ~~D4~~ | ~~Keyboard pass~~ — **DONE 2026-11-18** | Tab-to-link, Enter activation, visible focus, `aria-disabled` controls reachable with announced reasons | 0.75h |
| ~~D5~~ | ~~axe-core via Playwright~~ — **DONE 2026-11-18** | Zero critical or serious on 4 pages × 2 viewports | 0.5h |
| ~~D6~~ | ~~Responsive pass~~ — **DONE 2026-11-18** | No horizontal scroll at 390px; simulation bar collapse verified | 0.5h |
| D7 | Re-verify contrast on the final badge set; confirm reduced-motion | Ratios recomputed, not estimated | 0.25h |

## Phase E — Delivery assets (F6)

| # | Step | Acceptance | Est. |
| --- | --- | --- | --- |
| ~~E1~~ | ~~Playwright E2E for both journeys~~ — **DONE 2026-11-18** · [evidence](../03-evidence/D-browser-pass/checks.md) | 36/36 across desktop and mobile against the live API | 1h |
| ~~E2~~ | ~~Guest journey on a clean browser session~~ — **DONE 2026-11-18** | Fresh context per test; no credentials required | 0.5h |
| ~~E3~~ | ~~Record the demonstration~~ — **FOOTAGE DONE 2026-11-18** · [50s walkthrough](../03-evidence/E-delivery/recording/namaa-demo-walkthrough.webm) | Reproducible via `npm run demo`; narration still to record over it | 0.75h |
| ~~E4~~ | ~~Assemble deck and screenshots~~ — **DONE 2026-11-18** · [12-slide deck](https://claude.ai/artifact/XCVbNx8Kf2Gy8q8XEJi4nE) · 18 screenshots | Built / simulated / not built separated on slide 9 | 0.5h |
| E5 | Deployment instructions and local fallback — **blocked**: `output: "standalone"` makes `next start` unsupported; the command to document is unsettled | A fresh reviewer can start the UI from the guide | 0.25h |

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
