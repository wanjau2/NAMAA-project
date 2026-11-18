"""Fictional eligibility cards and intervals; these are NOT clinical schedules."""
from datetime import date, timedelta

from .contracts import ResourceVersion, RuleEvaluation, RuleSnapshot
from .fhir import CONCEPT_TEXT

RULES = {
    "DEMO_WCV_01": ("Demo WCV eligibility", "last_wcv", 37),
    "DEMO_ADULT_01": ("Demo adult eligibility", "last_adult_screening", 73),
}


def evaluate(snapshot: RuleSnapshot, rule_id: str) -> RuleEvaluation:
    if not isinstance(snapshot, RuleSnapshot):
        raise TypeError("Rules require a backend-authorized committed resource snapshot")
    if rule_id not in RULES:
        raise ValueError("Unsupported demonstration rule")
    if not snapshot.authorized:
        raise PermissionError("Backend snapshot authorization required")
    eligibility_code, history_concept, interval_days = RULES[rule_id]
    versions, missing, factors = [], [], []
    resources = []
    seen = set()
    for record in snapshot.resources:
        r = record.resource
        try:
            v = ResourceVersion(reference=f"{r['resourceType']}/{r['id']}", version=r["meta"]["versionId"])
        except (KeyError, ValueError):
            raise ValueError("Every input needs an authoritative resource reference and opaque version") from None
        versions.append(v)
        if v.reference in seen:
            missing.append("Duplicate or contradictory resource versions")
        seen.add(v.reference)
        if r["resourceType"] == "Patient":
            if v.reference != snapshot.patient_reference:
                raise PermissionError("Patient scope mismatch")
        elif r.get("subject", r.get("patient", {})).get("reference") != snapshot.patient_reference:
            raise PermissionError("Resource patient scope mismatch")
        if not record.reviewed:
            missing.append(f"Unreviewed input: {v.reference}")
        if r.get("modifierExtension"):
            missing.append("Unsupported modifier extension")
        resources.append(r)
    if snapshot.patient_reference not in seen:
        missing.append("Versioned Patient resource")
    if not snapshot.complete_for_rule:
        missing.append("Authoritative retrieval incomplete for this rule")

    def result(outcome, due=None):
        return RuleEvaluation(patient_reference=snapshot.patient_reference, as_of=snapshot.as_of,
                              rule_id=rule_id, outcome=outcome, input_versions=tuple(versions),
                              contributing_factors=tuple(factors), missing_information=tuple(dict.fromkeys(missing)),
                              due_date=due, simulated=snapshot.authority == "simulated_fhir")

    def observations(code):
        return [r for r in resources if r.get("resourceType") == "Observation" and r.get("code", {}).get("text") == code]

    eligibility = observations(eligibility_code)
    if not eligibility or any(type(r.get("valueBoolean")) is not bool or r.get("status") != "final" for r in eligibility):
        missing.append("Reviewed explicit fictional eligibility card")
    values = {r.get("valueBoolean") for r in eligibility if type(r.get("valueBoolean")) is bool}
    if len(values) > 1:
        missing.append("Contradictory fictional eligibility cards")
    if missing:
        return result("needs_review")
    factors.append(f"Fictional eligibility card: {next(iter(values))}")
    if values == {False}:
        return result("not_eligible")
    history = observations(CONCEPT_TEXT[history_concept])
    dates = set()
    if not history:
        missing.append("Reviewed explicit last-event date; absence of records is not a gap")
    for r in history:
        assertions = [c.get("valueCodeableConcept", {}).get("text") for c in r.get("component", []) if c.get("code", {}).get("text") == "Source assertion"]
        if assertions not in (["present"], ["historical"]) or r.get("status") != "final":
            missing.append("Last event is absent, uncertain, unreviewed or has conflicting assertions")
        try:
            event_date = date.fromisoformat(r["effectiveDateTime"])
            if event_date > snapshot.as_of:
                missing.append("Future last-event date")
            dates.add(event_date)
        except (KeyError, ValueError, TypeError):
            missing.append("Explicit last-event date")
    if len(dates) > 1:
        missing.append("Conflicting last-event dates; reconcile rather than select latest")
    if missing:
        return result("needs_review")
    event_date = next(iter(dates))
    due = event_date + timedelta(days=interval_days)
    factors += [f"Reviewed last event: {event_date}", f"Fictional interval: {interval_days} days; due on {due}"]
    return result("gap_identified" if snapshot.as_of >= due else "no_gap_identified_in_available_data", due)
