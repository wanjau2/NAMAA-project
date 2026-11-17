/**
 * Case action registry and LOCAL transition validation.
 *
 * ############################################################################
 * # THIS MODULE IS A STAND-IN FOR ISMAIL'S SERVER AND MUST BE DELETED AT F4. #
 * ############################################################################
 *
 * The work plan's dependency-slip rule permits the frontend to continue on
 * contract-matching mocks provided the result is labelled a simulation. That is
 * exactly what this is: it decides which actions to OFFER and applies them to
 * local state so both journeys can be demonstrated before the API exists.
 *
 * It is NOT enforcement. A reviewer with devtools can reach any state. The
 * server remains the only authority on whether a transition is valid, and every
 * rule here is a mirror of a rule that must also exist server-side.
 *
 * Kept deliberately in ONE file so that replacing it is a single deletion.
 */

import type { Role } from "@/lib/demo-session";
import type { CaseRow, Disposition, Stage } from "@/lib/mock-data";

/** Case state carries a little more than the list row. */
export type CaseState = CaseRow & {
  contact_preference?: {
    channel: string;
    language: string;
    preferred_time: string;
  };
  recall_date?: string | null;
  /** Evidence reference recorded at completion. Required to close as completed. */
  completion_evidence?: {
    evidence_type: string;
    evidence_reference: string;
  } | null;
  referral_outcome?: "pending" | "accepted" | "rejected" | null;
};

export type ActionId =
  | "record_contact_preference"
  | "approve_pathway"
  | "send_invitation"
  | "record_decline"
  | "record_unreachable"
  | "book_appointment"
  | "record_attendance"
  | "record_referral_outcome"
  | "reassign_owner"
  | "defer_with_recall"
  | "close_as_completed"
  | "close_other"
  | "reopen";

export type FieldSpec = {
  name: string;
  label: string;
  kind: "text" | "textarea" | "select" | "date" | "number" | "checkbox";
  required?: boolean;
  options?: { value: string; label: string }[];
  help?: string;
  placeholder?: string;
};

export type ActionSpec = {
  id: ActionId;
  label: string;
  /** The simulated role permitted to invoke it. */
  role: Role;
  tone: "primary" | "secondary" | "destructive";
  /** True when the action represents something only pretended, never performed. */
  simulated?: boolean;
  /** Safety caveat rendered inside the form. */
  note?: string;
  fields: FieldSpec[];
  /** Whether the current case is in a state where this action makes sense. */
  applies: (c: CaseState) => boolean;
  /**
   * Why the action cannot be taken right now, despite applying to this stage.
   * Null means it can proceed.
   */
  precondition?: (c: CaseState) => string | null;
};

const OPEN = (c: CaseState) => c.stage !== "closed";

