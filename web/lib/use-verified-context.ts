"use client";

/**
 * Live retrieved context: Relate (hints) then POST verified-context.
 *
 * The payload is records + scope metadata. It is not Alfred AssembledContext
 * (no query, tiers, or items). Do not cast one contract to the other.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorHttpStatus } from "@/lib/api";
import type { RelateBatch, Role, VerifiedContext } from "@/lib/api-types";
import { hintsFromRelate } from "@/lib/relate";
import {
  describeSecurityOutcome,
  type SecurityOutcome,
} from "@/lib/security-states";

export type LiveContextState =
  | { kind: "loading" }
  | { kind: "unavailable"; reason: "no_patient" }
  | { kind: "denied"; outcome: SecurityOutcome }
  | { kind: "failed"; outcome: SecurityOutcome }
  | {
      kind: "live";
      context: VerifiedContext;
      family: RelateBatch | null;
      carePlans: RelateBatch | null;
      relateFailed: boolean;
    }
  | {
      kind: "empty";
      context: VerifiedContext;
      family: RelateBatch | null;
      carePlans: RelateBatch | null;
      relateFailed: boolean;
    }
  | {
      kind: "stale";
      context: VerifiedContext;
      family: RelateBatch | null;
      carePlans: RelateBatch | null;
      relateFailed: boolean;
    }
  | {
      kind: "expired";
      context: VerifiedContext;
      family: RelateBatch | null;
      carePlans: RelateBatch | null;
      relateFailed: boolean;
    };

function classify(
  context: VerifiedContext,
  family: RelateBatch | null,
  carePlans: RelateBatch | null,
  relateFailed: boolean,
): Exclude<LiveContextState, { kind: "loading" | "denied" | "failed" | "unavailable" }> {
  const expired =
    Boolean(context.expires_at) &&
    Date.parse(context.expires_at) <= Date.now();
  const base = { context, family, carePlans, relateFailed };
  if (expired) return { kind: "expired", ...base };
  if (context.state === "stale") return { kind: "stale", ...base };
  if (!context.records?.length) return { kind: "empty", ...base };
  return { kind: "live", ...base };
}

function initialState(
  caseReady: boolean,
  sessionId: string | null,
  caseDenied: boolean,
  patientId: string | null | undefined,
): LiveContextState {
  if (!caseReady || !sessionId) return { kind: "loading" };
  if (caseDenied) {
    return {
      kind: "denied",
      outcome: describeSecurityOutcome(403, "context_retrieve"),
    };
  }
  if (!patientId) return { kind: "unavailable", reason: "no_patient" };
  return { kind: "loading" };
}

export function useVerifiedContext(
  patientId: string | null | undefined,
  sessionId: string | null,
  role: Role,
  sessionEpoch: number,
  caseReady: boolean,
  caseDenied = false,
): LiveContextState & { refresh: () => void } {
  const [runToken, setRunToken] = useState(0);
  const requestKey = `${sessionId ?? ""}:${patientId ?? ""}:${role}:${sessionEpoch}:${runToken}:${caseReady}:${caseDenied}`;
  const [snapshot, setSnapshot] = useState<{
    key: string;
    state: LiveContextState;
  }>(() => ({
    key: requestKey,
    state: initialState(caseReady, sessionId, caseDenied, patientId),
  }));
  const lastGenerationId = useRef<string | null>(null);

  if (snapshot.key !== requestKey) {
    setSnapshot({
      key: requestKey,
      state: initialState(caseReady, sessionId, caseDenied, patientId),
    });
  }

  const refresh = useCallback(() => setRunToken((n) => n + 1), []);

  useEffect(() => {
    if (!caseReady || !sessionId || caseDenied || !patientId) return;
    const controller = new AbortController();
    let cancelled = false;
    let expiryTimer: ReturnType<typeof setTimeout> | null = null;

    (async () => {
      let family: RelateBatch | null = null;
      let carePlans: RelateBatch | null = null;
      let relateFailed = false;
      try {
        try {
          family = await api.getRelateFamilyHistory(
            sessionId,
            role,
            patientId,
            controller.signal,
          );
        } catch (caught) {
          if (caught instanceof DOMException && caught.name === "AbortError") {
            return;
          }
          relateFailed = true;
        }
        try {
          carePlans = await api.getRelateCarePlans(
            sessionId,
            role,
            patientId,
            controller.signal,
          );
        } catch (caught) {
          if (caught instanceof DOMException && caught.name === "AbortError") {
            return;
          }
          relateFailed = true;
        }

        const hints = hintsFromRelate(family, carePlans);
        const context = await api.postVerifiedContext(
          sessionId,
          role,
          {
            patient_id: patientId,
            generation_id: lastGenerationId.current,
            relate_hints: hints,
          },
          controller.signal,
        );
        lastGenerationId.current = context.generation_id;
        if (cancelled) return;
        setSnapshot({
          key: requestKey,
          state: classify(context, family, carePlans, relateFailed),
        });

        const expiresAt = Date.parse(context.expires_at);
        if (!Number.isNaN(expiresAt) && expiresAt > Date.now()) {
          expiryTimer = setTimeout(() => {
            if (!cancelled) setRunToken((n) => n + 1);
          }, expiresAt - Date.now() + 250);
        }
      } catch (caught) {
        if (caught instanceof DOMException && caught.name === "AbortError") {
          return;
        }
        const httpStatus = errorHttpStatus(caught);
        const outcome = describeSecurityOutcome(httpStatus, "context_retrieve");
        if (!cancelled) {
          setSnapshot({
            key: requestKey,
            state:
              httpStatus === 401 || httpStatus === 403 || httpStatus === 404
                ? { kind: "denied", outcome }
                : { kind: "failed", outcome },
          });
        }
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
      if (expiryTimer) clearTimeout(expiryTimer);
    };
  }, [
    requestKey,
    caseReady,
    sessionId,
    caseDenied,
    patientId,
    role,
  ]);

  return { ...snapshot.state, refresh };
}
