# Draft handoff to Mark — remaining frontend gaps

**Prepared:** 19 November 2026  
**Baseline:** repository commit `167b797`; source and documentation review, not a fresh live-stack or browser test run.  
**Status:** draft for discussion and delivery planning. This does not record team agreement or assign backend work to Mark.

Mark — the backend bridges have landed. Your remaining work is to connect the existing interface to those contracts, complete the review flow, and refresh the evidence against the integrated build.

The four outcome labels, Unicode code-point helpers, nested-proposal normalizer, context display panel, case actions, API analytics panel, and earlier accessibility/browser passes already exist. They should be reused. The gaps below concern their actual integration, remaining defects, and unfinished delivery work.

**Priority:** P0 = correctness or misleading-state issue to resolve first; P1 = required integration and verification; P2 = remaining product/delivery work; conditional = needs a scope or contract decision.

## 1. Shared decision Mark needs to close with Alfred and Ismail

### M00 — Record the authoritative outcome contract · P0 · shared

Adopt the following four names verbatim for `rule_evaluation.outcome`:

| Outcome | Meaning the interface must preserve |
| --- | --- |
| `gap_identified` | The configured rule identified a possible gap for human review. |
| `no_gap_identified_in_available_data` | No configured gap was found in the available data; this is not assurance of health or complete records. |
| `needs_review` | Required information is missing, uncertain, contradictory, or unverified. |
| `not_eligible` | The configured pathway does not apply; this says nothing about other pathways. |

The current API already returns the canonical object from the evaluation endpoint. Its worklist `CaseRow.flag_status` remains `gap | needs_review`; evaluations can return `case: null`. Mark's display module already understands all four outcomes.

**Mark's deliverable:** agree where evaluations without a case are visible, then consume the canonical outcome there. Keep legacy aliases at the compatibility boundary and flag unknown values. Do not widen the frontend case type alone or create a care-gap case just to display a no-gap/ineligible result. If the team chooses to extend the case response, Ismail must publish the matching backend contract. A latest evaluation and a case's workflow state must remain distinguishable.

**Done when:** a recorded cross-team decision names the canonical field, compatibility behavior, and display path for `case: null`. This is the outcome-contract gate; independent review and resilience fixes can proceed now.

Evidence: [API evaluation and case schemas](../../api/app/schemas.py), [evaluation service](../../api/app/services/evaluations.py), [existing outcome display vocabulary](../../web/lib/rule-outcomes.ts), [Q12](../02-decisions/OPEN-QUESTIONS.md).

## 2. Immediate frontend correctness fixes

### M01 — Use the nested proposal throughout source review · P0 · Mark

**Gap:** `normalizeProposal()` understands nested `fact`, but `ApiProposal`, the review cards, correction defaults, and quote highlighting still read flat fields such as `proposal.value_text` and `proposal.excerpt`. The hook casts incoming status/SSE proposals to that flat type. Metadata normalization alone does not fix the live rendering path.

**Deliver:** normalize and validate once at the API boundary; use the resulting shape for text, subject, assertion, relationship, excerpt, review state, model provenance, and correction forms. Preserve the integer proposal version, opaque source version, source hash, and declared offset unit. Reject or visibly flag malformed required fields instead of defaulting them to a patient/present assertion or inventing a model identity.

**Done when:** actual nested status and SSE responses render correctly; quote highlighting uses code points; missing/mismatched source evidence blocks accept/correct; server-reviewed proposals display their returned state after reload.

### M02 — Send the edited fact when correcting · P0 · Mark

**Gap:** the correction form collects edits, but its submission calls `submitReview(..., null)`. `buildReviewCommand()` consequently refuses the correction because a complete replacement fact is required.

**Deliver:** build `correction` from the normalized original fact plus the permitted edits, preserving required fields and valid patient/family-member resource semantics. Retain the reason and show field-level server validation.

**Done when:** a changed value reaches `POST /api/v1/facts/{id}/review`, the server returns `corrected`, and `GET /api/v1/facts/{id}` confirms the corrected fact and new version.

### M03 — Make review state authoritative on the server · P0 · Mark

**Gap:** `onDecide` updates local badges and accepted/corrected counts before awaiting the API. A refused or unsent decision therefore still looks reviewed. The page also says both “not persisted” and “the rule is evaluated from” the local accepted count, even though the endpoint now exists and no evaluation is triggered here.

