# Synthetic evaluation method

`fixtures/notes.json` contains 40 authored fictional English notes with reference
labels and expected software-validation issues: 10 straightforward, 10 negation/
family, 10 missing-date/conflicting-history, and 10 irrelevant/injection/formatting.
Each group has five `development` and five `held_out` cases. The original prompt
version `extract-v1.0.0` was fixed before constructing the corpus and does not embed its
notes. Keep held-out cases out of prompt tuning; changes informed by a live
held-out run require a new untouched test set. The small authored set is not a
representative clinical dataset, and its labels have not had clinician adjudication.

Prompt `extract-v1.0.1` adds a narrowly gated `documented_condition` category.
The existing 40-note corpus has no positive gold examples for this new category;
unit tests cover explicit-current wording, historical/absent/non-current cases
and review-gated mapping. Do not interpret the existing corpus scores as
evaluating Condition extraction quality. A separate clinician-adjudicated
synthetic set is required before reporting such a metric.

The mock command deliberately replays each reference label as a scripted response.
Perfect field scores from it are expected by construction. They verify parsing,
source validation, counting and integration, **not MedGemma quality** or held-out
generalization. The repeated-excerpt case deliberately has an ambiguous quote
that cannot be promoted without correction. Hosted evaluation uses exactly the
same scoring path but a real explicitly selected adapter; none was run here.

## Metrics and denominators

- Field precision/recall: exact multiset matches of `(excerpt, field-value)` per
  note, independently for each ProposedFact field. TP/FP/FN are micro-aggregated;
  duplicates beyond gold counts are false positives. Missing output contributes
  false negatives. An incorrect excerpt prevents credit for fields tied to it.
  Subject and assertion precision/recall give attribution and assertion evidence;
  these are not clinical correctness scores.
- Unsupported additions: predicted semantic tuples (concept, subject, assertion,
  explicit date, relationship, original statement) absent from the reference
  multiset. Report count, predicted-fact denominator and rate. This is gold-label
  disagreement, not independently adjudicated hallucination. Source issues provide
  a separate traceability signal.
- Quote validity: unique exact source span with valid server-calculated offsets,
  divided by schema-valid proposed facts. An ambiguous repeated quote is invalid.
- Schema validity: requests ending with valid output schema divided by requests
  reaching an output response (transport failures excluded and reported separately).
  It measures final output after any bounded repair, not first-generation validity.
- Latency: end-to-end adapter milliseconds, median and nearest-rank p95, with
  sample size including failures. HTTP/network tests do not measure MedGemma speed.

Zero-denominator rates are null, not misleading 100% or zero. Reports include note
and fact counts, group/split counts, final outcome counts, model/prompt identity and
per-case issue codes. Notes are not copied into metric reports. Run development
and held-out reports separately:

```bash
namaa-ai evaluate --adapter mock --split development > evidence/mock-development.json
namaa-ai evaluate --adapter mock --split held_out > evidence/mock-held-out.json
```

The tests cover input/schema limits, exact/ambiguous quotes and Unicode offsets,
negation/attribution/history/conflicts, authorization/version/source gating,
accept/correct/reject, mapping/provenance, all four outcomes for both rules,
missing/contradictory/unreviewed data, HTTP retry/repair/timeout/invalid output,
context freshness/access rejection, handoff example/schema consistency and the
complete simulated slice. The tests make no live endpoint calls.

Context retrieval has a separate synthetic query set in
`fixtures/context-queries.json` (development and held-out splits). Run
`namaa-ai evaluate-context --split development` and `--split held_out` for hit
rate, recall@k and mean reciprocal rank with query counts. These fixtures check
ranking mechanics and source-version handling; they are not clinically
adjudicated relevance results and do not establish vector or graph quality.

Base FHIR R4 validation, Namaa profile validation, HAPI execution, real backend
authentication, live MedGemma quality/latency and integrated browser journeys are
not covered by these tests. Track them as pending integration checks.
