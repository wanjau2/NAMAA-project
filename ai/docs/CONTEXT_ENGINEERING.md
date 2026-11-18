# Context engineering: Alfred implementation and handoff

## Implemented in `namaa-ai`

- `ContextItem`, `ContextQuery`, and `AssembledContext` define a versioned,
  source-linked contract. Items retain patient scope, resource reference/version,
  retrieval tier, backend permission revision, generation ID, verification time,
  review marker and optional Unicode code-point offsets.
- `ContextAssembler` is disabled by default. When explicitly enabled, it accepts
  only a current authorized `VerifiedContext` whose workspace, patient,
  permission revision, generation, time window and source checks match the
  caller-supplied trusted context. Unsupported FHIR resource kinds are ignored.
- Each resource remains an independent candidate: structured state, a
  `DocumentReference` longitudinal note, or `FamilyMemberHistory` relational
  context. Resource boundaries are not merged.
- Local retrieval uses deterministic BM25. `DenseRetriever` is a replaceable
  ranking interface; `ReciprocalRankFusion` can combine lexical and injected
  dense rankings. Dense adapters receive only already authorized candidate
  items, and may return only those item IDs. No embedding model, vector database,
  hosted search service or graph client is implemented.
- The assembler enforces an item and character budget by omitting whole items,
  never clipping excerpts. It labels incomplete or empty results; empty means
  unknown in the checked scope, never no gap. Output is explicitly
  non-exhaustive and prohibits absence claims.
- `render_explanation_context` serializes the selected evidence as JSON and
  labels it untrusted source data. It adds no tools, decision authority, or
  automatic explanation call. The extraction adapter and deterministic rules do
  not consume assembled context.

The current API's verified-context endpoint is synthetic and does not yet supply
all the production metadata needed for rich passage retrieval. In particular,
Ismail must populate real source excerpts, correct versions, offsets, and any
backend attestation of reviewed state. A backend must recheck HAPI versions and
permission revisions before disclosure; this package cannot contact HAPI.

## Alfred / Ismail integration contract

Ismail's authenticated service should:

1. Build a trusted context from authenticated identity and current access records.
2. Authorize `context.retrieve` before calling the verified-context provider and
   separately authorize any external embedding/model destination before sending
   text or queries there.
3. Query HAPI through its authorized FHIR interface, not through HAPI database
   tables. Return only source-verified resources with logical references,
   versions, update times, checked-scope completeness, generation ID and current
   permission revision.
4. Treat Relate results as candidate references. Validate each path and its
   supporting resources through current FHIR and access services before adding
   verified source records. Do not send Cypher, unrestricted graph results, or
   unverified relationship claims to the model.
5. Reauthorize and recheck source versions before results and excerpts leave the
   backend. If a version changed, suppress that item and request context refresh.

The current application package can pass the resulting `VerifiedContext` and
trusted scope values to `ContextAssembler(enabled=True).assemble(...)`. The
backend must invoke this at the authorized service boundary; the browser must not
construct or assert the trusted context. For queued jobs, preserve the initiating
principal, workspace, patient scope and purpose, then reauthorize on claim and
before disclosure.

Before adding `pgvector`, Qdrant, or another service, decide tenancy, data
residency, retention, deletion/rebuild behavior, model destination and operational
ownership. Vector filters are candidate constraints, not authorization. The
retrieval adapter must receive a trusted authorized candidate set, and the
backend remains responsible for current access checks.

The current ranker boundary is synchronous and intended for local/index-query
implementations. A hosted embedding or reranking call is another external
processing boundary: Ismail must authorize that destination and Alfred must add a
separate async adapter with timeout, data-minimization and audit behavior before
using it. Do not send text to an embedding provider just because context retrieval
was permitted.

## Mark / user-interface handoff

- Render each assembled item with its resource type/reference, version, tier,
  reviewed marker and excerpt. Show current/partial/unknown state and the
  checked-scope notice.
- Display excerpts only after Ismail's result-disclosure and excerpt-display
  authorization checks. Convert Unicode code-point offsets to JavaScript UTF-16
  indices when highlighting.
- Do not call a vector similarity value confidence, risk or clinical priority.
  Do not infer that a family-history or graph relationship is caregiver
  authority, a patient diagnosis, or an eligibility decision.
- Keep the explanation panel separate from proposal review and rule results.
  Empty/partial context must remain visibly unknown.

## Offline evaluation

`fixtures/context-queries.json` has authored synthetic query/relevant-source
labels separated into development and held-out splits. Run from `ai/`:

```bash
namaa-ai evaluate-context --split development
namaa-ai evaluate-context --split held_out
```

The command reports hit rate at K, recall at K, mean reciprocal rank, and sample
counts for the deterministic local retriever. This fixture set is deliberately
small and authored around its queries. Its scores test the plumbing only; they
are not clinical relevance, model quality, or population generalization results.

## Deliberately not implemented

There is no PDF/OCR ingestion, document parser, embedding generation, vector
database, live hybrid search, Relate query, context synchronization, HAPI
verification, automatic model explanation, policy-guideline retrieval, or
condition-based risk adjustment in this package. Those features require their
own source, authorization, validation and evaluation contracts. The current
synthetic rules ignore retrieved context entirely.
