# Namaa software design

**FHIR first precision prevention platform**  
Software architecture and implementation specification  
Version 1.0 | 17 November 2026  
For Ismail, Alfred and Mark

---

## Purpose and intended outcome

Namaa identifies possible preventive care gaps, explains the evidence behind them, supports authorized human review and tracks the next action through attendance and follow-up. The first release demonstrates a child requiring Well-Child Visit review and an adult requiring comprehensive screening review.

This document specifies the proposed software. It is not a statement that the product has been implemented, clinically validated or connected to a provider. Clinical schedules, eligibility criteria and escalation rules in the demonstration remain synthetic until a qualified sponsor approves them.

## Confirmed design decisions

| Area | Decision |
| --- | --- |
| Clinical information | FHIR R4 version 4.0.1 from initial implementation |
| Application | Next.js with TypeScript, FastAPI and PostgreSQL |
| Clinical store | HAPI FHIR JPA server backed by a separate PostgreSQL database |
| AI | MedGemma 1.5 4B hosted on Hugging Face Inference Endpoints |
| Access | Invited team accounts and isolated guest demonstrations |
| Language and data | English only; fictional patient data in the first release |
| Decision authority | Reviewed facts, deterministic pathway rules and authorized human actions |

## Reading guide

Sections 1–3 define requirements, architecture and data ownership. Sections 4–7 specify FHIR validation, MedGemma processing, workflows and interfaces. Sections 8–10 cover user experience, security and operations. Sections 11–12 provide acceptance tests, team responsibilities, delivery gates and references.

## Release boundary

The prototype includes two complete synthetic journeys, source-linked AI extraction, human review, care plans, task ownership, simulated engagement, evidence-backed closure and FHIR import/export. Live messaging, real booking, production EHR integration, imaging, raw genomic analysis, disease-risk prediction and multilingual support are outside the first release.

---

## 1. Requirements and actors

### Functional requirements

| ID | Required behavior |
| --- | --- |
| FR01 | Create isolated guest workspaces and authenticate invited team members. |
| FR02 | Import and validate supported synthetic FHIR resources; preserve source identifiers. |
| FR03 | Extract proposed facts from English notes with exact source excerpts. |
| FR04 | Accept, correct or reject proposals before they influence pathway rules. |
| FR05 | Evaluate reviewed information against versioned demonstration rules. |
| FR06 | Assign care owners, next actions and deadlines; expose overdue or rejected handoffs. |
| FR07 | Record simulated invitation, booking, attendance and referral events. |
| FR08 | Require evidence and reviewer authorization for completed preventive care. |
| FR09 | Export the patient journey as FHIR resources and retain resource history. |
| FR10 | Report pathway completion and reach with explicit denominators and suppression. |

### Roles and permissions

* **Administrator:** Manage accounts and technical settings.
* **Coordinator:** Assign cases, record contact, book simulated appointments and track referrals.
* **Clinical reviewer:** Approve extracted facts and pathways, record clinical decisions and authorize closure.
* **Population analyst:** View approved aggregates without individual notes.

An administrator does not automatically gain clinical-review authority.

For the demonstration, a team member may hold multiple simulated roles. Guest users may switch roles only inside their own fictional workspace. A role label does not establish professional credentials or authorization for real clinical work.

### Quality targets

Design for ten concurrent demo sessions, ordinary API responses within two seconds at the 95th percentile under that load, and visible asynchronous inference progress. These are acceptance targets to measure, not proven performance. Inference has a 90-second timeout; correctness and reviewability take priority over a fast but unsupported answer.

### Clinical boundary

Population prioritization determines which records need attention. It does not establish a diagnosis or independently prescribe screening. An absent record means incomplete information unless completeness has been verified. Genomic information is optional and never a prerequisite for routine prevention.

---

## 2. Architecture and component boundaries

### Logical architecture

`Browser → React interface → FastAPI application → HAPI FHIR server → FHIR PostgreSQL database`

FastAPI also uses an application PostgreSQL database for identity, jobs, proposals and commands. A separate Python worker calls the protected MedGemma endpoint and processes durable jobs.

