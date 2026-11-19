# Alfred handoff: demo engagement and population metrics

These are synthetic product artifacts for Mark and Ismail. The copy is a draft
requiring team approval before it is shown as approved or used in any outreach.
The AI package does not send SMS, WhatsApp, or portal messages.

## Message handling

English templates are typed in `src/namaa_ai/engagement.py`; the JSON examples
are generated from those contracts. Copy avoids patient names, condition names,
screening instructions, appointment claims, urgency, and claims that a message
was sent. It offers a contact choice and a way to decline further demo reminders.

The current prototype is English-only. If the trusted backend preference is not
English or is missing, do not silently substitute English: withhold automated
copy and route to an authorized human contact workflow. Ismail must verify
workspace/patient scope, caregiver authority, purpose, communication preference,
consent/opt-out state, permitted channel, and current policy before any send.
Client payloads and model output are not evidence of those permissions.

## Metric definitions

`MetricDefinition` records the unit, numerator, denominator, exclusions, period,
version, and privacy requirements. The current definitions cover evidence-backed
completion, time to verified attendance, overdue active tasks, and recorded
responses to simulated invitations.

Count distinct patient-pathway units where appropriate. Completion requires
verified Encounter, Procedure or DiagnosticReport evidence, reviewer authorization,
and a completed disposition; attendance alone, bookings and generated proposals
do not count as completion. The completion definition is now `demo-1.1.0`. Report
the denominator and reporting period with each rate. A care-gap completion rate
is not a model accuracy metric. Model calibration is **not available** because
the extractor emits no probability scores and the rules are not a calibrated
predictive model.

Metric definitions mark counts below 10 for suppression and require
complementary suppression. Ismail must enforce this in the server-side reporting
projection before values reach Mark's browser; hiding a value in frontend code is
not sufficient. For each released total, suppress enough additional cells that
subtraction cannot recover a hidden count. Do not expose hidden counts in tooltips,
exports, APIs, or alternate breakdowns.

`analytics.suppress_population()` implements a conservative pure policy over
backend-prepared `MetricCount` rows. Supply the complete fixed publication family
(overview plus every related segment) together. If any count, denominator or
complement is below 10, all numeric values in the release are null, including
rates and denominators. A common suppression reason avoids identifying which
cell triggered suppression. Denominator labels and projection version remain.
Zero counts are suppressed too. When every cell and complement is at least 10,
explicit counts, denominators and rates are published.

Ismail must generate both overview and segments from that same release before
selecting views; calling the function on individual rows defeats complementary
protection. The function does not query a database or authenticate access.
Fixed cohorts, safe public segment labels, cross-release differencing controls,
projection rebuilding and endpoint wiring remain backend responsibilities.

## Review and limitations

The copy is English-only, synthetic, and pending team review. It is not clinical
advice or a clinically approved translation. Metrics are definitions for a
synthetic demonstration, not validated measures. No compliance claim follows
from these controls.
