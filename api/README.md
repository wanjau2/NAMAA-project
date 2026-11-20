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

CORS: `NAMAA_CORS_ORIGINS` must list every browser origin that will call this
API (scheme, host, and port). The default is
`http://localhost:3000,http://127.0.0.1:3000`. The web client bakes
`NEXT_PUBLIC_API_BASE_URL` at `next build` time; that URL must be reachable
from the browser, not only from inside Docker.

## Guest session

1. `POST /api/v1/demo/sessions` → `{ "session_id": "guest-..." }`
2. Send header `X-Namaa-Session: <session_id>` on every subsequent call
3. Required simulated role: `X-Namaa-Role: coordinator | clinical_reviewer | population_analyst`
   (EventSource uses `?role=` because the browser cannot set that header)
4. `POST /api/v1/demo/reset` restores the same seed cases for **that** session only

## Contract for Mark

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/v1/cases` | |
| GET | `/api/v1/cases/{id}` | Includes `caregiver_authority` and `available_actions` |
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

## Completion and concurrency guarantees

- Case actions reserve the expected revision with an atomic database update. A competing
  update receives `409 stale_revision`; identical committed request IDs replay their original response.
- `close_as_completed` requires an existing evidence resource in the same workspace, with
  the matching resource type, patient, and a completed status. It never creates clinical evidence.
- The immediate response leaves the case open and returns `completion_status: "pending"`.
  The worker closes it only when the FHIR transaction commits. Failed or uncertain writes do
  not count as completed care. Inspect/retry failed writes through `/api/v1/ops/outbox`.
- The case UI refreshes pending completion automatically. A replay returns the original command
  response; fetch the case for its current state. Successful persistence adds a
  `completion_committed` event and advances the case revision.
- Attendance metrics include only events transitioning to `attended`, excluding no-shows.

New/reset guest sessions include explicitly synthetic evidence `Encounter/enc-synthetic-02`
for Child B and `Encounter/enc-synthetic-06` for Child F. Reset an existing demo session to load
these fixtures. No schema migration is required by these changes.

## Action fields and booking records

Every action validates its own typed payload; `/api/v1/meta/actions` publishes the
`data_schema` for each action. Dates must be real calendar dates in `YYYY-MM-DD` format
(the booking form records a date, not an invented time or timezone). Selection values are
restricted to the supported options, attestations must be JSON `true`, and contact attempts
must be JSON integers from 1 to 1000. Names/locations/references are capped at 128 characters,
notes/reasons at 2000. Unknown fields and invalid types return structured 422 field errors.

Bookings are stored in the new `appointment_bookings` table in the same transaction as their
audit event. `detail.booking` returns the latest recorded date/location; each booking event
also returns its own `booking`. Previously discarded booking details remain `null` rather
than being reconstructed. Restart the API to create this additive table; existing data is kept.
Resetting a guest session clears only that workspace's bookings.

The web client sends the selected simulated role on case and analytics reads. Switching roles
clears case/source caches, cancels outstanding reads, and reloads under the new role while
retaining the same guest workspace. Population analysts cannot retrieve individual cases.

## Known limitations (submission-truthful)

- HAPI FHIR server is **not** deployed; dual-store outbox targets an in-process FHIR **gateway stub**
- MedGemma extraction is **not** live; SSE streams **offline-fixture** progress labelled as such
- Rules module is a local deterministic stub until Alfred replaces `app/rules/`
- Simulated roles via header are **not** production authentication
- SSE hub is in-process (single API replica); scale-out needs Redis/NATS
