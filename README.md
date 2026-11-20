# Namaa

FHIR-first precision prevention and care-coordination **prototype** — Population Health
Challenge 04. Finds possible preventive care gaps, explains the evidence, routes them to
authorized human review, and tracks the next action through attendance and documented
follow-up.

> **Synthetic demonstration only.** No real patient data, no live messaging, no live bookings,
> no production EHR integration, no clinically validated rules. Not for clinical use.

**Status:** the UI talks to the FastAPI demo API. Guest sessions, workflow, evaluations,
extraction SSE, fact review, and analytics are live against SQLite + a stub FHIR store.
Population counts are server-suppressed (`n < 10`, whole-release). A labelled reporting
cohort makes the funnel publishable; the coordinator worklist stays the six journey cases.
There is no production IdP, live HAPI, or live MedGemma.

## Start here

- [DOCKER.md](DOCKER.md) — run the full stack with Docker Compose
- [docs/README.md](docs/README.md) — documentation index, team ownership, the eight non-negotiables
- [docs/02-decisions/D003-backend-stack-and-api.md](docs/02-decisions/D003-backend-stack-and-api.md) — locked sprint stack and API paths
- [api/README.md](api/README.md) — Ismail: one-command API startup and contract
- [ai/README.md](ai/README.md) — Alfred: AI module setup, local demo, tests, contracts, and integration handoff
- [docs/02-decisions/OPEN-QUESTIONS.md](docs/02-decisions/OPEN-QUESTIONS.md) — remaining open questions
- [docs/01-milestones/MILESTONE-LOG.md](docs/01-milestones/MILESTONE-LOG.md) — what has actually been delivered

```bash
docker compose up --build
```

Team: Ismail (backend, FHIR, workflow) · Alfred (rules, AI, evaluation) · Mark (frontend, demo)
