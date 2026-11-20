/**
 * How a status GET after SSE drop/malformed frames should be read.
 *
 * Proposal count alone is not a result. Only a succeeded job with zero
 * proposals is an extraction-empty state, and that still says nothing about
 * a care gap.
 */

import type { ExtractionJobOut, ExtractionState } from "@/lib/api-types";

export const MAX_STATUS_POLLS = 8;
export const STATUS_POLL_MS = 1500;
export const MAX_SSE_ERRORS = 3;
export const MAX_MALFORMED_FRAMES = 3;

export type InterpretedJob =
  | {
      kind: "running";
      state: ExtractionState;
      message: string;
      progress: number;
    }
  | {
      kind: "succeeded";
      proposals: unknown[];
      empty: boolean;
    }
  | { kind: "failed"; message: string }
  | { kind: "timed_out"; message: string }
  | { kind: "cancelled"; message: string };

const NOT_A_GAP =
  "This is not a finding of no care gap. The note remains unreviewed.";

export function interpretExtractionJob(job: ExtractionJobOut): InterpretedJob {
  if (job.state === "succeeded") {
    const proposals = job.proposals ?? [];
    return { kind: "succeeded", proposals, empty: proposals.length === 0 };
  }
  if (job.state === "timed_out") {
    return {
      kind: "timed_out",
      message: `${job.error_message || job.message || "Extraction timed out"}. ${NOT_A_GAP}`,
    };
  }
  if (job.state === "cancelled") {
    return {
      kind: "cancelled",
      message: `${job.error_message || job.message || "Extraction was cancelled"}. ${NOT_A_GAP}`,
    };
  }
  if (job.state === "failed") {
    return {
      kind: "failed",
      message: `${job.error_message || job.message || "Extraction failed"}. ${NOT_A_GAP}`,
    };
  }
  return {
    kind: "running",
    state: job.state,
    message: job.message || "Extracting…",
    progress: job.progress_percent,
  };
}

/** True when this EventSource payload is a keepalive or otherwise unusable JSON. */
export function isUsableExtractionFrame(raw: string): boolean {
  const trimmed = raw.trim();
  if (!trimmed || trimmed.startsWith(":")) return false;
  try {
    const parsed = JSON.parse(trimmed) as { state?: unknown };
    return typeof parsed.state === "string";
  } catch {
    return false;
  }
}
