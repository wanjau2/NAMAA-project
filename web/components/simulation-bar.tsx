"use client";

/**
 * Persistent simulation and role bar — 44px, sticky, on every screen.
 *
 * Theme §4.1. This bar is the single most important safety affordance in the
 * product: it is the reason a reviewer can never mistake a synthetic journey
 * for a real one. It must not be collapsible away or hidden on any route.
 */

import { useId, useState } from "react";
import { AlertTriangle, RotateCcw, Settings2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { chrome } from "@/lib/copy";
import { useCaseStore } from "@/lib/case-store";
import {
  ROLES,
  ROLE_LABELS,
  useDemoSession,
  type Role,
} from "@/lib/demo-session";

export function SimulationBar() {
  const { role, setRole, locale, setLocale, resetSession } = useDemoSession();
  const { status, resetDemo, sessionId } = useCaseStore();
  const [confirmingReset, setConfirmingReset] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    // .on-dark swaps the focus ring to --brand-focus-on-dark for more headroom
    // against the slate bar (the default teal passes 3:1 at 3.9:1 either way).
    <div className="on-dark sticky top-0 z-50 w-full bg-sim-bar text-slate-100">
      <div className="flex h-11 items-center gap-3 px-4">
        {/* Start: the notice. Always visible, every width. */}
        <span
          data-testid="sim-notice"
          className="flex shrink-0 items-center gap-1.5 rounded bg-sim-badge px-2 py-1 text-xs font-bold text-sim-badge-fg"
        >
          <AlertTriangle aria-hidden="true" className="size-3.5" />
          <span className="hidden sm:inline">
            SYNTHETIC DEMO DATA — NOT FOR CLINICAL USE
          </span>
          <span className="sm:hidden">SYNTHETIC DEMO DATA</span>
        </span>

        <div className="flex-1" />

        <ApiStatus status={status} sessionId={sessionId} />

        {/* End: session controls. Collapsed behind a toggle under 640px (D002 §9). */}
        <div className="hidden items-center gap-3 sm:flex">
          <SessionControls
            role={role}
            setRole={setRole}
            locale={locale}
            setLocale={setLocale}
            confirmingReset={confirmingReset}
            setConfirmingReset={setConfirmingReset}
            resetSession={resetSession}
            onServerReset={resetDemo}
          />
        </div>

        <button
          type="button"
          onClick={() => setMobileOpen((open) => !open)}
          aria-expanded={mobileOpen}
          aria-controls="sim-bar-mobile-panel"
          className="flex items-center gap-1.5 rounded border border-slate-600 px-2 py-1 text-xs font-medium sm:hidden"
        >
          {mobileOpen ? (
            <X aria-hidden="true" className="size-3.5" />
          ) : (
            <Settings2 aria-hidden="true" className="size-3.5" />
          )}
          {chrome(locale, "session")}
        </button>
      </div>

      {mobileOpen ? (
        <div
          id="sim-bar-mobile-panel"
          className="flex flex-col gap-3 border-t border-slate-700 px-4 py-3 sm:hidden"
        >
          <SessionControls
            role={role}
            setRole={setRole}
            locale={locale}
            setLocale={setLocale}
            confirmingReset={confirmingReset}
            setConfirmingReset={setConfirmingReset}
            resetSession={resetSession}
            onServerReset={resetDemo}
            stacked
          />
        </div>
      ) : null}
    </div>
  );
}

