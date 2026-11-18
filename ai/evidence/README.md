# Local verification evidence

Recorded 2026-11-18. AI package changes are confined to `ai/`; API/frontend files
were not modified. The final AI suite passed with the isolated `ai/.venv` using
Pydantic 2.12.4, httpx 0.28.1 and pytest 9.0.1 on Python 3.14.10.

`pytest.txt` contains the passing suite output. `demo-run.json` contains the
complete offline slice, explicit scripted review commands, two transaction
proposals, pending validation reports and before/after simulated evaluations.
`environment.json` identifies versions, corpus/prompt hashes and unrun checks.
`context-development.json` and `context-held-out.json` report deterministic
BM25 retrieval plumbing over four authored synthetic queries per split. Both
currently score 1.0 on hit rate@3, recall@3 and MRR because the fixture is small
and authored around its labels; these are not clinical relevance measurements.

| Scripted replay | Development | Held-out |
| --- | --- | --- |
| Notes | 20 | 20 |
| Labelled / replayed facts | 20 / 20 | 20 / 20 |
| Valid output schemas | 20 / 20 | 20 / 20 |
| Unique exact supporting quotes | 19 / 20 | 20 / 20 |
| Reference-label additions | 0 / 20 | 0 / 20 |
| Blocked output | 1 intentionally repeated excerpt | 0 |

Each field's precision/recall is 1.0 because this adapter explicitly replays the
labels. These numbers are **not MedGemma quality results**. The intentionally
repeated excerpt correctly yields null offsets and `invalid_output`. Latency
samples in the JSON reports measure local replay/source checking, not inference.

Pending: official base FHIR R4 4.0.1 validation; Namaa profile validation; live
endpoint compatibility and MedGemma evaluation; HAPI execution/recovery; real
review authorization and persistence; frontend integration; HAPI-backed context
retrieval, vector index selection and Relate verification. No live model,
deployment, submission, graph or HAPI request was made.
