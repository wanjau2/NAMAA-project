# Namaa — Documentation

Namaa is a FHIR-first precision prevention and care-coordination **prototype** built for
Population Health Challenge 04. It identifies possible preventive care gaps, explains the
evidence behind each one, routes it to authorized human review, and tracks the next action
through attendance and documented follow-up.

**Everything in this repository is a synthetic demonstration.** No real patient data, no live
messaging, no live bookings, no production EHR integration, and no clinically validated rules.

## Team and ownership

| Member | Owns | Final handoff |
| --- | --- | --- |
| Ismail | Backend, data, FHIR gateway, workflow, integration | Running API, case storage, workflow controls, setup guide |
| Alfred | Rules, AI extraction, evaluation, claims truthfulness | Versioned demo rules, explanations, fixtures, evidence notes |
| Mark | Frontend, accessibility, demonstration | Connected interface, guest demo, recording, assembled deck |

## How this folder is organized

| Path | Purpose |
| --- | --- |
| [00-reference/](00-reference/) | The source documents. Treat as the baseline spec — do not rewrite them in place; supersede them with a dated milestone or decision record. |
| [01-milestones/](01-milestones/) | One file per major milestone, plus the running [MILESTONE-LOG.md](01-milestones/MILESTONE-LOG.md) index. |
| [01-milestones/frontend-roadmap.md](01-milestones/frontend-roadmap.md) | Mark's remaining frontend steps to F6, with blockers and estimates. |
| [02-decisions/](02-decisions/) | Decision records for choices that are hard to reverse, plus the [OPEN-QUESTIONS.md](02-decisions/OPEN-QUESTIONS.md) register. |
| [03-evidence/](03-evidence/) | Acceptance-check results, screenshots, test output, recordings — the proof behind each milestone claim. |

## Reference documents

| Document | What it governs |
| --- | --- |
| [namaa_detailed_team_work_plan.md](00-reference/namaa_detailed_team_work_plan.md) | Scope, work packages per member, case lifecycle, acceptance scenarios, three-day schedule, submission checklist. |
| [namaa_software_design_specification.md](00-reference/namaa_software_design_specification.md) | Full architecture: FHIR R4 contracts, MedGemma extraction, rules, APIs, security/isolation, operations, delivery gates. |
| [namaa_ui_theme_prompt.md](00-reference/namaa_ui_theme_prompt.md) | Design system "Clinical Desert Calm": color tokens, epistemic status tokens, typography, RTL rules, screen requirements, `globals.css`. |

## The non-negotiables

These hold in every milestone. A change here needs a decision record, not a commit message.

1. **Synthetic only.** A persistent `SYNTHETIC DEMO DATA — NOT FOR CLINICAL USE` bar on every screen.
2. **The server is authoritative.** The UI may request a transition; the backend decides validity and records the event.
3. **Stage and disposition are separate.** `declined`, `deferred` and `unreachable` are never silently relabelled `completed`.
4. **Completion requires evidence** plus reviewer authorization. A booking is not attendance; attendance is not completion.
5. **Missing data is not reassurance.** Absent records produce `needs_review`, never a low-risk result — and get equal visual weight to the recommendation.
6. **No unreviewed AI output reaches the rules.** The model proposes with an exact source quote; a human accepts, corrects or rejects. The model never sets urgency, issues requests, interprets raw variants or closes care.
7. **No unsupported clinical claims** in the UI, deck or pitch. Fixture pass rates are software evidence, not diagnostic accuracy.
8. **Suppress small cells** (`n < 10`) including complementary totals.

## Milestone documentation workflow

Every major milestone gets a record. The rule is: if it changed what the product *is* or what we
can *truthfully claim*, document it.

1. Copy [01-milestones/TEMPLATE.md](01-milestones/TEMPLATE.md) to `01-milestones/MNN-short-slug.md`.
2. Fill it in — including what is **built** vs **mocked** vs **not started**. Be exact; the
   submission has to describe the real level of integration.
3. Put the proof in [03-evidence/](03-evidence/) and link it from the record.
4. Add one line to [MILESTONE-LOG.md](01-milestones/MILESTONE-LOG.md).

## Current status

**Frontend foundation built** (Next.js 16 + Tailwind 4 + shadcn/ui in [web/](../web/)), running on
labelled mock data — see [M01](01-milestones/M01-frontend-foundation.md). No backend yet.
Stack choice is still formally open — see [OPEN-QUESTIONS.md](02-decisions/OPEN-QUESTIONS.md).
