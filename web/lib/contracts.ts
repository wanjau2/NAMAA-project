/**
 * TypeScript mirrors of Alfred's contracts (ai/src/namaa_ai/contracts.py).
 *
 * These are the shapes the frontend is asked to render: nested fact fields,
 * exact excerpts with code-point offsets, source versions, validation issues
 * and model identity — plus the assembled-context envelope.
 *
 * Prefer `normalizeProposal`: the API now speaks Alfred's nested shape
 * (Ismail I4). `fromApiProposal` remains for flat payloads and REPORTS absent
 * fields so nothing is invented or quietly defaulted.
 */

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

export const ASSERTIONS = [
  "present",
  "absent",
  "uncertain",
  "historical",
] as const satisfies readonly Assertion[];

export const FACT_SUBJECTS = [
  "patient",
  "family_member",
] as const satisfies readonly FactSubject[];

export const RELATIONSHIPS = [
  "mother",
  "father",
  "sister",
  "brother",
  "sibling",
  "grandmother",
  "grandfather",
] as const satisfies readonly Relationship[];

export const PROPOSED_RESOURCE_TYPES = [
  "Observation",
  "Condition",
  "FamilyMemberHistory",
] as const satisfies readonly ProposedResourceType[];

export type ProposedFact = {
  concept: string;
  /** The original statement, verbatim. Never a model paraphrase. */
  value_text: string;
  subject: FactSubject | null;
  assertion: Assertion | null;
  /** Explicit full ISO date only; null when the note gives none. */
  effective_date: string | null;
  excerpt: string;
  proposed_resource_type: ProposedResourceType | null;
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
  reviewer_reference: string | null;
  review_reason: string | null;
};

/** Contract fields the current API cannot supply. */
export type MissingContractField =
  | "source_sha256"
  | "issues"
  | "relationship"
  | "version"
  | "model";

/**
 * Required fields that arrived missing or with an illegal value.
 * The UI must not fill these in; review is blocked until a valid payload arrives.
 */
export type MalformedContractField =
  | "id"
  | "fact.concept"
  | "fact.value_text"
  | "fact.excerpt"
  | "fact.subject"
  | "fact.assertion"
  | "fact.proposed_resource_type"
  | "fact.relationship"
  | "offset_unit";

export type AdaptedProposal = {
  proposal: ContractProposal;
  /** Named so the UI can say what is absent instead of implying a value. */
  missing: MissingContractField[];
  malformed: MalformedContractField[];
};

/** Flat extraction shape kept only so older payloads still name their absences. */
export type FlatProposal = {
  id: string;
  concept: string;
  value_text: string;
  subject: FactSubject;
  assertion: Assertion;
  effective_date: string | null;
  proposed_resource_type: string;
  source_document_id: string;
  source_document_version: number | string;
  excerpt: string;
  offset_start: number | null;
  offset_end: number | null;
  offset_unit?: "unicode_code_points";
  review_state: ContractProposal["state"];
};

/**
 * Adapt a flat proposal to Alfred's nested contract.
 *
 * Absent fields are null and listed in `missing`. An EMPTY `issues` array
 * here means "this API does not report issues", which is not the same as
 * "the extractor found none". Job-level model hints are not turned into a
 * fabricated model identity.
 */
export function fromApiProposal(
  api: FlatProposal,
  modelHint: { revision: string | null; inferenceMode: string | null } | null,
): AdaptedProposal {
  void modelHint;
  const missing: MissingContractField[] = [
    "source_sha256",
    "issues",
    "relationship",
    "version",
    "model",
  ];
  const malformed: MalformedContractField[] = [];
  const subject = asEnum(api.subject, FACT_SUBJECTS);
  const assertion = asEnum(api.assertion, ASSERTIONS);
  const resourceType = asEnum(
    api.proposed_resource_type,
    PROPOSED_RESOURCE_TYPES,
  );
  if (!api.id) malformed.push("id");
  if (!api.concept) malformed.push("fact.concept");
  if (!api.value_text) malformed.push("fact.value_text");
  if (!api.excerpt) malformed.push("fact.excerpt");
  if (subject === null) malformed.push("fact.subject");
  if (assertion === null) malformed.push("fact.assertion");
  if (resourceType === null) malformed.push("fact.proposed_resource_type");

  return {
    missing,
    malformed,
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
        subject,
        assertion,
        effective_date: api.effective_date,
        excerpt: api.excerpt,
        proposed_resource_type: resourceType,
        relationship: null,
      },
      offset_start: api.offset_start,
      offset_end: api.offset_end,
      offset_unit: "unicode_code_points",
      issues: [],
      model: null,
      reviewer_reference: null,
      review_reason: null,
    },
  };
}

/** A blocking issue prevents acceptance outright. */
export function hasBlockingIssue(issues: ValidationIssue[]): boolean {
  return issues.some((issue) => issue.severity === "block");
}

export function reviewSeverityIssues(
  issues: ValidationIssue[],
): ValidationIssue[] {
  return issues.filter((issue) => issue.severity === "review");
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
  /**
   * Optional. The server binds the synthetic reviewer; the browser must not
   * present a typed identity as authorization.
   */
  reviewer_reference?: string;
  reason: string;
  /** Required for `correct`, forbidden otherwise. */
  correction: ProposedFact | null;
  acknowledged_issues: string[];
};