**Deliver:** separate draft, submitting, confirmed, rejected-request, and uncertain-result states. Update reviewed badges/counts only from a validated server response or readback. Check the returned proposal/request identity, state, fact, and resulting version. Replace stale endpoint-absence banners with the actual result. Label accepted facts as available for evaluation until a server evaluation confirms their use.

**Done when:** denied, invalid, stale, or unreachable submissions never increase confirmed counts; reload reconstructs the state from the server; the UI distinguishes a journaled review from the **stub FHIR gateway**, without claiming a HAPI commit.

### M04 — Complete review retry and conflict handling · P0 · Mark

**Gap:** each submission creates a new request ID; there is no proposal readback method in the web client; 404/405 and some unexpected failures are described as “endpoint absent.” A version returned by review is displayed but does not replace the proposal used for the next command.

**Deliver:** retain one request ID for retries of the same command, prevent duplicate in-flight submissions, refresh the authoritative proposal/version after success, and provide reload/reconcile on 409. Preserve unsaved corrections and reasons. Show 422 field errors and a useful request reference. Treat unavailable proposals and transport/protocol failures accurately; a lost response may follow a successful server write.

**Done when:** duplicate submission cannot create a second decision; a lost-response retry resolves the original result; stale-version recovery uses the refreshed version and a deliberately resubmitted command; no failure is falsely reported as a confirmed success or confirmed rollback.

### M05 — Collect explicit issue acknowledgements · P0 · Mark, identity contract shared

**Gap:** the client currently sends every issue code as acknowledged automatically, and supplies a fixed `Practitioner/demo-reviewer` reference.

**Deliver:** require the reviewer to acknowledge each applicable review-severity issue explicitly; retain blocking issues as blockers. Use the agreed server/session reviewer identity behavior and show returned reviewer provenance. Keep the simulated role clearly labelled; frontend controls do not establish authorization.

**Done when:** an unacknowledged issue cannot be represented as acknowledged by the client, and the displayed reviewer comes from the agreed synthetic identity contract. Ismail owns trustworthy server identity binding; Mark must not manufacture that assurance in the UI.

Evidence for M01–M05: [source review screen](../../web/app/cases/[id]/review/source-review-view.tsx), [review hook](../../web/lib/use-source-review.ts), [web types](../../web/lib/api-types.ts), [normalizer and command builder](../../web/lib/contracts.ts), [API client](../../web/lib/api.ts), [backend proposal serializer](../../api/app/services/proposals.py), [review endpoint](../../api/app/routers/facts.py), [review implementation](../../api/app/services/review.py).

### M06 — Preserve security and failure states across the read path · P0 · Mark

**Gap:** the source-document resolver catches every error and ultimately reports no accessible note. Denial, expired session, rate limiting, and an unavailable API can therefore become an empty state. Existing security-copy helpers are not consistently connected to the read path.

**Deliver:** distinguish loading, authorized empty, denied/unavailable, stale, validation failure, rate limiting, and service/transport failure for notes, proposal disclosure, review, evaluation, and context. Preserve useful drafts and provide the appropriate recovery. Denial messages must not infer or reveal record existence beyond the API response.

**Done when:** 401/403/404/409/422/429/503 and transport failures have exercised user-visible behavior; failure never reads as “no gap” or “no records.” Stop probing fallback documents on failures that should be surfaced. Do not display guessed/tried identifiers as additional evidence about inaccessible records.

### M07 — Fix extraction recovery and terminal-state handling · P1 · Mark

**Gap:** SSE exists, but after a stream error the fallback GET sets `ready` or `empty` solely from proposal count. A still-running, failed, cancelled, or timed-out job can therefore be presented incorrectly. Malformed stream frames are ignored without a visible recovery path.

**Deliver:** inspect the returned job state, retain running/stalled progress, and use bounded reconnect/status recovery until a genuine terminal result. Close obsolete streams, avoid duplicate terminal handling, and show failure/timeout distinctly. Only a successful extraction with zero proposals may show an extraction-empty state; that still says nothing about rule outcomes.

**Done when:** disconnect during running, terminal failure, timeout, malformed response, and successful empty extraction each lead to the correct state and recovery action.

