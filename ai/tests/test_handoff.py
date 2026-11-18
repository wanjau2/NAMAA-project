import json
from pathlib import Path

import pytest

from namaa_ai import contracts
from namaa_ai.contracts import AssembledContext, ContextQuery
from namaa_ai.fhir import local_mapping_checks

EXAMPLES = Path(__file__).parents[1] / "examples"


@pytest.mark.parametrize("filename,model", [
    ("extraction-request", contracts.ExtractionRequest), ("extraction-result", contracts.ExtractionResult),
    ("extraction-proposal", contracts.ExtractionProposal), ("review-accept", contracts.ReviewCommand),
    ("correction-extraction-proposal", contracts.ExtractionProposal),
    ("review-correct", contracts.ReviewCommand), ("review-reject", contracts.ReviewCommand),
    ("reviewed-fact", contracts.ReviewedFact), ("rule-evaluation", contracts.RuleEvaluation),
    ("rule-needs-review", contracts.RuleEvaluation), ("rule-input-snapshot", contracts.RuleSnapshot),
    ("verified-context", contracts.VerifiedContext), ("endpoint-response", contracts.EndpointResponse),
    ("condition-extraction-proposal", contracts.ExtractionProposal),
    ("condition-review-command", contracts.ReviewCommand),
    ("context-query", ContextQuery), ("assembled-context", AssembledContext),
])
def test_handoff_examples_match_contract(filename, model):
    model.model_validate_json((EXAMPLES / f"{filename}.json").read_text())


def test_published_schemas_are_current():
    for path in (EXAMPLES / "schemas").glob("*.json"):
        assert json.loads(path.read_text()) == getattr(contracts, path.stem).model_json_schema()


@pytest.mark.parametrize("kind", ["observation", "family-history"])
def test_fhir_examples_are_locally_checked_and_pending_official_validation(kind):
    report = local_mapping_checks(json.loads((EXAMPLES / f"{kind}-transaction.json").read_text()))
    assert report.model_dump() == json.loads((EXAMPLES / f"{kind}-validation.json").read_text())


def test_condition_transaction_example_is_review_gated_and_locally_checked():
    bundle = json.loads((EXAMPLES / "condition-transaction.json").read_text())
    report = local_mapping_checks(bundle)
    assert report.executable is False
    resource = bundle["entry"][0]["resource"]
    assert resource["resourceType"] == "Condition"
    assert resource["subject"]["reference"].startswith("Patient/")
