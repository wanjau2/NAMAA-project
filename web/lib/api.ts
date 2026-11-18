/**
 * Namaa API client.
 *
 * Replaces the local transition stand-in. The server is now authoritative for
 * every transition, every validation and every event — this module only
 * transports requests and surfaces structured errors.
 *
 * Session handling: the API requires `X-Namaa-Session` on every call and
 * `X-Namaa-Role` for the simulated role. A guest session is created on demand
 * and held in memory only, so a reload starts a fresh synthetic session.
 */

import type {
  ActionRequest,
  ActionResponse,
  AnalyticsOverview,
  CaseOut,
  CaseRow,
  DemoResetOut,
  DemoSessionOut,
  DocumentOut,
  ExtractionAccepted,
  ExtractionJobOut,
  Role,
  StructuredError,
} from "@/lib/api-types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

/** Thrown for any non-2xx response, carrying the server's structured error. */
export class ApiError extends Error {
  readonly status: number;
  readonly error: StructuredError;

  constructor(status: number, error: StructuredError) {
    super(error.message);
    this.name = "ApiError";
    this.status = status;
    this.error = error;
  }

  get code(): string {
    return this.error.code;
  }

  get fieldErrors(): Record<string, string> {
    return this.error.field_errors ?? {};
  }
}

/** A transport failure: the API is unreachable, not a rejected request. */
export class ApiUnreachableError extends Error {
  constructor(cause: unknown) {
    super(
      `Cannot reach the Namaa API at ${API_BASE}. Start it with: cd api && uvicorn app.main:app --port 8000`,
    );
    this.name = "ApiUnreachableError";
    this.cause = cause;
  }
}

type RequestOptions = {
  method?: "GET" | "POST";
  session?: string | null;
  role?: Role;
  body?: unknown;
  signal?: AbortSignal;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", session, role, body, signal } = options;

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (session) headers["X-Namaa-Session"] = session;
  if (role) headers["X-Namaa-Role"] = role;

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
      cache: "no-store",
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiUnreachableError(cause);
  }

  if (!response.ok) {
    let parsed: StructuredError;
    try {
      const json = (await response.json()) as Partial<StructuredError> & {
        detail?: unknown;
      };
      parsed = {
        code: json.code ?? `http_${response.status}`,
        message:
          json.message ??
          (typeof json.detail === "string"
            ? json.detail
            : `Request failed with status ${response.status}.`),
        field_errors: json.field_errors ?? {},
        request_id: json.request_id ?? null,
      };
    } catch {
      parsed = {
        code: `http_${response.status}`,
        message: `Request failed with status ${response.status}.`,
        field_errors: {},
        request_id: null,
      };
    }
    throw new ApiError(response.status, parsed);
  }

  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string; version: string }>("/health"),

  createSession: () =>
    request<DemoSessionOut>("/api/v1/demo/sessions", { method: "POST" }),

  resetSession: (session: string) =>
    request<DemoResetOut>("/api/v1/demo/reset", { method: "POST", session }),

  listCases: (session: string, signal?: AbortSignal) =>
    request<CaseRow[]>("/api/v1/cases", { session, signal }),

  getCase: (session: string, id: string, signal?: AbortSignal) =>
    request<CaseOut>(`/api/v1/cases/${encodeURIComponent(id)}`, {
      session,
      signal,
    }),

  postAction: (
    session: string,
    role: Role,
    id: string,
    body: ActionRequest,
  ) =>
    request<ActionResponse>(
      `/api/v1/cases/${encodeURIComponent(id)}/actions`,
      { method: "POST", session, role, body },
    ),

  /** Authorized note retrieval; the server applies a policy check first. */
  getDocument: (
    session: string,
    role: Role,
    documentId: string,
    signal?: AbortSignal,
  ) =>
    request<DocumentOut>(
      `/api/v1/documents/${encodeURIComponent(documentId)}`,
      { session, role, signal },
    ),

  startExtraction: (session: string, role: Role, documentId: string) =>
    request<ExtractionAccepted>(
      `/api/v1/documents/${encodeURIComponent(documentId)}/extractions`,
      { method: "POST", session, role },
    ),

  getExtraction: (
    session: string,
    role: Role,
    jobId: string,
    signal?: AbortSignal,
  ) =>
    request<ExtractionJobOut>(
      `/api/v1/extractions/${encodeURIComponent(jobId)}`,
      { session, role, signal },
    ),

  analyticsOverview: (session: string, signal?: AbortSignal) =>
    request<AnalyticsOverview>("/api/v1/analytics/overview", {
      session,
      signal,
    }),
};

/** Idempotency key for one form instance; reused on retry so retries are safe. */
export function newRequestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `req-${Math.random().toString(36).slice(2)}-${Date.now()}`;
}
