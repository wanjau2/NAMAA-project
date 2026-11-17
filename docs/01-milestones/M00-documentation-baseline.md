# M00 — Documentation baseline

**Date:** 2026-11-17
**Owner:** Mark
**Status:** Done
**Gate:** Pre-kickoff

## What changed

The project directory was empty; the three planning documents existed only as chat
attachments. They are now on disk as the reference baseline, with a documentation
structure for recording every subsequent milestone, decision and piece of evidence.

## Scope delivered

| Item | Built | Mocked | Not started | Note |
| --- | --- | --- | --- | --- |
| `docs/00-reference/` with all three source documents | ✅ | | | Verbatim; the baseline spec |
| `docs/README.md` index and non-negotiables | ✅ | | | Eight safety rules extracted from the specs |
| `docs/01-milestones/` log + template | ✅ | | | M01–M07 planned from the design spec's delivery gates |
| `docs/02-decisions/` index, template, open questions | ✅ | | | Seven open questions, none yet decided |
| `docs/03-evidence/` structure and rules | ✅ | | | Empty until M02 |
| Application code | | | ❌ | Nothing written. Blocked on Q1 (stack). |

## Acceptance checks

| Scenario | Expected | Observed | Pass | Evidence |
| --- | --- | --- | --- | --- |
| Reference documents readable from disk | All three present, content intact | 213 / 449 / 168 lines written | ✅ | `docs/00-reference/` |
| A new team member can find the rules | Index names the non-negotiables and points to each source | `docs/README.md` | ✅ | — |
| Conflicts between the plans are visible, not buried | Each disagreement stated with both positions | 7 questions registered | ✅ | `docs/02-decisions/OPEN-QUESTIONS.md` |

## Non-negotiables re-verified

Not applicable — no product surface exists yet. The eight rules are now written down in
`docs/README.md` and the milestone template carries them as a per-milestone checklist.

## Contract changes

None. No contract has been agreed yet. Both candidate API conventions are recorded in Q5.

## Known limitations

- The documentation describes a product that **does not exist yet**. Nothing here should be
  read as implemented.
- The two reference plans specify materially different systems. Until Q1 is decided, the
  milestone list M01–M07 follows the design specification's gate sequence, which may change.
- The submission deadline is unverified. Alfred owns checking the portal (Q4).

## Next

Kickoff decisions, in this order — all three members present:

1. **Q1 stack** — then record it as `D001`. Nothing else can start first.
2. **Q5 API convention and the five shared records** (Patient, Observation, Care gap, Case,
   Event/evidence) — Ismail writes them down; Alfred and Mark confirm before coding.
3. **Q3 AI scope** — decides whether Alfred's week is fixtures or an evaluation set.
4. **Q2 language scope** — Mark adopts logical CSS properties regardless.
5. **Q4** — Alfred reports the portal requirements into the open-questions register.

Milestone M01 closes when items 1–4 are recorded as decisions.
