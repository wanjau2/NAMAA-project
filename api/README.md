# Namaa API (Ismail)

Synthetic demo backend for Population Health Challenge 04.  
**NOT FOR CLINICAL USE.** No real patient data, live SMS, or bookings.

Stack (sprint): FastAPI + SQLite — see [D003](../docs/02-decisions/D003-backend-stack-and-api.md).

## Docker (preferred for full stack)

From the repo root:

```bash
docker compose up --build
```

See [DOCKER.md](../DOCKER.md).

## One-command start (local)

```bash
cd api
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
pip install -e ../ai   # or rely on app.ai_runtime path insert when the repo layout is intact
copy .env.example .env   # or: cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

- Health: <http://127.0.0.1:8000/health>
- OpenAPI: <http://127.0.0.1:8000/docs>
- Actions catalog: <http://127.0.0.1:8000/api/v1/meta/actions>

## Guest session

1. `POST /api/v1/demo/sessions` → `{ "session_id": "guest-..." }`
2. Send header `X-Namaa-Session: <session_id>` on every subsequent call
3. Optional role switch: `X-Namaa-Role: coordinator | clinical_reviewer`
4. `POST /api/v1/demo/reset` restores the same seed cases for **that** session only

## Contract for Mark

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/v1/cases` | |
| GET | `/api/v1/cases/{id}` | Includes `caregiver_authority` |
| GET | `/api/v1/cases/{id}/documents` | Case source documents |
| POST | `/api/v1/cases/{id}/actions` | |
| POST | `/api/v1/patients/{id}/evaluations` | Canonical `rule_evaluation` (Alfred `evaluate`) |
| GET | `/api/v1/patients/{id}/evaluations/latest` | Persisted canonical evaluation |
| GET | `/api/v1/analytics/overview` | One `suppress_population` family |
| GET | `/api/v1/analytics/segments` | Same family, segment view |
| POST | `/api/v1/demo/sessions` | |
| POST | `/api/v1/demo/reset` | |
| POST | `/api/v1/documents/{id}/extractions` | Queue extraction (202 + job id) |
| GET | `/api/v1/extractions/{id}` | Snapshot (fallback only) |
| GET | `/api/v1/extractions/{id}/events` | **SSE progress** (preferred) |
| GET | `/api/v1/ops/outbox` | Outbox / DLQ inspection |
| POST | `/api/v1/ops/outbox/{id}/retry` | Re-queue dead-lettered FHIR command |
| GET | `/api/v1/facts/{id}` | Alfred-shaped proposal |
| POST | `/api/v1/facts/{id}/review` | Human review (clinical_reviewer; FHIR stub) |
| GET | `/api/v1/relate/family-history` | Relate discovery (no authz grant) |
| GET | `/api/v1/relate/care-plans` | Relate discovery (no authz grant) |
| POST | `/api/v1/relate/refresh` | Synthetic refresh enqueue |
| POST | `/api/v1/security/revocations` | Synthetic principal revoke |

Extraction UI helper: `web/lib/extraction-sse.ts`. See [D004](../docs/02-decisions/D004-sse-and-outbox.md).

AuthZ / audit for Alfred: [authz-audit-integration-for-alfred.md](../docs/00-reference/authz-audit-integration-for-alfred.md) (D005).

Action names match `web/lib/case-actions.ts`. Mutation body:

```json
{
  "action": "approve_pathway",
  "expected_revision": 1,
  "request_id": "uuid-or-unique-string",
  "data": { "attestation": true }
}
```

Errors always look like:

```json
{
  "code": "stale_revision",
  "message": "...",
  "field_errors": {},
  "request_id": "..."
}
```

## Reset

Deleting `namaa_demo.sqlite3` and restarting also recreates an empty DB; use
`POST /demo/reset` for an in-session restore without losing the session id.

## Tests

```bash
pytest
```

## Known limitations (submission-truthful)

- HAPI FHIR server is **not** deployed; dual-store outbox targets an in-process FHIR **gateway stub**
- MedGemma extraction is **not** live; SSE streams **offline-fixture** progress labelled as such
- Rules module is a local deterministic stub until Alfred replaces `app/rules/`
- Simulated roles via header are **not** production authentication
- SSE hub is in-process (single API replica); scale-out needs Redis/NATS