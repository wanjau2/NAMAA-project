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

**Progress: A1, A2, A4, A5 (limited inspector), A6 complete.** Next: A3.

**Alfred's frontend handoff complete 2026-11-19** — typed extraction contract rendering and
the assembled-context panel are built ([evidence](../03-evidence/F-contracts/checks.md)). Q10,
Q12 and C3 later landed on the running API (2026-11-20 notes).

**Alfred's contract work started 2026-11-18** — code-point offsets and the four-outcome
display layer are done ([evidence](../03-evidence/F-contracts/checks.md)); the enum itself is Q12.

**Delivery assets 2026-11-18** — demo footage and the 12-slide deck are done (E3 footage, E4);
see [E-delivery](../03-evidence/E-delivery/README.md). E5 is blocked on the standalone question.

**M15–M19 (2026-11-20)** — selected/current-page nav, D002 hover/selected, reset `alertdialog`,
`verify:contrast` plus reduced-motion; chrome dictionary with unreviewed Arabic (Q2 still open;
clinical copy stays English); inspector from live audit/outbox without HAPI claims; dated
evidence addenda (footage/narration/deck-share not re-cut); `available_actions` and
`GET /cases/{id}/documents` as the live display path. **E5** startup path landed with M14
(`npm start` → standalone server).

**Browser pass complete 2026-11-18** — see [M04](M04-browser-verification.md). D3–D6 and E1–E2
done; six defects found and fixed.

**A1 read path cut over to the API 2026-11-18** (proposals, note text, SSE progress).

**Phase C landed 2026-11-18** — see [M03](M03-api-integration.md). The local transition layer is
deleted; the server is authoritative. B1, B4, B5, B6 and C1/C2/C4 came with it.

Phase A screens now read the live API. Remaining A3 (patient overview) can still ship inside case detail.

| # | Step | Acceptance | Est. |
| --- | --- | --- | --- |
| ~~A1~~ | ~~**Source review panel**~~ — **DONE 2026-11-17**, **API read path 2026-11-18** · [evidence](../03-evidence/A1-source-review/checks.md) | 49/49 contract checks incl. 15 extraction checks; fixtures deleted. Review *writes* still blocked on Q10 | 1.5h |
| ~~A2~~ | ~~**Action forms**~~ — **DONE 2026-11-17** · [evidence](../03-evidence/A2-action-forms/checks.md) | 26/26 transition checks pass (`npm run verify:actions`); offered actions verified per state | 1.5h |
| A3 | **Patient overview** — clinical history, caregiver information, contact preferences | Caregiver authority shown separately from relationship | 0.75h |
| ~~A4~~ | ~~**`/metrics` population dashboard**~~ — **DONE 2026-11-17** · [evidence](../03-evidence/A4-population-dashboard/checks.md) | 53/53 definition + suppression checks pass (`npm run verify:metrics`). Q8 now **demonstrated**: hidden counts are readable in the JS bundle | 1.25h |
| ~~A5~~ | ~~**FHIR / audit inspector**~~ — **DONE 2026-11-20, limited scope** · application ids + live `GET /audit/events` and `GET /ops/outbox`. Not HAPI; case revision is a concurrency token, not `CarePlan/{id}` · rev | Q1: HAPI deferred (D003). Stub gateway labelled on screen | 0.75h |
| ~~A6~~ | ~~**Navigation shell**~~ — **DONE 2026-11-20** · selected underline + subtle fill (D002 §5); `aria-current="page"` | Keyboard reachable; current page announced | 0.5h |

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

## Phase C — Connect to the backend (F4)

Q1 and Q5 were answered by [D003](../02-decisions/D003-backend-stack-and-api.md). The gating is
no longer cosmetic: the server validates every transition. C3 has a reporting cohort (2026-11-20);
the threshold stays ≥ 10.

| # | Step | Depends on |
| --- | --- | --- |
| ~~C1~~ | ~~Swap mocks for the real API~~ — **DONE 2026-11-18**; `case-actions.ts` deleted | — |
| ~~C2~~ | ~~Verify revision conflicts and duplicate request IDs~~ — **DONE**; 34/34 contract checks | — |
| ~~C3~~ | ~~Render suppression from server flags~~ — **DONE 2026-11-20** · reporting cohort publishes; `/metrics` is live overview + segments; 16/16 on the 18 November seed is historical | Threshold stays ≥ 10. Shrinking the cohort re-locks the family |
| ~~C4~~ | ~~Replace `generateStaticParams` on `/cases/[id]`~~ — **DONE 2026-11-18** | — |

