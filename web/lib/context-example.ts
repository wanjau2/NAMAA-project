/**
 * Alfred's canonical AssembledContext example, copied verbatim from
 * ai/examples/assembled-context.json.
 *
 * It exists so the context panel can be reviewed against the real contract
 * before any backend serves one. It is NOT backend data and is never shown
 * without saying so — the panel's default state is "no verified-context
 * service is available", which is the truth today.
 *
 * Delete this once M2 lands and the panel reads from the API.
 */

import type { AssembledContext } from "@/lib/contracts";

export const ALFRED_CONTEXT_EXAMPLE: AssembledContext = {
  query: "What source-verified observation is available?",
  workspace_id: "offline-demo",
  patient_reference: "Patient/demo-patient",
  generation_id: "generation-demo-1",
  permission_revision: "permissions-v1",
  state: "assembled",
  completeness: "partial",
  items: [
    {
      item_id: "ctx-1a363bab7c20f35f74434c6e",
      source: {
        reference: "Observation/demo-observation",
        version: "opaque-v1",
      },
      patient_reference: "Patient/demo-patient",
      tier: "structured",
      source_last_updated: "2026-11-18T08:30:00Z",
      verified_at: "2026-11-18T09:00:00Z",
      permission_revision: "permissions-v1",
      generation_id: "generation-demo-1",
      authorized: true,
      source_verified: true,
      reviewed: false,
      text: "Fictional source-verified record summary supplied by the backend.",
      offset_start: null,
      offset_end: null,
      offset_unit: "unicode_code_points",
    },
  ],
  character_count: 65,
  exhaustive: false,
  absence_claims_allowed: false,
  notice:
    "Context is limited to current authorized sources in the backend checked scope.",
};

/** An empty envelope, to check that empty renders as unknown. */
export const EMPTY_CONTEXT_EXAMPLE: AssembledContext = {
  ...ALFRED_CONTEXT_EXAMPLE,
  state: "empty_unknown",
  completeness: "unknown",
  items: [],
  character_count: 0,
};