| Component | Responsibility and boundary |
| --- | --- |
| Next.js frontend | Presentation, review controls and client validation. No direct FHIR or model credentials. |
| FastAPI | Session authorization, business commands, FHIR gateway, rule evaluation and application APIs. |
| HAPI FHIR | Canonical clinical resources, version history, search and FHIR validation. Private network only. |
| Application database | Identity, workspace mapping, proposals, jobs, rule versions, command journal and reporting projections. |
| Worker | Inference, reconciliation, overdue-task checks, projection updates and expiry cleanup. |
| Model endpoint | Bounded text extraction. No tools, database access or authority to execute care actions. |

### Deployment topology

Use Docker Compose for development: reverse proxy, frontend assets, API, worker, PostgreSQL and HAPI. One PostgreSQL instance may host separate application and FHIR databases with different credentials. Only the reverse proxy is publicly accessible. The model endpoint is reached over authenticated HTTPS from the worker.

Use a modular backend rather than independent application microservices. Identity, records, extraction, review, rules, workflow, analytics and audit remain distinct modules with explicit interfaces. The worker shares tested modules but runs as a separate process.

### Sources of truth

HAPI is authoritative for clinical facts, preventive plans, requests, tasks and evidence. The application database is authoritative for accounts, access and technical processing. Dashboards may use rebuildable projections. Neither application code nor reporting queries may access HAPI internal database tables directly.

### Dependency configuration

Pin tested versions of HAPI, the FHIR validator, Python packages, frontend packages and the model revision. Record deployment settings without secrets. Secrets include database passwords, session configuration and the model endpoint token; inject them at deployment. The model-hosting account and compute budget are rollout prerequisites.

---

## 3. Clinical and application data model

| Clinical information | FHIR resource | Mapping rule |
| --- | --- | --- |
| Patient and caregiver | `Patient`; `RelatedPerson` | Keep relationship separate from verified authority. |
| Staff and provider | `Practitioner`; `PractitionerRole`; `Organization` | Link application accounts only where appropriate. |
| Source note | `DocumentReference`; `Binary` | Store immutable text and explicit replacements. |
| Finding or measurement | `Observation` | Preserve value, units, effective date and source. |
| Patient diagnosis | `Condition` | Only reviewed statements with the correct meaning. |
| Relative medical history | `FamilyMemberHistory` | Never convert a relative's condition into a patient diagnosis. |
| Caregiver questionnaire | `QuestionnaireResponse` | Retain versioned questionnaire reference. |
| Prevention pathway | `CarePlan` | Draft before review; active after authorization. |
| Screening or referral request | `ServiceRequest` | Separate proposed requests from authorized orders. |
| Coordination action | `Task` | Owner, state, deadline and purpose. |
| Booking and visit | `Appointment`; `Encounter` | A booking is not proof of attendance or completion. |
| Completed action and result | `Procedure`; `DiagnosticReport`; `Observation` | Choose the resource appropriate to the evidence. |
| Communication and lineage | `Communication`; `Provenance`; `AuditEvent` | Keep simulated contact, record lineage and security events distinct. |

### Application entities

* **Workspace:** Stores its ID, type, FHIR partition, status and expiry.
* **User and Membership:** Store identity and roles.
* **ExtractionJob:** Stores document versions, state, attempts, lease, model revision and prompt version.
* **Proposal:** Stores extracted facts and review history.
* **RuleEvaluation:** Stores inputs, resource versions and outcomes.
* **Command:** Stores request ID, payload hash, state and intended FHIR transaction.
* **CohortSnapshot and Projection:** Store reporting definitions and rebuildable results.

### Identifiers and relationships

Use UUIDs for application entities and stable valid FHIR logical IDs for resources. Preserve external identifier system and value separately from logical IDs. A patient can have multiple pathways, but only one active care plan per patient and pathway. Re-evaluation appends an evaluation snapshot rather than creating another active case.

---

## 4. FHIR contracts and validation

### Version and conformance package

Use FHIR R4 4.0.1 consistently. Publish a project implementation package with `ImplementationGuide`, `StructureDefinition` profiles, `CodeSystem` and `ValueSet` definitions, `CapabilityStatement` and example Bundles. Use `https://namaa.example/fhir` as an explicitly provisional canonical namespace; replace it with an organization-controlled namespace before a pilot.

