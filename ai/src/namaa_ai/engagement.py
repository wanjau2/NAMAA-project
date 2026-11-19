"""English-only, non-sending demo copy and population metric definitions."""
from .contracts import EngagementTemplate, MetricDefinition


TEMPLATES = (
    EngagementTemplate(
        template_id="demo-prevention-sms-v1", channel="sms", language="en",
        purpose="prevention_reminder",
        text="Your care team has a preventive health update for you. Contact them when convenient to discuss your options. No action is required based on this message. Reply STOP to decline demo reminders.",
        review_status="human_review_required_before_demo",
    ),
    EngagementTemplate(
        template_id="demo-followup-portal-v1", channel="portal", language="en",
        purpose="follow_up_choice",
        text="Your care team would like to discuss preventive care options with you. You can choose a convenient time, ask for another contact method, or decline further reminders.",
        review_status="human_review_required_before_demo",
    ),
    EngagementTemplate(
        template_id="demo-prevention-whatsapp-v1", channel="whatsapp", language="en",
        purpose="prevention_reminder",
        text="Your care team has a preventive health update for you. Contact them when convenient to discuss your options. You may decline further demo reminders at any time.",
        review_status="human_review_required_before_demo",
    ),
)


METRICS = (
    MetricDefinition(
        metric_id="gap-completion-rate", version="demo-1.0.0",
        name="Evidence-backed care-gap completion rate",
        unit_of_analysis="patient_pathway",
        aggregation="rate",
        numerator="Distinct eligible patient-pathways with verified attendance evidence during the reporting period",
        denominator="Distinct eligible patient-pathways with an identified gap at the start of the reporting period",
        exclusions=("needs_review", "not_eligible", "declined without attendance evidence"),
        reporting_period="cohort_followup",
    ),
    MetricDefinition(
        metric_id="median-time-to-attendance", version="demo-1.0.0",
        name="Median days from gap identification to verified attendance",
        unit_of_analysis="patient_pathway",
        aggregation="median",
        numerator="Elapsed calendar days from first gap identification to verified attendance evidence",
        denominator="Patient-pathways with both valid timestamps and verified attendance evidence",
        exclusions=("open pathways", "missing timestamps", "unverified booking or attendance"),
        reporting_period="cohort_followup",
    ),
    MetricDefinition(
        metric_id="overdue-task-rate", version="demo-1.0.0",
        name="Overdue active follow-up task rate",
        unit_of_analysis="task",
        aggregation="rate",
        numerator="Active tasks past their due time at the reporting instant",
        denominator="Active tasks with a valid due time at the reporting instant",
        exclusions=("closed tasks", "tasks without a due time"),
        reporting_period="point_in_time",
    ),
    MetricDefinition(
        metric_id="invitation-response-rate", version="demo-1.0.0",
        name="Recorded response rate to simulated invitations",
        unit_of_analysis="patient_pathway",
        aggregation="rate",
        numerator="Distinct invited patient-pathways with a recorded accept or decline response",
        denominator="Distinct patient-pathways with a simulated invitation in the reporting period",
        exclusions=("undelivered or unsent invitations", "no recorded response"),
        reporting_period="calendar_month",
    ),
)


def select_template(*, language: str, channel: str, purpose: str) -> EngagementTemplate:
    """Return demo copy only; this function does not authorize or send messages."""
    if language != "en":
        raise ValueError("unsupported_language_for_current_demo")
    for template in TEMPLATES:
        if (template.language, template.channel, template.purpose) == (language, channel, purpose):
            return template
    raise ValueError("no_demo_template_for_requested_channel_and_purpose")