### M08 — Clear stale data on scope and session changes · P0 · Mark

**Gap:** review decisions are component-local; the extraction hook does not clear all document/job/model state at the start of a new scope; the analytics panel skips loading when it already has data. These paths need explicit invalidation rather than relying on component remounts.

**Deliver:** clear or invalidate source text, proposals, review decisions, context, and analytics when session/reset, patient, role/permission scope, source version, or extraction generation changes. Cancel requests where possible and ignore late results from the previous scope. Reset within the same session must also invalidate cached data.

**Done when:** role/session/reset and rapid patient navigation cannot show stale confirmed decisions or data from the previous scope; a revoked or expired context stops being presented as current.

Evidence for M06–M08: [document resolver](../../web/lib/source-documents.ts), [review hook](../../web/lib/use-source-review.ts), [SSE transport](../../web/lib/extraction-sse.ts), [review state](../../web/app/cases/[id]/review/source-review-view.tsx), [analytics cache](../../web/components/api-analytics-panel.tsx).

### M09 — Remove unsupported caregiver-authority claims · P0 · Mark; data from Ismail

**Gap:** case detail hardcodes `Caregiver authority: Verified (synthetic)` for every case. The case response shown in the web types does not supply evidence for that claim.

**Deliver:** show verified authority only when a server field supports it; otherwise show unknown/not supplied or not applicable as appropriate. Complete the remaining patient overview with available clinical history, caregiver relationship, authority, and contact preferences shown separately. This can live in case detail rather than requiring another route.

**Done when:** a relationship is never interpreted as authorization, and no case gains an authority claim from a hardcoded label. Missing backend fields are an explicit dependency, not filled with invented facts.

Evidence: [case detail](../../web/app/cases/[id]/case-detail-view.tsx), [case response types](../../web/lib/api-types.ts), [roadmap A3](../01-milestones/frontend-roadmap.md).

## 3. Complete the live integration

### M10 — Connect review to canonical evaluation results · P1 · Mark, after M00

**Gap:** the web client has no patient-evaluation method; case detail resolves only `row.flag_status`. The four-value renderer therefore cannot expose all live evaluation outcomes through the current case-only flow.

**Deliver:** add a typed evaluation request/result flow using `POST /api/v1/patients/{id}/evaluations`. Display `rule_evaluation.outcome` with its rule/version, input provenance, missing information, and limitations. Retain the canonical object; use legacy fields only for explicit compatibility. Refresh the affected case from the server where one is returned, and render the evaluation when `case` is null. Keep workflow stage/disposition separate from the rule outcome.

**Done when:** all four outcomes are demonstrated from API responses, including no-case results; pending/rejected facts are not claimed as rule inputs; the UI shows the actual evaluation response rather than inferring it from review counts.

**Dependency:** Ismail and Alfred must demonstrate how reviewed facts enter rule inputs and how canonical evaluations are persisted/retrieved. Current review code journals proposals and enqueues the stub FHIR transaction; evaluation code reads observations and persists a reduced `flag_status/factors/missing` result before constructing the canonical response. A response field alone does not establish durable canonical persistence or review-to-rule propagation. Mark should surface that boundary, not implement clinical rule logic in the browser.

### M11 — Connect the context view to verified backend data · P1 · Mark; adapter contract shared

**Gap:** “Live backend” always selects `{kind: "unavailable"}` and says the service does not exist. The backend now provides Relate discovery and verified context. Its verified response contains `records`, while the existing display expects an Alfred `AssembledContext` with `items`, tiers, query, and other assembly metadata.

**Deliver:** use the fixed Relate discovery endpoints where relational discovery is needed, then obtain `POST /api/v1/security/verified-context` before presenting verified records. Agree with Alfred/Ismail whether the UI receives assembled context or displays a faithful adapter over verified records; do not invent assembly metadata or cast one contract to the other. Show source/version, checked scope, completeness, permission revision, generation, verification time/expiry, and actual review status where supplied.

**Done when:** live, loading, empty-unknown, denied, stale/expired, and failed states are real; contract examples remain explicitly labelled examples. Relate results never grant permission, imply caregiver authority, or establish eligibility. Refresh expired verification and invalidate on scope changes.

### M12 — Finish the metrics migration without weakening suppression · P1 · Mark; cohort decision shared