Initial profiles cover `Patient`, `DocumentReference`, verified `Observation`, preventive `CarePlan`, coordination `Task`, screening `ServiceRequest` and clinical `Provenance`. Keep constraints small and purposeful. The package must document mandatory fields, allowed codes and resource relationships without claiming national approval.

### Status codes and extensions

Use standard FHIR status values exactly. Local codes describe demonstration pathways, care-gap reasons, task purposes and dispositions. Document extensions for case disposition and human-review attestation where no suitable standard element exists. Final `Observation` status alone is not proof of human review.

Use verified standard clinical codes when available. Preserve text without a code when a reliable mapping is unavailable. MedGemma must not invent SNOMED CT or LOINC identifiers. Confirm terminology licensing and local bindings before pilot deployment.

### Validation sequence

1. Validate JSON structure and the supported resource type.
2. Validate against base FHIR R4 and the applicable Namaa profile.
3. Check required terminology bindings and reject unsupported modifier extensions.
4. Validate references, patient consistency and workspace boundaries.
5. Apply authorization, business-state and clinical-review rules before committing.

### Import and export

Seed the prototype with version-controlled transaction Bundles. Accept only allowlisted types and operations. Do not follow arbitrary external URLs or attachments. Require inline synthetic text or authorized local `Binary` references. Match identities using identifier system and value within the workspace; ambiguous or conflicting matches require reconciliation.

Export a collection Bundle containing the patient's authorized clinical journey and permitted referenced resources. Preserve identifiers and provenance. External imports remain pending review unless explicitly recognized as trusted, versioned demonstration fixtures. Record unsupported capabilities rather than silently dropping important content.

### Validation result

FHIR-facing errors use `OperationOutcome`. Structural validity, clinical correctness and permission are separate checks. A successful validator result is not a clinical endorsement or a certificate of interoperability with a provider.

---

## 5. MedGemma extraction and review

### Model configuration

Use `google/medgemma-1.5-4b-it` on a protected Hugging Face Inference Endpoint with a tested custom serving container. Keep the endpoint token in the backend environment. Begin capacity testing with one GPU offering at least 24 GB memory, one concurrent generation and unquantized weights; validate actual memory and latency before committing to the instance size.

### Bounded input and output

Process one English plain-text note per request, up to 6,000 characters. Reject oversized notes rather than truncating them. Include source ID, version and document date. Use greedy decoding and a maximum 2,048 new tokens. Supply only the content needed for extraction, not an entire patient record by default.

| Proposal field | Meaning |
| --- | --- |
| `concept` and `value_text` | Controlled category and the original extracted statement |
| `subject` and `assertion` | Patient or family member; present, absent, uncertain or historical |
| `effective_date` | Explicit date only; otherwise null |
| `source reference` | Document ID, version and exact supporting excerpt |
| `proposed resource type` | Suggested mapping category, subject to deterministic validation |
| `review state` | Proposed, accepted, corrected or rejected; reviewer and reason retained |

### Processing flow

`Queue the job → retrieve the authorized note → run extraction → validate schema and quote → store proposals outside FHIR → human review → deterministic resource mapping → FHIR/profile validation → transaction containing accepted resource and Provenance → pathway re-evaluation`

Calculate quote offsets server-side. Ambiguous repeated excerpts require more source context. A matching quote establishes traceability, not correctness. Accepted facts retain source versions, model revision, prompt version and reviewer identity. Represent the model as a `Device` agent and the human reviewer separately in `Provenance`.

### Failures and prohibited behavior

Use a 90-second timeout, one transient retry and one formatting-repair attempt. Failed output never becomes "no risk." Notes are untrusted input; embedded instructions cannot invoke tools or actions. The model cannot set urgency, issue requests, interpret raw variants or close care plans. Clearly labelled offline fixtures may support rehearsals but must never be presented as live inference.

---

## 6. Prevention rules and case workflow

### Rule evaluation

