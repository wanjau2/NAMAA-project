"""Offline fixture harness; explicitly simulates authorization and FHIR commit."""
from copy import deepcopy
from datetime import datetime, timezone

from .adapters import MockAdapter
from .contracts import ExtractionRequest, ReviewCommand, RuleSnapshot, VerifiedResource
from .fhir import propose_transaction
from .review import apply_review
from .rules import evaluate


class DemoAuthorizer:
    """Only for the fixed fictional CLI demonstration. Not an authentication system."""
    def require_review(self, command, proposal):
        if (command.reviewer_reference, proposal.workspace_id, proposal.patient_reference) != (
                "Practitioner/demo-reviewer", "offline-demo", "Patient/demo-patient") or not proposal.model.simulated:
            raise PermissionError("Outside simulated reviewer scope")


def simulated_snapshot(reviewed_resources, *, rule_id="DEMO_WCV_01"):
    patient = {"resourceType": "Patient", "id": "demo-patient", "meta": {"versionId": "demo-v1"}}
    eligibility = {"resourceType": "Observation", "id": "demo-eligibility", "meta": {"versionId": "demo-v1"},
                   "status": "final", "subject": {"reference": "Patient/demo-patient"},
                   "code": {"text": "Demo WCV eligibility" if rule_id == "DEMO_WCV_01" else "Demo adult eligibility"}, "valueBoolean": True}
    resources = [patient, eligibility]
    for resource in reviewed_resources:
        r = deepcopy(resource)
        r.setdefault("meta", {})["versionId"] = "simulated-commit-v1"
        resources.append(r)
    return RuleSnapshot(workspace_id="offline-demo", patient_reference="Patient/demo-patient", as_of="2026-11-18",
                        authority="simulated_fhir", authorized=True, complete_for_rule=True,
                        resources=tuple(VerifiedResource(resource=r, review_reference="simulated-review-receipt", reviewed=True) for r in resources))


async def run_demo():
    statements = [
        ("The patient attended a well-child visit on 2026-09-01.", "last_wcv", "2026-09-01", None),
        ("Mother has asthma.", "family_condition", None, "mother"),
    ]
    facts = [{"concept": concept, "value_text": text, "subject": "family_member" if relation else "patient",
              "assertion": "present", "effective_date": day, "excerpt": text,
              "proposed_resource_type": "FamilyMemberHistory" if relation else "Observation", "relationship": relation}
             for text, concept, day, relation in statements]
    request = ExtractionRequest(request_id="demo-extraction", workspace_id="offline-demo", patient_reference="Patient/demo-patient",
                                source_id="demo-note", source_version="v1", source_date="2026-11-18",
                                note_text=" ".join(s[0] for s in statements))
    extraction = await MockAdapter({request.note_text: {"facts": facts}}).extract(request)
    transactions, decisions = [], []
    for index, proposal in enumerate(extraction.proposals):
        command = ReviewCommand(request_id=f"demo-human-review-{index}", proposal_id=proposal.id, expected_proposal_version=1,
                                action="accept", reviewer_reference="Practitioner/demo-reviewer",
                                reason="Scripted fictional reviewer explicitly accepts the quoted statement for this local demonstration.",
                                acknowledged_issues=tuple(i.code for i in proposal.issues if i.severity == "review"))
        decision = apply_review(request, proposal, command, current_version=1,
                                reviewed_at=datetime(2026, 11, 18, 9, tzinfo=timezone.utc), authorizer=DemoAuthorizer())
        decisions.append(decision.model_dump(mode="json"))
        transactions.append(propose_transaction(decision.fact))
    before = evaluate(simulated_snapshot([]), "DEMO_WCV_01")
    after = evaluate(simulated_snapshot([t.bundle["entry"][0]["resource"] for t in transactions]), "DEMO_WCV_01")
    return {"notice": "SIMULATED extraction, reviewer authorization and FHIR commit; no live model or HAPI calls",
            "request": request.model_dump(mode="json"), "extraction": extraction.model_dump(mode="json"),
            "review_decisions": decisions, "transaction_proposals": [t.model_dump(mode="json") for t in transactions],
            "before_reviewed_commit": before.model_dump(mode="json"), "after_simulated_commit": after.model_dump(mode="json")}
