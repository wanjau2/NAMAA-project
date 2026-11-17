import Link from "next/link";
import { AlertTriangle, ArrowRight } from "lucide-react";

/**
 * Guest entry / Welcome (theme §5).
 * Centred card on the canvas, explicit synthetic-data notice, one primary CTA,
 * no credentials. Entering starts a fresh isolated synthetic session.
 */
export default function GuestEntryPage() {
  return (
    <div className="flex min-h-[calc(100vh-2.75rem)] items-center justify-center px-4 py-12">
      <div className="w-full max-w-xl rounded-lg border border-border bg-surface p-8 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
          Population Health Challenge 04
        </p>

        <h1 className="mt-2 text-2xl text-ink">Namaa</h1>

        <p className="mt-3 text-base text-ink-muted">
          Finds possible preventive care gaps, explains the evidence behind each
          one, routes it to authorized human review, and tracks the next action
          through attendance and documented follow-up.
        </p>

        {/* Needs-review tokens: this notice is a caveat, not an error. */}
        <section className="mt-6 rounded-lg border border-s-4 border-status-review border-s-status-review bg-status-review-bg p-4">
          <h2 className="flex items-center gap-2 text-base font-semibold text-status-review">
            <AlertTriangle aria-hidden="true" className="size-4 shrink-0" />
            Synthetic demonstration only
          </h2>
          <ul className="mt-2 space-y-1 text-sm text-ink">
            <li>
              Every patient, note, date and count is fictional. No real patient
              data is present.
            </li>
            <li>
              Invitations, bookings and role switching are simulated. Nothing is
              sent to anyone.
            </li>
            <li>
              Pathway rules are unvalidated demonstration logic, not clinical
              guidance. Not for clinical use.
            </li>
          </ul>
        </section>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
          <Link
            href="/cases"
            className="inline-flex items-center justify-center gap-2 rounded-md bg-brand px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-hover"
          >
            Start Synthetic Demo Session
            <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
          <p className="text-xs text-ink-muted">
            No credentials required. Your session is isolated and resets from the
            bar above.
          </p>
        </div>
      </div>
    </div>
  );
}
