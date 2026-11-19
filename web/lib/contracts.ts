/**
 * TypeScript mirrors of Alfred's contracts (ai/src/namaa_ai/contracts.py).
 *
 * These are the shapes the frontend is asked to render: nested fact fields,
 * exact excerpts with code-point offsets, source versions, validation issues
 * and model identity — plus the assembled-context envelope.
 *
 * The API does not speak these shapes yet. `fromApiProposal` adapts what it
 * does send and REPORTS what is absent, so a field the API cannot supply shows
 * as "not provided" rather than being invented or quietly defaulted.
 */

import type { ApiProposal } from "@/lib/api-types";

/* ------------------------------------------------------------- extraction */

export type Assertion = "present" | "absent" | "uncertain" | "historical";
export type FactSubject = "patient" | "family_member";

export type Relationship =
  | "mother"
  | "father"
  | "sister"
  | "brother"
  | "sibling"
  | "grandmother"
  | "grandfather";

export type ProposedResourceType =
  | "Observation"
  | "Condition"
  | "FamilyMemberHistory";

export type ProposedFact = {
  concept: string;
  /** The original statement, verbatim. Never a model paraphrase. */
  value_text: string;
  subject: FactSubject;
  assertion: Assertion;
  /** Explicit full ISO date only; null when the note gives none. */
  effective_date: string | null;
  excerpt: string;
  proposed_resource_type: ProposedResourceType;
  relationship: Relationship | null;
};

export type IssueSeverity = "block" | "review";

export type ValidationIssue = {
  code: string;
  severity: IssueSeverity;
  message: string;
};

export type ModelIdentity = {
  model_id: string;
  model_revision: string;
  prompt_version: string;
  /** True when the output came from a fixture rather than live inference. */
  simulated: boolean;
};

export type ContractProposal = {
  id: string;
  /** Integer concurrency version. Not a FHIR version; do not sort FHIR strings. */
  version: number | null;
  state: "proposed" | "accepted" | "corrected" | "rejected";
  source_document_id: string;
  /** Opaque string. Never parsed or compared as a number. */
  source_document_version: string;
  /** SHA-256 of the source text, binding the proposal to an exact note. */
  source_sha256: string | null;
  fact: ProposedFact;
  offset_start: number | null;
  offset_end: number | null;
  offset_unit: "unicode_code_points";
  issues: ValidationIssue[];
  model: ModelIdentity | null;
};

/** Contract fields the current API cannot supply. */
export type MissingContractField =
  | "source_sha256"
  | "issues"
  | "relationship"
  | "version";

export type AdaptedProposal = {
  proposal: ContractProposal;
  /** Named so the UI can say what is absent instead of implying a value. */
  missing: MissingContractField[];
};

/**
 * Adapt the API's flat proposal to Alfred's nested contract.
 *
 * Absent fields are null and listed in `missing`. In particular an EMPTY
 * `issues` array here means "this API does not report issues", which is not
 * the same as "the extractor found none" — the UI must not render it as a
 * clean bill of health.
 */
export function fromApiProposal(
  api: ApiProposal,
  model: { revision: string | null; inferenceMode: string | null } | null,
): AdaptedProposal {
  const missing: MissingContractField[] = [
    "source_sha256",
    "issues",
    "relationship",
    "version",
  ];

  return {
    missing,
    proposal: {
      id: api.id,
      version: null,
      state: api.review_state,
      source_document_id: api.source_document_id,
      source_document_version: String(api.source_document_version),
      source_sha256: null,
      fact: {
        concept: api.concept,
        value_text: api.value_text,
        subject: api.subject,
        assertion: api.assertion,
        effective_date: api.effective_date,
        excerpt: api.excerpt,
        // The API's value is already one of the three contract types.
        proposed_resource_type: api.proposed_resource_type as ProposedResourceType,
        relationship: null,
      },
      offset_start: api.offset_start,
      offset_end: api.offset_end,
      offset_unit: "unicode_code_points",
      issues: [],
      model: model
        ? {
            model_id: "google/medgemma-1.5-4b-it",
            model_revision: model.revision ?? "unknown",
            prompt_version: "unknown",
            simulated: model.inferenceMode !== "live",
          }
        : null,
    },
  };
}

/** A blocking issue prevents acceptance outright. */
export function hasBlockingIssue(issues: ValidationIssue[]): boolean {
  return issues.some((issue) => issue.severity === "block");
}

/* ---------------------------------------------------------------- context */

export type ResourceVersion = {
  reference: string;
  /** Opaque. Never parsed or sorted. */
  version: string;
};

export type ContextTier = "structured" | "longitudinal" | "relational";

export type Completeness = "complete_in_checked_scope" | "partial" | "unknown";

export type ContextItem = {
  item_id: string;
  source: ResourceVersion;
  patient_reference: string;
  tier: ContextTier;
  source_last_updated: string;
  verified_at: string;
  permission_revision: string;
  generation_id: string;
  authorized: boolean;
  source_verified: boolean;
  reviewed: boolean;
  text: string;
  offset_start: number | null;
  offset_end: number | null;
  offset_unit: "unicode_code_points";
};

export type AssembledContext = {
  query: string;
  workspace_id: string;
  patient_reference: string;
  generation_id: string;
  permission_revision: string;
  state: "assembled" | "empty_unknown";
  completeness: Completeness;
  items: ContextItem[];
  character_count: number;
  /** Always false: the context is never a complete view of the record. */
  exhaustive: false;
  /** Always false: absence of an item is never evidence of absence. */
  absence_claims_allowed: false;
  notice: string;
};

