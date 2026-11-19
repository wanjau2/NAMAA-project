# AI security boundary and backend handoff

## Implemented in Alfred's package

`namaa_ai.security` defines `PolicyDecisionClient`, a strict parser for the
backend-minted `GET /api/v1/security/context`, a fail-closed HTTP bridge for
`POST /api/v1/authz/evaluation` and `/api/v1/audit/events`, a deterministic
allowlist-only `LocalSyntheticPolicy`, `SecurityEnforcer`, and an authorized
extraction orchestration boundary. The enforcer requests a fresh policy decision
and emits a structured audit record every time; it caches no decisions. Audit
sink failure blocks disclosure. Errors returned to callers use only
`access_denied` and do not reveal record existence.

The orchestration checks `note.retrieve` before the source provider is called,
`model.dispatch` separately before handing the note to the adapter, and
`proposal.disclose` after inference before returning results. `context.retrieve`
is required before invoking the fixed backend verified-context operation.
`authorize_excerpt` must be called immediately before rendering or exporting a
source quote. `apply_review_authorized` rechecks `review.apply`; the caller must
be Ismail's authenticated review endpoint and bind reviewer identity to its
session. A sentence in a note or prompt claiming approval is never authority.

The point immediately before `adapter.extract(request)` is the model dispatch
boundary. Revocation before that call prevents dispatch. Once bytes have been
sent to the endpoint, revocation cannot recall them; the post-inference decision
prevents subsequent disclosure. A queued worker must retain the initiating
principal and scope, obtain a current context on claim, and call the same checks
before dispatch and disclosure. It cannot substitute its broader service
identity for the initiating user.

## Backend wire and ownership

The official [OpenID AuthZEN authorization API specification](https://openid.github.io/authzen/)
defines an access evaluation request around subject, action, resource and
context, with a boolean decision response. The present backend uses that
conceptual shape at Namaa-specific `/api/v1/authz/evaluation`; it adds a context
object containing decision ID, decision value, policy and permission revisions,
adapter name, synthetic-production marker and reason code. This is an
application-specific adapter, **not a claim of complete AuthZEN wire
conformance or certification**. If another PDP is connected, Ismail should
confirm the endpoint binding and response extension before changing this codec.

Ismail remains responsible for minting trusted context from authenticated
identity, current workspace membership, patient assignment and explicit care
relationships, verified caregiver authority, permitted purpose, sensitivity,
restrictions, approved model destinations and current policy/permission
revisions. The AI module does not accept these claims from note text, prompts,
or client request fields. The API must deny missing and indeterminate inputs,
and must bind every evaluation to the authenticated initiating principal and
workspace. Permission to retrieve a note must not imply permission to dispatch
it to a model.

Relate is a disposable index. The model receives no graph query interface.
Ismail's fixed `POST /api/v1/security/verified-context` operation must
reauthorize patient and supporting resource scope, check source versions and
permission revision, and suppress stale/unverified records. Graph paths never
grant permission. Empty or partial context does not establish absence of care.

## Configuration

`BackendHttpClient` requires the API base URL and caller-supplied authenticated
headers. Obtain those headers from Ismail's server-side session or service-token
integration; do not pass credentials through the browser, model adapter or
audit event. `X-Namaa-Session` is required even for service calls; optional
service-token/role headers select the backend identity. Production must inject
a real backend client. Missing configuration
or a failed policy/audit service is a denial. `LocalSyntheticPolicy` is suitable
only for deterministic tests and must never be selected as production fallback.

The existing backend currently identifies itself as
`synthetic_guest_v1` / `synthetic-policy-v1` / `permissions-v1` and always
reports `production_authorization=false`. This is simulation, not production
access control. Do not process real patient information with it.

## Acceptance coverage

`tests/test_security.py` uses fabricated principals, patients, versions and
decisions. It covers default-deny, patient/workspace scope mismatch, read versus
model permission, policy outage, stale revisions, blocked dispatch before
source retrieval, suppressed post-inference disclosure after revocation, and
payload-free audit evidence. These are security boundary tests, not model
quality measurements. Broader integration coverage for caregiver authority,
stale graph suppression, worker reauthorization, and central identity
revocation belongs in Ismail's API integration suite, because those facts are
minted and enforced there. The AI package now also exercises the real API
context, AuthZEN and audit routes, source retrieval, and verified-context scope
through `tests/integration/test_api_security.py`. It includes regression tests
for cross-patient Relate hints and subsecond verification timestamps. See the
[backend bridge guide](BACKEND_BRIDGES.md) for dependencies and opt-in HTTP
AuthZEN checks. Review, canonical rule and Relate discovery client tests use
announced contracts; deployed verification awaits the newer backend routes.

## Pilot requirements still outstanding

- Replace synthetic guest policy with a production PDP, authoritative identity
  and access records, policy administration, current revisions, and authenticated
  review authorization. Never silently allow when the service is unavailable.
- Ensure every API and worker path reauthorizes at source read, model dispatch,
  context retrieval, result disclosure, excerpt display/export and review apply.
- Protect audit delivery with service authentication and operational controls:
  access restrictions, retention/rotation, backup, monitoring, clock
  synchronization and an independently controlled append-only or tamper
  evident store. Application logs alone are not immutable or tamper-proof.
- Pin and verify model endpoint destination, model revision and data handling;
  review legal basis, notices, residency/transfer, retention and incident
  response with the appropriate local legal and operational owners.
- Complete applicable-law and operational review before any compliance claim or
  real-patient pilot. These technical controls do not establish GDPR, CCPA, or
  local legal compliance.

No real patient data, live model endpoint, or production authorization is used
by these tests.