**Gap:** the API analytics panel already renders `suppressed` flags correctly, but the richer funnel/segment/timeliness cards remain a larger local fixture. The existing seed suppresses the live cells; that is not a frontend suppression defect.

**Deliver:** use the server's values and suppression flags for every card described as live. Keep unsupported metric views explicitly as design examples, or defer them until equivalent API aggregates exist. Preserve numerator/denominator and non-completion semantics; refresh on reset/session changes. Do not reconstruct hidden counts or choose a lower threshold in the browser.

**Done when:** no live metric depends on the bundled cohort; suppressed cells reveal no hidden counts through client data, tooltips, or exports. The team records whether to supply a larger synthetic API cohort or keep the fully suppressed demonstration. Ismail owns the aggregate/seed changes.

Evidence for M10–M12: [web API client](../../web/lib/api.ts), [case outcome display](../../web/app/cases/[id]/case-detail-view.tsx), [evaluation service](../../api/app/services/evaluations.py), [context route](../../web/app/cases/[id]/context/context-view.tsx), [context panel](../../web/components/context-panel.tsx), [verified-context payload](../../api/app/security/verified_context.py), [metrics page](../../web/app/metrics/page.tsx), [API analytics panel](../../web/components/api-analytics-panel.tsx).

## 4. Verification and delivery

### M13 — Replace readiness probes with integration assertions · P1 · Mark

**Gap:** `verify:api` still treats some shipped capabilities as optional readiness items. Its review probe accepts anything other than 404/405 as endpoint availability, which does not prove successful persistence. Its excerpt comparison uses JavaScript `String.slice`, despite the code-point contract. Browser tests still expect “no verified-context service,” missing issues, and unpersisted reviews.

**Deliver:** update contract tests and browser expectations for the current API. Cover nested status/SSE proposals; correct code-point offsets including an astral character; accept/correct/reject plus readback; explicit issue acknowledgement; duplicate requests; stale versions; server refusals; lost-response recovery; all four canonical outcomes and `case: null`; verified-context scope/expiry; reset isolation; API suppression. Unknown or malformed responses must fail the check rather than satisfy readiness.

**Done when:** `npm run verify`, `npm run verify:api`, relevant Playwright journeys, lint, and build have current evidence tied to the integrated commit and run configuration. Keep both child and adult journeys, fresh guest sessions, desktop/mobile, and the affected accessibility/RTL checks. Older pass counts are historical evidence, not acceptance of the new bridges. Backend enforcement and Alfred's AuthZEN codec tests remain their owners' responsibility.

Evidence: [API checks](../../web/scripts/verify-api-contract.ts), [shape checks](../../web/scripts/verify-contract-shapes.ts), [context browser tests](../../web/e2e/context.spec.ts), [journey tests](../../web/e2e/journeys.spec.ts), [package scripts](../../web/package.json).

### M14 — Align build configuration and startup instructions · P1 · Mark with Ismail for deployment

**Gap:** the browser client reads `NEXT_PUBLIC_API_BASE_URL`, while Docker, Compose, and `.env.example` configure `NEXT_PUBLIC_API_URL`. A configured deployment can therefore fall back to the client's localhost default. `npm start` also uses `next start` while the project builds standalone output; Docker already runs `node server.js`.

**Deliver:** choose one API URL variable across the client and build configuration, document when it is embedded in the browser build, and verify a non-default URL. Publish a working standalone startup path with assets plus the existing local development fallback. Confirm browser-reachable API URL/CORS with Ismail; do not describe the entire Docker path as absent.

**Done when:** a fresh reviewer can start the documented build and complete a guest journey without editing source or silently calling the wrong API. Resolve hosting Q7 only if hosted delivery is in scope.

Evidence: [API base URL](../../web/lib/api.ts), [Dockerfile](../../web/Dockerfile), [Compose](../../docker-compose.yml), [environment example](../../.env.example), [Next configuration](../../web/next.config.ts), [web scripts](../../web/package.json), [Docker guide](../../DOCKER.md).

### M15 — Finish navigation and final accessibility polish · P2 · Mark

Complete selected/current-page navigation, remaining hover/reset-confirmation polish, and the final badge contrast and reduced-motion checks. Preserve the persistent synthetic banner, keyboard-reachable controls with reasons, mobile layout, and bidi isolation. Keyboard, axe, RTL, and responsive work already has evidence; rerun the affected journeys after integration rather than treating those foundations as unbuilt.

