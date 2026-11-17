"use client";

/**
 * Local case store — the frontend's stand-in for Ismail's persistence layer.
 * Deleted at F4 together with lib/case-actions.ts.
 *
 * It exists so both synthetic journeys can be demonstrated end to end before
 * the API lands, and it models three server behaviours the UI must handle
 * correctly rather than discover late:
 *
 *  1. REVISION CHECKS — a stale `expected_revision` is rejected, not applied.
 *  2. IDEMPOTENCY — a repeated `request_id` returns the first result and does
 *     NOT append a second event.
 *  3. SERVER-ECHO STATE — the UI never advances a stage itself. It submits and
 *     renders whatever comes back.
 *
 * Nothing is persisted across a reload, and a demo reset restores the seed.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  applyAction,
  type ActionRequest,
  type AppliedEvent,
  type CaseState,
  type StructuredError,
} from "@/lib/case-actions";
import { MOCK_CASES, getCaseDetail } from "@/lib/mock-data";
import { useDemoSession } from "@/lib/demo-session";

export type SubmitResult =
  | { ok: true; event: AppliedEvent; duplicate: boolean }
  | { ok: false; error: StructuredError };

type CaseStoreValue = {
  cases: Record<string, CaseState>;
  getCase: (id: string) => CaseState | undefined;
  eventsFor: (id: string) => AppliedEvent[];
  submit: (caseId: string, request: ActionRequest) => SubmitResult;
  /** Fresh request id for a form instance; reused on retry so retries are safe. */
  newRequestId: () => string;
};

const CaseStoreContext = createContext<CaseStoreValue | null>(null);

function seedCases(): Record<string, CaseState> {
  return Object.fromEntries(MOCK_CASES.map((row) => [row.id, { ...row }]));
}

function makeId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `req-${Math.random().toString(36).slice(2)}-${Date.now()}`;
}

/**
 * A demo reset retires this synthetic session. Remounting on `sessionEpoch`
 * rebuilds every piece of state from the seed in one step — no reset effect,
 * and no window in which half the store is stale.
 */
export function CaseStoreProvider({ children }: { children: ReactNode }) {
  const { sessionEpoch } = useDemoSession();
  return <CaseStoreInner key={sessionEpoch}>{children}</CaseStoreInner>;
}

function CaseStoreInner({ children }: { children: ReactNode }) {
  const { role } = useDemoSession();
  const [cases, setCases] = useState<Record<string, CaseState>>(seedCases);
  const [events, setEvents] = useState<AppliedEvent[]>([]);

  // request_id -> the result it already produced.
  const handled = useRef<Map<string, SubmitResult>>(new Map());

  const submit = useCallback(
    (caseId: string, request: ActionRequest): SubmitResult => {
      const prior = handled.current.get(request.request_id);
      if (prior) {
        // Idempotent replay: same answer, no second event.
        return prior.ok ? { ...prior, duplicate: true } : prior;
      }

      const current = cases[caseId];
      if (!current) {
        const result: SubmitResult = {
          ok: false,
          error: {
            code: "not_found",
            message: "This case no longer exists in the current session.",
            field_errors: {},
            request_id: request.request_id,
          },
        };
        return result;
      }

      const outcome = applyAction(
        current,
        request,
        role,
        new Date().toISOString(),
      );

      if (!outcome.ok) {
        // Failures are not memoised: the reviewer may fix the form and retry
        // with the same request id, which must then be allowed through.
        return { ok: false, error: outcome.error };
      }

      setCases((prev) => ({ ...prev, [caseId]: outcome.next }));
      setEvents((prev) => [...prev, outcome.event]);

      const result: SubmitResult = {
        ok: true,
        event: outcome.event,
        duplicate: false,
      };
      handled.current.set(request.request_id, result);
      return result;
    },
    [cases, role],
  );

  const value = useMemo<CaseStoreValue>(
    () => ({
      cases,
      getCase: (id) => cases[id],
      eventsFor: (id) => events.filter((event) => event.case_id === id),
      submit,
      newRequestId: makeId,
    }),
    [cases, events, submit],
  );

  return (
    <CaseStoreContext.Provider value={value}>
      {children}
    </CaseStoreContext.Provider>
  );
}

export function useCaseStore(): CaseStoreValue {
  const ctx = useContext(CaseStoreContext);
  if (!ctx) {
    throw new Error("useCaseStore must be used inside <CaseStoreProvider>");
  }
  return ctx;
}

/** Seeded timeline from the fixtures, plus anything done in this session. */
export function useCaseTimeline(id: string) {
  const { eventsFor } = useCaseStore();
  const seeded = getCaseDetail(id).events;
  const live = eventsFor(id);
  return { seeded, live };
}
