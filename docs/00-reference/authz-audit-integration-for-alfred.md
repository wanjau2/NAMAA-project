# AuthZ / audit integration handoff (Ismail → Alfred)

**Decision:** [D005](../02-decisions/D005-authz-audit-pdp.md)  
**Status:** Backend interfaces live in `api/`. Guest policy is **synthetic only**.

Alfred’s message referenced `ai/src/namaa_ai/security.py` (scaffolding). That file is
not in the tree yet — wire your AuthZEN client to the endpoints and Python hooks below.

---

## 1. Trusted request context

**Do not** accept purpose, membership, caregiver authority, model destination, or
policy revisions from the request body or prompt.

| Surface | How |
| --- | --- |
| HTTP | `GET /api/v1/security/context` |
| Python (API/worker) | `app.security.build_trusted_context(...)` via `get_trusted_context` |

Headers that *select* session (not authority):

- `X-Namaa-Session` — guest workspace (or `?session=` for SSE)
- `X-Namaa-Role` — simulated role switch inside the guest session
- `X-Namaa-Request-Id` — optional correlation id
- `X-Namaa-Purpose` — optional purpose **hint**; must be in the allowlist or it is ignored/replaced
- `X-Namaa-Service-Token` — worker/service calls (`NAMAA_SERVICE_TOKEN`, default dev token)

Minted fields include: user/service ids, active membership role, patient assignment /
care relationships, caregiver authority map, purpose of use, sensitivity/restrictions,
approved model destination, `policy_adapter=synthetic_guest_v1`,
`policy_revision=synthetic-policy-v1`, `permission_revision=permissions-v1`,
`production_authorization=false`.

---

## 2. Policy decision service (AuthZEN 1.0 shape)

| Item | Value |
| --- | --- |
| Endpoint | `POST /api/v1/authz/evaluation` |
| Batch | `POST /api/v1/authz/evaluations` |
| Service auth | Session headers **or** `X-Namaa-Service-Token` |
| Policy revision | `synthetic-policy-v1` (also echoed on every decision) |
| Decision id | `context.decision_id` (e.g. `dec-…`) |
| Adapter label | `context.policy_adapter` = `synthetic_guest_v1` |
| Production flag | `context.production_authorization` = `false` |

Request body (AuthZEN-style):

```json
{
  "subject": { "type": "user", "id": "guest:…" },
  "resource": {
    "type": "DocumentReference",
    "id": "doc-synthetic-11",
    "workspace_id": "guest-…",
    "patient_id": "pat-synthetic-11"
  },
  "action": { "name": "note.retrieve" },
  "context": { "purpose_of_use": "demo_model_extraction" }
}
```

Response:

```json
{
  "decision": true,
  "context": {
    "decision_id": "dec-…",
    "decision_value": "Permit",
    "policy_revision": "synthetic-policy-v1",
    "permission_revision": "permissions-v1",
    "policy_adapter": "synthetic_guest_v1",
    "production_authorization": false,
    "reason_code": "synthetic_policy_permit"
  }
}
```

**Missing, unknown action, or indeterminate → Deny** (`decision: false`).  
Subject id, if present, must match the trusted principal.

### Action names (closed set)

`note.retrieve` · `model.dispatch` · `context.retrieve` · `proposal.disclose` ·
`excerpt.display` · `excerpt.export` · `review.apply` · `evaluation.run` · `audit.write`

---

## 3. Enforcement hooks (Python)

Prefer the in-process hook inside API routers/workers (avoids extra HTTP hop):

```python
from app.security import authorize, AuthorizationDenied

decision = authorize(
    db, ctx,
    action="note.retrieve",
    resource_type="DocumentReference",
    resource_id=document_id,
    patient_id=patient_id,
)
```

Already enforced on:

| Boundary | When |
| --- | --- |
| Note retrieval | `GET /api/v1/documents/{id}` |
| Model dispatch + note | `POST .../extractions` queue |
| Worker start | `reauthorize_job_execution` on claim |
| Proposal / excerpt disclose | `GET /extractions/{id}` and SSE terminal payloads |
| Verified context | `POST /api/v1/security/verified-context` |

Queued jobs persist `initiating_user_id`, `initiating_role`, `initiating_purpose`,
`initiating_request_id`, and `principal_snapshot_json`, then **re-authorize** at
execution and before proposal return.

For `ReviewAuthorizer`, call `authorize(..., action="review.apply", ...)` with the
clinical_reviewer principal (or service + `initiating_role=clinical_reviewer`).

---

## 4. Audit sink

| Item | Value |
| --- | --- |
| Write | `POST /api/v1/audit/events` |
| Read (workspace) | `GET /api/v1/audit/events` |
| Python | `app.security.emit_audit(...)` |

Required / recorded fields: request/job ids, user + service, workspace/resource refs,
action, purpose, decision + decision_id, policy + permission revisions, policy_adapter,
source versions map, model/prompt versions, reviewer id, timestamp, safe reason code.

**Rejected in detail:** `note_text`, `token`, `prompt`, `full_prompt`, `authorization`,
raw model payloads. Server strips known forbidden keys.

---

## 5. FHIR / Relate boundary

`POST /api/v1/security/verified-context`

```json
{
  "patient_id": "pat-synthetic-11",
  "generation_id": "optional",
  "relate_hints": [
    { "resource_type": "Observation", "logical_id": "obs-…" }
  ]
}
```

- Re-checks assignment + `context.retrieve` authorization
- Relate hints are **candidates only** — never grant access
- Unverified / out-of-scope / stale rows are suppressed
- Returns Alfred-compatible `VerifiedContext` fields plus
  `exhaustive: false`, `absence_claims_allowed: false`,
  `policy_adapter`, `production_authorization`

Compose `VerifiedContextAdapter(enabled=True)` only after calling this endpoint
(or the Python `build_verified_context` helper) immediately before disclosure.

---

## 6. Where this lives

```
api/app/security/
  context.py      # TrustedRequestContext builder
  pdp.py          # AuthZEN evaluation (default-deny)
  enforce.py      # authorize() hook
  audit.py        # emit_audit()
  verified_context.py
  deps.py         # FastAPI dependencies
  constants.py    # synthetic_guest_v1 labels

api/app/routers/security.py   # HTTP surfaces
api/app/services/extractions.py  # job principal + reauth
api/app/workers/runtime.py       # reauth on claim
```

Guest demo identification (always present on context and decisions):

- `policy_adapter`: **`synthetic_guest_v1`**
- `production_authorization`: **`false`**
- restrictions include `not_production_authorization`

---

## 7. Suggested Alfred next steps

1. Point AuthZEN client base URL at `/api/v1/authz/evaluation` with service token.
2. Implement `ReviewAuthorizer` via `authorize(..., action="review.apply")`.
3. Before model call: require `note.retrieve` + `model.dispatch` decisions (or rely on
   queue endpoint which already does both).
4. Before returning proposals/summaries/excerpts: `proposal.disclose` /
   `excerpt.display`.
5. Emit audit events without note/prompt/token fields.
6. Add security acceptance tests against deny-by-default and synthetic adapter labels.

Until a real IdP/PDP exists, treat every Permit as **demo-only**.
