# D006 — Canonical rule-outcome contract and case lifecycle

**Date:** 2026-11-20
**Status:** Accepted
**Decided by:** Alfred (contract owner) with Ismail implementing the backend projection
**Resolves:** OPEN-QUESTIONS Q12; I00 / M00

## Context

Three vocabularies described the same four evaluation results. Cases could only carry
`gap | needs_review`, so live worklist data could not represent no-gap or ineligible
results. Creating a care-gap case solely to display those outcomes would invent work.

## Decision

We will use Alfred's four names verbatim on `rule_evaluation.outcome`:

- `gap_identified`
- `no_gap_identified_in_available_data`
- `needs_review`
- `not_eligible`

`legacy_flag_status` and `api_compatibility` remain explicit compatibility projections
via `prepare_rule_handoff`. `not_eligible` projects to a null legacy flag and must not
be stored or displayed as `no_gap`.

A care-gap **case** is opened or refreshed only for `gap_identified` and `needs_review`.
Evaluations that return `no_gap_identified_in_available_data` or `not_eligible` persist
the canonical object and return `case: null`. An existing workflow is not auto-closed,
completed, or coerced. Callers read the latest evaluation separately from case stage
and disposition.

## Options considered

| Option | Pro | Con | Why not chosen |
| --- | --- | --- | --- |
| Widen `CaseRow.flag_status` to four values | Worklist can show every outcome | Mixes rule result with workflow | A case is work to do; no-gap/ineligible is not work |
| Auto-close on not_eligible | Worklist stays tidy | Silent completion / lost ownership | Forbidden by the non-negotiables |
| Keep API `gap` / `no_gap` as canonical | Less UI change | Diverges from the evaluator | Alfred's package is where rules run |

## Consequences

Mark consumes `rule_evaluation.outcome` on the evaluation resource, including
`case: null`. Worklist `flag_status` stays `gap | needs_review` for open work.
Ismail persists the nested canonical object; a reload must recover all four values
without reconstructing them from a lossy flag.

## Revisit when

The team needs an evaluation-only worklist that is not a care-gap case.