**Done when:** current location is announced, final contrast/motion checks are recorded, and the changed review/context flows retain accessible focus, error, loading, and retry behavior.

### M16 — Settle language scope and finish the corresponding copy work · P2 · conditional

The roadmap still lists string extraction and Arabic copy as unfinished; Q2 remains open. Mark should record the team's English-only versus EN/AR decision, finish dictionary extraction if retained in scope, and integrate approved/reviewed copy accordingly. Any unreviewed Arabic demonstration copy must keep its label; changing direction alone must not be presented as a completed translation. Preserve working RTL mechanics either way.

**Done when:** language controls, actual translated content, and demo claims agree with the recorded scope. Alfred supplies/reviews clinical explanation wording; Mark integrates it.

### M17 — Complete the inspector only to the agreed scope · P2 · conditional

The FHIR/audit inspector remains a small reference panel. If retained, connect permitted audit data and available resource references/versions, review provenance, validation information, and stub/outbox status through agreed read contracts. Do not infer a FHIR resource/version from a case revision or present stub storage as HAPI persistence.

**Done when:** every displayed provenance claim has a source, or the inspector is explicitly deferred. API resource exposure, audit enforcement, and HAPI integration belong to Ismail, not Mark. The roadmap already identifies this screen as deferrable.

### M18 — Refresh demo assets and reconcile the documentation · P2 · Mark

Footage, a deck, and screenshots already exist. Record the remaining narration, update affected footage/screens after integration, check reviewer access to delivery links, and keep the same tested build for both journeys. Ensure the deck distinguishes connected, simulated, and deferred behavior, including offline extraction where applicable and the HAPI stub.

Update the frontend roadmap, F-contracts evidence, and affected open-question entries: Q10 is no longer “no review endpoint”; verified context is available; Q12 needs the recorded contract decision; C3 is a cohort/coverage decision. Coordinate corrections to README/DOCKER statements that the entire frontend still runs on mocks. Preserve dated historical evidence rather than silently rewriting old test results.

**Done when:** the handoff gives reproducible startup/test instructions, current evidence, accessible assets, and an accurate remaining-dependency list. Submission deadline/portal verification remains Alfred's task.

### M19 — Resolve remaining display-contract duplication · P2 · conditional

Q9 proposes server-returned `available_actions`; it has not become a frontend blocker. Keep current action-catalog checks against `/meta/actions`, and treat local predicates only as display hints. If Ismail adds available actions and blocked reasons, consume them and remove duplicated predicates. Q11 still needs an authoritative case-to-document association/listing: Mark should replace the fixture fallback when that contract is supplied and preserve patient/case checks in the meantime.

**Done when:** actions reflect the published contract and source selection uses authoritative associations where available. Do not guess document links or move authorization into the browser to compensate for a missing API field.

Evidence for M15–M19: [frontend roadmap](../01-milestones/frontend-roadmap.md), [open questions](../02-decisions/OPEN-QUESTIONS.md), [case detail/inspector](../../web/app/cases/[id]/case-detail-view.tsx), [source resolver](../../web/lib/source-documents.ts), [F-contracts evidence and bridge update](../03-evidence/F-contracts/checks.md), [delivery assets](../03-evidence/E-delivery/README.md).

## Ownership boundary and suggested order

Mark owns frontend wiring, truthful state/error presentation, frontend integration/browser evidence, accessibility, and demonstration assets. He does **not** own implementing the PDP/AuthZEN codec, backend authorization/audit durability, clinical rules, durable canonical evaluation storage, reviewed-fact ingestion, HAPI commits, or model hosting.

The external requests are concrete: Alfred and Ismail confirm M00 and review-to-rule semantics; Ismail supplies document associations, supported authority/provenance fields, and any missing aggregate/resource reads; Alfred and Ismail agree the verified-record/assembled-context boundary; the team decides cohort, language, and hosting scope.

Work order: close M00 alongside the P0 review/authority/state fixes; finish evaluation, context, and metrics integration; update the integration/browser evidence and startup path; then finish the retained polish and delivery scope. Backend dependencies should remain visible without blocking independent Mark-owned fixes.
