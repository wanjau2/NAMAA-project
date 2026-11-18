# A4 — Population dashboard: acceptance checks

**Date:** 2026-11-17
**Owner:** Mark
**Route:** `/metrics`
**Reproduce:** `cd web && npm run verify:metrics` (53 checks), then `npm run build && npm start`

All counts are fictional. These are software checks on metric *definitions* and suppression
logic. Nothing here evidences clinical accuracy, calibration or effectiveness.

## Acceptance criteria from the roadmap

> Denominators always visible; declined and unreachable people remain in the denominator; no
> figure implies a real-world outcome.

## Definition checks — 53/53 pass

| Group | Check | Result |
| --- | --- | --- |
| Cohorts | Child and adult reported as separate cohorts | ✅ |
| Denominator | Only one disposition counts as completed | ✅ |
| Denominator | The completing disposition equals the published numerator | ✅ |
| Denominator | `clinically_closed_other` does not count as completed | ✅ |
| Denominator | Declined / deferred / unreachable / other all reported, not dropped | ✅ 4 non-completions per pathway |
| Denominator | Non-completions fit inside the eligible denominator | ✅ |
| Funnel | Monotonic: eligible ≥ invited ≥ booked ≥ attended | ✅ |
| Funnel | Verified completed never exceeds attended | ✅ |
| Funnel | Follow-up completed never exceeds follow-up due | ✅ |
| Funnel | Eligible-due step equals the published denominator | ✅ |
| Funnel | Booking and attendance carry their caveats | ✅ |
| Timeliness | Missing timestamps reported rather than excluded | ✅ |
| Suppression | No published cell is below the threshold | ✅ all 6 groups |
| Suppression | Suppressed cells carry **no value** in the returned data | ✅ |
| Suppression | Never exactly one suppressed cell in a group | ✅ |
| Suppression | Residual cannot be attributed to a single cell | ✅ |
| Suppression | A lone small cell triggers complementary suppression of the next smallest | ✅ |
| Suppression | Complementary suppression labelled with its reason | ✅ |
| Suppression | The largest cell survives suppression | ✅ |
| Suppression | Two small cells need no complementary suppression | ✅ |
| Suppression | No suppression when every cell clears the threshold | ✅ |
| Rate | Null on a zero denominator; percentage otherwise | ✅ |

## Rendering checks — served production build

| Check | Observed |
| --- | --- |
| Synthetic banner | `Synthetic Demo Metrics — fictional population, not real-world outcomes` |
| Numerator / denominator visible | `68 / 142` and `33 / 97` with the label `verified completed / eligible due` |
| Denominator caveat | `Declined, deferred and unreachable people remain in this denominator. Only an authorized closure with evidence counts in the numerator.` |
| Distinct funnel counts | Eligible due, Invited, Booked, Attended, Follow-up due, Follow-up completed, Verified completed |
| Completion labelling | 2 × `Counts as completed`, 8 × `Not a completion` across both pathways |
| Suppressed cells | 10 hatched cells, 10 lock icons, label `Suppressed (n < 10)` |
| Suppressed values absent from markup | `15–17 years` renders the label plus lock only — no count |

Suppressed-cell arithmetic reconciles: child 6 (age 10–14, 15–17; Email + complementary Phone;
Zone D + complementary Zone C) and adult 4 (age 40–44, 60+; Zone D + complementary Zone C) = 10.
The adult channel group has no cell below 10, so nothing is suppressed there.

## Q8 DEMONSTRATED: client-side suppression is cosmetic

The markup is correct, but the suppressed counts are present verbatim in the JavaScript bundle,
because `buildMetrics()` runs in the browser:

```
$ grep -F '"15–17 years",count:3' bundle.js   → PRESENT
$ grep -F '"10–14 years",count:6' bundle.js   → PRESENT
$ grep -F '"Zone D",count:8'      bundle.js   → PRESENT
$ grep -F '"Email",count:7'       bundle.js   → PRESENT
```

Anyone can read the hidden groups from devtools. **This is not a bug in the UI — it is the
reason [Q8](../../02-decisions/OPEN-QUESTIONS.md) exists.** The data layer was written so the
component only ever receives suppressed cells with the value absent, which is the shape the API
must return; moving the computation server-side is what turns that shape into an actual
safeguard.

Until Q8 is resolved, the submission must not claim that suppression protects small groups.

## Deliberate design choices

| Choice | Why |
| --- | --- |
| Suppression applied in the data layer, not the component | The component can only render what it is given, so the contract is already correct for F4 |
| Complementary suppression picks the next smallest | With one cell hidden and the total published, the residual is the hidden value. Losing a large cell is the cost of preventing reconstruction, and the UI says so |
| Fixed cohort snapshot with a refresh time | A projection has latency by design (§10). Session actions are reported **separately** rather than folded in, because a dashboard that invents precision is worse than one that admits latency |
| No charting library | Theme scope guardrail. The funnel is CSS bars with the numbers stated in text |
| Analyst notice | Fixed segment views, no overlapping filters, no individual-level export, so small groups cannot be reconstructed by combining views |

## Limitations

- **Suppression is not yet a security property** (above). Blocked on Q8.
- Counts are a static fixture. No projection rebuild, no reconciliation, no source resource
  versions — all of which §10 requires of the real thing.
- Median time to attendance is a fixture value, not computed from timestamps.
- Session activity shows open-case and rejected-referral counts from live state; it does not
  recompute the cohort.
- Not yet run: axe-core, keyboard-only pass, RTL snapshot (D4–D6). The hatch pattern does not
  mirror under RTL, which is accepted as cosmetic.
