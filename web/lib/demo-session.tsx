"use client";

/**
 * Guest demo session state: simulated role and UI language.
 *
 * Scope boundaries this deliberately enforces:
 *  - This is NOT authentication or authorization. It is a labelled simulation
 *    confined to one synthetic guest session, per the design specification
 *    (§1 Roles and permissions, §9 Workspace partitioning).
 *  - Nothing is persisted. A reload starts a fresh synthetic session.
 *  - The server remains authoritative for every transition. Role here only
 *    changes what the UI *offers*; it never grants permission.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export const ROLES = [
  "coordinator",
  "clinical_reviewer",
  "population_analyst",
] as const;

export type Role = (typeof ROLES)[number];

/**
 * NOTE: the Arabic strings here are UNREVIEWED demo translations. The UI must
 * label them as such (theme §3) and must never present them as clinically
 * approved copy. Alfred supplies reviewed copy where available.
 */
export const ROLE_LABELS: Record<Role, { en: string; ar: string }> = {
  coordinator: { en: "Coordinator", ar: "منسق الرعاية" },
  clinical_reviewer: { en: "Clinical Reviewer", ar: "المراجع السريري" },
  population_analyst: { en: "Population Analyst", ar: "محلل البيانات السكانية" },
};

export type Locale = "en" | "ar";

type DemoSessionValue = {
  role: Role;
  setRole: (role: Role) => void;
  locale: Locale;
  setLocale: (locale: Locale) => void;
  dir: "ltr" | "rtl";
  /** Monotonic counter — bump to signal that a reset occurred. */
  sessionEpoch: number;
  resetSession: () => void;
};

const DemoSessionContext = createContext<DemoSessionValue | null>(null);

export function DemoSessionProvider({ children }: { children: ReactNode }) {
  const [role, setRole] = useState<Role>("coordinator");
  const [locale, setLocale] = useState<Locale>("en");
  const [sessionEpoch, setSessionEpoch] = useState(0);

  const dir = locale === "ar" ? "rtl" : "ltr";

  // The root layout renders lang="en" dir="ltr" on the server; keep the real
  // document in sync so logical CSS properties mirror the whole layout.
  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = dir;
  }, [locale, dir]);

  const resetSession = useCallback(() => {
    setRole("coordinator");
    setLocale("en");
    setSessionEpoch((n) => n + 1);
  }, []);

  const value = useMemo<DemoSessionValue>(
    () => ({ role, setRole, locale, setLocale, dir, sessionEpoch, resetSession }),
    [role, locale, dir, sessionEpoch, resetSession],
  );

  return (
    <DemoSessionContext.Provider value={value}>
      {children}
    </DemoSessionContext.Provider>
  );
}

export function useDemoSession(): DemoSessionValue {
  const ctx = useContext(DemoSessionContext);
  if (!ctx) {
    throw new Error("useDemoSession must be used inside <DemoSessionProvider>");
  }
  return ctx;
}
