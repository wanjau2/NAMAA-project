"use client";

/**
 * Action panel (theme §5, work plan F3).
 *
 * Rules this panel implements:
 *  - Only actions valid for the current stage and disposition are offered.
 *  - Actions belonging to another role are shown, not hidden, in an
 *    aria-disabled state with a visible reason (D002 §2).
 *  - Every mutation carries action name + expected revision + request id.
 *  - The UI does not advance state itself; it renders what came back.
 *  - A failed submit PRESERVES entered input and explains the failure.
 *  - Simulated actions say so, inside the form, every time.
 */

import { useMemo, useState } from "react";
import {
  AlertOctagon,
  CheckCircle2,
  ChevronDown,
  Info,
  RotateCcw,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useDemoSession, type Role } from "@/lib/demo-session";
import { useCaseStore } from "@/lib/case-store";
import {
  ACTIONS,
  type ActionRequest,
  type ActionSpec,
  type CaseState,
  type FieldSpec,
  type StructuredError,
} from "@/lib/case-actions";

const ROLE_WORDS: Record<Role, string> = {
  coordinator: "Coordinator",
  clinical_reviewer: "Clinical Reviewer",
  population_analyst: "Population Analyst",
};

export function ActionPanel({ caseState }: { caseState: CaseState }) {
  const { role } = useDemoSession();
  const [openAction, setOpenAction] = useState<string | null>(null);

  // Actions that make sense for this stage, whatever the current role. Actions
  // for another role stay visible so the governance boundary is legible.
  const applicable = useMemo(
    () => ACTIONS.filter((spec) => spec.applies(caseState)),
    [caseState],
  );

  return (
    <section className="rounded-lg border border-border bg-surface p-5">
      <h2 className="text-lg text-ink">Actions</h2>
      <p className="mt-1 text-xs text-ink-muted">
        Valid next actions for{" "}
        <span className="font-mono-tech">
          {caseState.stage}/{caseState.disposition}
        </span>{" "}
        at <span className="font-mono-tech">rev {caseState.revision}</span>. The
        server validates every transition and records an event.
      </p>

      {applicable.length === 0 ? (
        <p className="mt-4 rounded-md border border-border bg-subtle p-3 text-sm text-ink-muted">
          No actions are valid from this state.
        </p>
      ) : (
        <ul className="mt-4 space-y-2">
          {applicable.map((spec) => (
            <li key={spec.id}>
              <ActionRow
                spec={spec}
                caseState={caseState}
                role={role}
                open={openAction === spec.id}
                onToggle={() =>
                  setOpenAction((current) =>
                    current === spec.id ? null : spec.id,
                  )
                }
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ActionRow({
  spec,
  caseState,
  role,
  open,
  onToggle,
}: {
  spec: ActionSpec;
  caseState: CaseState;
  role: Role;
  open: boolean;
  onToggle: () => void;
}) {
  const permitted = role === spec.role;
  const blocked = spec.precondition?.(caseState) ?? null;
  const reasonId = `gate-${spec.id}`;
  const canOpen = permitted && !blocked;

  return (
    <div
      className={cn(
        "rounded-md border",
        open ? "border-brand-focus bg-canvas" : "border-border bg-surface",
      )}
    >
      <button
        type="button"
        aria-disabled={!canOpen}
        aria-expanded={open}
        aria-describedby={canOpen ? undefined : reasonId}
        onClick={() => {
          if (!canOpen) return;
          onToggle();
        }}
        className={cn(
          "flex w-full items-center justify-between gap-2 px-3 py-2.5 text-start text-sm font-semibold",
          canOpen
            ? "text-ink hover:bg-subtle"
            : "cursor-not-allowed text-ink-muted",
        )}
      >
        <span className="flex items-center gap-2">
          {spec.label}
          {spec.simulated ? (
            <span className="rounded border border-dashed border-status-proposed px-1.5 py-0.5 text-xs font-medium text-status-proposed">
              Simulated
            </span>
          ) : null}
        </span>
        <ChevronDown
          aria-hidden="true"
          className={cn("size-4 shrink-0 transition-transform", open && "rotate-180")}
        />
      </button>

      {/* Visible, announced reason. Never a tooltip only. */}
      {!canOpen ? (
        <p
          id={reasonId}
          className="flex items-start gap-1.5 border-t border-border px-3 py-2 text-xs text-ink-muted"
        >
          <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          <span>
            {blocked ??
              `Requires the ${ROLE_WORDS[spec.role]} role. Switch role in the simulation bar to demonstrate this step.`}
          </span>
        </p>
      ) : null}

      {open && canOpen ? (
        <ActionForm spec={spec} caseState={caseState} onDone={onToggle} />
      ) : null}
    </div>
  );
}

function initialValues(spec: ActionSpec): Record<string, string | boolean> {
  const values: Record<string, string | boolean> = {};
  for (const field of spec.fields) {
    values[field.name] =
      field.kind === "checkbox" ? false : field.options?.[0]?.value ?? "";
  }
  return values;
}

function ActionForm({
  spec,
  caseState,
  onDone,
}: {
  spec: ActionSpec;
  caseState: CaseState;
  onDone: () => void;
}) {
  const { submit, newRequestId } = useCaseStore();
  const [values, setValues] = useState(() => initialValues(spec));
  const [error, setError] = useState<StructuredError | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState(false);

  // One request id per form instance. A retry after a failure reuses it, which
  // is exactly the idempotency semantic the server expects.
  const [requestId, setRequestId] = useState(() => newRequestId());

  // Captured when the form opened. If the case moved on, the submit is stale.
  const [openedAtRevision] = useState(caseState.revision);
  const stale = caseState.revision !== openedAtRevision;

  function set(name: string, value: string | boolean) {
    setValues((prev) => ({ ...prev, [name]: value }));
  }

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    const request: ActionRequest = {
      action: spec.id,
      expected_revision: openedAtRevision,
      request_id: requestId,
      data: values,
    };
    const result = submit(caseState.id, request);
    if (result.ok) {
      setError(null);
      setDuplicate(result.duplicate);
      setSuccess(
        result.duplicate
          ? "Already recorded. The repeated request produced no second event."
          : `Recorded. ${result.event.prior_state} → ${result.event.new_state}.`,
      );
    } else {
      // Entered values are deliberately NOT cleared.
      setSuccess(null);
      setError(result.error);
    }
  }

  return (
    <form onSubmit={onSubmit} className="border-t border-border px-3 py-3">
      {spec.note ? (
        <p className="flex items-start gap-1.5 rounded-md border border-status-review bg-status-review-bg p-2 text-xs text-status-review">
          <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          <span>{spec.note}</span>
        </p>
      ) : null}

      {/* Stale-revision banner with a non-destructive recovery (D002 §4). */}
      {stale ? (
        <div className="mt-3 rounded-md border border-status-overdue bg-status-overdue-bg p-2">
          <p className="flex items-start gap-1.5 text-xs text-status-overdue">
            <AlertOctagon aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
            <span>
              This case changed since you opened the form (now{" "}
              <span className="font-mono-tech">rev {caseState.revision}</span>).
              Reload the latest state — your entries are kept.
            </span>
          </p>
          <button
            type="button"
            onClick={() => {
              setRequestId(newRequestId());
              setError(null);
              onDone();
            }}
            className="mt-2 inline-flex items-center gap-1.5 rounded border border-status-overdue px-2 py-1 text-xs font-semibold text-status-overdue"
          >
            <RotateCcw aria-hidden="true" className="size-3" />
            Reload latest state
          </button>
        </div>
      ) : null}

      <div className="mt-3 space-y-3">
        {spec.fields.map((field) => (
          <FieldInput
            key={field.name}
            field={field}
            value={values[field.name]}
            error={error?.field_errors[field.name]}
            onChange={(value) => set(field.name, value)}
          />
        ))}
      </div>

      {error ? (
        <p className="mt-3 flex items-start gap-1.5 rounded-md border border-status-overdue bg-status-overdue-bg p-2 text-xs text-status-overdue">
          <AlertOctagon aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          <span>
            {error.message}{" "}
            <span className="font-mono-tech">[{error.code}]</span>
          </span>
        </p>
      ) : null}

      {success ? (
        <p
          className={cn(
            "mt-3 flex items-start gap-1.5 rounded-md border p-2 text-xs",
            duplicate
              ? "border-status-review bg-status-review-bg text-status-review"
              : "border-status-verified bg-status-verified-bg text-status-verified",
          )}
        >
          <CheckCircle2 aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          <span>{success}</span>
        </p>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="submit"
          className={cn(
            "rounded-md px-3 py-1.5 text-xs font-semibold",
            spec.tone === "destructive"
              ? "bg-status-overdue text-white"
              : spec.tone === "primary"
                ? "bg-brand text-white hover:bg-brand-hover"
                : "border border-border bg-surface text-ink hover:bg-subtle",
          )}
        >
          {success ? "Submit again" : spec.label}
        </button>
        <button
          type="button"
          onClick={onDone}
          className="rounded-md border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-ink hover:bg-subtle"
        >
          Close
        </button>
      </div>

      {/* The exact envelope. Visible so the contract is concrete for Ismail. */}
      <details className="mt-3">
        <summary className="cursor-pointer text-xs font-medium text-ink-muted">
          Request envelope
        </summary>
        <pre className="mt-2 overflow-x-auto rounded-md bg-subtle p-2 font-mono-tech text-xs text-ink">
{JSON.stringify(
  {
    action: spec.id,
    expected_revision: openedAtRevision,
    request_id: requestId,
    data: values,
  },
  null,
  2,
)}
        </pre>
        <p className="mt-1 text-xs text-ink-muted">
          Not sent anywhere. Applied by the local simulation layer until the API
          lands.
        </p>
      </details>
    </form>
  );
}

function FieldInput({
  field,
  value,
  error,
  onChange,
}: {
  field: FieldSpec;
  value: string | boolean;
  error?: string;
  onChange: (value: string | boolean) => void;
}) {
  const id = `field-${field.name}`;
  const describedBy = [
    field.help ? `${id}-help` : null,
    error ? `${id}-error` : null,
  ]
    .filter(Boolean)
    .join(" ");

  const common = {
    id,
    "aria-invalid": error ? (true as const) : undefined,
    "aria-describedby": describedBy || undefined,
    className: cn(
      "w-full rounded-md border bg-surface px-2 py-1.5 text-sm text-ink",
      error ? "border-status-overdue" : "border-border",
    ),
  };

  return (
    <div>
      {field.kind === "checkbox" ? (
        <label htmlFor={id} className="flex items-start gap-2 text-sm text-ink">
          <input
            id={id}
            type="checkbox"
            checked={value === true}
            onChange={(event) => onChange(event.target.checked)}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy || undefined}
            className="mt-0.5 size-4 shrink-0 accent-[var(--brand-primary)]"
          />
          <span>{field.label}</span>
        </label>
      ) : (
        <>
          <label htmlFor={id} className="text-xs font-medium text-ink-muted">
            {field.label}
            {field.required ? (
              <span aria-hidden="true" className="text-status-overdue">
                {" "}
                *
              </span>
            ) : null}
          </label>
          <div className="mt-1">
            {field.kind === "select" ? (
              <select
                {...common}
                value={String(value)}
                onChange={(event) => onChange(event.target.value)}
              >
                {field.options?.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            ) : field.kind === "textarea" ? (
              <textarea
                {...common}
                rows={2}
                value={String(value)}
                placeholder={field.placeholder}
                onChange={(event) => onChange(event.target.value)}
              />
            ) : (
              <input
                {...common}
                type={
                  field.kind === "date"
                    ? "date"
                    : field.kind === "number"
                      ? "number"
                      : "text"
                }
                value={String(value)}
                placeholder={field.placeholder}
                onChange={(event) => onChange(event.target.value)}
              />
            )}
          </div>
        </>
      )}

      {field.help ? (
        <p id={`${id}-help`} className="mt-1 text-xs text-ink-muted">
          {field.help}
        </p>
      ) : null}
      {error ? (
        <p
          id={`${id}-error`}
          className="mt-1 flex items-start gap-1.5 text-xs text-status-overdue"
        >
          <AlertOctagon aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          <span>{error}</span>
        </p>
      ) : null}
    </div>
  );
}
