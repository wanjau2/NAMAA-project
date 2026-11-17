# Namaa team delivery plan

**Population Health Challenge 04 — Precision Prevention and Screening**

Prepared for Ismail, Alfred and Mark | 17 November 2026

## The shared delivery goal

Build a demonstrable prototype in which a fictional child and adult move from an explainable care gap to clinician review, engagement, attendance and documented follow-up. Ismail owns the backend and workflow, Alfred owns prioritization and evaluation, and Mark owns the interface and demonstration experience.

This plan turns the concept-stage submission into a focused three-day build. The schedule is relative to kickoff and assumes each member can contribute approximately 18 focused hours across the sprint. These are planning estimates, not commitments or confirmation of an event deadline.

| Member | Primary responsibility | Final handoff |
| ----- | ----- | ----- |
| Ismail | Backend and integration | Running API, case storage, workflow controls and setup guide |
| Alfred | AI engineering and evaluation | Versioned demo rules, explanations, test cases and evidence notes |
| Mark | Frontend and experience | Connected interface, guest demo, recording and assembled deck |

## Build only what proves the concept

Two synthetic journeys, a coordinator worklist, explainable flags, simulated clinician review, a case timeline and basic outcome reporting.

Use demonstration workflows only as clearly labelled simulations. Clinical rules require qualified review before any real use.

Exclude real patient data, live SMS, live bookings, raw genomic analysis, autonomous diagnosis and production EHR integration.

## Working defaults

If no codebase exists, use FastAPI with SQLite for the demo backend and React with TypeScript for the frontend. Alfred supplies a local Python rules module called by Ismail. Keep an existing workable stack if one is already in use; lock the choice at kickoff. Do not add a separate AI service or external model dependency to the critical path.

## Ismail — backend and workflow ownership

Ismail is accountable for a reliable source of truth. The frontend may request a change, but the backend decides whether it is valid and records what happened.

### Ordered work packages

* **B1 Foundation** — Create the backend structure, environment example, dependency lockfile and one-command startup. Add a health endpoint and a reset command that restores the same synthetic scenarios. *Estimate: 2 hours.*
* **B2 Data model** — Store patients, source observations, care gaps, cases, events, preferences and completion evidence. Use fictional IDs, UTC timestamps and rule-version references. Separate a person from their pathway-specific cases. *Estimate: 3 hours.*
* **B3 Workflow** — Implement review, assignment, invitation, booking, attendance, referral, follow-up and disposition actions. Require an owner for active cases and a due time for the next action. Validate transitions on the server. *Estimate: 4 hours.*
* **B4 Rules integration** — Call Alfred's deterministic evaluator, retain its input snapshot and result, and prevent duplicate open cases for the same patient, pathway and rule version. *Estimate: 2 hours.*
* **B5 Reliability** — Record audit events, reject stale updates, handle repeated requests safely and expose overdue work. Use simulated roles only within isolated guest sessions. *Estimate: 3 hours.*
* **B6 Integration and release** — Connect Mark's UI, fix contract mismatches, prepare a local fallback and document deployment/reset steps. *Estimate: 4 hours.*

### Required behavior

Store both case stage and disposition. A case may be at follow-up with an active disposition, or at invitation with a declined disposition. Completed care requires evidence; an authorized simulated clinician decision may close a case with a different reason but must not increase the completed-care count. Rejected referrals stay visible and return to the owning coordinator for reassignment.

### Handoff to Alfred and Mark

Deliver an OpenAPI specification, sample responses, a seed dataset and a short setup guide. Return the same structured error format for validation failures, stale revisions and unavailable services. Provide a list of supported action names and role requirements before Mark connects the screens.

### Definition of done

Both journeys survive a restart; invalid closure fails; duplicated requests do not create duplicate actions; every transition is auditable; declined and unreachable cases remain separate from completions; a fresh reviewer can start and reset the demo using the guide.

## Alfred — AI engineering and evaluation ownership

Alfred owns the reasoning behind each flag and the truthfulness of the submission. For this sprint, a transparent rules module is the executable intelligence layer. It must not be described as a trained or clinically validated predictive model.

