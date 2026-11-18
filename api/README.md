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

| Method | Path |
| --- | --- |
| GET | `/api/v1/cases` |
| GET | `/api/v1/cases/{id}` |
| POST | `/api/v1/cases/{id}/actions` |
| POST | `/api/v1/patients/{id}/evaluations` |
| GET | `/api/v1/analytics/overview` |
| POST | `/api/v1/demo/sessions` |
| POST | `/api/v1/demo/reset` |

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

- HAPI FHIR server is **not** deployed; IDs are FHIR-shaped strings in SQLite
- MedGemma extraction is **not** on the critical path
- Rules module is a local deterministic stub until Alfred replaces `app/rules/`
- Simulated roles via header are **not** production authentication