# Alfred → Ismail — integration handoff

**Date:** 19 November 2026  
**Commit:** `1e694e3` on `main`  
**Canonical document:** [ai/docs/HANDOVER_TO_ISMAIL.md](../../ai/docs/HANDOVER_TO_ISMAIL.md)

Ismail — Alfred's extraction, review mapping, rules, bounded context, Relate
refresh contract, and population-suppression policy are on `main` in `ai/`.
The FastAPI app was not switched onto those callables. Please connect the
existing routes rather than reimplementing validators or rule semantics.

| Connect | Alfred entry | Existing route |
| --- | --- | --- |
| Durable extraction | `AuthorizedExtractionPipeline` | `POST /api/v1/documents/{id}/extractions` |
| Human review | `apply_review`, `propose_transaction` | `POST /api/v1/facts/{id}/review` |
| Rules | `evaluate`, `rules_for_reviewed_commit` | `POST /api/v1/patients/{id}/evaluations` |
| Context / graph | `ScopedContextAssembler`, `RelateResolver` | verified-context + Relate GETs |
| Reporting | `suppress_population`, `publish_population` | `/overview`; `/segments` still needed |

Do not fall back to extraction fixtures when hosted inference fails. Do not map
`FamilyMemberHistory` to a patient `Condition` or `Observation`. Missing
screening history is `needs_review`. Suppression applies to one complete
publication family, including complements.

Workflow (draft CarePlan/Task, ServiceRequest, overdue escalation) stays with
you. HAPI, PostgreSQL leases, and production identity are still required for
the target architecture.

Companion (older API defect register): [ismail-gap-handoff-draft.md](ismail-gap-handoff-draft.md).
Implementation notes: [ai/docs/SAFETY_IMPLEMENTATION.md](../../ai/docs/SAFETY_IMPLEMENTATION.md).
