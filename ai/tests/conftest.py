import json
from pathlib import Path

import pytest

from namaa_ai.contracts import ExtractionRequest, ModelIdentity, ProposedFact
from namaa_ai.validation import make_proposals


@pytest.fixture
def corpus():
    return json.loads((Path(__file__).parents[1] / "fixtures/notes.json").read_text())["notes"]


@pytest.fixture
def request_note():
    return ExtractionRequest(request_id="test-extraction", workspace_id="offline-demo", patient_reference="Patient/demo-patient",
                             source_id="source-1", source_version="v1", source_date="2026-11-18",
                             note_text="The patient attended a well-child visit on 2026-09-01.")


@pytest.fixture
def fact(request_note):
    return ProposedFact(concept="last_wcv", value_text=request_note.note_text, subject="patient", assertion="present",
                        effective_date="2026-09-01", excerpt=request_note.note_text, proposed_resource_type="Observation", relationship=None)


@pytest.fixture
def proposal(request_note, fact):
    return make_proposals(request_note, (fact,), ModelIdentity(model_revision="simulated-fixture-v1", simulated=True))[0]