### Ordered work packages

* **A1 Scenario design** — Create the child and adult anchor stories, then variations covering missing records, conflicting history, declined outreach and referral delay. Use entirely fictional data. *Estimate: 3 hours.*
* **A2 Rules contract** — Define deterministic care-gap evaluation with patient ID, pathway, status, contributing factors, source dates, missing fields, next review action and rule version. *Estimate: 3 hours.*
* **A3 Explanation quality** — Produce readable reasons and distinguish a documented overdue event from an unknown record. Explain uncertainty without inventing risk probabilities or genomic significance. *Estimate: 3 hours.*
* **A4 Evaluation fixtures** — Write expected outputs for flagged and unflagged records, ineligible examples, duplicate inputs and boundary dates. Check reproducibility and missing-data handling. *Estimate: 4 hours.*
* **A5 Engagement and metrics** — Prepare short approved-for-demo message templates, language preference behavior and metric definitions. Demonstrate suppression of small groups. *Estimate: 2 hours.*
* **A6 Submission and rehearsal** — Update the pitch, verify citations and product claims, review the integrated demo and lead the final narrative. *Estimate: 3 hours.*

### Rules and AI boundaries

Use versioned synthetic rules with explicit labels such as `DEMO_WCV_01` and `DEMO_ADULT_01`. Eligibility uncertainty produces "needs review," not a screening instruction. Optional interpreted genomic findings may appear as a source for clinician review; absence of genomic data must never block routine prevention. Do not infer clinical relevance from raw variants.

If time remains, add optional AI-assisted wording from structured facts. Keep a deterministic message template as the fallback; do not send personal data to an external model. Generated text cannot change eligibility, urgency, test selection or closure status.

### Handoff and definition of done

Give Ismail the evaluator, versioned rule definitions and fixtures. Give Mark approved labels, explanations, uncertainty messages and example patient communications. All fixtures pass; outputs match their source facts; no unsupported clinical performance claims appear in the UI, deck or pitch. Report fixture pass rates as software checks, not diagnostic accuracy.

## Mark — frontend and demonstration ownership

Mark owns whether a reviewer can understand the concept and complete both journeys without assistance. The interface must make the current status, next action and responsible person obvious.

### Ordered work packages

* **F1 Screen skeleton** — Build guest entry, persistent simulation notice, navigation and a coordinator worklist using agreed mock responses. *Estimate: 3 hours.*
* **F2 Case detail** — Show the care gap, source dates, major factors, missing information, pathway suggestion and assigned owner. Give uncertainty equal visibility to the recommendation. *Estimate: 3 hours.*
* **F3 Journey actions** — Add simulated clinician approval, preference selection, invitation, booking, attendance, referral acceptance and closure evidence forms. *Estimate: 4 hours.*
* **F4 Backend connection** — Replace mocks with Ismail's API, handle loading/error/empty states and display server validation failures without losing entered data. *Estimate: 3 hours.*
* **F5 Dashboard and accessibility** — Show eligible, invited, attended and completed counts with denominators. Add suppression labels, keyboard support and clear contrast. *Estimate: 2 hours.*
* **F6 Delivery assets** — Test the guest journey, record the demonstration, assemble the revised deck and verify the links on a clean browser session. *Estimate: 3 hours.*

### Required screens

Guest entry opens a fresh synthetic session. The worklist supports pathway, stage and overdue filters. Case detail presents explanations and a chronological event list. The action panel exposes only valid next actions, while the server remains authoritative. The population view labels all figures as synthetic demo data and avoids implying real-world outcomes.

### Communication and accessibility

Offer English and an Arabic preference in the demonstration. Alfred supplies reviewed sample copy where available; unreviewed translations must be labelled and must not be presented as clinically approved. Support right-to-left layout if Arabic copy is included. Show phone-assisted support as an option, and never imply that a message was actually sent.

### Handoff and definition of done

Deliver the runnable interface, deployment instructions, a short recording and final slide assembly. Both journeys work at desktop and mobile widths, all controls are keyboard accessible, failed actions have understandable messages, and reset reliably clears a previous guest session. No real credentials or sensitive information appear in the recording.