Estimated 3h once unblocked.

## Phase D — Bilingual and accessibility (F5)

| # | Step | Acceptance | Est. |
| --- | --- | --- | --- |
| D1 | Extract all strings into a dictionary — **PARTIAL 2026-11-20** · chrome (nav/session) in `web/lib/copy.ts`. Clinical explanations stay English in components | Q2 open; not a full i18n extract | 1h |
| D2 | Integrate Arabic copy with `Unreviewed demo translation` badges — **PARTIAL 2026-11-20** · unreviewed chrome only; badge and safety banner stay English | Gated on Q2. Direction change is not a completed translation | 0.75h |
| ~~D3~~ | ~~RTL audit~~ — **DONE 2026-11-18** | Every `.font-mono-tech` node verified `direction: ltr; unicode-bidi: isolate` under `dir="rtl"` | 0.75h |
| ~~D4~~ | ~~Keyboard pass~~ — **DONE 2026-11-18** | Tab-to-link, Enter activation, visible focus, `aria-disabled` controls reachable with announced reasons | 0.75h |
| ~~D5~~ | ~~axe-core via Playwright~~ — **DONE 2026-11-18** | Zero critical or serious on 4 pages × 2 viewports | 0.5h |
| ~~D6~~ | ~~Responsive pass~~ — **DONE 2026-11-18** | No horizontal scroll at 390px; simulation bar collapse verified | 0.5h |
| ~~D7~~ | ~~Re-verify contrast / reduced-motion~~ — **DONE 2026-11-20** · `npm run verify:contrast` reads `globals.css`; `prefers-reduced-motion` short-circuits pulse | Ratios computed, not estimated | 0.25h |

## Phase E — Delivery assets (F6)

| # | Step | Acceptance | Est. |
| --- | --- | --- | --- |
| ~~E1~~ | ~~Playwright E2E for both journeys~~ — **DONE 2026-11-18** · [evidence](../03-evidence/D-browser-pass/checks.md) | 36/36 across desktop and mobile against the live API | 1h |
| ~~E2~~ | ~~Guest journey on a clean browser session~~ — **DONE 2026-11-18** | Fresh context per test; no credentials required | 0.5h |
| ~~E3~~ | ~~Record the demonstration~~ — **FOOTAGE DONE 2026-11-18** · [50s walkthrough](../03-evidence/E-delivery/recording/namaa-demo-walkthrough.webm) | Reproducible via `npm run demo`; narration still to record over it | 0.75h |
| ~~E4~~ | ~~Assemble deck and screenshots~~ — **DONE 2026-11-18** · [12-slide deck](https://claude.ai/artifact/XCVbNx8Kf2Gy8q8XEJi4nE) · 18 screenshots | Built / simulated / not built separated on slide 9 | 0.5h |
| ~~E5~~ | ~~Deployment instructions and local fallback~~ — **DONE 2026-11-20** · `npm start` → `scripts/start-standalone.mjs`; Docker already `node server.js`. Q7 hosting still open | A fresh reviewer can start the UI from [web/README.md](../../web/README.md) | 0.25h |

## Polish backlog

- ~~**Hover treatment for the dark fill**~~ — **DONE 2026-11-20**. `#0F5C5C` stays on primary
  actions. Selected nav, filter pills and context chips use brand underline / subtle fill;
  hover is canvas, not always-on brand fill.
- ~~Row hover and selected-nav treatments (D002 §5)~~ — **DONE 2026-11-20**.
- ~~Reset confirmation visual refinement~~ — **DONE 2026-11-20** (`alertdialog`, overdue tokens,
  consequence stated).

## What the frontend needs from the team

| Need | From | Blocks |
| --- | --- | --- |
| **Q1** stack decision | All three | Resolved (D003). A5 shipped as application-store inspector |
| **Q5** API paths, action names, role requirements | Ismail | Resolved (D003) |
| **Q8** server-side small-cell suppression | Ismail + Alfred | Resolved; reporting cohort publishes; threshold ≥ 10 |
| **Q2** whether Arabic copy ships | All three | Still open. Chrome dictionary ships labelled unreviewed |
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

Phase C landed 2026-11-18: the server validates every transition. Remaining simulated pieces are
the FHIR gateway stub, deterministic extraction (not MedGemma), and unreviewed Arabic chrome.
The submission must describe that level of integration, including HAPI not deployed.
