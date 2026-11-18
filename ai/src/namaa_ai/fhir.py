"""FHIR R4 transaction proposals only. Never connects to HAPI or its database."""
from __future__ import annotations

import re
from uuid import NAMESPACE_URL, uuid5

from .contracts import Contract, ReviewedFact

CANONICAL = "https://namaa.example/fhir"  # explicitly provisional, not an approved IG
CONCEPT_TEXT = {
    "last_wcv": "Reported last well-child visit",
    "last_adult_screening": "Reported last adult screening",
    "caregiver_concern": "Reported caregiver concern",
    "tobacco_use": "Reported tobacco use",
}


class ValidationReport(Contract):
    fhir_version: str = "4.0.1"
    local_mapping_checks: str
    base_r4_validator: str = "pending: HL7 validator not installed or configured"
    namaa_profiles: str = "pending: Namaa conformance package not supplied"
    executable: bool = False


class TransactionProposal(Contract):
    bundle: dict
    validation: ValidationReport
    simulated: bool
    backend_requirements: tuple[str, ...] = (
        "Authenticate reviewer and scope all references to the authorized workspace/patient",
        "Journal command and payload hash; compare-and-swap proposal version atomically",
        "Resolve stable IDs against HAPI; attach If-Match to authorized updates and reconcile prior creates",
        "Validate base R4, Namaa profiles, terminology, references and authorization",
        "Execute through HAPI transaction gateway; reconcile uncertain outcomes before retry",
        "Reload committed versioned resources with review attestations before rule evaluation",
    )


def local_mapping_checks(bundle: dict) -> ValidationReport:
    """Allowlisted mapping checks, NOT a substitute for HL7 FHIRPath/terminology validation."""
    if bundle.get("resourceType") != "Bundle" or bundle.get("type") != "transaction":
        raise ValueError("Expected transaction Bundle")
    entries = bundle.get("entry", [])
    if len(entries) != 2:
        raise ValueError("Expected one reviewed resource and one Provenance")
    urls = [entry.get("fullUrl") for entry in entries]
    if len(set(urls)) != 2:
        raise ValueError("Duplicate fullUrl")
    for entry in entries:
        resource = entry["resource"]
        kind, rid = resource.get("resourceType"), resource.get("id", "")
        if kind not in {"Observation", "FamilyMemberHistory", "Provenance"} or not re.fullmatch(r"[A-Za-z0-9.-]{1,64}", rid):
            raise ValueError("Unsupported resource or logical id")
        if "modifierExtension" in resource or "extension" in resource:
            raise ValueError("This mapping supports no extensions")
        if entry["request"] != {"method": "PUT", "url": f"{kind}/{rid}"}:
            raise ValueError("Expected stable-id write proposal; backend resolves create/update preconditions")
    fact, provenance = [entry["resource"] for entry in entries]
    if fact["resourceType"] == "Observation":
        if fact.get("status") != "final" or not fact.get("code", {}).get("text") or not fact.get("valueString"):
            raise ValueError("Invalid Observation mapping")
        patient = fact.get("subject", {}).get("reference", "")
    elif fact["resourceType"] == "FamilyMemberHistory":
        if fact.get("status") != "partial" or not fact.get("relationship", {}).get("text"):
            raise ValueError("Invalid FamilyMemberHistory mapping")
        patient = fact.get("patient", {}).get("reference", "")
    else:
        raise ValueError("First entry must be a reviewed clinical resource")
    if not re.fullmatch(r"Patient/[A-Za-z0-9.-]{1,64}", patient):
        raise ValueError("Patient reference required")
    if provenance.get("resourceType") != "Provenance" or not provenance.get("recorded"):
        raise ValueError("Provenance required")
    if provenance.get("target") != [{"reference": urls[0]}] or len(provenance.get("agent", [])) != 2:
        raise ValueError("Provenance must target the resource with human and model agents")
    if not re.fullmatch(r"DocumentReference/[A-Za-z0-9.-]{1,64}/_history/[A-Za-z0-9.-]{1,64}", provenance["entity"][0]["what"]["reference"]):
        raise ValueError("Versioned source required")
    return ValidationReport(local_mapping_checks="passed (allowlisted subset only)")