function SessionControls({
  role,
  setRole,
  locale,
  setLocale,
  confirmingReset,
  setConfirmingReset,
  resetSession,
  onServerReset,
  stacked = false,
}: {
  role: Role;
  setRole: (role: Role) => void;
  locale: "en" | "ar";
  setLocale: (locale: "en" | "ar") => void;
  confirmingReset: boolean;
  setConfirmingReset: (value: boolean) => void;
  resetSession: () => void;
  onServerReset: () => Promise<void>;
  stacked?: boolean;
}) {
  const group = stacked
    ? "flex flex-col items-start gap-1.5"
    : "flex items-center gap-2";

  // This component is rendered twice (desktop row and mobile panel), so the
  // control ids must be unique per instance or the label points at the wrong,
  // hidden control.
  const roleSelectId = useId();

  return (
    <>
      {/* Simulated role. A native select is keyboard- and screen-reader-correct
          without pulling in a popover primitive. Switching role NEVER grants
          permission — the server stays authoritative. */}
      <div className={group}>
        <label
          htmlFor={roleSelectId}
          className="text-xs font-medium text-slate-400"
        >
          {chrome(locale, "simulatedRole")}
        </label>
        <select
          id={roleSelectId}
          value={role}
          onChange={(event) => setRole(event.target.value as Role)}
          className="rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs font-medium text-slate-100"
        >
          {ROLES.map((value) => (
            <option key={value} value={value}>
              {ROLE_LABELS[value][locale]}
            </option>
          ))}
        </select>
      </div>

      {/* Language. Arabic copy is unreviewed and is labelled as such (theme §3). */}
      <div className={group}>
        <span className="text-xs font-medium text-slate-400">
          {chrome(locale, "language")}
        </span>
        <div className="flex items-center gap-1" role="group" aria-label={chrome(locale, "language")}>
          <LangButton
            active={locale === "en"}
            onClick={() => setLocale("en")}
            label="EN"
            full="EN — English"
          />
          <LangButton
            active={locale === "ar"}
            onClick={() => setLocale("ar")}
            label="عربي"
            full="عربي — Arabic (unreviewed demo translation)"
          />
        </div>
      </div>

      {locale === "ar" ? (
        <span className="rounded border border-dashed border-slate-500 px-2 py-1 text-xs text-slate-300">
          Unreviewed demo translation
        </span>
      ) : null}

      {/* Reset. Two-step, overdue tokens, consequence stated (D002 §5). */}
      <div className={group}>
        {confirmingReset ? (
          <div
            role="alertdialog"
            aria-labelledby={`${roleSelectId}-reset-title`}
            aria-describedby={`${roleSelectId}-reset-desc`}
            className="flex flex-wrap items-center gap-2 rounded border border-status-overdue bg-status-overdue-bg px-2 py-1"
          >
            <span
              id={`${roleSelectId}-reset-title`}
              className="sr-only"
            >
              {chrome(locale, "resetConfirmAction")}
            </span>
            <span
              id={`${roleSelectId}-reset-desc`}
              className="text-xs font-medium text-status-overdue"
            >
              {chrome(locale, "resetConfirm")}
            </span>
            <button
              type="button"
              onClick={() => {
                void onServerReset();
                resetSession();
                setConfirmingReset(false);
              }}
              className="rounded bg-status-overdue px-2 py-1 text-xs font-semibold text-white hover:bg-status-overdue"
            >
              {chrome(locale, "resetConfirmAction")}
            </button>
            <button
              type="button"
              onClick={() => setConfirmingReset(false)}
              className="rounded border border-status-overdue px-2 py-1 text-xs font-medium text-status-overdue hover:bg-status-overdue-bg"
            >
              {chrome(locale, "cancel")}
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setConfirmingReset(true)}
            className="flex items-center gap-1.5 rounded border border-slate-600 px-2 py-1 text-xs font-medium hover:bg-slate-800"
          >
            <RotateCcw aria-hidden="true" className="size-3.5" />
            {chrome(locale, "resetDemo")}
          </button>
        )}
      </div>
    </>
  );
}

function LangButton({
  active,
  onClick,
  label,
  full,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  full: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      aria-label={full}
      className={cn(
        "rounded px-2 py-1 text-xs font-semibold",
        active
          ? "bg-slate-100 text-slate-900"
          : "border border-slate-600 text-slate-200",
      )}
    >
      {label}
    </button>
  );
}

/** Connection indicator. A demo that silently shows nothing is worse than one that says why. */
function ApiStatus({
  status,
  sessionId,
}: {
  status: "connecting" | "ready" | "unreachable";
  sessionId: string | null;
}) {
  const text =
    status === "ready"
      ? "API connected"
      : status === "connecting"
        ? "Connecting…"
        : "API unreachable";
  return (
    // role="status" both permits aria-label (a bare span does not) and is the
    // right semantics: connection state changes should be announced.
    <span
      role="status"
      aria-label={text}
      className={cn(
        "flex shrink-0 items-center gap-1.5 rounded border px-2 py-1 text-xs font-medium",
        status === "ready"
          ? "border-slate-600 text-slate-300"
          : status === "connecting"
            ? "border-slate-600 text-slate-400"
            : "border-status-overdue text-status-overdue",
      )}
      title={sessionId ? `Session ${sessionId}` : undefined}
    >
      <span
        aria-hidden="true"
        className={cn(
          "size-1.5 rounded-full",
          status === "ready"
            ? "bg-status-verified"
            : status === "connecting"
              ? "bg-slate-400"
              : "bg-status-overdue",
        )}
      />
      {/* Below 640px only the dot is shown; the bar must not overflow, and the
          accessible name still carries the full state. */}
      <span className="hidden sm:inline">{text}</span>
    </span>
  );
}