Rules consume reviewed resources and produce an immutable evaluation snapshot with patient reference, input versions, rule ID/version, eligibility, gap result, contributing factors, missing inputs and proposed review action. `DEMO_WCV_01` and `DEMO_ADULT_01` use synthetic conditions and due dates. Do not encode real clinical schedules without sponsor approval.

| Evaluation | Meaning |
| --- | --- |
| Gap identified | Verified inputs meet the configured demonstration gap condition. |
| No gap identified | No configured gap found in available data; not an assurance of health. |
| Needs review | Required information is missing, contradictory or unverified. |
| Not eligible | Explicit verified inputs exclude this configured pathway. |

### Plan and task lifecycle

A possible gap creates a draft `CarePlan` and review `Task`. The reviewer confirms facts and eligibility, activates the plan and authorizes any `ServiceRequest`. Coordinators handle invitation, booking, attendance and referral progress. Record separate tasks for meaningful handoffs so each action has its own owner and deadline.

`Task.status` uses `requested`, `accepted`, `in-progress`, `on-hold`, `completed`, `failed`, `cancelled` or `rejected` as appropriate. `Task.businessStatus` records Namaa operational detail. Task completion means the task was performed; it does not prove that preventive care occurred.

### Disposition and closure

Keep case disposition separate: active, preventive action completed, declined, deferred, unreachable or clinically closed for another reason. Active work uses an active plan; temporary deferral uses `on-hold`; finished intended care uses `completed`; discontinued care uses `revoked`, with the disposition and reason preserved.

Clinical completion requires appropriate `Encounter`, `Procedure` or reviewed report evidence and reviewer authorization. Reference evidence in the relevant task output and plan outcomes. Appointment booking alone is insufficient. Other authorized closures never increase completed-care counts. Reopening requires a recorded reason.

### Ownership and escalation

Every active task has an owner and next action. Use `Task.restriction.period.end` for applicable execution deadlines. A worker checks overdue tasks every minute, creates one escalation per missed deadline and preserves ownership. Referral rejection creates reassignment work; deferred care retains a recall date. Queue order uses reviewer-marked urgency and due times, not an unvalidated AI risk score.

---

## 7. APIs and consistency

| Application endpoint | Purpose |
| --- | --- |
| `POST /api/v1/auth/login` and `logout` | Create or revoke team session |
| `POST /api/v1/demo/sessions` and `reset` | Provision or replace an isolated guest workspace |
| `GET /api/v1/patients` and `/patients/{id}` | Authorized patient lists and FHIR-derived detail |
| `POST /api/v1/documents/{id}/extractions` | Queue job; return 202 and job ID |
| `GET /api/v1/extractions/{id}` | Job status and proposals |
| `POST /api/v1/facts/{id}/review` | Accept, correct or reject with reason |
| `POST /api/v1/patients/{id}/evaluations` | Evaluate reviewed resource versions |
| `GET /api/v1/cases` and `/cases/{id}` | CarePlan worklist, tasks and timeline |
| `POST /api/v1/cases/{id}/actions` | Execute validated workflow commands |
| `GET /api/v1/analytics/overview` and `segments` | Pathway metrics and approved segment reports |

### FHIR gateway

Expose `/fhir/R4` only through the authenticated gateway. Support metadata, authorized reads and instance history, allowlisted patient-scoped searches, validation, controlled transaction import and collection-Bundle export. Advertise only implemented interactions in `CapabilityStatement`. General-purpose guest writes are disabled.

### Command and error contracts

A mutation carries action, expected resource version, unique request ID, action data and any required reason. Return the resulting resource references and versions. Repeated IDs with the same payload return the prior result; reuse with a different payload is rejected. Application errors include `code`, `message`, `field_errors` and `request_id`. Use `401`, `403`, `404`, `409`, `422`, `429` and `503` consistently.

### Clinical atomicity and recovery

Use FHIR transaction Bundles for related clinical changes, stable logical IDs for creates and `If-Match` for version-aware updates. A stale version produces a conflict, not an overwrite. Validate every reference in the transaction.

The application database and HAPI do not share an atomic transaction. First journal the command and intended Bundle, then execute the FHIR transaction, then mark it complete and refresh projections. After a crash, reconcile stable IDs, versions and command provenance before retrying. Never blindly repeat a transaction whose outcome is uncertain.