export const ACTIONS: ActionSpec[] = [
  {
    id: "record_contact_preference",
    label: "Record contact preference",
    role: "coordinator",
    tone: "secondary",
    note: "Preference only. Recording it does not contact anyone.",
    applies: OPEN,
    fields: [
      {
        name: "channel",
        label: "Preferred channel",
        kind: "select",
        required: true,
        options: [
          { value: "sms", label: "SMS" },
          { value: "phone", label: "Phone (assisted)" },
          { value: "email", label: "Email" },
        ],
        help: "Phone-assisted support is always offered as an option.",
      },
      {
        name: "language",
        label: "Preferred language",
        kind: "select",
        required: true,
        options: [
          { value: "en", label: "English" },
          { value: "ar", label: "Arabic (unreviewed demo translation)" },
        ],
      },
      {
        name: "preferred_time",
        label: "Preferred time",
        kind: "select",
        required: true,
        options: [
          { value: "morning", label: "Morning" },
          { value: "afternoon", label: "Afternoon" },
          { value: "evening", label: "Evening" },
        ],
      },
    ],
  },
  {
    id: "approve_pathway",
    label: "Approve pathway",
    role: "clinical_reviewer",
    tone: "primary",
    note:
      "Confirms eligibility and activates the care plan. Prioritization is not a diagnosis and does not by itself order a screening test.",
    applies: (c) => c.stage === "identified",
    precondition: (c) =>
      c.flag_status === "needs_review"
        ? "Information is missing or unverified. Resolve it in source review and let the rule re-evaluate before approving — unknown is not the same as up to date."
        : null,
    fields: [
      {
        name: "attestation",
        label:
          "I have reviewed the contributing records and confirm eligibility for this demonstration pathway.",
        kind: "checkbox",
        required: true,
      },
      { name: "reason", label: "Note (optional)", kind: "textarea" },
    ],
  },
  {
    id: "send_invitation",
    label: "Send invitation",
    role: "coordinator",
    tone: "primary",
    simulated: true,
    note:
      "Simulated. No message is sent to anyone, and no real contact details exist in this session.",
    applies: (c) => c.stage === "reviewed",
    precondition: (c) =>
      !c.contact_preference
        ? "Record a contact preference first, so the invitation uses a channel the person actually chose."
        : null,
    fields: [
      {
        name: "template",
        label: "Message template",
        kind: "select",
        required: true,
        options: [
          { value: "wcv_invite_v1", label: "Well-child visit invitation (reviewed)" },
          { value: "screening_invite_v1", label: "Screening invitation (reviewed)" },
        ],
        help:
          "Reviewed templates populated from verified facts only. Free-form generated outreach is deferred.",
      },
    ],
  },
  {
    id: "record_decline",
    label: "Record decline",
    role: "coordinator",
    tone: "secondary",
    note:
      "A decline stays in the eligible denominator and is never relabelled as completed care.",
    applies: (c) => ["invited", "booked"].includes(c.stage),
    fields: [
      {
        name: "reason",
        label: "Reason given",
        kind: "textarea",
        required: true,
        placeholder: "As stated by the person or caregiver",
      },
    ],
  },
  {
    id: "record_unreachable",
    label: "Record unreachable",
    role: "coordinator",
    tone: "secondary",
    note:
      "Failed contact is not a decline and not a completion. The case stays owned.",
    applies: (c) => ["reviewed", "invited"].includes(c.stage),
    fields: [
      {
        name: "attempts",
        label: "Contact attempts made",
        kind: "number",
        required: true,
      },
      { name: "reason", label: "Detail", kind: "textarea", required: true },
    ],
  },
  {
    id: "book_appointment",
    label: "Book appointment",
    role: "coordinator",
    tone: "primary",
    simulated: true,
    note:
      "Simulated booking. A booking is not proof of attendance and never completes preventive care.",
    applies: (c) => c.stage === "invited" && c.disposition === "active",
    fields: [
      { name: "appointment_time", label: "Appointment date", kind: "date", required: true },
      { name: "location", label: "Location (synthetic)", kind: "text", required: true },
    ],
  },
  {
    id: "record_attendance",
    label: "Record attendance",
    role: "coordinator",
    tone: "primary",
    applies: (c) => c.stage === "booked",
    fields: [
      {
        name: "attended",
        label: "Outcome",
        kind: "select",
        required: true,
        options: [
          { value: "attended", label: "Attended" },
          { value: "did_not_attend", label: "Did not attend" },
        ],
      },
      { name: "reason", label: "Note", kind: "textarea" },
    ],
  },
  {
    id: "record_referral_outcome",
    label: "Record referral outcome",
    role: "coordinator",
    tone: "secondary",
    note:
      "Acceptance, appointment and attendance are distinct events. A rejection does not close the case — it creates reassignment work.",
    applies: (c) => ["attended", "follow_up"].includes(c.stage),
    fields: [
      {
        name: "outcome",
        label: "Outcome",
        kind: "select",
        required: true,
        options: [
          { value: "pending", label: "Pending with receiving service" },
          { value: "accepted", label: "Accepted" },
          { value: "rejected", label: "Rejected" },
        ],
      },
      { name: "reason", label: "Reason / detail", kind: "textarea", required: true },
    ],
  },
  {
    id: "reassign_owner",
    label: "Reassign owner",
    role: "coordinator",
    tone: "secondary",
    note: "Ownership is preserved through escalation — work is never left unowned.",
    applies: OPEN,
    fields: [
      { name: "owner", label: "New owner", kind: "text", required: true },
      { name: "reason", label: "Reason", kind: "textarea", required: true },
    ],
  },
  {
    id: "defer_with_recall",
    label: "Defer with recall date",
    role: "coordinator",
    tone: "secondary",
    note: "Deferred care retains a recall date. It is not a completion.",
    applies: OPEN,
    fields: [
      { name: "recall_date", label: "Recall date", kind: "date", required: true },
      { name: "reason", label: "Reason", kind: "textarea", required: true },
    ],
  },
  {
    id: "close_as_completed",
    label: "Close as completed",
    role: "clinical_reviewer",
    tone: "primary",
    note:
      "The only disposition that increases the completed-care count. Requires evidence and reviewer authorization — a booking or an attendance record alone is not sufficient.",
    applies: (c) => ["attended", "follow_up"].includes(c.stage),
    precondition: (c) =>
      c.stage === "follow_up" && c.referral_outcome === "rejected"
        ? "The referral was rejected and is still open. Reassign it before closing, or close with another reason."
        : null,
    fields: [
      {
        name: "evidence_type",
        label: "Evidence type",
        kind: "select",
        required: true,
        options: [
          { value: "Encounter", label: "Encounter" },
          { value: "Procedure", label: "Procedure" },
          { value: "DiagnosticReport", label: "Reviewed DiagnosticReport" },
        ],
      },
      {
        name: "evidence_reference",
        label: "Evidence reference",
        kind: "text",
        required: true,
        placeholder: "Encounter/enc-synthetic-01",
        help: "The resource that evidences the completed preventive action.",
      },
      {
        name: "attestation",
        label:
          "I authorize closure and confirm the referenced evidence supports completed preventive care.",
        kind: "checkbox",
        required: true,
      },
    ],
  },
  {
    id: "close_other",
    label: "Close for another reason",
    role: "clinical_reviewer",
    tone: "destructive",
    note:
      "An authorized clinical closure that does NOT increase the completed-care count. The reason is retained.",
    applies: OPEN,
    fields: [
      { name: "reason", label: "Clinical reason for closure", kind: "textarea", required: true },
    ],
  },
  {
    id: "reopen",
    label: "Reopen case",
    role: "clinical_reviewer",
    tone: "secondary",
    note: "Reopening requires a recorded reason.",
    applies: (c) => c.stage === "closed",
    fields: [
      { name: "reason", label: "Reason for reopening", kind: "textarea", required: true },
    ],
  },
];

