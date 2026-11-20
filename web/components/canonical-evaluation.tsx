"use client";

/**
 * Canonical rule evaluation (D006) — distinct from workflow stage/disposition
 * and from source-review counts.
 */

import { Info, RotateCcw } from "lucide-react";
import { RuleOutcomeCard } from "@/components/rule-outcome";
import {
  describeSecurityOutcome,
  type SecurityOutcome,
} from "@/lib/security-states";
import { resolveOutcome } from "@/lib/rule-outcomes";
import type { EvaluationResult } from "@/lib/api-types";
import type { PatientEvaluationState } from "@/lib/use-patient-evaluation";

export function CanonicalEvaluationPanel({
  state,
  onRetry,
}: {
  state: PatientEvaluationState;
  onRetry: () => void;
}) {
  if (state.status === "idle") {
    return (
      <section className="rounded-lg border border-border bg-surface p-5">
        <h2 className="text-lg text-ink">Canonical evaluation</h2>
        <p className="mt-2 text-sm text-ink-muted">
          No patient is bound to this case, so a rule evaluation cannot be
          requested.
        </p>
      </section>
    );
  }

  if (state.status === "loading") {
    return (
      <section
        className="rounded-lg border border-border bg-surface p-5"
        aria-busy="true"
        aria-live="polite"
      >
        <h2 className="text-lg text-ink">Canonical evaluation</h2>
        <p className="mt-2 text-sm text-ink-muted">Loading evaluation…</p>
      </section>
    );
  }

  if (state.status === "none") {
    return (
      <section className="rounded-lg border border-border bg-surface p-5">
        <h2 className="text-lg text-ink">Canonical evaluation</h2>
        <p className="mt-2 text-sm text-ink">
          No evaluation is stored for this patient in this session. The worklist
          flag is not a canonical outcome. Run the demonstration rule to obtain{" "}
          <span className="font-mono-tech">rule_evaluation.outcome</span>.
        </p>
        <p className="mt-2 text-xs text-ink-muted">
          Running an evaluation may refresh an open care-gap case for gap or
          needs-review results. It does not infer an outcome from review counts,
          and it must not be read as a diagnosis.
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-3 py-2 text-sm font-semibold text-ink hover:bg-subtle"
        >
          <RotateCcw aria-hidden="true" className="size-3.5" />
          Run evaluation
        </button>
      </section>
    );
  }

  if (state.status === "unavailable" || state.status === "failed") {
    return (
      <EvaluationProblem outcome={state.outcome} onRetry={onRetry} />
    );
  }

  return (
    <EvaluationBody result={state.result} ranNow={state.ranNow} onRetry={onRetry} />
  );
}