export const TIER_LABELS: Record<ContextTier, string> = {
  structured: "Structured",
  longitudinal: "Longitudinal",
  relational: "Relational",
};

export const COMPLETENESS_DISPLAY: Record<
  Completeness,
  { label: string; meaning: string }
> = {
  complete_in_checked_scope: {
    label: "Complete in checked scope",
    meaning:
      "Everything inside the scope the backend checked was returned. Records outside that scope were not looked at.",
  },
  partial: {
    label: "Partial",
    meaning:
      "Some authorized records were not returned — a limit was reached or a source could not be verified.",
  },
  unknown: {
    label: "Unknown",
    meaning:
      "The extent of what was checked is not known. Nothing here supports a statement about what is absent.",
  },
};

/* ----------------------------------------------------------------- review */

export type ReviewAction = "accept" | "correct" | "reject";

/** Mirrors ReviewCommand in ai/src/namaa_ai/contracts.py. */
export type ReviewCommand = {
  request_id: string;
  proposal_id: string;
  /**
   * Integer concurrency token, >= 1. The client REFUSES to invent one: a
   * fabricated version would let a review address a proposal it never saw.
   */
  expected_proposal_version: number;
  action: ReviewAction;
  reviewer_reference: string;
  reason: string;
  /** Required for `correct`, forbidden otherwise. */
  correction: ProposedFact | null;
  acknowledged_issues: string[];
};

export type ReviewDecision = {
  command: ReviewCommand;
  resulting_proposal_version: number;
  state: "accepted" | "corrected" | "rejected";
  fact: unknown | null;
};

export type BuildCommandResult =
  | { ok: true; command: ReviewCommand }
  | { ok: false; reason: string };

export function buildReviewCommand(input: {
  requestId: string;
  proposal: ContractProposal;
  action: ReviewAction;
  reviewerReference: string;
  reason: string;
  correction: ProposedFact | null;
  acknowledgedIssues: string[];
}): BuildCommandResult {
  if (input.proposal.version === null) {
    return {
      ok: false,
      reason:
        "This proposal carries no version. A review command requires an integer proposal version for concurrency, and the client will not invent one — a fabricated version would let a review address a proposal the reviewer never saw.",
    };
  }
  if ((input.action === "correct") !== (input.correction !== null)) {
    return {
      ok: false,
      reason: "Only a correction carries a complete replacement fact.",
    };
  }
  if (!input.reason.trim()) {
    return { ok: false, reason: "A reason is required so the change is auditable." };
  }

  return {
    ok: true,
    command: {
      request_id: input.requestId,
      proposal_id: input.proposal.id,
      expected_proposal_version: input.proposal.version,
      action: input.action,
      reviewer_reference: input.reviewerReference,
      reason: input.reason.trim(),
      correction: input.correction,
      acknowledged_issues: input.acknowledgedIssues,
    },
  };
}

/* ------------------------------------------------- forward-compatible read */

type UnknownRecord = Record<string, unknown>;

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asNullableNumber(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

/**
 * Read a proposal in EITHER shape.
 *
 * Alfred's contract nests the extracted fields under `fact`; the API still
 * sends them flat. Accepting both means the interface keeps working on the day
 * the backend switches, with no coordinated deploy — and the adapter reports
 * which shape it saw so the difference is visible rather than silent.
 */
export function normalizeProposal(raw: unknown): AdaptedProposal & {
  shape: "nested" | "flat";
} {
  const record = (raw ?? {}) as UnknownRecord;
  const nested = record.fact as UnknownRecord | undefined;

  if (nested && typeof nested === "object") {
    const issues = Array.isArray(record.issues)
      ? (record.issues as ValidationIssue[])
      : [];
    const model = (record.model ?? null) as ModelIdentity | null;
    const missing: MissingContractField[] = [];
    if (record.source_sha256 == null) missing.push("source_sha256");
    if (!Array.isArray(record.issues)) missing.push("issues");
    if (record.version == null) missing.push("version");

    return {
      shape: "nested",
      missing,
      proposal: {
        id: asString(record.id),
        version: asNullableNumber(record.version),
        state: (asString(record.state, "proposed") ||
          "proposed") as ContractProposal["state"],
        source_document_id: asString(record.source_document_id),
        source_document_version: asString(record.source_document_version),
        source_sha256:
          typeof record.source_sha256 === "string" ? record.source_sha256 : null,
        fact: {
          concept: asString(nested.concept),
          value_text: asString(nested.value_text),
          subject: (nested.subject as FactSubject) ?? "patient",
          assertion: (nested.assertion as Assertion) ?? "present",
          effective_date:
            typeof nested.effective_date === "string"
              ? nested.effective_date
              : null,
          excerpt: asString(nested.excerpt),
          proposed_resource_type:
            (nested.proposed_resource_type as ProposedResourceType) ??
            "Observation",
          relationship:
            (nested.relationship as Relationship | null) ?? null,
        },
        offset_start: asNullableNumber(record.offset_start),
        offset_end: asNullableNumber(record.offset_end),
        offset_unit: "unicode_code_points",
        issues,
        model,
      },
    };
  }

  // Flat shape: reuse the existing adapter, which names what is absent.
  const flat = fromApiProposal(raw as ApiProposal, null);
  return { ...flat, shape: "flat" };
}
