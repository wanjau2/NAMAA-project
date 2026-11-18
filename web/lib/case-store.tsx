"use client";

/**
 * Case store — API-backed.
 *
 * The local transition layer is gone. This store only transports: it fetches
 * from the API, submits mutations, and renders whatever comes back. It never
 * advances a stage, never validates a transition and never fabricates an event.
 *
 * Session lifecycle: a guest session is created on first load and held in
 * memory, so a reload starts a fresh synthetic workspace. Reset calls
 * `POST /api/v1/demo/reset`, which restores the seed for that session only.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  ApiError,
  ApiUnreachableError,
  api,
  newRequestId,
  API_BASE,
} from "@/lib/api";
import type {
  ActionRequest,
  CaseOut,
  CaseRow,
  EventOut,
  StructuredError,
} from "@/lib/api-types";
import { useDemoSession } from "@/lib/demo-session";

export type ConnectionStatus = "connecting" | "ready" | "unreachable";

export type SubmitResult =
  | { ok: true; event: EventOut; case: CaseOut }
  | { ok: false; error: StructuredError; status: number };

type CaseStoreValue = {
  status: ConnectionStatus;
  /** Set when the API cannot be reached; the UI explains how to start it. */
  connectionMessage: string | null;
  apiBase: string;
  sessionId: string | null;

  /** Worklist rows. Empty while loading. */
  rows: CaseRow[];
  rowsLoading: boolean;
  rowsError: StructuredError | null;
  reloadRows: () => void;

  /** Full case including detail, once fetched. */
  getCase: (id: string) => CaseOut | undefined;
  loadCase: (id: string) => void;
  caseLoading: (id: string) => boolean;
  caseError: (id: string) => StructuredError | null;

  submit: (caseId: string, request: ActionRequest) => Promise<SubmitResult>;
  newRequestId: () => string;
  resetDemo: () => Promise<void>;
};

const CaseStoreContext = createContext<CaseStoreValue | null>(null);

function toStructured(error: unknown): { error: StructuredError; status: number } {
  if (error instanceof ApiError) {
    return { error: error.error, status: error.status };
  }
  if (error instanceof ApiUnreachableError) {
    return {
      error: {
        code: "api_unreachable",
        message: error.message,
        field_errors: {},
        request_id: null,
      },
      status: 0,
    };
  }
  return {
    error: {
      code: "unexpected_error",
      message:
        error instanceof Error ? error.message : "An unexpected error occurred.",
      field_errors: {},
      request_id: null,
    },
    status: 0,
  };
}