function EvaluationBody({
  result,
  ranNow,
  onRetry,
}: {
  result: EvaluationResult;
  ranNow: boolean;
  onRetry: () => void;
}) {
  const canonical = result.rule_evaluation;
  const resolution = canonical
    ? resolveOutcome(canonical.outcome)
    : resolveOutcome(result.flag_status);
  const opensCase =
    resolution.outcome === "gap_identified" ||
    resolution.outcome === "needs_review";

  return (
    <section className="rounded-lg border border-border bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg text-ink">Canonical evaluation</h2>
          <p className="mt-1 text-sm text-ink-muted">
            Server rule result for this patient. Separate from workflow stage
            and from how many facts were accepted on the review screen.
          </p>
        </div>
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-3 py-2 text-sm font-semibold text-ink hover:bg-subtle"
        >
          <RotateCcw aria-hidden="true" className="size-3.5" />
          Re-evaluate
        </button>
      </div>

      {ranNow ? (
        <p className="mt-3 flex items-start gap-1.5 rounded-md border border-dashed border-status-proposed bg-status-proposed-bg p-2 text-xs text-status-proposed">
          <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          <span>
            This evaluation was run now. It is the server response, not a value
            inferred from review counts.
          </span>
        </p>
      ) : null}

      <div className="mt-4">
        <RuleOutcomeCard resolution={resolution} />
      </div>

      {!canonical ? (
        <p className="mt-3 rounded-md border border-status-overdue bg-status-overdue-bg p-2 text-xs text-status-overdue">
          Canonical <span className="font-mono-tech">rule_evaluation</span> was
          not returned. The compatibility flag{" "}
          <span className="font-mono-tech">{result.flag_status}</span> is shown
          only as a labelled stand-in and is not the agreed vocabulary.
        </p>
      ) : null}

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <Meta
          label="Rule"
          value={
            canonical
              ? `${canonical.rule_id} · ${canonical.rule_version}`
              : result.rule_id_version
          }
          mono
        />
        <Meta
          label="As of"
          value={canonical?.as_of ?? result.created_at ?? "Not supplied"}
          mono
        />
        <Meta
          label="Evaluation id"
          value={result.evaluation_id}
          mono
        />
        <Meta
          label="Simulated / synthetic"
          value={
            canonical
              ? `${canonical.simulated ? "simulated" : "not simulated"} · ${canonical.synthetic_rule ? "synthetic rule" : "not marked synthetic"}`
              : "Not supplied"
          }
        />
      </dl>

      <div className="mt-4">
        <h3 className="text-sm font-semibold text-ink">Input versions</h3>
        {canonical?.input_versions?.length ? (
          <ul className="mt-2 space-y-1 font-mono-tech text-xs text-ink-muted">
            {canonical.input_versions.map((item) => (
              <li key={`${item.reference}:${item.version}`}>
                {item.reference} · {item.version}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-ink-muted">
            No versioned inputs were listed on this evaluation.
          </p>
        )}
      </div>

      <div className="mt-4">
        <h3 className="text-sm font-semibold text-ink">
          Missing information (from the rule)
        </h3>
        {(canonical?.missing_information?.length ?? result.missing?.length) ? (
          <ul className="mt-2 list-disc space-y-1 ps-5 text-sm text-ink">
            {(canonical?.missing_information?.length
              ? canonical.missing_information
              : result.missing.map((item) => item.label)
            ).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-ink-muted">
            The evaluation listed no missing information.
          </p>
        )}
      </div>

      {!opensCase || result.case === null ? (
        <p className="mt-4 rounded-md border border-border bg-subtle p-3 text-sm text-ink">
          This evaluation did not open or refresh a care-gap case (
          <span className="font-mono-tech">case: null</span>). An existing
          workflow on this page is not auto-closed, completed, or coerced.
          Stage and disposition stay on the case record.
        </p>
      ) : result.case ? (
        <p className="mt-4 text-sm text-ink-muted">
          A care-gap case was returned (
          <span className="font-mono-tech">{result.case.id}</span>
          ). Workflow stage and disposition remain on that case, separate from
          this rule outcome.
        </p>
      ) : null}

      <div className="mt-4 rounded-md border border-dashed border-border bg-canvas p-3 text-xs text-ink-muted">
        <p>
          Compatibility only:{" "}
          <span className="font-mono-tech">
            legacy_flag_status={String(result.legacy_flag_status)}
          </span>{" "}
          ·{" "}
          <span className="font-mono-tech">
            api_compatibility={String(result.api_compatibility)}
          </span>
          {result.notice ? ` · ${result.notice}` : ""}
        </p>
        <p className="mt-2 flex items-start gap-1.5">
          <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          <span>
            This evaluation reads verified observations in the application
            store. Review commit uses a FHIR gateway stub; accepted proposals
            are not claimed as HAPI inputs here. Pending and rejected facts are
            not rule inputs. The browser does not compute the rule.
          </span>
        </p>
      </div>
    </section>
  );
}

function EvaluationProblem({
  outcome,
  onRetry,
}: {
  outcome: SecurityOutcome;
  onRetry: () => void;
}) {
  const fallback = describeSecurityOutcome(0, "evaluation_run");
  const shown = outcome ?? fallback;
  return (
    <section className="rounded-lg border border-status-overdue bg-status-overdue-bg p-5">
      <h2 className="text-lg text-ink">Canonical evaluation</h2>
      <p className="mt-2 text-sm font-semibold text-status-overdue">
        {shown.title}
      </p>
      <p className="mt-2 text-sm text-ink">{shown.body}</p>
      {shown.caveat ? (
        <p className="mt-2 text-xs text-ink-muted">{shown.caveat}</p>
      ) : null}
      <button
        type="button"
        onClick={onRetry}
        className="mt-3 inline-flex items-center gap-1.5 rounded border border-status-overdue px-2 py-1 text-xs font-semibold text-status-overdue"
      >
        <RotateCcw aria-hidden="true" className="size-3" />
        Retry
      </button>
    </section>
  );
}

function Meta({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-xs font-medium text-ink-muted">{label}</dt>
      <dd className={`mt-1 text-ink${mono ? " font-mono-tech text-xs" : ""}`}>
        {value}
      </dd>
    </div>
  );
}