export function getAction(id: ActionId): ActionSpec {
  const spec = ACTIONS.find((action) => action.id === id);
  if (!spec) throw new Error(`Unknown action: ${id}`);
  return spec;
}

/** The mutation envelope the real API expects (work plan § API ownership). */
export type ActionRequest = {
  action: ActionId;
  /** Optimistic concurrency: rejected by the server if stale. */
  expected_revision: number;
  /** Idempotency key: a repeat must not produce a second event. */
  request_id: string;
  data: Record<string, string | boolean>;
};

export type StructuredError = {
  code: string;
  message: string;
  field_errors: Record<string, string>;
  request_id: string;
};

export type ActionOutcome =
  | { ok: true; next: CaseState; event: AppliedEvent }
  | { ok: false; error: StructuredError };

export type AppliedEvent = {
  id: string;
  case_id: string;
  timestamp: string;
  actor_role: Role;
  action: ActionId;
  prior_state: string;
  new_state: string;
  reason?: string;
  evidence_reference?: string;
  request_id: string;
};

function stateLabel(c: CaseState): string {
  return `${c.stage}/${c.disposition}`;
}

/**
 * Local stand-in for POST /cases/{id}/actions.
 * Validates role, stage applicability, preconditions, required fields and
 * revision, then returns the next state and the event it produced.
 */
