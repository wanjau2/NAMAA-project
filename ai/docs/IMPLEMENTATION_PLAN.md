# Alfred's initialization plan and repository findings

Inspected on 2026-11-18 before implementation. Source: supplied
`Namaa_FHIR_Software_Design.docx`, version 1.1, 17 November 2026, including §§13–16.

The clean starting repository contains a FastAPI/Pydantic 2 API using SQLite,
workflow commands, guest role headers, analytics, and a placeholder evaluator.
Next.js/TypeScript consumes the API; source review still uses local fixtures.
There are no extraction/review endpoints, HAPI gateway, profiles, validator jar,
or AI package. D003 explicitly defers HAPI and MedGemma from the current sprint.
Only `web/AGENTS.md` exists; it governs web changes, which this task does not make.
No ancestor AGENTS.md was found. Existing work remains unchanged.

1. Contracts: isolated importable `ai/`, Pydantic 2 JSON contracts, custom endpoint
   protocol, explicit review and backend trust boundaries. No new web/API service.
2. Vertical slice: bounded adapter → schema/source checks → explicit authorized
   review → deterministic Observation/FamilyMemberHistory + Provenance proposal →
   simulated committed snapshot → deterministic rules. A proposed Bundle cannot
   itself become a rule input. Official validation remains visibly pending if absent.
3. Verification: 40 manually specified synthetic notes, balanced 20/20 development
   and held-out split, integration evaluation and adversarial/failure-path tests.
4. Handoff: generated schemas and JSON examples, commands, evidence, and pending
   backend contracts. No deployment, patient data, paid provisioning or live calls.

Key design choices: preserve original statements as text rather than invent
terminology; dates remain null unless explicit; mock results are labelled at every
boundary; conflicting records never silently select a winner; Python offsets use
Unicode code points (Mark must convert for JavaScript UTF-16 slicing).

## Completion evidence

All four local initialization phases are complete. The implemented slice and
commands are in `../README.md`; generated contracts/examples are in `../examples/`;
test and replay evidence is in `../evidence/`. Official FHIR/profile validation,
real authentication/persistence, HAPI execution, actual endpoint compatibility
and model quality remain pending integration checks, not completed capabilities.
