"use client";

/**
 * Case inspector — application identifiers plus live audit and outbox reads.
 *
 * Identifiers are synthetic application ids, not HAPI resources. Case revision
 * is a concurrency token, not a FHIR version. Outbox rows are the stub FHIR
 * gateway, not a HAPI commit.
 */

import { useEffect, useState, type ReactNode } from "react";
import { AlertOctagon, Info, Lock } from "lucide-react";
import { api, errorHttpStatus } from "@/lib/api";
import type { AuditEventOut, CaseOut, OutboxRow } from "@/lib/api-types";
import { chrome } from "@/lib/copy";
import { useCaseStore } from "@/lib/case-store";
import { useDemoSession } from "@/lib/demo-session";
import {
  describeSecurityOutcome,
  type SecurityOutcome,
} from "@/lib/security-states";

type Load<T> =
  | { kind: "loading" }
  | { kind: "ready"; rows: T[] }
  | { kind: "denied"; outcome: SecurityOutcome }
  | { kind: "failed"; outcome: SecurityOutcome };

export function CaseInspector({ caseState }: { caseState: CaseOut }) {
  const { locale, role, sessionEpoch } = useDemoSession();
  const { sessionId, status } = useCaseStore();
  const [reloadToken, setReloadToken] = useState(0);
  const [audit, setAudit] = useState<Load<AuditEventOut>>({ kind: "loading" });
  const [outbox, setOutbox] = useState<Load<OutboxRow>>({ kind: "loading" });

  useEffect(() => {
    if (status !== "ready" || !sessionId) return;
    let cancelled = false;
    (async () => {
      const [nextAudit, nextOutbox] = await Promise.all([
        loadAudit(sessionId, role, caseState.patient_id),
        loadOutbox(sessionId, role, caseState.id),
      ]);
      if (!cancelled) {
        setAudit(nextAudit);
        setOutbox(nextOutbox);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [
    status,
    sessionId,
    role,
    sessionEpoch,
    reloadToken,
    caseState.id,
    caseState.patient_id,
  ]);

  const retry = () => {
    setAudit({ kind: "loading" });
    setOutbox({ kind: "loading" });
    setReloadToken((n) => n + 1);
  };

  const evidence = caseState.detail.completion_evidence;

  return (
    <section className="rounded-lg border border-border bg-subtle p-4">
      <h2 className="text-sm font-semibold text-ink">
        {chrome(locale, "inspectorTitle")}
      </h2>
      <p className="mt-1 text-xs text-ink-muted">
        Synthetic application store. HAPI is not deployed. FHIR commit uses the
        gateway stub. Case revision is a concurrency token, not a resource
        version.
      </p>

      <dl className="mt-3 space-y-1 text-xs">
        <Meta label="Case" value={caseState.id} />
        <Meta
          label="Patient (application id)"
          value={caseState.patient_id ?? "—"}
        />
        <Meta label="Care-gap id (application)" value={caseState.care_gap_id} />
        <Meta label="Case revision (concurrency)" value={String(caseState.revision)} />
        {evidence?.evidence_reference ? (
          <Meta
            label="Completion evidence (as recorded)"
            value={evidence.evidence_reference}
          />
        ) : null}
      </dl>

      <ListBlock
        title="Audit (this patient)"
        load={audit}
        empty="No audit events for this patient in this session."
        onRetry={audit.kind === "failed" ? retry : undefined}
        render={(row) => (
          <li key={row.id} className="py-1.5">
            <p className="font-mono-tech text-ink-muted">{row.timestamp}</p>
            <p className="text-ink">
              {row.action}
              {row.decision ? ` · ${row.decision}` : ""}
            </p>
            <p className="font-mono-tech text-ink-muted">
              {[row.resource_type, row.resource_id].filter(Boolean).join("/") ||
                "—"}
              {row.reason_code ? ` · ${row.reason_code}` : ""}
            </p>
          </li>
        )}
      />

      <ListBlock
        title="Outbox (this case)"
        load={outbox}
        empty="No outbox entries for this case in this session."
        onRetry={outbox.kind === "failed" ? retry : undefined}
        render={(row) => (
          <li key={row.id} className="py-1.5">
            <p className="font-mono-tech text-ink-muted">{row.updated_at}</p>
            <p className="text-ink">
              {row.action} · {row.state}
            </p>
            <p className="text-ink-muted">
              Stub FHIR gateway
              {row.last_error ? ` · ${row.last_error}` : ""}
            </p>
          </li>
        )}
      />

      <p className="mt-3 flex items-start gap-1.5 text-xs text-ink-muted">
        <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
        <span>
          Policy adapter is synthetic_guest_v1. production_authorization is
          false. Nothing here is a HAPI persistence claim.
        </span>
      </p>
    </section>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-wrap justify-between gap-2">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="font-mono-tech text-ink">{value}</dd>
    </div>
  );
}

function ListBlock<T>({
  title,
  load,
  empty,
  render,
  onRetry,
}: {
  title: string;
  load: Load<T>;
  empty: string;
  render: (row: T) => ReactNode;
  onRetry?: () => void;
}) {
  return (
    <div className="mt-4">
      <h3 className="text-xs font-semibold text-ink">{title}</h3>
      {load.kind === "loading" ? (
        <p className="mt-1 text-xs text-ink-muted">Loading…</p>
      ) : load.kind === "denied" || load.kind === "failed" ? (
        <div className="mt-1">
          <p className="flex items-start gap-1.5 text-xs text-ink-muted">
            {load.kind === "denied" ? (
              <Lock aria-hidden="true" className="mt-0.5 size-3 shrink-0" />
            ) : (
              <AlertOctagon aria-hidden="true" className="mt-0.5 size-3 shrink-0" />
            )}
            <span>
              {load.outcome.body}
              {load.outcome.caveat ? ` ${load.outcome.caveat}` : ""}
            </span>
          </p>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="mt-1 text-xs font-semibold text-ink underline-offset-2 hover:underline"
            >
              Retry
            </button>
          ) : null}
        </div>
      ) : load.rows.length === 0 ? (
        <p className="mt-1 text-xs text-ink-muted">{empty}</p>
      ) : (
        <ul className="mt-1 divide-y divide-border text-xs">{load.rows.slice(0, 8).map(render)}</ul>
      )}
    </div>
  );
}

async function loadAudit(
  sessionId: string,
  role: Parameters<typeof api.listAuditEvents>[1],
  patientId: string | null,
): Promise<Load<AuditEventOut>> {
  try {
    const rows = await api.listAuditEvents(sessionId, role);
    return {
      kind: "ready",
      rows: patientId
        ? rows.filter((row) => row.patient_id === patientId)
        : [],
    };
  } catch (caught) {
    const httpStatus = errorHttpStatus(caught);
    const outcome = describeSecurityOutcome(httpStatus, "audit_read");
    if (httpStatus === 401 || httpStatus === 403 || httpStatus === 404) {
      return { kind: "denied", outcome };
    }
    return { kind: "failed", outcome };
  }
}

async function loadOutbox(
  sessionId: string,
  role: Parameters<typeof api.listOutbox>[1],
  caseId: string,
): Promise<Load<OutboxRow>> {
  try {
    const rows = await api.listOutbox(sessionId, role);
    return {
      kind: "ready",
      rows: rows.filter((row) => row.case_id === caseId),
    };
  } catch (caught) {
    const httpStatus = errorHttpStatus(caught);
    const outcome = describeSecurityOutcome(httpStatus, "outbox_read");
    if (httpStatus === 401 || httpStatus === 403 || httpStatus === 404) {
      return { kind: "denied", outcome };
    }
    return { kind: "failed", outcome };
  }
}
