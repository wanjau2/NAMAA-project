# M05 — Ismail I4–I7 bridge (review, handoff, Relate)

**Date:** 2026-11-19
**Owner:** Ismail
**Status:** Partial (synthetic prototype; HAPI still stub)

## Built

- Alfred-shaped proposals (`fact`, `version`, `source_sha256`, `issues`, `model`, offsets)
- `GET /api/v1/facts/{id}` and `POST /api/v1/facts/{id}/review` with `review.apply`,
  idempotent journal, clinical_reviewer binding, stub FHIR outbox on accept/correct
- Evaluations return lossless `rule_evaluation` + `legacy_flag_status` / `api_compatibility`
  (supports `not_eligible`)
- `evaluation.run` authorized on `POST /patients/{id}/evaluations`
- Relate fixed ops: `GET /api/v1/relate/family-history`, `GET /api/v1/relate/care-plans`
- Principal revocation: `POST /api/v1/security/revocations` (blocks job reauth)

## Still stub / deferred

- Live HAPI R4 validator and partition gateway
- Production IdP / PDP (`synthetic_guest_v1` only)
- Append-only external audit store

## Evidence

```text
cd api && pytest -q
# From repo root — Alfred HTTP acceptance against a temp API:
ai/.venv/Scripts/python ai/scripts/check_backend.py --local --report ai/evidence/backend-acceptance-local.json
```

**2026-11-19 follow-up (I03/I05/I07 + I01/I02):** Alfred local acceptance **12 passed, 0 failed**
(`ai/evidence/backend-acceptance-local.json`). Canonical proposal/review wire shape,
bound `Practitioner/demo-reviewer`, unique proposal IDs per job, durable
`rule_evaluation` + `GET /patients/{id}/evaluations/latest`, reviewed facts upserted
as observations for the evaluation path.
