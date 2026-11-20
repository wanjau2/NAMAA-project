# Namaa AI module — Alfred

This isolated Python package implements a fictional English note → extraction
proposal → source validation → explicit human review command → FHIR transaction
proposal → deterministic demonstration-rule slice. It does not change `api/` or
`web/`. HAPI remains the intended clinical source of truth; no HAPI connection or
write is implemented here. The existing SQLite demo remains as documented in D003.

**Synthetic only. Mock results are simulated. No clinical validation is claimed.**

The [19 November safety implementation and backend handoff](docs/SAFETY_IMPLEMENTATION.md)
records the current Alfred-only scope: strict extraction decoding, bounded
patient/guideline retrieval, explicit graph refresh outcomes, family-history
re-evaluation routing and population suppression. No live HAPI or model endpoint
was used. The API still uses SQLite and a stub FHIR gateway.

For integration, start with the [draft handover to Ismail](docs/HANDOVER_TO_ISMAIL.md):
delivered interfaces, backend work sequence, contract decisions and acceptance gates.

## Setup and local demonstration

From the repository root, with Python 3.11+ (tested here on Python 3.14.10):

```bash
cd ai
python -m venv .venv
source .venv/bin/activate
python -m pip install -c requirements-lock.txt -e '.[test]'
namaa-ai demo
python -m pytest -q
namaa-ai evaluate --adapter mock --split development
namaa-ai evaluate --adapter mock --split held_out
namaa-ai evaluate-context --split development
namaa-ai evaluate-context --split held_out
```

The demo explicitly constructs two **scripted** accept commands using a narrowly
scoped fictional reviewer. It prints the original request, checked proposals,
review decisions, an Observation Bundle, a FamilyMemberHistory Bundle and pending
FHIR validation reports. Before the simulated commit, the rule returns
`needs_review`; after it, `gap_identified`. The simulation assigns clearly marked
resource versions; it is not evidence of a HAPI transaction. Ordinary extraction
never automatically invokes review or mapping. Python consumers can call
`apply_review` with an explicit `ReviewCommand` and backend `ReviewAuthorizer`.

No environment variables are required for offline commands. `.env.example` lists
the backend-only hosted settings without credentials. The package does not load
`.env` automatically. Inject settings into Ismail's worker environment. After the
actual custom endpoint protocol has been verified and credentials deliberately
supplied, this command makes live requests and can incur endpoint usage charges:

```bash
namaa-ai evaluate --adapter hosted --split held_out
```

No hosted requests were made during initialization. There is no automatic switch
from a failed live adapter to mock results. A missing replay fixture is an error,
not a successful empty extraction.

## Package map

| File | Responsibility |
| --- | --- |
| `src/namaa_ai/contracts.py` | Pydantic 2 contracts with unknown fields forbidden |
| `src/namaa_ai/adapters.py` | Backend-only hosted adapter and labelled fixture replay |
| `src/namaa_ai/extraction.py` | Strict JSON decoder; duplicate-key and deployment-identity rejection |
| `src/namaa_ai/validation.py` | Exact excerpts, offsets, qualifiers, source conflicts |
| `src/namaa_ai/review.py` | Accept/correct/reject, authorization callback and version checks |
| `src/namaa_ai/backend.py` | Session-bound API bridges for nested proposals, review, canonical rules and verified Relate discovery |
| `src/namaa_ai/fhir.py` | Deterministic reviewed Observation, Condition and FamilyMemberHistory mappings, Provenance and local mapping checks |
| `src/namaa_ai/rules.py` | Versioned fictional rules over backend resource snapshots |
| `src/namaa_ai/context.py` | Verified-context gate (enabled by default; `enabled=False` is a kill switch) |
| `src/namaa_ai/context_engineering.py` | FHIR-resource-bounded retrieval, BM25, optional dense adapter, rank fusion and bounded context assembly |
| `src/namaa_ai/context_assembler.py` | Approved guidelines and patient passages with a shared retrieval budget |
| `src/namaa_ai/ingestion.py` | Layout/OCR parser protocol and explicitly simulated fixture parser |
| `src/namaa_ai/relate.py` | Relate candidate verification (enabled by default; `enabled=False` is a kill switch) |
| `src/namaa_ai/relate_graph.py` | Per-request verification callback, unknown suppression and refresh requests |
| `src/namaa_ai/analytics.py` | Pure small-cell/complementary suppression for one complete publication family |
| `src/namaa_ai/engagement.py` | English-only, non-sending demo templates and versioned metric definitions |
| `src/namaa_ai/evaluation.py` | Field metrics, source/schema validity and latency |
| `fixtures/notes.json` | 40 labelled notes with 20 development / 20 held-out records |
| `fixtures/context-queries.json` | Synthetic retrieval fixtures with development / held-out splits |
| `examples/` | Representative JSON and generated JSON Schemas for Ismail and Mark |
| `evidence/` | Local test and simulated evaluation evidence |

Read [contracts and integration](docs/CONTRACTS.md), [endpoint protocol](docs/ENDPOINT.md),
[evaluation methodology](docs/EVALUATION.md), and the pre-implementation
[phased plan](docs/IMPLEMENTATION_PLAN.md). The retrieval implementation and
Mark/Ismail handoffs are in [context engineering](docs/CONTEXT_ENGINEERING.md).
The demo copy and metric definitions are documented in
[engagement and metrics](docs/ENGAGEMENT_AND_METRICS.md); product claims and the
Alfred demo narrative are in [claims and demo](docs/CLAIMS_AND_DEMO.md).

