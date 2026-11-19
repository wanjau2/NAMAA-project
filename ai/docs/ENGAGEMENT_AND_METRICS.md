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

Count distinct patient-pathway units where appropriate. Use verified attendance
evidence; bookings and generated proposals do not count as completion. Report
the denominator and reporting period with each rate. A care-gap completion rate
is not a model accuracy metric. Model calibration is **not available** because
the extractor emits no probability scores and the rules are not a calibrated
predictive model.

Metric definitions mark counts below 10 for suppression and require
complementary suppression. Ismail must enforce this in the server-side reporting
projection before values reach Mark's browser; hiding a value in frontend code is
not sufficient. For each released total, suppress enough additional cells that
subtraction cannot recover a hidden count. Do not expose hidden counts in tooltips,
exports, APIs, or alternate breakdowns. The AI package defines this requirement;
it does not replace the API's aggregate privacy implementation or its tests.

## Review and limitations

The copy is English-only, synthetic, and pending team review. It is not clinical
advice or a clinically approved translation. Metrics are definitions for a
synthetic demonstration, not validated measures. No compliance claim follows
from these controls.