---

## 8. User experience and patient journeys

| Screen | Essential behavior |
| --- | --- |
| Welcome | Team sign-in or isolated guest entry; synthetic-data notice |
| Coordinator worklist | Pathway, owner, status and overdue filters; next action visible |
| Patient overview | Clinical history, caregiver information and contact preferences |
| Source review | Source excerpt beside proposed fact; accept, correct or reject |
| Case detail | Plan, rule explanation, owner, deadline, referral and event timeline |
| Action forms | Only valid actions; server remains authoritative |
| Population dashboard | Explicit cohorts, denominators, suppression and refresh time |
| Interoperability view | Authorized resource JSON, references, versions and validation results |

### Child journey

A synthetic note contains a caregiver concern and an unknown last visit date. MedGemma proposes the documented facts. The reviewer verifies or corrects them. The rule returns needs review until the missing history is resolved. A reviewed care gap leads to an active plan, chosen contact channel, simulated booking and recorded attendance. Any follow-up remains assigned until evidence supports closure.

### Adult journey

A synthetic note includes family history and incomplete screening history. Family information becomes `FamilyMemberHistory` after review, not a patient diagnosis. Eligibility is checked before a request is authorized. A simulated screening finding leads to a referral `Task`; acceptance, appointment and attendance are distinct events. Rejection or delay remains visible to the owner.

### Interaction rules

Use English, plain-language explanations, visible keyboard focus and text labels in addition to color. Show proposed, verified and missing information distinctly. The reviewer sees exactly what changed after a correction. Preserve entered data after a failed request; refresh and explain version conflicts rather than overwriting.

Poll active inference jobs every two seconds and stop at a terminal state. Display timeout and retry states. Label invitations, bookings and role switching as simulated. Use reviewed patient-message templates populated from verified facts; free-form generated outreach is deferred.

### Participation and accessibility

Offer preferred contact channel and time, telephone assistance and a meaningful decline option. Verify caregiver authority separately from relationship. English-only is a prototype limitation; Arabic and other languages require later local testing and separate evaluation.

---

## 9. Security privacy and isolation

### Authentication and authorization

Use invited accounts with no public registration. Hash passwords with Argon2id. Keep sessions server-side with opaque `HttpOnly`, `Secure`, `SameSite=Lax` cookies, CSRF protection, a 30-minute inactivity limit and an eight-hour maximum lifetime. Rate-limit login attempts and invalidate sessions when accounts are disabled.

Apply role and workspace checks to every API and worker action. Administrators cannot authorize clinical actions unless independently assigned that role. Analysts receive aggregate views only. Provision initial accounts through a protected administrative procedure without shared default passwords.

### Workspace partitioning

Each workspace maps to a dedicated HAPI partition. The server derives the partition from the session; clients cannot supply it as authority. Ordinary application access must not permit default-partition or cross-partition requests. Validate references across reads, searches, histories, `Binary` access and Bundle operations. Tags are labels, not access controls.

Guests receive a new synthetic partition with a 24-hour expiry. Reset replaces the current workspace and retires the prior one. Cleanup removes expired synthetic partitions through a tested administrative process. Guest role switching is constrained to that workspace and cannot change team permissions.

### Threat controls

| Threat | Required control |
| --- | --- |
| Cross-workspace access | Partition enforcement, reference checks and isolation tests |
| Prompt injection in a note | No model tools; treat note content as data; human review |
| External URL or attachment abuse | No arbitrary fetching; allow only authorized local references |
| Resource exhaustion | Body limits, bounded model tokens, queue limits and rate limits |
| Credential exposure | Backend-only tokens, secret injection and redacted logs |
| False success or unsafe closure | Server transitions, evidence requirements and audit events |

### Data handling

TLS protects public traffic and model requests. Do not log note bodies, prompts, passwords or tokens in routine logs. Record request IDs and operational metadata. Synthetic-only scope does not establish permission for future real health data. A pilot must approve data location, processing agreements, retention, access and clinical accountability before use.

---

## 10. Operations analytics and reliability

### Durable processing

