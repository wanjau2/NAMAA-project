# Code-point offsets and the four rule outcomes

**Date:** 2026-11-18
**Owner:** Mark, against Alfred's handoff (`ai/docs/CONTRACTS.md`, `ai/src/namaa_ai/contracts.py`)
**Reproduce:** `cd web && npm run verify:contracts` — 24 checks, no services needed

## 1. Offsets are Unicode code points, not JavaScript indices

Alfred's contract states it directly: offsets are zero-based, end-exclusive **Unicode code
points**, and JavaScript must use `Array.from(text).slice(start, end).join("")`.

The UI was slicing with `text.slice()` — **UTF-16 code units**. Python indexes by code point,
JavaScript by code unit.

**This was not broken in the current build**, and the earlier evidence that said every excerpt
verified was true. ASCII agrees between the two; so does Arabic, which is inside the BMP at one
code unit per character. They diverge for **astral characters** — emoji and rarer scripts — and
the failure is silent: the excerpt stops matching, the proposal is marked untraceable, and a
correct extraction becomes unreviewable with no error anywhere.

The check that proves it, from the suite:

```
PASS  astral: code-point slice recovers the excerpt
PASS  astral: the naive JS slice at the SAME offsets does NOT — the bug this prevents
```

New module: [`web/lib/text-offsets.ts`](../../../web/lib/text-offsets.ts).

### Null offsets

Alfred: null offsets mean the source match failed or was ambiguous, and the UI must **never**
highlight the first occurrence of the excerpt — that would invent a provenance the extractor did
not claim. `ApiProposal.offset_start` / `offset_end` are now `number | null`, and the three
failure modes are told apart on screen rather than collapsed into one message:

| State | What the reviewer is told |
| --- | --- |
| `no_offsets` | "No source offsets were returned… the interface will not guess one." |
| `out_of_range` | "The stated offsets fall outside this note." |
| `mismatch` | "The text at these offsets does not match the excerpt. The note reads …" |

All three block acceptance. The caption now reads `code points 44–86` rather than `offsets`.

## 2. All four rule outcomes, none collapsed

New module: [`web/lib/rule-outcomes.ts`](../../../web/lib/rule-outcomes.ts) and
[`web/components/rule-outcome.tsx`](../../../web/components/rule-outcome.tsx).

Each outcome carries a label, a meaning, and a **limitation that is never optional**:

| Outcome | Limitation shown with it |
| --- | --- |
| `gap_identified` | A prioritization signal for human review. Not a diagnosis; does not order a test. |
| `no_gap_identified_in_available_data` | **Not an assurance of health.** Absent records were not assessed. |
| `needs_review` | Unknown is not the same as up to date. The pathway stays blocked. |
| `not_eligible` | Scoped to this pathway only. Says nothing about other preventive care. |

Deliberately **not** the `StatusBadge` vocabulary: Alfred asked that the AI explanation and
context view stay distinct from review decisions and rule results, so a rule outcome has its own
component, icons and shapes.

Before this, the worklist and case header labelled only `needs_review` — a `gap` case showed no
outcome at all, and `not_eligible` had nowhere to appear.

### Handling the three-way divergence (Q12)

`resolveOutcome()` maps what the API sends today and **reports how it got there**:

- `canonical` — Alfred's vocabulary, passed through
- `aliased` — a known API spelling (`gap`, `no_gap`) mapped, and the UI says so on screen
- `unknown` — shown as `needs_review` **and flagged in red**: "The server reported an outcome
  this interface does not recognise… Do not read it as a conclusion."

An outcome nobody agreed on is never silently rendered as a conclusion.

## Checks — 24/24 pass

Offsets: ASCII parity, Arabic BMP parity, astral divergence proven both ways, before/match/after
split, null and half-null offsets, out-of-range, inverted span, mismatch reporting what it found.

Outcomes: four outcomes exist, each has label + meaning + limitation, the two reassurance-prone
limitations are asserted by content, no two labels collide, canonical pass-through, aliasing
flagged, unknown falls back and is flagged, only `needs_review` blocks the pathway.

## Regression status

Build, lint and both typechecks clean. **49/49** API contract checks and **36/36** browser checks
still pass. Demo footage and the three affected deck screenshots were regenerated so the deck
still matches the product.

## Still blocked

- **Q12 / Alfred's M0** — the API has no `not_eligible` and `CaseRow.flag_status` is still
  `gap | needs_review`. The display layer is ready; the enum is not agreed. Until it is, the UI
  can only ever show two of the four from live data.
- Review persistence (Q10), verified-context panel (M2/M3), server-sourced metrics (C3).

## Note on the astral test data

The suite uses emoji to force the divergence. No note fixture contains astral characters today,
so this is a latent bug fixed before it could bite, not an observed failure.
