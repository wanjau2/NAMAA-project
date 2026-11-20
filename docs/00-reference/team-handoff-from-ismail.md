# Team handoff from Ismail — 20 Nov 2026

## Status (synthetic prototype only)

| Milestone | State |
| --- | --- |
| I1 Trusted context | Done (`GET /api/v1/security/context`) |
| I2 AuthZEN + enforcement | Done for note/model/context/disclose/review/eval |
| I3 Audit + job reauth + revocation hook | Done (prototype; not production audit store) |
| I4 Source + proposals | Done (Alfred-shaped proposals; unique ids per job) |
| I5 Human review + FHIR | **Partial** — `apply_review` + `propose_transaction`; **FHIR = stub**, not HAPI |
| I6 Rule handoff | Done — evaluations call `namaa_ai.rules.evaluate`; persist canonical object |
| I7 Relate + verified-context | Done (Relate discovery, `/relate/refresh`, verified-context) |
| I8 Mark contracts + security tests | Partial — OpenAPI live; Mark P0 UI gaps are separate |

Guest auth remains `policy_adapter=synthetic_guest_v1`, `production_authorization=false`.
**No real patient data.**

---

## Message for Alfred

Hi Alfred —

Backend bridges for your AI module are up on the synthetic stack:

1. **Security** — Use `BackendHttpClient` against:
   - `GET /api/v1/security/context`
   - `POST /api/v1/authz/evaluation`
   - `POST /api/v1/audit/events`
   Headers: `X-Namaa-Session` + optional `X-Namaa-Service-Token` / `X-Namaa-Role`.
   Do **not** enable `LocalSyntheticPolicy` outside unit tests.

2. **Review** — Wire `apply_review_authorized` / `ReviewAuthorizer` to:
   - `POST /api/v1/facts/{proposal_id}/review`
   Body matches your `ReviewCommand` (request_id, expected_proposal_version, action,
   reason, correction?, acknowledged_issues).
   Proposals from extraction status/SSE are now **nested Alfred shape** (`fact`, `model`,
   `source_sha256`, `offset_unit`, `issues`).

3. **Rules** — `POST /api/v1/patients/{id}/evaluations` runs Alfred `evaluate` and
   returns:
   - `rule_evaluation` (canonical outcome including `not_eligible`)
   - `legacy_flag_status` / `api_compatibility` (lossy projection for Mark)
   - `case: null` for `no_gap_identified_in_available_data` and `not_eligible` (D006)
   Reload via `GET /api/v1/patients/{id}/evaluations/latest`.

4. **Relate / context** — Discovery only:
   - `GET /api/v1/relate/family-history?patient_id=`
   - `GET /api/v1/relate/care-plans?patient_id=`
   - `POST /api/v1/relate/refresh` (synthetic enqueue; hints still do not grant access)
   Then **always** `POST /api/v1/security/verified-context` before
   `VerifiedContextAdapter` / `VerifiedCandidateAdapter`.

5. **Please add/adjust on your side**
   - Integration tests hitting the real API (not only `LocalSyntheticPolicy`)
   - Confirm AuthZEN codec against live responses (`decision` + `context.decision_id`)
   - Keep OCR/vector/Relate adapters as test boundaries until you consume verified-context
   - Document that HAPI commit is still **stub** — do not claim live FHIR write

Full notes: `docs/00-reference/authz-audit-integration-for-alfred.md`

---

## Message for Mark

Hi Mark —

Backend pieces you need for F4 / Phase C and source review:

1. **Proposals** — Extraction job payloads now use Alfred’s nested proposal contract
   (`fact`, `version`, `issues`, `model`, code-point offsets). Update
   `use-source-review` / UI to stop expecting the flat fixture shape.

2. **Review** — Call `POST /api/v1/facts/{id}/review` with clinical_reviewer role
   (`X-Namaa-Role: clinical_reviewer`). Handle 403 / 409 stale / 422 validation with the
   shared error envelope (`code`, `message`, `field_errors`, `request_id`).
   Never treat client role switches as production auth — keep the synthetic banner.

3. **Evaluations / outcomes** — Eval responses include four outcomes via
   `rule_evaluation.outcome` and may set `flag_status: not_eligible`.
   Use `RuleOutcome` / `api_compatibility`; do not collapse `not_eligible` into `no_gap`.

4. **Security UX** — Surface loading / empty / **denied** / stale / failed states for
   note retrieve, extraction SSE, proposal disclose, and review. Denied must not leak
   whether a record exists beyond the API message.

5. **Please deliver**
   - Wire review actions to the new facts endpoint (drop any remaining local-only accept)
   - Contract verify script update for nested proposals + review + `not_eligible`
   - Keep metrics suppression rendering driven by API `suppressed` flags only

OpenAPI: `http://localhost:8000/docs` after `docker compose up` or local uvicorn.

---

## Shared reminder

Real patient data still requires production IdP/PDP, hardened audit storage, HAPI,
and legal/ops review. This milestone set is **synthetic prototype only**.