export function applyAction(
  current: CaseState,
  request: ActionRequest,
  role: Role,
  now: string,
): ActionOutcome {
  const spec = getAction(request.action);

  if (role !== spec.role) {
    return {
      ok: false,
      error: {
        code: "forbidden_role",
        message: `This action requires the ${spec.role.replace("_", " ")} role.`,
        field_errors: {},
        request_id: request.request_id,
      },
    };
  }

  if (request.expected_revision !== current.revision) {
    return {
      ok: false,
      error: {
        code: "stale_revision",
        message: `This case changed since the form was opened (expected revision ${request.expected_revision}, current ${current.revision}). Reload the latest state — your entries are preserved.`,
        field_errors: {},
        request_id: request.request_id,
      },
    };
  }

  if (!spec.applies(current)) {
    return {
      ok: false,
      error: {
        code: "invalid_transition",
        message: `"${spec.label}" is not a valid action from ${stateLabel(current)}.`,
        field_errors: {},
        request_id: request.request_id,
      },
    };
  }

  const blocked = spec.precondition?.(current) ?? null;
  if (blocked) {
    return {
      ok: false,
      error: {
        code: "precondition_failed",
        message: blocked,
        field_errors: {},
        request_id: request.request_id,
      },
    };
  }

  const field_errors: Record<string, string> = {};
  for (const field of spec.fields) {
    if (!field.required) continue;
    const value = request.data[field.name];
    if (field.kind === "checkbox") {
      if (value !== true) field_errors[field.name] = "This confirmation is required.";
    } else if (typeof value !== "string" || !value.trim()) {
      field_errors[field.name] = "This field is required.";
    }
  }
  if (Object.keys(field_errors).length > 0) {
    return {
      ok: false,
      error: {
        code: "validation_failed",
        message: "Some required information is missing.",
        field_errors,
        request_id: request.request_id,
      },
    };
  }

  const prior = stateLabel(current);
  const next: CaseState = { ...current, revision: current.revision + 1 };
  const data = request.data;

  switch (request.action) {
    case "record_contact_preference":
      next.contact_preference = {
        channel: String(data.channel),
        language: String(data.language),
        preferred_time: String(data.preferred_time),
      };
      next.next_action = "Invite using the recorded preference";
      break;

    case "approve_pathway":
      next.stage = "reviewed";
      next.disposition = "active";
      next.next_action = "Record contact preference and invite";
      break;

    case "send_invitation":
      next.stage = "invited";
      next.next_action = "Await response, then book";
      break;

    case "record_decline":
      // Stage deliberately does NOT advance. Disposition carries the outcome.
      next.disposition = "declined";
      next.next_action = "No further contact. Remains in the eligible denominator.";
      next.due_time = null;
      break;

    case "record_unreachable":
      next.disposition = "unreachable";
      next.next_action = "Offer phone-assisted support";
      break;

    case "book_appointment":
      next.stage = "booked";
      next.next_action = "Confirm attendance after the appointment";
      break;

    case "record_attendance":
      if (data.attended === "attended") {
        next.stage = "attended";
        next.next_action = "Record follow-up or close with evidence";
      } else {
        // Did not attend: stay at booked, needs rebooking. Not a completion.
        next.next_action = "Did not attend — re-contact and rebook";
      }
      break;

    case "record_referral_outcome":
      next.stage = "follow_up";
      next.referral_outcome = data.outcome as CaseState["referral_outcome"];
      next.next_action =
        data.outcome === "rejected"
          ? "Referral rejected — reassign owner"
          : data.outcome === "accepted"
            ? "Await referral appointment and attendance"
            : "Chase receiving service";
      next.overdue = data.outcome === "rejected";
      break;

    case "reassign_owner":
      next.owner = String(data.owner);
      next.next_action = "New owner to progress the case";
      next.overdue = false;
      break;

    case "defer_with_recall":
      next.disposition = "deferred";
      next.recall_date = String(data.recall_date);
      next.due_time = `${String(data.recall_date)}T09:00:00Z`;
      next.next_action = `Recall on ${String(data.recall_date)}`;
      break;

    case "close_as_completed":
      next.stage = "closed";
      next.disposition = "completed";
      next.completion_evidence = {
        evidence_type: String(data.evidence_type),
        evidence_reference: String(data.evidence_reference),
      };
      next.next_action = "None — closed with evidence";
      next.due_time = null;
      next.overdue = false;
      break;

    case "close_other":
      next.stage = "closed";
      // Explicitly NOT `completed`: this must not raise the completed-care count.
      next.disposition = "clinically_closed_other";
      next.next_action = "None — closed for another clinical reason";
      next.due_time = null;
      next.overdue = false;
      break;

    case "reopen":
      next.stage = "follow_up";
      next.disposition = "active";
      next.next_action = "Reopened — determine next step";
      break;
  }

  const event: AppliedEvent = {
    id: `evt-${request.request_id.slice(0, 8)}`,
    case_id: current.id,
    timestamp: now,
    actor_role: role,
    action: request.action,
    prior_state: prior,
    new_state: stateLabel(next),
    reason: typeof data.reason === "string" && data.reason.trim()
      ? data.reason.trim()
      : undefined,
    evidence_reference:
      typeof data.evidence_reference === "string" && data.evidence_reference.trim()
        ? data.evidence_reference.trim()
        : undefined,
    request_id: request.request_id,
  };

  return { ok: true, next, event };
}

/** Actions worth offering for this case, in lifecycle order. */
export function availableActions(c: CaseState): ActionSpec[] {
  return ACTIONS.filter((spec) => spec.applies(c));
}

export const STAGE_ORDER: Stage[] = [
  "identified",
  "reviewed",
  "invited",
  "booked",
  "attended",
  "follow_up",
  "closed",
];

/** Dispositions that must never be counted as completed care. */
export const NON_COMPLETION_DISPOSITIONS: Disposition[] = [
  "declined",
  "deferred",
  "unreachable",
  "clinically_closed_other",
];
