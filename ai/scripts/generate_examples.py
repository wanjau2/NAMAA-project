"""Run from ai/ after editable installation. Only fictional, offline examples."""
import asyncio
import json
from pathlib import Path

from namaa_ai.adapters import HostedAdapter, HostedConfig, PROTOCOL, MODEL_ID, PROMPT_VERSION
from namaa_ai.contracts import ExtractionRequest, ModelIdentity, ProposedFact, VerifiedContext
from namaa_ai.demo import run_demo, simulated_snapshot
from namaa_ai.rules import evaluate
from namaa_ai.validation import make_proposals

OUT = Path("examples")
OUT.mkdir(exist_ok=True)


def save(name, value):
    (OUT / f"{name}.json").write_text(json.dumps(value, indent=2) + "\n")


demo = asyncio.run(run_demo())
demo["extraction"]["latency_ms"] = 0  # representative example, not a latency measurement
save("extraction-request", demo["request"])
save("extraction-result", demo["extraction"])
save("extraction-proposal", demo["extraction"]["proposals"][0])
save("review-accept", demo["review_decisions"][0]["command"])
family = demo["extraction"]["proposals"][1]["fact"]
wrong = ProposedFact.model_validate(family | {"subject": "patient", "relationship": None, "proposed_resource_type": "Observation"})
bad_proposal = make_proposals(ExtractionRequest.model_validate(demo["request"]), (wrong,), ModelIdentity(model_revision="simulated-fixture-v1", simulated=True))[0]
save("correction-extraction-proposal", bad_proposal.model_dump(mode="json"))
save("review-correct", demo["review_decisions"][0]["command"] | {"proposal_id": bad_proposal.id, "request_id": "demo-correction", "action": "correct", "reason": "The source attributes asthma to the mother, not the patient. Correct subject and mapping; date remains unknown.", "correction": family, "acknowledged_issues": ["missing_date"]})
save("review-reject", demo["review_decisions"][0]["command"] | {"request_id": "demo-rejection", "action": "reject", "reason": "Reviewer rejects this statement for the demonstration."})
save("reviewed-fact", demo["review_decisions"][0]["fact"])
for name, tx in zip(("observation", "family-history"), demo["transaction_proposals"]):
    save(f"{name}-transaction", tx["bundle"])
    save(f"{name}-validation", tx["validation"])
save("rule-evaluation", demo["after_simulated_commit"])
save("rule-needs-review", demo["before_reviewed_commit"])
save("rule-input-snapshot", simulated_snapshot([t["bundle"]["entry"][0]["resource"] for t in demo["transaction_proposals"]]).model_dump(mode="json"))
ctx = VerifiedContext.model_validate(dict(workspace_id="offline-demo", patient_reference="Patient/demo-patient", generation_id="generation-demo-1", mapping_version="mapping-v1", permission_revision="permissions-v1", built_at="2026-11-18T08:00:00Z", verified_at="2026-11-18T09:00:00Z", expires_at="2026-11-18T09:01:00Z", state="current", authorized=True, source_verified=True, completeness="partial", checked_scope="Fictional patient journey; no exhaustive absence checks", records=[dict(source=dict(reference="Observation/demo-observation", version="opaque-v1"), patient_reference="Patient/demo-patient", source_last_updated="2026-11-18T08:30:00Z", verified_at="2026-11-18T09:00:00Z", authorized=True, source_verified=True, text="Fictional source-verified record summary supplied by the backend.")]))
save("verified-context", ctx.model_dump(mode="json"))
# Sentinel configuration used ONLY to render a request. Never sent to any endpoint.
adapter = HostedAdapter(HostedConfig("https://example.invalid/extract", "not-a-real-token", "0" * 40))
save("endpoint-request", adapter.payload(ExtractionRequest.model_validate(demo["request"]), False))
save("endpoint-response", dict(protocol=PROTOCOL, model_id=MODEL_ID, model_revision="0"*40, prompt_version=PROMPT_VERSION, output={"facts": [p["fact"] for p in demo["extraction"]["proposals"]]}))