Extraction jobs use `queued`, `running`, `succeeded`, `failed` and `cancelled` states. Claim a job using a database transaction and lease. Store attempts and lease expiry; recover abandoned work after a crash with bounded retries. Do not rely on in-process background tasks for durable inference.

Keep one inference replica warm during demonstration windows and pause it outside agreed windows. Limit model submissions to five per minute per session and 30 per guest workspace per day. Begin with one concurrent generation. Monitor queue depth before increasing concurrency.

### Reporting projections

Build projections from committed FHIR resources, retain source versions and a refresh time, and reconcile periodically. A failed reporting update cannot change clinical truth. Avoid FHIR subscriptions in the initial release. A projection rebuild must reproduce the same counts for the same cohort and observation window.

| Measure | Definition |
| --- | --- |
| Primary completion | Eligible people with verified completed care within the window divided by eligible people due; separate child and adult pathways. |
| Engagement and progression | Successful contact, invitations, booking, attendance and referral acceptance are distinct counts. |
| Follow-up | Completed required follow-ups divided by follow-ups due within the defined cohort and window. |
| Timeliness | Median time to attendance plus overdue task count; report missing timestamps. |
| Operational value | Coordinator workload, rejected handoffs and reasons for delay; no unmeasured clinical-benefit claim. |

### Population safeguards

Use fixed cohorts and fixed segment views for age band, contact channel and synthetic geography. Suppress cells below 10 and complementary totals that would reveal hidden counts. Restrict overlapping filters and individual-level exports for analysts. Declined or unreachable people remain in the eligible denominator. Label all prototype outcomes synthetic.

### Monitoring and recovery

Track API errors and latency, queued-job age, inference timeout/schema failure, rejected closure attempts, orphaned tasks and login failures. Provide liveness and dependency readiness endpoints. Keep a tested local startup route and clearly labelled recording fallback. Before a pilot, define backup frequency, restore objectives, incident ownership and recovery drills with the sponsor.

---

## 11. Verification and acceptance

| Test group | Acceptance criteria |
| --- | --- |
| FHIR structure | Valid fixtures pass R4/profile validation. Invalid status, required field, reference and modifier extension examples fail. |
| Import and export | Identifiers and provenance survive round trip; exported collection validates; conflicting identity is rejected. |
| Clinical transaction | Related writes commit together or not at all. Stale versions fail. Duplicate commands produce one logical action. |
| Isolation | A guest cannot read another workspace through normal read, search, history, `Binary`, validation or Bundle operations. |
| AI review | No unreviewed proposal influences rules. Negation, subject attribution and source excerpts remain correct in accepted facts. |
| Failure behavior | Model timeout leaves reviewable jobs; API errors preserve state; uncertain transaction outcomes reconcile safely. |
| Care closure | Bookings alone cannot complete care. Evidence and review are required. Declined contact is not a completed intervention. |
| Workflow resilience | Rejected referrals and overdue tasks remain assigned; recall dates persist; reopening requires a reason. |
| Analytics | Fixed cohort calculations reproduce; suppression prevents reconstruction; projections rebuild correctly. |
| Frontend | Both journeys complete using keyboard controls; loading, empty, error and conflict states are usable. |

### AI evaluation set

Prepare 40 synthetic labelled notes: 10 straightforward, 10 negation/family-attribution, 10 missing-date/conflicting-history and 10 irrelevant-content/instruction/formatting cases. Use half for prompt development and half for held-out checks. Report field precision/recall, assertion accuracy, attribution, quote validity, unsupported additions, schema validity and latency with sample sizes.

Synthetic fixture results are software evidence, not clinical diagnostic accuracy, population calibration or effectiveness. All displayed proposals need valid provenance; unsupported information must never enter verified resources automatically.

### Test tooling and evidence

Use `pytest` for rules, mappings and backend behavior; a pinned R4 validator for examples and profiles; and Playwright for full browser journeys. Keep expected outputs, observed results and evidence links. Mocked model tests verify integration behavior; they do not verify MedGemma quality. Run separate live endpoint evaluation before describing inference as operational.

---

## 12. Delivery responsibilities and pilot gates

