# Open questions register

Last updated: 2026-11-17

Questions that must be answered before or at kickoff, because they change what gets built.
The two reference plans disagree in places — that is expected (one is a three-day sprint plan,
the other a full architecture), but the team has to lock one answer per row and record it as a
decision. Recommendations below are suggestions, not settled calls.

| ID | Question | Status |
| --- | --- | --- |
| Q1 | Which stack do we actually build? | **Resolved for sprint** — [D003](D003-backend-stack-and-api.md): FastAPI + SQLite; HAPI deferred |
| Q2 | English only, or bilingual EN/AR with RTL? | **Open** — implementation half settled by [D002](D002-ui-theme-addendum.md) |
| Q3 | Is MedGemma extraction in the demo or deferred? | **Deferred for sprint** — deterministic rules only (D003); revisit if Q6 clears |
| Q4 | What is the real submission deadline and required file list? | **Open — Alfred to verify portal** |
| Q5 | Which API path convention is authoritative? | **Resolved** — [D003](D003-backend-stack-and-api.md): `/api/v1/...` |
| Q6 | Do we have model hosting and GPU budget? | **Open — prerequisite** |
| Q7 | Where does the demo get hosted, if anywhere? | **Open** |
| Q8 | Does the metrics API suppress small cells server-side? | **Resolved** — [D003](D003-backend-stack-and-api.md): yes, server-side. Verified live; see note below |
| Q9 | Should the API return `available_actions` per case? | **Open — Mark → Ismail** |
| Q10 | Are there proposal / fact-review endpoints this sprint? | **Half answered** — read path shipped; **no write endpoint** |
| Q11 | How does a client find a case's source documents? | **Open — no listing endpoint** |
| Q12 | Which rule-outcome vocabulary is authoritative? | **Open — three in play; Alfred's M0** |

---

## Q1 — Which stack do we actually build?

The two documents specify different systems:

| | Work plan | Design specification |
| --- | --- | --- |
| Backend | FastAPI + SQLite | FastAPI + PostgreSQL + HAPI FHIR JPA server (separate PostgreSQL) |
| Frontend | React + TypeScript | Next.js + TypeScript |
| Intelligence | Local deterministic Python rules module | MedGemma 1.5 4B on Hugging Face Inference Endpoints + deterministic rules |
| Clinical data | Plain application tables | FHIR R4 4.0.1 resources, profiles, validator, transaction Bundles |
| Deployment | One-command local startup | Docker Compose: proxy, frontend, API, worker, PostgreSQL, HAPI |
| Timeline | 3 days, ~18 focused hours each | Four sequenced gates; explicitly calls 3 days "a stretch target" |

The work plan also says **"do not add a separate AI service or external model dependency to the
critical path"** — which the design specification's MedGemma endpoint directly is.

These are not reconcilable by compromise. Pick one and write it down.

**Recommendation:** build the design specification's shape (FHIR-first is the project's actual
differentiator and the UI design system already assumes FHIR resources, revisions and an audit
inspector), but treat MedGemma as **optional and gated** per Q3, and accept that the three-day
schedule becomes the gate sequence in the milestone log rather than a calendar. If the deadline
turns out to be genuinely 72 hours (Q4), fall back to the work plan's FastAPI + SQLite defaults
and present FHIR as designed-not-built.

## Q2 — English only, or bilingual EN/AR with RTL?

- Work plan: "Offer English and an Arabic preference in the demonstration… Support right-to-left layout if Arabic copy is included."
- UI theme prompt: mandates a language toggle (`EN` / `عربي`), IBM Plex Sans Arabic, and **logical CSS properties only** so the layout mirrors.
- Design specification: "English only" under confirmed decisions; "English-only is a prototype limitation; Arabic and other languages require later local testing and separate evaluation."

**Recommendation:** adopt the UI prompt's discipline unconditionally — use logical CSS
properties (`ms-*`, `pe-*`, `text-start`) from the first component, since retrofitting them is
expensive and they cost nothing now. Then decide separately whether Arabic *copy* ships. If it
does, every unreviewed string carries the `Unreviewed demo translation` badge and is never
presented as clinically approved.

## Q3 — Is MedGemma extraction in the demo or deferred?

The design specification puts source-linked AI extraction in gate 2 of 4 and asks for a
**40-note labelled evaluation set** with precision/recall, assertion accuracy, attribution and
quote validity reporting. The work plan's A1–A6 packages (18 hours) contain no such workload —
its intelligence layer is a deterministic rules module, with AI wording as an optional extra.

