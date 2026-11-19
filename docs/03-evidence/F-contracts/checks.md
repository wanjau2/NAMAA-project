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

---

# 3. Typed extraction contract and the context panel — 2026-11-19

Completes the remaining frontend items from Alfred's handoff that do not need a backend.

**Reproduce:** `cd web && npm run verify:shapes` (24 checks) and `npm run e2e` (46 browser checks).

## Typed extraction and review contract

New: [`web/lib/contracts.ts`](../../../web/lib/contracts.ts) — TypeScript mirrors of
`ai/src/namaa_ai/contracts.py`, plus `fromApiProposal()`, an adapter from the API's flat shape.

The adapter's job is to **not lie about what the API cannot send**. Four contract fields have no
source today — `source_sha256`, `issues`, `relationship`, proposal `version` — so they are `null`
and every one is named in a `missing` list the UI renders from.

The case that matters most:

> An empty `issues` array from an API that does not report issues is **not** "the extractor found
> none". The review screen prints *"Validation issues are not reported by this API. An empty list
> here means **not reported**, not 'none found'."*

Also now rendered per proposal: opaque source version (never parsed as a number), truncated source
hash or "not supplied", model revision with a **simulated** badge when inference was a fixture, and
the family relationship when present — or an explicit note that the API does not supply it.

`hasBlockingIssue()` distinguishes `block` from `review` severity; a blocking issue prevents
acceptance in the same way an unverifiable quote does.

## Assembled-context panel

New: [`web/components/context-panel.tsx`](../../../web/components/context-panel.tsx) on its own
route, `/cases/[id]/context`.

**Why a separate route.** Alfred asked that the AI explanation and context view stay distinct from
review decisions and rule results. Putting retrieved records on the case detail screen — beside the
rule outcome and the action panel — invites exactly the conflation he is guarding against.

The panel's default state is the truth: **no verified-context service exists**. That is rendered as
an absence of a service, explicitly *not* as a finding that no records exist. Alfred's published
examples (`ai/examples/assembled-context.json`, copied verbatim) are available behind a labelled
toggle so the rendering can be reviewed before M2 lands.

What every result carries, never optional:

| Element | Behaviour |
| --- | --- |
| Completeness | `complete_in_checked_scope` / `partial` / `unknown`, each with its meaning. "Complete" is always scoped to what was **checked**, never to the record |
| Checked scope | The backend's notice, plus generation id and permission revision |
| Non-exhaustive notice | Not dismissible: "absence of a record here is **not** evidence that it does not exist" |
| Empty result | Renders as **Unknown — nothing was returned**, never "nothing found" |
| Per item | Resource reference, opaque version, retrieval tier, last updated, verified at, and authorized / source-verified / **reviewed** markers |
| Offsets | Code points; an unverifiable span is stated, never guessed |
| Framing | "Not a diagnosis, a permission, a clinical risk or an eligibility decision" |

## Checks

**24/24** shape checks, including: fields nested under `fact`; metadata outside it; the source
version carried as an opaque string; absent fields null **and** listed; an offline fixture marked
simulated while a live mode is not; blocking vs review severity; "complete" scoped to what was
checked; "unknown" forbidding absence statements; and the empty envelope resolving to
`empty_unknown` / `unknown`.

**5 new browser checks** (46 total, desktop and mobile), covering the absence-of-service wording,
the not-a-diagnosis framing, a loaded envelope's completeness and markers, the empty-as-unknown
rendering, and the issues-not-reported line on the review screen.

## Regression status

Lint, both typechecks and build clean. **49/49** API contract, **53/53** metrics, **24/24**
offsets and outcomes, **24/24** shapes, **46/46** browser.

## Still blocked on the team

- **Q12 / M0** — rule-outcome enum. The display layer handles four; the API can send two.
- **Q10 / M1** — no review-write endpoint, so review decisions remain unpersisted.
- **M2** — no verified-context service, so the panel's live mode is correctly empty.
- **C3** — analytics cohort still suppresses all sixteen cells.

The frontend side of Alfred's M0–M3 is now built as far as it can go without those four.

---

# 4. Review wiring, security states and a readiness gate — 2026-11-19

Delivered against Alfred's five-item request. **Three of the five describe API capabilities that
do not exist in the running service**, verified against the live route list on 2026-11-19:

| Alfred's item | Status in the running API |
| --- | --- |
| Proposals use the nested contract | **Flat.** Keys are `concept, value_text, subject, …` with no `fact` |
| `POST /api/v1/facts/{id}/review` | **Absent.** Not in `/openapi.json`; returns 404 |
| Eval returns `not_eligible` via `rule_evaluation.outcome` | **Absent.** Evaluations return `flag_status` only, with no `outcome` or `rule_evaluation` key |
| Security UX for denied / stale / failed | Endpoints exist (`/security/*`, `/authz/*`, `/audit/events`) |
| Metrics suppression API-driven | Already true; unchanged |

So the work was built to be correct **whether or not** those land.

## Readiness gate replaces prose

`npm run verify:api` now reports a third category. Agreed-but-unimplemented capabilities are
`PENDING`, not `FAIL`: they do not break the suite, and they flip to `PASS` by themselves the day
the API ships them.

```
50 passed, 0 failed, 6 pending (agreed but not implemented)

PENDING  proposals use the nested `fact` contract
PENDING  proposals carry an integer concurrency version
PENDING  proposals carry validation issues
PENDING  proposals carry a source hash binding them to an exact note
PENDING  POST /api/v1/facts/{id}/review exists — returns 404
PENDING  evaluations expose a four-value rule outcome — only flag_status "needs_review"
```

This is a more precise handoff artefact than any status document: it is executable, it names the
exact gap, and nobody has to believe a claim about it.

## Both proposal shapes are read

`normalizeProposal()` accepts the nested contract **or** the current flat payload and reports
which it saw. The interface keeps working the day the backend switches, with no coordinated
deploy. Nested payloads supply version, `source_sha256` and issues, so nothing is reported as
missing; flat ones name each absence.

## Review wired to the real endpoint

Review decisions now call `POST /api/v1/facts/{id}/review` with
`X-Namaa-Role: clinical_reviewer` and Alfred's `ReviewCommand` shape, and report precisely what
happened:

| Outcome | Shown to the reviewer |
| --- | --- |
| Persisted | "Recorded by the server. Proposal now at version N." |
| 404 / 405 | "Held in this browser only… not an authorization receipt." |
| Cannot build | The reason — see below |
| 403 / 409 / 422 / 429 / transport | The security outcome, via the shared envelope |

**The client refuses to invent a concurrency token.** `ReviewCommand` requires
`expected_proposal_version`, and flat proposals carry none. Rather than send `1` and hope, the
command is not built and the reviewer is told why: *"a fabricated version would let a review
address a proposal the reviewer never saw."* This resolves itself when proposals go nested.

## Security states never leak existence

New: [`web/lib/security-states.ts`](../../../web/lib/security-states.ts).

The governing rule: **403 and 404 are indistinguishable to the user.** If "forbidden" and "not
found" read differently, anyone can enumerate which patients, notes or jobs exist in another
workspace by watching which message appears. Both resolve to one `not_available` state with
identical wording, which also explains *why* it is identical. The structured code remains visible
for developers.

Covered for all four operations Alfred named — note retrieval, SSE, disclosure, review — with
`stale` (409) offering non-destructive recovery, and failures stating that nothing changed. A
failed extraction still carries "not a finding of no care gap".

## Checks

| Suite | Result |
| --- | --- |
| `verify:metrics` | 53/53 |
| `verify:contracts` (offsets, outcomes) | 24/24 |
| `verify:shapes` (contracts, review, security) | **45/45** (was 24) |
| `verify:api` (live) | **50 passed, 0 failed, 6 pending** |
| Browser, desktop + mobile | **48/48** (was 46) |

New among them: both proposal shapes read; a review command refused without a version; `correct`
without a replacement fact refused and `accept` with one refused; empty reason refused; 403/404
indistinguishable for all four operations; denied disclosure marked an access outcome rather than
a clinical finding.

## Update — Ismail I4–I7 landed on API (2026-11-19)

Against current `main` API, the readiness probes should flip:

| Item | Now |
| --- | --- |
| Nested `fact` proposals + version / issues / `source_sha256` | **Present** |
| `POST /api/v1/facts/{id}/review` | **Present** (FHIR outbox still stub) |
| `rule_evaluation.outcome` incl. path to `not_eligible` | **Present** on evaluations |
| `POST /api/v1/security/verified-context` + Relate GETs | **Present** (context panel still shows absence until Mark wires live fetch) |

`CaseRow.flag_status` remains `gap | needs_review` for worklist rows; four-value outcomes live on evaluation responses. Re-run `npm run verify:api` with API up to refresh the PASS/PENDING counts.

## What Alfred still needs to land

Items 1, 2 and 3 of his list. The frontend is wired for all three and will start exercising them
without further changes — the readiness gate will say so.