export function CaseStoreProvider({ children }: { children: ReactNode }) {
  const { role } = useDemoSession();

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [connectionMessage, setConnectionMessage] = useState<string | null>(null);

  const [rows, setRows] = useState<CaseRow[]>([]);
  const [rowsLoading, setRowsLoading] = useState(false);
  const [rowsError, setRowsError] = useState<StructuredError | null>(null);

  const [cases, setCases] = useState<Record<string, CaseOut>>({});
  const [caseLoadingIds, setCaseLoadingIds] = useState<Record<string, boolean>>({});
  const [caseErrors, setCaseErrors] = useState<Record<string, StructuredError>>({});

  // Guards against duplicate in-flight fetches for the same case.
  const inFlight = useRef<Set<string>>(new Set());

  const fetchRows = useCallback(async (session: string) => {
    setRowsLoading(true);
    setRowsError(null);
    try {
      const data = await api.listCases(session);
      setRows(data);
    } catch (caught) {
      const { error } = toStructured(caught);
      setRowsError(error);
      if (error.code === "api_unreachable") {
        setStatus("unreachable");
        setConnectionMessage(error.message);
      }
    } finally {
      setRowsLoading(false);
    }
  }, []);

  // Create the guest session once, then load the worklist.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const session = await api.createSession();
        if (cancelled) return;
        setSessionId(session.session_id);
        setStatus("ready");
        setConnectionMessage(null);
        await fetchRows(session.session_id);
      } catch (caught) {
        if (cancelled) return;
        const { error } = toStructured(caught);
        setStatus("unreachable");
        setConnectionMessage(error.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [fetchRows]);

  const loadCase = useCallback(
    (id: string) => {
      if (!sessionId || inFlight.current.has(id)) return;
      inFlight.current.add(id);
      setCaseLoadingIds((prev) => ({ ...prev, [id]: true }));
      (async () => {
        try {
          const data = await api.getCase(sessionId, id);
          setCases((prev) => ({ ...prev, [id]: data }));
          setCaseErrors((prev) => {
            const next = { ...prev };
            delete next[id];
            return next;
          });
        } catch (caught) {
          const { error } = toStructured(caught);
          setCaseErrors((prev) => ({ ...prev, [id]: error }));
        } finally {
          inFlight.current.delete(id);
          setCaseLoadingIds((prev) => ({ ...prev, [id]: false }));
        }
      })();
    },
    [sessionId],
  );

  const submit = useCallback(
    async (caseId: string, request: ActionRequest): Promise<SubmitResult> => {
      if (!sessionId) {
        return {
          ok: false,
          status: 0,
          error: {
            code: "no_session",
            message: "No guest session yet. Reload the page to start one.",
            field_errors: {},
            request_id: request.request_id,
          },
        };
      }
      try {
        const result = await api.postAction(sessionId, role, caseId, request);
        // Server echo is the only source of new state.
        setCases((prev) => ({ ...prev, [caseId]: result.case }));
        setRows((prev) =>
          prev.map((row) =>
            row.id === caseId ? { ...row, ...stripDetail(result.case) } : row,
          ),
        );
        return { ok: true, event: result.event, case: result.case };
      } catch (caught) {
        const { error, status } = toStructured(caught);
        return { ok: false, error, status };
      }
    },
    [sessionId, role],
  );

  const reloadRows = useCallback(() => {
    if (sessionId) void fetchRows(sessionId);
  }, [sessionId, fetchRows]);

  const resetDemo = useCallback(async () => {
    if (!sessionId) return;
    try {
      await api.resetSession(sessionId);
      setCases({});
      setCaseErrors({});
      await fetchRows(sessionId);
    } catch (caught) {
      const { error } = toStructured(caught);
      setRowsError(error);
    }
  }, [sessionId, fetchRows]);

  const value = useMemo<CaseStoreValue>(
    () => ({
      status,
      connectionMessage,
      apiBase: API_BASE,
      sessionId,
      rows,
      rowsLoading,
      rowsError,
      reloadRows,
      getCase: (id) => cases[id],
      loadCase,
      caseLoading: (id) => Boolean(caseLoadingIds[id]),
      caseError: (id) => caseErrors[id] ?? null,
      submit,
      newRequestId,
      resetDemo,
    }),
    [
      status,
      connectionMessage,
      sessionId,
      rows,
      rowsLoading,
      rowsError,
      reloadRows,
      cases,
      loadCase,
      caseLoadingIds,
      caseErrors,
      submit,
      resetDemo,
    ],
  );

  return (
    <CaseStoreContext.Provider value={value}>
      {children}
    </CaseStoreContext.Provider>
  );
}

/** Worklist rows carry no `detail`; drop it when folding an action response in. */
function stripDetail({ detail, ...row }: CaseOut): CaseRow {
  void detail;
  return row;
}

export function useCaseStore(): CaseStoreValue {
  const ctx = useContext(CaseStoreContext);
  if (!ctx) {
    throw new Error("useCaseStore must be used inside <CaseStoreProvider>");
  }
  return ctx;
}

/** Fetches one case on mount and keeps it fresh after actions. */
export function useCase(id: string) {
  const { getCase, loadCase, caseLoading, caseError, status } = useCaseStore();
  const data = getCase(id);

  useEffect(() => {
    if (status === "ready" && !data) loadCase(id);
  }, [status, data, id, loadCase]);

  return {
    case: data,
    loading: caseLoading(id) || (status === "connecting" && !data),
    error: caseError(id),
    reload: () => loadCase(id),
  };
}
