# Local verification evidence

Recorded 2026-11-18. All changes are confined to `ai/`; existing API/frontend files
were not modified. Tests use the installed package and pinned Pydantic 2.12.4,
httpx 0.28.1 and pytest 9.0.1 on Python 3.14.10. Installation succeeded in the
isolated `ai/.venv`; `pip check` reported no broken requirements.

`pytest.txt` contains the passing suite output. `demo-run.json` contains the
complete offline slice, explicit scripted review commands, two transaction
proposals, pending validation reports and before/after simulated evaluations.
`environment.json` identifies versions, corpus/prompt hashes and unrun checks.

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
review authorization and persistence; frontend integration. No live model,
deployment, submission, graph or HAPI request was made.