## Shared interfaces and case lifecycle

### Agree these records before coding

| Record | Minimum fields |
| ----- | ----- |
| Patient | `id`, `age_band`, `synthetic_flag`, `language_channel_preferences`, `caregiver_authority_status` |
| Observation | `id`, `patient_id`, `type`, `value`, `source`, `observed_time`, `missing_conflict_indicator` |
| Care gap | `id`, `patient_id`, `pathway`, `rule_id_version`, `flag_status`, `factors`, `source_ids`, `uncertainty`, `suggested_review_action` |
| Case | `id`, `care_gap_id`, `stage`, `disposition`, `owner`, `next_action`, `due_time`, `revision` |
| Event and evidence | `id`, `case_id`, `actor_role`, `action`, `timestamp`, `prior_new_state`, `reason`, `evidence_reference` |

### API ownership and behavior

Ismail maintains the API contract. Use `GET /cases` and `GET /cases/{id}` for reads; `POST /patients/{id}/evaluate` for rules evaluation; `POST /cases/{id}/actions` for changes; `GET /metrics` for aggregates; and `POST /demo/reset` for an isolated guest reset. Mark passes an action name, expected revision and request ID. Ismail returns the updated case and event, or a structured error with code, message and field errors.

### Lifecycle rules

* **Stages:** `identified → reviewed → invited → booked → attended → follow_up → closed`. Referral acceptance is tracked as an event during follow-up. A clinician-approved pathway may close after attendance if no further action is needed.
* **Dispositions:** `active`, `completed`, `declined`, `deferred`, `unreachable`, or `clinically_closed_other`. Declined, deferred and unreachable must never be silently relabelled completed.

Only the simulated clinician role may approve a pathway or authorize clinical closure. Coordinators manage assignment, contact and scheduling. Guest users may switch these roles within a synthetic session for demonstration, but this is not production authentication or authorization.

### Failure handling

Use a revision check to prevent one action overwriting another. A repeated request ID must not repeat the event. An unavailable evaluator returns a visible retry state; it does not create a low-risk result. A failed API call leaves the UI at the last confirmed state. Missing data creates a review task. Overdue tasks remain assigned and gain an escalation event.

## Three-day schedule and collaboration

Each day includes approximately six focused hours per member. Use the final hour for integration, not additional features. If time is shorter, retain both end-to-end journeys and cut optional AI wording, visual polish and advanced analytics first.

| Checkpoint | Ismail | Alfred | Mark |
| ----- | ----- | ----- | ----- |
| Day 1 first hour | Agree records and API | Agree fixtures and outputs | Agree screens and labels |
| Day 1 close | Seeded backend and reads | Rules module and examples | Clickable screens on mocks |
| Day 2 midpoint | Actions and audit trail | Rules wired into cases | Child journey connected |
| Day 2 close | Evidence and escalation | Failure fixtures pass | Adult journey connected |
| Day 3 midpoint | Reliability and fallback | Claims and metric review | Guest and responsive QA |
| Day 3 close | Release instructions | Pitch and evidence sign-off | Recording and final deck |

### Daily operating rhythm

Start with a 15-minute check-in: what works, what is blocked and the next handoff. Meet briefly at the midpoint to run the current journey together. End with a shared demo and update the task board. Raise interface blockers immediately rather than waiting for the next meeting.

### Task board and review rules

Use **Backlog**, **Ready**, **In progress**, **Review** and **Done**. Every task has one owner, an acceptance check and a dependency. Keep one substantial task in progress per person. Use short feature branches and a peer review before merging shared code. Ismail reviews frontend API usage; Alfred reviews explanation and metric behavior; Mark reviews user-facing flows and wording.

### Integration ownership

Ismail coordinates merges and the runnable release. Alfred maintains one fixture set and the claims register. Mark controls the demonstration sequence and slide assembly. Record contract changes in one shared specification and update fixtures before changing consumers. Do not change status names or response fields privately.

### When a dependency slips

