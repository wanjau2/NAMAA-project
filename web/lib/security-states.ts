/**
 * Security outcomes, phrased so they never leak existence.
 *
 * Alfred's handoff: surface denied / stale / failed for note retrieval, SSE,
 * disclosure and review "without leaking existence".
 *
 * The rule that drives everything here: **403 and 404 must be
 * indistinguishable to the user.** If "forbidden" and "not found" read
 * differently, anyone can enumerate which patients, notes or jobs exist in
 * another workspace simply by watching which message appears. So both resolve
 * to the same `not_available` state with the same words.
 *
 * The distinction is still available to developers — the structured error code
 * is logged and shown in the technical line — but the user-facing sentence is
 * identical.
 */

export type SecurityState =
  /** 403 or 404: exists-but-forbidden and does-not-exist are the same answer. */
  | "not_available"
  /** 401: no usable session. */
  | "no_session"
  /** 409: the thing moved under us. */
  | "stale"
  /** 422/429/5xx/transport: it did not work, and nothing was changed. */
  | "failed";

export type SecurityOperation =
  | "note_retrieve"
  | "extraction_stream"
  | "proposal_disclose"
  | "fact_review";

export type SecurityOutcome = {
  state: SecurityState;
  title: string;
  body: string;
  /** What the reviewer should do, when there is something to do. */
  action: string | null;
  /** Never implies that a failure is a clinical finding. */
  caveat: string | null;
};

const OPERATION_NOUN: Record<SecurityOperation, string> = {
  note_retrieve: "this source note",
  extraction_stream: "this extraction",
  proposal_disclose: "these proposals",
  fact_review: "this review",
};

/**
 * `status` 0 means a transport failure (the API could not be reached).
 */
export function describeSecurityOutcome(
  status: number,
  operation: SecurityOperation,
): SecurityOutcome {
  const noun = OPERATION_NOUN[operation];

  if (status === 401) {
    return {
      state: "no_session",
      title: "No active session",
      body: "This guest session is no longer valid.",
      action: "Reload the page to start a fresh synthetic session.",
      caveat: null,
    };
  }

  // 403 and 404 deliberately share one answer.
  if (status === 403 || status === 404) {
    return {
      state: "not_available",
      title: "Not available in this session",
      body: `${capitalise(noun)} is not available to you here. This response is the same whether the record does not exist or is outside your authorization, so nothing about other workspaces can be inferred from it.`,
      action: null,
      caveat:
        operation === "proposal_disclose" || operation === "note_retrieve"
          ? "This is an access outcome, not a clinical finding. It says nothing about what the record contains."
          : null,
    };
  }

  if (status === 409) {
    return {
      state: "stale",
      title: "Changed since you loaded it",
      body: `${capitalise(noun)} moved on while this screen was open, so the request was refused rather than applied to a version you did not see.`,
      action: "Reload the latest state and try again. Your entries are kept.",
      caveat: null,
    };
  }

  if (status === 422) {
    return {
      state: "failed",
      title: "Rejected as invalid",
      body: "The server rejected the request. Nothing was changed.",
      action: "Correct the highlighted fields and submit again.",
      caveat: null,
    };
  }

  if (status === 429) {
    return {
      state: "failed",
      title: "Rate limited",
      body: "Too many requests in a short period. Nothing was changed.",
      action: "Wait a moment and try again.",
      caveat: null,
    };
  }

  return {
    state: "failed",
    title: status === 0 ? "Could not reach the server" : "The request failed",
    body:
      status === 0
        ? "No response was received, so nothing was changed."
        : `The server returned an error (${status}). Nothing was changed.`,
    action: "Try again.",
    caveat:
      operation === "extraction_stream" || operation === "proposal_disclose"
        ? "A failed extraction is not a finding of no care gap. The note remains unreviewed."
        : null,
  };
}

function capitalise(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

/** True when two statuses must be indistinguishable to the user. */
export function leaksExistence(
  a: number,
  b: number,
  operation: SecurityOperation,
): boolean {
  const first = describeSecurityOutcome(a, operation);
  const second = describeSecurityOutcome(b, operation);
  return first.title !== second.title || first.body !== second.body;
}
