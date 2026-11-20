/**
 * Action catalog — PRESENTATION METADATA ONLY.
 *
 * This replaces the former `lib/case-actions.ts`, whose transition engine,
 * validation and state mutation have all been DELETED. The API now owns every
 * one of those: see `api/app/workflow/`.
 *
 * What legitimately remains client-side is how to *draw* a form: labels, field
 * kinds, option lists and the safety caveats that must appear next to each
 * control. The server publishes action ids, roles and required fields at
 * `GET /api/v1/meta/actions`, so drift between this file and the API is
 * detectable (see scripts/verify-api-contract.ts).
 *
 * `displayWhen` is a last-resort display hint when `available_actions` is
 * absent from the payload. Live case detail always publishes the server list;
 * the panel renders that list and never invents authorization from these
 * predicates.
 */

import type { ActionId, CaseOut, Role, Stage } from "@/lib/api-types";

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
  /** Role the API requires. Mirrors docs/00-reference/api-actions-and-roles.md. */
  role: Role;
  tone: "primary" | "secondary" | "destructive";
  /** Something only pretended, never performed. Labelled in the form. */
  simulated?: boolean;
  /** Safety caveat rendered inside the form, every time. */
  note?: string;
  fields: FieldSpec[];
  /** Display hint only — see the file header. */
  displayWhen: (c: CaseOut) => boolean;
};

const OPEN = (c: CaseOut) => c.stage !== "closed";
const atStage =
  (...stages: Stage[]) =>
  (c: CaseOut) =>
    stages.includes(c.stage);

export const ACTION_CATALOG: ActionSpec[] = [
  {
    id: "record_contact_preference",
    label: "Record contact preference",
    role: "coordinator",
    tone: "secondary",
    note: "Preference only. Recording it does not contact anyone.",
    displayWhen: OPEN,
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
    displayWhen: atStage("identified"),
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
    displayWhen: atStage("reviewed"),
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
    displayWhen: atStage("invited", "booked"),
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
    displayWhen: atStage("reviewed", "invited"),
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
    displayWhen: (c) => c.stage === "invited" && c.disposition === "active",
    fields: [
      {
        name: "appointment_time",
        label: "Appointment date",
        kind: "date",
        required: true,
      },
      { name: "location", label: "Location (synthetic)", kind: "text", required: true },
    ],
  },
  {
    id: "record_attendance",
    label: "Record attendance",
    role: "coordinator",
    tone: "primary",
    displayWhen: atStage("booked"),
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
    displayWhen: atStage("attended", "follow_up"),
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
    displayWhen: OPEN,
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
    displayWhen: OPEN,
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
    displayWhen: atStage("attended", "follow_up"),
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
    displayWhen: OPEN,
    fields: [
      {
        name: "reason",
        label: "Clinical reason for closure",
        kind: "textarea",
        required: true,
      },
    ],
  },
  {
    id: "reopen",
    label: "Reopen case",
    role: "clinical_reviewer",
    tone: "secondary",
    note: "Reopening requires a recorded reason.",
    displayWhen: (c) => c.stage === "closed",
    fields: [
      { name: "reason", label: "Reason for reopening", kind: "textarea", required: true },
    ],
  },
];

export function displayableActions(c: CaseOut): ActionSpec[] {
  if (Array.isArray(c.available_actions)) {
    const allowed = new Set(c.available_actions.map((item) => item.id));
    return ACTION_CATALOG.filter((spec) => allowed.has(spec.id));
  }
  return ACTION_CATALOG.filter((spec) => spec.displayWhen(c));
}

export function blockedReason(c: CaseOut, actionId: ActionId): string | null {
  return (
    c.available_actions?.find((item) => item.id === actionId)?.blocked_reason ??
    null
  );
}

export const ROLE_WORDS: Record<Role, string> = {
  coordinator: "Coordinator",
  clinical_reviewer: "Clinical Reviewer",
  population_analyst: "Population Analyst",
};