| Owner | Implementation responsibility | Review handoff |
| --- | --- | --- |
| Ismail | HAPI, databases, partitions, auth, FHIR gateway, transactions, workflow and reconciliation | API/resource versions to Mark; source and write contracts to Alfred |
| Alfred | Profiles with Ismail, MedGemma, extraction schema, mapping, rules, provenance and evaluation | Fixtures and expected results to Ismail; explanation labels to Mark |
| Mark | Interface, review controls, FHIR-derived case views, accessibility and demonstration | Integrated journey evidence to both; final recording and visual assembly |

### Sequenced delivery gates

1. **Foundation:** Deploy HAPI and databases, isolate workspaces, validate seed Bundles and display patient records.
2. **Reviewable AI:** Process a note, preserve proposals outside FHIR and promote accepted facts with `Provenance`.
3. **Accountable care:** Complete both synthetic journeys with plans, tasks, requests, evidence and escalation.
4. **Interoperability and release:** Verify round-trip export, access boundaries, recovery, reporting and the recorded demonstration.

FHIR infrastructure, authentication and hosted inference make the earlier three-day estimate a stretch target. Plan against these gates. If time is limited, defer visual polish and advanced analytics rather than validation, isolation or closure checks.

### Required design and build artifacts

Maintain the implementation guide, profiles and terminology; synthetic transaction Bundles; OpenAPI and `CapabilityStatement`; model/prompt versions and fixtures; rules and workflow definitions; validation and recovery tests; deployment/reset guide; and a truthful list of implemented versus simulated features.

### Pilot prerequisites

Confirm the partner's FHIR version, implementation guides, terminology bindings, identity services and authorization requirements. R4 support alone does not establish compatibility with an Abu Dhabi provider or exchange. Obtain a clinical sponsor, approved rules, lawful data access, accepted hosting and processing arrangements, production identity controls and a prospective evaluation protocol.

### Future extensions

After these gates, consider provider scheduling interfaces, live communications, SMART authorization where required, additional languages, clinical terminology services and larger evaluation cohorts. Imaging, raw genomic interpretation and autonomous clinical decisions remain separate initiatives requiring their own evidence and governance.

---

## References and design assumptions

The following primary documentation informs the architecture. Product-specific choices, numerical limits and release gates in this document are proposed Namaa design decisions. They are not requirements imposed by the cited standards.

* **HL7 FHIR R4 REST API** — Resource interactions, version-aware updates, transactions and `CapabilityStatement`.  
  <https://hl7.org/fhir/R4/http.html>
* **HL7 FHIR R4 CarePlan** — Representation of intended care and plan activities.  
  <https://hl7.org/fhir/R4/careplan.html>
* **HL7 FHIR R4 Task** — Execution tracking and ownership of work.  
  <https://hl7.org/fhir/R4/task.html>
* **HL7 FHIR R4 FamilyMemberHistory** — Family history distinct from a patient condition.  
  <https://hl7.org/fhir/R4/familymemberhistory.html>
* **HL7 FHIR R4 Provenance** — Agents and sources involved in creating or revising resources.  
  <https://hl7.org/fhir/R4/provenance.html>
* **HAPI FHIR JPA server** — FHIR persistence and server configuration.  
  <https://hapifhir.io/hapi-fhir/docs/server_jpa/get_started.html>
* **HAPI partition interceptors** — Partition selection from trusted request context.  
  <https://hapifhir.io/hapi-fhir/docs/server_jpa_partitioning/partition_interceptor_examples.html>
* **MedGemma model card** — Model identity, use limitations and application-specific validation.  
  <https://developers.google.com/health-ai-developer-foundations/medgemma/model-card>
* **Hugging Face custom containers** — Custom model-serving deployment.  
  <https://huggingface.co/docs/inference-endpoints/guides/custom_container>
* **Hugging Face endpoint security** — Protected versus private endpoint access.  
  <https://huggingface.co/docs/inference-endpoints/security>

### Assumptions to verify before deployment

The team has access to an eligible model-hosting account and compute budget. Model license terms are accepted by the deploying organization. The selected HAPI release, partitioning mode and validator are tested together. Endpoint availability, memory sizing and latency are verified with the actual workload. No real patient information is used until pilot prerequisites are met.