export type ReviewedFactPayload = {
  fact?: ProposedFact;
};

export type ReviewDecision = {
  command: ReviewCommand;
  resulting_proposal_version: number;
  state: "accepted" | "corrected" | "rejected";
  fact: ReviewedFactPayload | null;
  fhir_gateway?: string | null;
  outbox_id?: string | null;
  notice?: string | null;
};

export type BuildCommandResult =
  | { ok: true; command: ReviewCommand }
  | { ok: false; reason: string };

export function buildReviewCommand(input: {
  requestId: string;
  proposal: ContractProposal;
  action: ReviewAction;
  reviewerReference?: string;
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
  if (!factIsComplete(input.proposal.fact)) {
    return {
      ok: false,
      reason:
        "Required fact fields are missing or illegal on this proposal, so a review command cannot be built.",
    };
  }
  if (input.correction && !factIsComplete(input.correction)) {
    return {
      ok: false,
      reason:
        "A correction must be a complete replacement fact with valid subject, assertion and resource type.",
    };
  }

  const command: ReviewCommand = {
    request_id: input.requestId,
    proposal_id: input.proposal.id,
    expected_proposal_version: input.proposal.version,
    action: input.action,
    reason: input.reason.trim(),
    correction: input.correction,
    acknowledged_issues: input.acknowledgedIssues,
  };
  if (input.reviewerReference) {
    command.reviewer_reference = input.reviewerReference;
  }
  return { ok: true, command };
}

/**
 * Build a complete replacement fact from the normalized original plus the
 * fields the reviewer is allowed to edit. Resource semantics stay valid:
 * family members map only to FamilyMemberHistory; patient findings stay
 * Observation or Condition.
 */
export function buildCorrection(
  original: ProposedFact,
  edits: {
    value_text: string;
    subject: FactSubject;
    assertion: Assertion;
    effective_date: string;
    relationship: Relationship | null;
  },
): ProposedFact | null {
  if (!factIsComplete(original) && !original.excerpt) return null;
  const family = edits.subject === "family_member";
  const resourceType: ProposedResourceType = family
    ? "FamilyMemberHistory"
    : original.proposed_resource_type === "Condition" ||
        original.concept === "documented_condition"
      ? "Condition"
      : "Observation";
  const value_text = edits.value_text.trim();
  if (!value_text) return null;
  return {
    concept: original.concept,
    value_text,
    subject: edits.subject,
    assertion: edits.assertion,
    effective_date: edits.effective_date.trim() || null,
    excerpt: original.excerpt,
    proposed_resource_type: resourceType,
    relationship: family ? edits.relationship : null,
  };
}

export function factIsComplete(
  fact: ProposedFact,
): fact is ProposedFact & {
  subject: FactSubject;
  assertion: Assertion;
  proposed_resource_type: ProposedResourceType;
} {
  return (
    Boolean(fact.concept) &&
    Boolean(fact.value_text) &&
    Boolean(fact.excerpt) &&
    fact.subject !== null &&
    fact.assertion !== null &&
    fact.proposed_resource_type !== null
  );
}

export function commandFingerprint(command: {
  action: ReviewAction;
  reason: string;
  correction: ProposedFact | null;
  acknowledgedIssues: string[];
}): string {
  return JSON.stringify({
    action: command.action,
    reason: command.reason.trim(),
    correction: command.correction,
    acknowledgedIssues: [...command.acknowledgedIssues].sort(),
  });
}

export function mergeReviewedProposal(
  current: ContractProposal,
  decision: ReviewDecision,
  readback: unknown | null,
): ContractProposal {
  const fromDecisionFact =
    decision.fact &&
    typeof decision.fact === "object" &&
    decision.fact.fact &&
    typeof decision.fact.fact === "object"
      ? decision.fact.fact
      : current.fact;
  const reviewer =
    decision.command.reviewer_reference ?? current.reviewer_reference;
  const merged: ContractProposal = {
    ...current,
    version: decision.resulting_proposal_version,
    state: decision.state,
    fact: fromDecisionFact,
    reviewer_reference: reviewer ?? null,
    review_reason: decision.command.reason ?? current.review_reason,
  };
  if (readback == null) return merged;
  const adapted = normalizeProposal(readback);
  return {
    ...adapted.proposal,
    state:
      adapted.proposal.state === "proposed"
        ? decision.state
        : adapted.proposal.state,
    reviewer_reference:
      adapted.proposal.reviewer_reference ?? merged.reviewer_reference,
    review_reason: adapted.proposal.review_reason ?? merged.review_reason,
  };
}

export function decisionMatchesCommand(
  decision: ReviewDecision,
  command: ReviewCommand,
): boolean {
  if (decision.command.request_id !== command.request_id) return false;
  if (decision.command.proposal_id !== command.proposal_id) return false;
  if (decision.command.action !== command.action) return false;
  if (
    typeof decision.resulting_proposal_version !== "number" ||
    decision.resulting_proposal_version < command.expected_proposal_version
  ) {
    return false;
  }
  const expectedState =
    command.action === "accept"
      ? "accepted"
      : command.action === "correct"
        ? "corrected"
        : "rejected";
  return decision.state === expectedState;
}

/* ------------------------------------------------- forward-compatible read */

type UnknownRecord = Record<string, unknown>;

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asNullableNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asEnum<T extends string>(
  value: unknown,
  allowed: readonly T[],
): T | null {
  return typeof value === "string" && (allowed as readonly string[]).includes(value)
    ? (value as T)
    : null;
}

function asModelIdentity(value: unknown): ModelIdentity | null {
  if (!value || typeof value !== "object") return null;
  const record = value as UnknownRecord;
  const model_id = asString(record.model_id);
  const model_revision = asString(record.model_revision);
  const prompt_version = asString(record.prompt_version);
  if (!model_id || !model_revision || !prompt_version) return null;
  return {
    model_id,
    model_revision,
    prompt_version,
    simulated: record.simulated === true,
  };
}

function asIssues(value: unknown): ValidationIssue[] | null {
  if (!Array.isArray(value)) return null;
  const issues: ValidationIssue[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const record = item as UnknownRecord;
    const code = asString(record.code);
    const severity = asEnum(record.severity, ["block", "review"] as const);
    const message = asString(record.message);
    if (!code || !severity || !message) continue;
    issues.push({ code, severity, message });
  }
  return issues;
}

function asReviewState(
  value: unknown,
): ContractProposal["state"] | null {
  return asEnum(value, ["proposed", "accepted", "corrected", "rejected"] as const);
}

/**
 * Read a proposal in EITHER shape.
 *
 * Alfred's contract nests the extracted fields under `fact`; older payloads
 * send them flat. Required fields that are missing or illegal are listed in
 * `malformed` rather than defaulted to a patient/present Observation or a
 * fabricated model identity.
 */
export function normalizeProposal(raw: unknown): AdaptedProposal & {
  shape: "nested" | "flat";
} {
  const record = (raw ?? {}) as UnknownRecord;
  const nested = record.fact as UnknownRecord | undefined;

  if (nested && typeof nested === "object") {
    const issues = asIssues(record.issues);
    const model = asModelIdentity(record.model);
    const missing: MissingContractField[] = [];
    const malformed: MalformedContractField[] = [];
    if (typeof record.source_sha256 !== "string") missing.push("source_sha256");
    if (!Array.isArray(record.issues)) missing.push("issues");
    if (record.version == null) missing.push("version");
    if (model === null) missing.push("model");

    const subject = asEnum(nested.subject, FACT_SUBJECTS);
    const assertion = asEnum(nested.assertion, ASSERTIONS);
    const resourceType = asEnum(
      nested.proposed_resource_type,
      PROPOSED_RESOURCE_TYPES,
    );
    const relationship = asEnum(nested.relationship, RELATIONSHIPS);
    const id = asString(record.id);
    const concept = asString(nested.concept);
    const value_text = asString(nested.value_text);
    const excerpt = asString(nested.excerpt);

    if (!id) malformed.push("id");
    if (!concept) malformed.push("fact.concept");
    if (!value_text) malformed.push("fact.value_text");
    if (!excerpt) malformed.push("fact.excerpt");
    if (subject === null) malformed.push("fact.subject");
    if (assertion === null) malformed.push("fact.assertion");
    if (resourceType === null) malformed.push("fact.proposed_resource_type");
    if (
      nested.relationship != null &&
      nested.relationship !== "" &&
      relationship === null
    ) {
      malformed.push("fact.relationship");
    }
    if (
      record.offset_unit != null &&
      record.offset_unit !== "unicode_code_points"
    ) {
      malformed.push("offset_unit");
    }

    if (subject === "family_member" && relationship === null) {
      missing.push("relationship");
    }

    const reviewState =
      asReviewState(record.review_state) ??
      asReviewState(record.state) ??
      "proposed";

    return {
      shape: "nested",
      missing,
      malformed,
      proposal: {
        id,
        version: asNullableNumber(record.version),
        state: reviewState,
        source_document_id: asString(record.source_document_id),
        source_document_version: asString(record.source_document_version),
        source_sha256:
          typeof record.source_sha256 === "string" ? record.source_sha256 : null,
        fact: {
          concept,
          value_text,
          subject,
          assertion,
          effective_date:
            typeof nested.effective_date === "string"
              ? nested.effective_date
              : null,
          excerpt,
          proposed_resource_type: resourceType,
          relationship,
        },
        offset_start: asNullableNumber(record.offset_start),
        offset_end: asNullableNumber(record.offset_end),
        offset_unit: "unicode_code_points",
        issues: issues ?? [],
        model,
        reviewer_reference:
          typeof record.reviewer_reference === "string"
            ? record.reviewer_reference
            : null,
        review_reason:
          typeof record.review_reason === "string" ? record.review_reason : null,
      },
    };
  }

  const flat = fromApiProposal(raw as FlatProposal, null);
  return { ...flat, shape: "flat" };
}
