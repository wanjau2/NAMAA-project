# Alfred handoff: product claims and demo narrative

## Claims register

| Claim suitable for the demo | Evidence in this repository | Required qualification |
| --- | --- | --- |
| The prototype checks source-grounded extraction proposals before review. | Exact excerpt, offset, source-version, and issue checks in `validation.py`; synthetic tests. | Traceability is not clinical correctness. |
| Unreviewed proposals do not feed the deterministic rules. | `rules.evaluate` accepts a backend-authorized `RuleSnapshot`; missing or unreviewed resources yield `needs_review`. | Real snapshot authorization and FHIR execution belong to Ismail. |
| Demonstration rules return explainable, versioned outcomes. | `DEMO_WCV_01` and `DEMO_ADULT_01`, synthetic intervals, input references/versions and factors. | Intervals are fictional; no Abu Dhabi schedule or screening authorization is implemented. |
| Relate may suggest source references for optional context. | Disabled-by-default candidate adapter that resolves hints only against current verified backend context. | No graph service is connected; graph paths never grant access or establish risk. |
| The AI processing boundary is designed for review and audit. | Policy client boundary, authorization hooks, and structured audit event contract. | Production identity, protected audit storage, and backend enforcement are pending Ismail's integration. |

Do not claim clinical validation, diagnostic accuracy, risk prediction, calibrated
probabilities, approved screening schedules, production authorization, live OCR,
live graph retrieval, or real patient outcomes. Mock extraction reports test
plumbing only. No live MedGemma endpoint has been evaluated.

## Three-minute Alfred segment

1. **Problem (30 seconds):** Preventive information may be spread across notes
   and structured records, making it harder to see what is documented and what
   still needs human review.
2. **What Namaa demonstrates (60 seconds):** A synthetic note produces
   source-linked proposals; a reviewer must accept, correct, or reject them;
   deterministic demonstration rules then evaluate only reviewed, versioned
   resources and explain their outcome.
3. **Boundaries (45 seconds):** The rules and intervals are fictional. The AI
   does not diagnose, authorize screening, determine urgency, write to FHIR, or
   close a case. Empty or conflicting data leads to review rather than a
   reassuring conclusion.
4. **Integration state (30 seconds):** Identify what is simulated, what Ismail's
   backend authorizes and persists, and which profile/model/context integrations
   remain pending. Show only evaluation sample sizes and label mock metrics as
   software checks.
5. **Ask (15 seconds):** Request feedback on the workflow and the evidence needed
   before a properly governed pilot; do not imply the prototype is ready for
   real patient data.
