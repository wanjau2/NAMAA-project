# Milestone log

Newest first. One line per milestone; detail lives in the linked record.

| # | Date | Milestone | Owner | Status | Record |
| --- | --- | --- | --- | --- | --- |
| M00 | 2026-11-17 | Documentation baseline established | Mark | Done | [M00-documentation-baseline.md](M00-documentation-baseline.md) |

## Planned milestones

Taken from the delivery gates in the design specification, which supersede the
three-day schedule in the work plan (see OPEN-QUESTIONS Q1).

| # | Gate | Acceptance summary |
| --- | --- | --- |
| M01 | Kickoff and contracts locked | Stack decided; records, API contract, action names, screens and labels agreed and written down. |
| M02 | Foundation | Datastore up, workspaces isolated, seed data validated, patient records display. |
| M03 | Reviewable intelligence | Care-gap evaluation runs from reviewed facts only; proposals stay outside the clinical store until accepted; explanations readable. |
| M04 | Accountable care | Both synthetic journeys complete end to end: review, ownership, invitation, booking, attendance, referral, evidence-backed closure, escalation. |
| M05 | Reliability and isolation | Stale-revision rejection, duplicate-request safety, overdue escalation, guest reset, audit trail, cross-workspace isolation. |
| M06 | Interface complete | Worklist, case detail, equal-weight uncertainty, action panel, metrics with denominators and suppression, keyboard access, both widths. |
| M07 | Release and submission | Both journeys on one build, claims register verified, recording, deck matching the product, submission package and receipt. |

## Status vocabulary

`Done` — acceptance checks pass in the integrated build, evidence linked.
`Partial` — working but with a stated limitation. Name the limitation.
`Mocked` — the interface or contract exists; the behavior behind it is simulated.
`Blocked` — name the blocker and the owner.