If the backend is late, Mark continues with contract-matching mocks and labels the result a simulation. If optional AI is unreliable, Alfred retains deterministic templates. If hosting fails, Ismail provides the local startup route and Mark supplies a recording. The submission must describe the actual level of integration, including any remaining mocks.

## Verification and measurable acceptance

A task is done only when its acceptance check passes in the integrated build. Keep a short log containing scenario, expected outcome, observed outcome, owner and evidence. All test cases below use synthetic data.

| Scenario | Expected result | Owner |
| ----- | ----- | ----- |
| Child care gap | Explanation, review, invitation, attendance and follow-up evidence are visible. | All three |
| Adult screening need | Eligibility review precedes invitation; referral stays owned through closure. | All three |
| Missing or conflicting history | Needs-review state; no unsupported assurance or automatic invitation. | Alfred |
| No genomic information | Routine prevention journey remains available. | Alfred |
| Invalid or unsupported closure | Server rejects the action; completion count does not change. | Ismail |
| Decline or failed contact | Separate disposition and reason; no increase in completed care. | Ismail |
| Rejected referral or overdue task | Visible owner, next action and escalation; no silent closure. | Ismail |
| Duplicate or stale request | One event for a repeated request; stale changes rejected. | Ismail |
| API outage and retry | Clear error and retry; last verified state preserved. | Mark |
| Guest reset and keyboard use | Fresh synthetic session; usable controls and visible focus. | Mark |
| Small population segment | Suppressed result and no identifying complementary total. | Alfred and Mark |

## Metrics everyone must interpret consistently

$$\text{Completion rate} = \frac{\text{People with a verified completed action}}{\text{Eligible people due in a fixed cohort}}$$

Report completion rates separately for child and adult pathways. A declined or unanswered invitation stays in that denominator. Show invitation reach, booking, attendance, follow-up completion and time to action separately. Label all prototype counts synthetic.

Use $n < 10$ as a demonstration suppression default, with complementary suppression where totals could reveal a hidden group. A real pilot needs governance-approved thresholds. Do not claim false-positive rates, false-negative rates or model calibration from a few fictional examples; those require appropriate real-world adjudicated evaluation.

## Demo submission and release checklist

### Three-minute demonstration sequence

| Time | Presenter | What to show |
| ----- | ----- | ----- |
| 0:00–0:30 | Alfred | Problem, concept status and the explanation-plus-owner promise |
| 0:30–1:20 | Mark | Child flag, uncertainty, simulated review, preferred contact and visit completion |
| 1:20–2:05 | Mark with Ismail | Adult journey, referral handoff, overdue case and closure evidence |
| 2:05–2:35 | Alfred | Synthetic metrics, suppression and the boundary between prioritization and clinical decisions |
| 2:35–3:00 | Alfred | Pilot ask and clear statement of what is built, mocked and unvalidated |

### Submission responsibilities

Alfred writes the narrative, capability summary, evidence notes and pitch. Ismail supplies architecture, data handling, security controls, setup requirements and known integration limitations. Mark assembles slides, screenshots, demo access and recording. All three verify their own names, countries, organizations, age confirmations, IP contributions and conflicts; do not invent missing details.

### Release gate

* Both journeys run on the same build with the same fixtures. Every critical acceptance check passes, or the remaining limitation is stated accurately.
* There are no patient records, live booking calls or real outbound messages. Guest reset affects only its synthetic session.
* A fresh browser can enter the demo without unavailable credentials. Local fallback and recording are accessible to the team.
* The deck matches the delivered product. Completed features, mocked interactions and future capabilities are clearly separated.
* The team checks the official submission portal for the current deadline, required files, eligibility and access conditions. Assign Alfred to verify requirements and record the result.
* Alfred prepares the submission package; the team names an authorized submitter. After submission, save the receipt and verify that the intended files and demo links are present.

## After the hackathon prototype

A real pilot requires a clinical sponsor, approved local pathway rules, lawful data access, production identity and access controls, hosting/security review and an agreed evaluation protocol. These are future work and cannot be replaced by the three technical roles. Retain the prototype as a synthetic demonstration until those prerequisites are met.
