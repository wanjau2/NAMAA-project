/**
 * Rule outcomes — Alfred's four-value vocabulary.
 *
 * Source: ai/src/namaa_ai/contracts.py. All four must be shown as themselves;
 * none may be collapsed into another, and `no_gap_identified_in_available_data`
 * must always carry its limitation — it is NOT an assurance of health.
 *
 * ## Contract divergence (OPEN-QUESTIONS Q12, Alfred's M0)
 *
 * Three vocabularies are in play right now:
 *
 * | Concept                      | Alfred (ai/)                            | API today        |
 * | ---------------------------- | --------------------------------------- | ---------------- |
 * | A gap was found              | `gap_identified`                        | `gap`            |
 * | None found in available data | `no_gap_identified_in_available_data`   | `no_gap`*        |
 * | Information is missing       | `needs_review`                          | `needs_review`   |
 * | Pathway does not apply       | `not_eligible`                          | **absent**       |
 *
 * *only on evaluations; `CaseRow.flag_status` is `gap | needs_review` alone.
 *
 * This module is the display layer for the agreed vocabulary. `resolveOutcome`
 * maps what the API sends today and REPORTS when it had to, so a value nobody
 * agreed on surfaces instead of being silently coerced.
 */

export const RULE_OUTCOMES = [
  "gap_identified",
  "no_gap_identified_in_available_data",
  "needs_review",
  "not_eligible",
] as const;

export type RuleOutcome = (typeof RULE_OUTCOMES)[number];

export type OutcomeTone = "finding" | "review" | "neutral";

export type OutcomeDisplay = {
  /** Short label for a badge. */
  label: string;
  /** What the outcome asserts, in plain language. */
  meaning: string;
  /**
   * The limit of the claim. Rendered wherever the outcome is, never optional
   * for the two outcomes that could be misread as reassurance.
   */
  limitation: string | null;
  tone: OutcomeTone;
};

export const OUTCOME_DISPLAY: Record<RuleOutcome, OutcomeDisplay> = {
  gap_identified: {
    label: "Gap identified",
    meaning:
      "Verified inputs meet the configured demonstration gap condition for this pathway.",
    limitation:
      "A prioritization signal for human review. It is not a diagnosis and does not order a screening test.",
    tone: "finding",
  },
  no_gap_identified_in_available_data: {
    label: "No gap identified in available data",
    meaning:
      "No configured gap was found in the records available for this pathway.",
    limitation:
      "Not an assurance of health. Records that are absent were not assessed, and completeness has not been verified.",
    tone: "neutral",
  },
  needs_review: {
    label: "Needs review",
    meaning:
      "Required information is missing, contradictory or unverified, so the rule did not reach a conclusion.",
    limitation:
      "Unknown is not the same as up to date. The pathway stays blocked until a human resolves it.",
    tone: "review",
  },
  not_eligible: {
    label: "Not eligible",
    meaning:
      "Explicit verified inputs exclude this patient from this configured pathway.",
    limitation:
      "Scoped to this pathway only. It says nothing about any other preventive care.",
    tone: "neutral",
  },
};

export type OutcomeResolution = {
  outcome: RuleOutcome;
  /** Exactly what the server sent, kept for display and debugging. */
  raw: string;
  /**
   * canonical — the server used Alfred's vocabulary.
   * aliased   — a known shorter API spelling was mapped.
   * unknown   — unrecognised; shown as needs_review AND flagged, never hidden.
   */
  source: "canonical" | "aliased" | "unknown";
};

/** Known shorter spellings the API uses today. */
const ALIASES: Record<string, RuleOutcome> = {
  gap: "gap_identified",
  no_gap: "no_gap_identified_in_available_data",
  // Present for completeness; the API does not emit these yet.
  no_gap_identified: "no_gap_identified_in_available_data",
  ineligible: "not_eligible",
};

export function resolveOutcome(raw: string): OutcomeResolution {
  if ((RULE_OUTCOMES as readonly string[]).includes(raw)) {
    return { outcome: raw as RuleOutcome, raw, source: "canonical" };
  }
  const aliased = ALIASES[raw];
  if (aliased) return { outcome: aliased, raw, source: "aliased" };

  // An outcome nobody agreed on must not be rendered as a conclusion.
  return { outcome: "needs_review", raw, source: "unknown" };
}

/** Whether this outcome should block the pathway from advancing. */
export function blocksPathway(outcome: RuleOutcome): boolean {
  return outcome === "needs_review";
}
