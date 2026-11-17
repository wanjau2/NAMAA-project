# A2 — Action forms: acceptance checks

**Date:** 2026-11-17
**Owner:** Mark
**Build:** Next 16.4.6 production build; transition rules executed directly under Node 22
**Reproduce:** `cd web && npm run verify:actions`

All data is synthetic. These are software checks on the frontend's local transition layer,
not clinical validation.

## Acceptance criteria from the roadmap

> Only valid transitions are exposed; closure requires an evidence reference; every form labels
> itself a simulation.

## Transition rules — 26/26 pass

Run `npm run verify:actions` ([web/scripts/verify-actions.ts](../../../web/scripts/verify-actions.ts)).

| Group | Check | Result |
| --- | --- | --- |
| Role boundary | Coordinator cannot approve a pathway | ✅ `forbidden_role` |
| Role boundary | Coordinator cannot authorize clinical closure | ✅ `forbidden_role` |
| Missing data | `needs_review` blocks pathway approval | ✅ `precondition_failed` |
| Attestation | Approval requires reviewer attestation | ✅ `validation_failed` |
| Approval | Reviewer approves: `identified → reviewed`, revision increments | ✅ |
| Concurrency | Stale `expected_revision` is rejected, not applied | ✅ `stale_revision` |
| Engagement | Invitation blocked until a contact preference is recorded | ✅ `precondition_failed` |
| Engagement | Preference recorded, then `reviewed → invited` | ✅ |
| Decline | Decline sets disposition only; stage unchanged | ✅ stays `invited` |
| Decline | Decline is never relabelled `completed` | ✅ |
| Booking | `invited → booked` | ✅ |
| **Booking** | **Booking alone cannot close as completed** | ✅ `invalid_transition` |
| Attendance | Did-not-attend does not advance the stage | ✅ stays `booked` |
| Attendance | `booked → attended` | ✅ |
| **Closure** | **Closure without an evidence reference fails** | ✅ `validation_failed` on `evidence_reference` |
| **Closure** | **Closure without reviewer attestation fails** | ✅ `validation_failed` on `attestation` |
| Closure | Closure with evidence + attestation completes, evidence retained | ✅ `closed/completed` |
| Closure | Completion records the evidence reference on the event | ✅ |
| **Counting** | **`close_other` closes without completing** | ✅ `clinically_closed_other` |
| Reopening | Reopen requires a reason | ✅ `validation_failed` |
| Reopening | Reopen returns the case to `follow_up` / `active` | ✅ |
| Referral | Rejected referral stays open, owned and overdue | ✅ owner preserved |
| Referral | Rejected referral blocks completion until reassigned | ✅ `precondition_failed` |
| Deferral | Deferral retains a recall date; not a completion | ✅ |
| Audit | Every event records prior → new state and the request id | ✅ |

## Offered actions by state — verified in the served build

Only applicable actions appear. Confirmed over HTTP against `next start`:

| Case | State | Offered | Correctly absent |
| --- | --- | --- | --- |
| `case-0001` | `identified` / `active`, `flag_status: needs_review` | Approve pathway *(blocked, with reason)*, Record contact preference, Reassign owner, Defer with recall date, Close for another reason | **Send invitation** (stage is not `reviewed`), **Book appointment**, **Record attendance**, **Close as completed** |
| `case-0002` | `booked` / `active` | Record attendance, Record decline, Record contact preference, Reassign owner, Defer with recall date, Close for another reason | **Close as completed** (booking alone cannot complete), **Book appointment** (already booked), **Approve pathway** (already reviewed) |

Rendered copy confirmed present:

- `Information is missing or unverified. Resolve it in source review and let the rule re-evaluate before approving — unknown is not the same as up to date.`
- `Requires the Clinical Reviewer role. Switch role in the simulation bar to demonstrate this step.`
- `Simulated` badge on invitation and booking
- `Valid next actions for <stage>/<disposition> at rev <n>`

## Other behaviour built and asserted

| Behaviour | How |
| --- | --- |
| Mutation envelope | Every submit carries `action`, `expected_revision`, `request_id`, `data`. The form shows the exact JSON under "Request envelope" so the contract is concrete for Ismail |
| Idempotency | A repeated `request_id` returns the first result and appends **no second event**; the form says "the repeated request produced no second event" |
| Failed submit preserves input | Entered values are never cleared on error (D002 §4) |
| Stale revision recovery | Inline overdue banner with **Reload latest state**, entries kept |
| Server-echo only | The UI never advances a stage itself; it renders what the store returned |
| Field errors | `field_errors` map to the specific input, with `aria-invalid` and `aria-describedby` |

## Toolchain note

`scripts/` is excluded from the app `tsconfig.json` (Node type-stripping needs explicit `.ts`
import extensions, which Next's config rejects) and has its own `scripts/tsconfig.json`, so the
checks stay type-checked: `npx tsc -p scripts --noEmit`.

## Limitations

- **This is not enforcement.** `lib/case-actions.ts` and `lib/case-store.tsx` are a labelled
  stand-in for Ismail's server and must be **deleted at F4**. Anyone with devtools can reach any
  state. Every rule asserted above must also exist server-side; these checks are written so they
  can be re-pointed at the real API.
- Nothing persists across a reload. No `Provenance`, no FHIR write, no reviewer identity.
- Idempotency is in-memory per session, and failures are deliberately not memoised so a
  corrected retry with the same `request_id` is allowed through.
- Overdue escalation is set by action outcomes, not by a clock. No worker checks deadlines.
- Not yet run: axe-core, keyboard-only completion, RTL snapshot (D4–D6).
