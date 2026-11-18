# Namaa

FHIR-first precision prevention and care-coordination **prototype** — Population Health
Challenge 04. Finds possible preventive care gaps, explains the evidence, routes them to
authorized human review, and tracks the next action through attendance and documented
follow-up.

> **Synthetic demonstration only.** No real patient data, no live messaging, no live bookings,
> no production EHR integration, no clinically validated rules. Not for clinical use.

**Status:** backend demo API in progress (FastAPI + SQLite). Frontend runs on mocks until F4.

## Start here

- [docs/README.md](docs/README.md) — documentation index, team ownership, the eight non-negotiables
- [docs/02-decisions/D003-backend-stack-and-api.md](docs/02-decisions/D003-backend-stack-and-api.md) — locked sprint stack and API paths
- [api/README.md](api/README.md) — Ismail: one-command API startup and contract
- [ai/README.md](ai/README.md) — Alfred: AI module setup, local demo, tests, contracts, and integration handoff
- [docs/02-decisions/OPEN-QUESTIONS.md](docs/02-decisions/OPEN-QUESTIONS.md) — remaining open questions
- [docs/01-milestones/MILESTONE-LOG.md](docs/01-milestones/MILESTONE-LOG.md) — what has actually been delivered

Team: Ismail (backend, FHIR, workflow) · Alfred (rules, AI, evaluation) · Mark (frontend, demo)