Authorization boundary and synthetic security tests are documented in
[security integration](docs/SECURITY.md). Alfred's `SecurityEnforcer` asks
Ismail's backend for a fresh decision at each boundary; it does not treat local
roles, prompts, or Relate paths as authority. The local policy adapter is an
explicit deterministic test fixture only. Backend guest decisions always carry
`production_authorization=false`.

The [backend bridge guide](docs/BACKEND_BRIDGES.md) covers API integration tests,
live AuthZEN checks, and the review/rule/Relate clients. HAPI commit is still
stubbed. Current acceptance evidence is recorded in the safety handoff above;
older evidence in the bridge guide describes its original checkout.

From the repository root, run the isolated HTTP acceptance checks with
`ai/.venv/bin/python ai/scripts/check_backend.py --local`. For an existing
synthetic stack, use `--api-url` instead. The command returns a failing exit code
for contract failures; see the guide for compact JSON evidence and rule fixtures.

The context assembler is on and accepts only current, backend-verified
context envelopes. Default ranking is hybrid BM25 plus a hashed-token dense
ranker; a production dense retriever can be injected. That hashed ranker is
not an embedding model or vector database. The layout/OCR parser remains a
test boundary. Relate resolution is on and returns verified items or unknown
plus refresh. `publish_population` exposes overview and segment views of one
suppressed analytics release.

Context evaluation uses separate synthetic development and held-out queries; it
tests retrieval plumbing, not clinical relevance. Rules continue to
consume reviewed committed snapshots directly and never retrieval results.

## Demonstration rule definitions

Both rules have version `synthetic-1.0.0`. Eligibility is an explicit reviewed
**fictional enrolment card**, represented by an Observation with a boolean value.
No age, risk score or Abu Dhabi screening schedule is inferred.

| Rule | Fictional eligibility Observation `code.text` | Last-event Observation `code.text` | Fictional interval |
| --- | --- | --- | --- |
| `DEMO_WCV_01` | `Demo WCV eligibility` | `Reported last well-child visit` | 37 days |
| `DEMO_ADULT_01` | `Demo adult eligibility` | `Reported last adult screening` | 73 days |

The due date is the reviewed explicit last-event date plus the fictional interval.
On or after it: `gap_identified`; before it:
`no_gap_identified_in_available_data`. Explicit false eligibility:
`not_eligible`. Missing, uncertain, contradictory, unreviewed or incompletely
retrieved required data: `needs_review`. A missing event is not evidence of a gap.
An explicit excluded enrolment does not require last-event history. Dates in
different last-event records require reconciliation; the evaluator does not
silently choose the latest. Every result includes the evaluation date, all input
references/opaque versions, rule version, factors and missing information.

These are software demonstration rules, not approved prevention schedules or
screening authorization. Neither rule consumes proposals or graph context.

## Implemented, mocked and pending

**Implemented:** contracts; input/output limits; hosted HTTP protocol adapter with
90-second total deadline, one transient retry and one schema-repair regeneration
(three attempts maximum); source checks; explicit review logic; deterministic
Observation/Condition/FamilyMemberHistory mapping and Provenance; local mapping checks;
fictional rules; security boundary; verified-context gating and offline context
assembly/retrieval interfaces; synthetic extraction and retrieval evaluation.

Condition proposals are limited to verbatim statements explicitly saying the
patient is currently diagnosed. The lexical guard rejects inferred, historical,
absent, uncertain and relative conditions. They require the same authenticated
human review; no clinical status or terminology code is inferred, and the demo
rules do not consume Condition resources. This is extraction/mapping support, not
model diagnosis.

**Mocked:** extraction through a configured label replay; the CLI's reviewer
authorization; FHIR commit and version assignment. Mock metrics test software
plumbing, not MedGemma extraction quality.

**Pending with Ismail:** authenticated source retrieval; durable jobs, queues and
rate limits; proposal persistence and atomic review updates; command idempotency;
real review authorization; HAPI gateway, partition/reference checks, version
preconditions, transaction execution and crash reconciliation; trusted snapshot
construction; Namaa profiles, terminology and official FHIR validator; deployed
endpoint serving contract and immutable model revision; live evaluation; Relate
verification contract; production context endpoint with source-level offsets,
review attestations and version freshness; selection/deployment of a retrieval
projection, embedding model and its indexing lifecycle. The hosted adapter is
implemented, not live-verified.

**Pending with Mark:** adapt the nested proposal contract and opaque string source
versions, convert code-point offsets for JS display, show review issues and mock/
failure states, and connect to Ismail's future proposal/review endpoints.

## Validation status and limitations

Example Bundles pass only the package's allowlisted mapping checks. The official
base FHIR R4 4.0.1 validator and Namaa profiles were unavailable. Both checks are
reported **pending**, and proposals have `executable: false`. No `meta.profile`
conformance claim is added. Ismail must validate with the pinned validator and
profile package before executing any Bundle; structural validity does not prove
clinical correctness. The stable-ID PUT proposals are deliberately incomplete
with respect to server state: resolve creates/updates and attach `If-Match` for
authorized updates, with command-journal reconciliation for retry safety.

Lexical source checks are conservative, limited to six controlled categories,
and can both overflag and miss semantic errors. They do not establish patient
identity, automatically detect language, understand arbitrary clinical text or
prove absence of contradictory records. English is an explicit request contract.
Only full explicit ISO event dates are extracted in this slice; relative or
partial dates remain null. No codes, dates or probability scores are invented.
The reviewer must inspect the whole note. A matching excerpt proves traceability
only. There are no diagnosis, urgency, order, ownership or closure operations.

To regenerate handoff files after a contract change:

```bash
python scripts/generate_examples.py
namaa-ai schemas
python -m pytest -q
```