def propose_transaction(reviewed: ReviewedFact) -> TransactionProposal:
    if not isinstance(reviewed, ReviewedFact):
        raise TypeError("Only an authorized ReviewedFact can be mapped")
    reviewed = ReviewedFact.model_validate(reviewed.model_dump())
    fact, proposal, command = reviewed.fact, reviewed.proposal, reviewed.review
    if fact.subject == "family_member":
        if fact.proposed_resource_type != "FamilyMemberHistory" or fact.concept != "family_condition" or not fact.relationship:
            raise ValueError("Unsafe relative mapping")
        resource = {"resourceType": "FamilyMemberHistory", "status": "partial",
                    "patient": {"reference": proposal.patient_reference},
                    "relationship": {"text": fact.relationship}, "date": reviewed.source_date.isoformat(),
                    "note": [{"text": f"{fact.assertion}: {fact.value_text}"}]}
        # An absent or uncertain statement must never produce a positive condition.
        if fact.assertion in {"present", "historical"}:
            resource["condition"] = [{"code": {"text": fact.value_text},
                                      "note": [{"text": f"Source assertion: {fact.assertion}; explicit event date: {fact.effective_date or 'unknown'}"}]}]
    else:
        if fact.proposed_resource_type != "Observation" or fact.concept not in CONCEPT_TEXT or fact.relationship:
            raise ValueError("Unsupported patient mapping")
        resource = {"resourceType": "Observation", "status": "final",
                    "code": {"text": CONCEPT_TEXT[fact.concept]}, "subject": {"reference": proposal.patient_reference},
                    "valueString": fact.value_text,
                    "component": [{"code": {"text": "Source assertion"}, "valueCodeableConcept": {"text": fact.assertion}}]}
        if fact.effective_date:
            resource["effectiveDateTime"] = fact.effective_date.isoformat()
    seed = f"namaa-review/{proposal.workspace_id}/{proposal.patient_reference}/{proposal.id}/{command.request_id}"
    rid, pid = str(uuid5(NAMESPACE_URL, seed)), str(uuid5(NAMESPACE_URL, seed + "/provenance"))
    resource["id"] = rid
    resource["identifier"] = [{"system": CANONICAL + "/review-command", "value": f"{proposal.workspace_id}:{command.request_id}"}]
    source = f"DocumentReference/{proposal.source_document_id}/_history/{proposal.source_document_version}"
    resource.setdefault("note", []).append({"text": f"Reviewed source {source}; quote [{reviewed.offset_start},{reviewed.offset_end}) Unicode code points: {fact.excerpt}"})
    tag = "simulated" if proposal.model.simulated else "synthetic-data"
    resource["meta"] = {"tag": [{"system": CANONICAL + "/data-mode", "code": tag}]}
    provenance = {
        "resourceType": "Provenance", "id": pid, "target": [{"reference": f"urn:uuid:{rid}"}],
        "recorded": reviewed.reviewed_at.isoformat(),
        "activity": {"text": f"Human review: {command.action}; reason: {command.reason}; proposal {proposal.id} version {proposal.version}"},
        "agent": [
            {"type": {"text": "Human reviewer"}, "who": {"reference": command.reviewer_reference}},
            {"type": {"text": "Simulated extraction" if proposal.model.simulated else "Model extraction"}, "who": {"reference": "#model"}},
        ],
        "contained": [{"resourceType": "Device", "id": "model", "status": "active",
                       "deviceName": [{"name": proposal.model.model_id, "type": "model-name"}],
                       "version": [{"type": {"text": "Model revision"}, "value": proposal.model.model_revision},
                                   {"type": {"text": "Prompt version"}, "value": proposal.model.prompt_version}]}],
        "entity": [{"role": "source", "what": {"reference": source, "display": f"SHA-256 {proposal.source_sha256}"}}],
    }
    bundle = {"resourceType": "Bundle", "type": "transaction", "entry": [
        {"fullUrl": f"urn:uuid:{r['id']}", "resource": r,
         "request": {"method": "PUT", "url": f"{r['resourceType']}/{r['id']}"}}
        for r in (resource, provenance)
    ]}
    return TransactionProposal(bundle=bundle, validation=local_mapping_checks(bundle), simulated=proposal.model.simulated)
