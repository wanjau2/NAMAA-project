/**
 * Extraction progress via Server-Sent Events (D004).
 *
 * Replaces the planned 2-second polling loop. Open one EventSource per job;
 * stop on terminal states. Status GET is a fallback only — do not hammer it.
 *
 * Headers: browsers cannot set custom headers on EventSource. Pass the guest
 * session as a query param (`session`) until cookie-based sessions land.
 */

export type ExtractionState =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "timed_out";

export type ExtractionProgressEvent = {
  event: "progress" | "terminal";
  job_id: string;
  document_id: string;
  document_version: number;
  state: ExtractionState;
  progress_percent: number;
  message: string;
  elapsed_ms: number;
  timeout_ms: number;
  model_revision: string;
  prompt_version: string;
  error_code?: string | null;
  error_message?: string | null;
  synthetic: boolean;
  inference_mode: string;
  proposals?: unknown[];
};

const TERMINAL: ReadonlySet<ExtractionState> = new Set([
  "succeeded",
  "failed",
  "cancelled",
  "timed_out",
]);

export function isTerminalExtraction(state: ExtractionState): boolean {
  return TERMINAL.has(state);
}

export type SubscribeExtractionOptions = {
  apiBaseUrl: string;
  jobId: string;
  sessionId: string;
  onEvent: (event: ExtractionProgressEvent) => void;
  onError?: (error: Event) => void;
};

/**
 * Subscribe to `/api/v1/extractions/{id}/events`.
 * Returns an unsubscribe function.
 */
export function subscribeExtractionProgress(
  options: SubscribeExtractionOptions,
): () => void {
  const url = new URL(
    `${options.apiBaseUrl.replace(/\/$/, "")}/api/v1/extractions/${options.jobId}/events`,
  );
  // Temporary until cookie sessions: SSE cannot send X-Namaa-Session.
  url.searchParams.set("session", options.sessionId);

  const source = new EventSource(url.toString());

  const handle = (raw: MessageEvent) => {
    try {
      const data = JSON.parse(String(raw.data)) as ExtractionProgressEvent;
      options.onEvent(data);
      if (isTerminalExtraction(data.state)) {
        source.close();
      }
    } catch {
      // Ignore malformed frames; keepalives are comments.
    }
  };

  source.addEventListener("progress", handle);
  source.addEventListener("terminal", handle);
  source.onerror = (err) => {
    options.onError?.(err);
  };

  return () => source.close();
}

/** Format the elapsed line required by the UI theme (e.g. Extracting… 12s (90s timeout)). */
export function formatExtractionElapsed(event: ExtractionProgressEvent): string {
  const elapsedSec = Math.floor(event.elapsed_ms / 1000);
  const timeoutSec = Math.floor(event.timeout_ms / 1000);
  if (event.state === "timed_out") {
    return `Extraction timed out after ${timeoutSec}s — retry. Not the same as finding no care gap.`;
  }
  if (isTerminalExtraction(event.state)) {
    return event.message;
  }
  return `${event.message || "Extracting…"} ${elapsedSec}s (${timeoutSec}s timeout)`;
}