This is the single largest scope difference between the documents.

**Recommendation:** deterministic rules are the critical path and must work without the model.
Treat extraction as a gated addition with a clearly labelled offline fixture fallback — the
design specification already permits labelled offline fixtures for rehearsal, provided they are
never presented as live inference.

## Q4 — What is the real submission deadline and required file list?

Both documents state the deadline is unconfirmed. The work plan assigns **Alfred** to check the
official portal for deadline, required files, eligibility and access conditions, and to record
the result here. Nothing downstream can be sized until this is known.

## Q5 — Which API path convention is authoritative?

| Purpose | Work plan | Design specification |
| --- | --- | --- |
| Read cases | `GET /cases`, `GET /cases/{id}` | `GET /api/v1/cases`, `/cases/{id}` |
| Evaluate | `POST /patients/{id}/evaluate` | `POST /api/v1/patients/{id}/evaluations` |
| Act on case | `POST /cases/{id}/actions` | `POST /api/v1/cases/{id}/actions` |
| Metrics | `GET /metrics` | `GET /api/v1/analytics/overview`, `segments` |
| Guest reset | `POST /demo/reset` | `POST /api/v1/demo/sessions`, `reset` |

Both agree on the important part: mutations carry an **action name, expected revision and
request ID**, and errors return `code`, `message`, `field_errors` (+ `request_id`).

**Recommendation:** the versioned `/api/v1/...` paths, since the UI prompt already references
`POST /demo/reset` loosely and a prefix is trivial for the frontend to configure once.
Ismail owns this contract either way.

## Q6 — Do we have model hosting and GPU budget?

The design specification lists as prerequisites: an eligible Hugging Face account, accepted
MedGemma license terms, and compute budget for a GPU with **at least 24 GB memory**. Unknown
whether the team has these. If not, Q3 answers itself.

## Q7 — Where does the demo get hosted, if anywhere?

Both documents allow a local-startup fallback plus a recording if hosting fails. Decide early
whether to attempt hosting at all, because "a fresh browser can enter the demo without
unavailable credentials" is in the release gate.

## Q8 — Does the metrics API suppress small cells server-side?

Raised by [D002](D002-ui-theme-addendum.md) §8. Both reference documents require `n < 10`
suppression including complementary totals, but neither says **where** it happens.

If the frontend applies it, the true counts still travel in the network response and anyone can
read the hidden group from DevTools — the suppression is cosmetic. Suppression also depends on
cohort and complementary-cell logic that lives with the metric definitions, not in the UI.

**Recommendation:** the API returns the cell already suppressed with the value omitted —
`{ "suppressed": true, "reason": "small_cell", "threshold": 10 }` — and the UI renders only what
it is given. Owners: Ismail (endpoint) and Alfred (cohort and complementary logic).
Mark cannot close the suppression acceptance check until this is decided.

### Why this mattered — demonstrated client-side leak (2026-11-17)

`/metrics` was built with suppression applied in the data layer, and the rendered markup is
correct: 10 suppressed cells, lock icons, no values. The hidden counts are nevertheless readable
in the JavaScript bundle, because the computation runs in the browser:

```
grep -F '"15-17 years",count:3' bundle.js   -> PRESENT
grep -F '"Zone D",count:8'      bundle.js   -> PRESENT
```

See [A4 evidence](../03-evidence/A4-population-dashboard/checks.md). This was the argument for
deciding Q8 the way [D003](D003-backend-stack-and-api.md) did, and `GET /api/v1/analytics/overview`
now suppresses server-side: verified on 2026-11-18, with suppressed cells returning
`numerator: null, denominator: null, suppressed: true, reason: "small_cell", threshold: 10`.

**Residual issue — not a suppression bug.** With the seeded cohort at 3 cases per pathway and a
threshold of 10, **all 16 analytics cells return suppressed**, so the population view renders
nothing but locked cells. The logic is right and the cohort is too small. The team needs to
choose: a larger synthetic reporting cohort in the API seed, or a stated demonstration
threshold. Until then `/metrics` stays on its local cohort fixture and is labelled as such.

## Q9 — Should the API return `available_actions` per case?

