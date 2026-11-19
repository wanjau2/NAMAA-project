"""Alfred-shaped proposal serialization (outside FHIR until review commit)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.models import Proposal

CONCEPT_MAP = {
    "Caregiver concern": "caregiver_concern",
    "Last well-child visit": "last_wcv",
    "Family history": "family_condition",
    "Bowel screening": "last_adult_screening",
}

# Alfred ModelIdentity requires this literal (I03).
ALFRED_PROMPT_VERSION = "extract-v1.0.1"


def source_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def alfred_concept(label: str) -> str:
    return CONCEPT_MAP.get(label, label.replace(" ", "_").lower()[:64])


def proposal_to_alfred(
    p: Proposal,
    *,
    version: int | None = None,
    fact_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Canonical ExtractionProposal wire shape — no review envelope fields (I03).

    Alfred's ExtractionProposal.state is always `proposed` on the extraction
    contract. Review decisions bind the original proposed snapshot separately.
    """
    issues = json.loads(p.issues_json or "[]")
    fact = fact_override or {
        "concept": alfred_concept(p.concept) if " " in (p.concept or "") else p.concept,
        "value_text": p.value_text,
        "subject": p.subject,
        "assertion": p.assertion,
        "effective_date": p.effective_date,
        "excerpt": p.excerpt,
        "proposed_resource_type": p.proposed_resource_type,
        "relationship": p.relationship,
    }
    return {
        "id": p.id,
        "version": int(version if version is not None else p.version),
        "state": "proposed",
        "workspace_id": p.workspace_id,
        "patient_reference": f"Patient/{p.patient_id}",
        "source_document_id": p.document_id,
        "source_document_version": str(p.document_version),
        "source_sha256": p.source_sha256,
        "fact": fact,
        "offset_start": p.offset_start,
        "offset_end": p.offset_end,
        "offset_unit": "unicode_code_points",
        "issues": issues,
        "model": {
            "model_id": p.model_id or "google/medgemma-1.5-4b-it",
            "model_revision": p.model_revision or "offline-fixture-v1",
            "prompt_version": ALFRED_PROMPT_VERSION,
            "simulated": bool(p.model_simulated),
        },
    }
