"use client";

/**
 * Load the canonical patient evaluation (D006).
 *
 * GET latest first. A 404 here means this session has no stored evaluation,
 * not that the patient is missing — the case is already loaded. POST runs
 * only when the reviewer asks. Outcomes come from `rule_evaluation`, never
 * from review counts or worklist `flag_status`.
 */

import { useCallback, useEffect, useState } from "react";
import { ApiError, api, errorHttpStatus } from "@/lib/api";
import type { EvaluationResult, Pathway, Role } from "@/lib/api-types";
import {
  describeSecurityOutcome,
  type SecurityOutcome,
} from "@/lib/security-states";

export type PatientEvaluationState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "none" }
  | { status: "ready"; result: EvaluationResult; ranNow: boolean }
  | { status: "unavailable"; outcome: SecurityOutcome }
  | { status: "failed"; outcome: SecurityOutcome };

function initialState(
  sessionId: string | null,
  patientId: string | null | undefined,
): PatientEvaluationState {
  if (!sessionId) return { status: "loading" };
  if (!patientId) return { status: "idle" };
  return { status: "loading" };
}

function asUnavailableOrFailed(caught: unknown): PatientEvaluationState {
  const httpStatus = errorHttpStatus(caught);
  const outcome = describeSecurityOutcome(httpStatus, "evaluation_run");
  if (httpStatus === 401 || httpStatus === 403 || httpStatus === 404) {
    return { status: "unavailable", outcome };
  }
  return { status: "failed", outcome };
}

export function usePatientEvaluation(
  patientId: string | null | undefined,
  pathway: Pathway | undefined,
  sessionId: string | null,
  role: Role,
  sessionEpoch: number,
): PatientEvaluationState & { reevaluate: () => void } {
  const [runToken, setRunToken] = useState(0);
  const requestKey = `${sessionId ?? ""}:${patientId ?? ""}:${role}:${sessionEpoch}:${runToken}`;
  const [snapshot, setSnapshot] = useState<{
    key: string;
    state: PatientEvaluationState;
  }>(() => ({
    key: requestKey,
    state: initialState(sessionId, patientId),
  }));

  if (snapshot.key !== requestKey) {
    setSnapshot({
      key: requestKey,
      state: initialState(sessionId, patientId),
    });
  }

  const reevaluate = useCallback(() => setRunToken((n) => n + 1), []);

  useEffect(() => {
    if (!sessionId || !patientId) return;
    const controller = new AbortController();
    let cancelled = false;

    (async () => {
      try {
        if (runToken === 0) {
          try {
            const latest = await api.getLatestEvaluation(
              sessionId,
              role,
              patientId,
              controller.signal,
            );
            if (!cancelled) {
              setSnapshot({
                key: requestKey,
                state: { status: "ready", result: latest, ranNow: false },
              });
            }
            return;
          } catch (caught) {
            if (caught instanceof DOMException && caught.name === "AbortError") {
              return;
            }
            if (caught instanceof ApiError && errorHttpStatus(caught) === 404) {
              if (!cancelled) {
                setSnapshot({ key: requestKey, state: { status: "none" } });
              }
              return;
            }
            if (!cancelled) {
              setSnapshot({
                key: requestKey,
                state: asUnavailableOrFailed(caught),
              });
            }
            return;
          }
        }

        const posted = await api.evaluatePatient(sessionId, role, patientId, {
          pathway: pathway ?? null,
        });
        if (!cancelled) {
          setSnapshot({
            key: requestKey,
            state: { status: "ready", result: posted, ranNow: true },
          });
        }
      } catch (caught) {
        if (caught instanceof DOMException && caught.name === "AbortError") {
          return;
        }
        if (!cancelled) {
          setSnapshot({
            key: requestKey,
            state: asUnavailableOrFailed(caught),
          });
        }
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [requestKey, sessionId, patientId, role, pathway, runToken]);

  return { ...snapshot.state, reevaluate };
}