Raised by Mark, 2026-11-18. `lib/action-catalog.ts` keeps `displayWhen` stage predicates so the
action panel does not offer obviously irrelevant controls. They are documented as display hints
and the server still decides — a wrong hint surfaces as `invalid_transition`, which the UI shows.

But it is duplicated knowledge, and the kind that drifts silently. If `GET /api/v1/cases/{id}`
returned `available_actions: [{ id, permitted_role, blocked_reason }]`, the hints could be
deleted and the panel would render exactly what the server permits.

**Recommendation:** add it when there is slack. Low risk, removes a duplication. Until then
`npm run verify:api` fails if the catalog and `/meta/actions` disagree on ids or roles.

## Q10 — Are there proposal / fact-review endpoints this sprint?

Raised by Mark, 2026-11-18. The API models no proposals: `grep -ri proposal api/app` returns
nothing. The design specification §7 has `POST /api/v1/documents/{id}/extractions`,
`GET /api/v1/extractions/{id}` and `POST /api/v1/facts/{id}/review`, none of which are built —
consistent with Q3 deferring MedGemma.

Consequence: the source review screen (A1) runs on `lib/source-review-fixtures.ts` and review
decisions are **not persisted** — no `Provenance`, no reviewer identity, nothing carried into
rule evaluation. The screen states this on-screen.

**Options:** (a) accept it and label the screen a simulation in the submission; (b) Ismail adds
proposal read + review write endpoints backed by the existing seed, with no model in the loop.
(b) is a few hours and would make the review step genuinely server-authoritative like the rest.

**Recommendation:** (b) if time allows, since human review of proposed facts is the concept's
central safety claim. Otherwise (a), stated plainly.

## Q11 — How does a client find a case's source documents?

Raised by Mark, 2026-11-18, during the A1 read-path cutover. There is no documents-by-case
listing, and the two available routes are each incomplete:

| Case | Cites in `detail.factors` | Document actually exists? |
| --- | --- | --- |
| `case-0001` | `doc-synthetic-11` | yes |
| `case-0002` | `doc-synthetic-01` | **404** |
| `case-0003` | **none** | `doc-synthetic-31` exists and is linked to it |
| `case-0006` | `doc-synthetic-06` | **404** |

`GET /api/v1/documents/{id}` returns the document's `case_id`, but there is no way to search in
the other direction. The UI therefore tries cited ids first, then a small explicitly labelled
fallback map in `web/lib/source-documents.ts`, and in both paths verifies the returned
`case_id` before rendering — a wrong guess can never show another patient's note.

**Recommendation:** add `GET /api/v1/cases/{id}/documents` (or `documents?case_id=`) and delete
the fallback map. Separately, either seed the cited documents for `case-0002` / `case-0006` or
stop citing them in those cases' factors, because a care gap that references a note nobody can
open is confusing in a demo about transparent evidence.

### Also for Alfred — restore the mismatched-quote fixture

The fixture set lost the proposal whose excerpt deliberately does not match its offsets. The UI
still refuses untraceable quotes and the contract suite still verifies every excerpt against the
note, but nothing exercises the refusal on screen any more. One bad proposal in
`api/app/services/extraction_fixtures.py` restores a demonstration of the safeguard.

## Q12 — Which rule-outcome vocabulary is authoritative?

Raised by Mark, 2026-11-18, after Alfred's handoff. Three vocabularies describe the same four
concepts:

| Concept | Alfred (`ai/src/namaa_ai/contracts.py`) | API today | UI before today |
| --- | --- | --- | --- |
| A gap was found | `gap_identified` | `gap` | `gap` |
| None found in available data | `no_gap_identified_in_available_data` | `no_gap` (evaluations only) | not shown |
| Information missing | `needs_review` | `needs_review` | `needs_review` |
| Pathway does not apply | `not_eligible` | **absent everywhere** | not shown |

`CaseRow.flag_status` is `gap | needs_review`, so two of the four outcomes cannot reach the
interface at all from live data, whatever the UI supports.

The frontend now renders all four with their limitations and maps the API's current spellings,
flagging anything unrecognised rather than coercing it — see
[F-contracts evidence](../03-evidence/F-contracts/checks.md). That is a display layer, not an
agreement.

**Recommendation:** adopt Alfred's four names verbatim, since his package is where the rules
actually run, and widen `CaseRow.flag_status` to carry all four. This is Alfred's **M0** and it
gates his M1–M3. It is a short conversation, not a build task — but nothing downstream should be
treated as settled until it happens.
