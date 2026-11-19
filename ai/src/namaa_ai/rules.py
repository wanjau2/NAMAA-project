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
    snapshot = RuleSnapshot.model_validate(snapshot.model_dump())
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
        if not record.reviewed or not record.review_reference.strip():
            missing.append(f"Unreviewed input: {v.reference}")
        if r.get("modifierExtension"):
            missing.append("Unsupported modifier extension")
        resources.append(r)
    if snapshot.patient_reference not in seen:
        missing.append("Versioned Patient resource")
    if not snapshot.complete_for_rule:
        missing.append("Authoritative retrieval incomplete for this rule")

    # Familial findings remain about the relative. They explain the review
    # context but never infer patient diagnosis, eligibility or a shorter interval.
    if rule_id == "DEMO_ADULT_01":
        for record in snapshot.resources:
            r = record.resource
            if (record.reviewed and record.review_reference.strip() and not r.get("modifierExtension")
                    and r.get("resourceType") == "FamilyMemberHistory"
                    and r.get("status") in {"partial", "completed"} and r.get("condition")):
                factors.append(f"Reviewed family history: FamilyMemberHistory/{r['id']}; "
                               "relative's finding only; adult screening history still required")

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
    try:
        due = event_date + timedelta(days=interval_days)
    except OverflowError:
        missing.append("Last-event date exceeds supported calculation range")
        return result("needs_review")
    factors += [f"Reviewed last event: {event_date}", f"Fictional interval: {interval_days} days; due on {due}"]
    return result("gap_identified" if snapshot.as_of >= due else "no_gap_identified_in_available_data", due)


def rules_for_reviewed_commit(snapshot: RuleSnapshot, changed: ResourceVersion) -> tuple[str, ...]:
    """Backend post-commit routing, never called with an uncommitted proposal.

    Ismail's outbox calls this only after reloading a reviewed HAPI version.
    Routing requests evaluation; it does not authorize screening or any write.
    """
    if not isinstance(snapshot, RuleSnapshot):
        raise TypeError("Rule routing requires an authoritative committed snapshot")
    snapshot = RuleSnapshot.model_validate(snapshot.model_dump())
    if not snapshot.authorized:
        raise PermissionError("Backend snapshot authorization required")
    records = [r for r in snapshot.resources
               if f"{r.resource.get('resourceType')}/{r.resource.get('id')}" == changed.reference]
    if len(records) != 1:
        return ()
    record = records[0]
    r = record.resource
    if (not record.reviewed or not record.review_reference.strip()
            or r.get("meta", {}).get("versionId") != changed.version):
        return ()
    if r.get("subject", r.get("patient", {})).get("reference") != snapshot.patient_reference:
        raise PermissionError("Resource patient scope mismatch")
    if r.get("resourceType") == "FamilyMemberHistory":
        return ("DEMO_ADULT_01",)
    if r.get("resourceType") == "Observation":
        code = r.get("code", {}).get("text")
        return tuple(rule for rule, (eligibility, concept, _) in RULES.items()
                     if code in {eligibility, CONCEPT_TEXT[concept]})
    return ()
