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


def source_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def alfred_concept(label: str) -> str:
    return CONCEPT_MAP.get(label, label.replace(" ", "_").lower()[:64])


def proposal_to_alfred(p: Proposal) -> dict[str, Any]:
    issues = json.loads(p.issues_json or "[]")
    return {
        "id": p.id,
        "version": p.version,
        "state": p.review_state if p.review_state == "proposed" else p.review_state,
        "workspace_id": p.workspace_id,
        "patient_reference": f"Patient/{p.patient_id}",
        "source_document_id": p.document_id,
        "source_document_version": str(p.document_version),
        "source_sha256": p.source_sha256,
        "fact": {
            "concept": alfred_concept(p.concept) if " " in p.concept else p.concept,
            "value_text": p.value_text,
            "subject": p.subject,
            "assertion": p.assertion,
            "effective_date": p.effective_date,
            "excerpt": p.excerpt,
            "proposed_resource_type": p.proposed_resource_type,
            "relationship": p.relationship,
        },
        "offset_start": p.offset_start,
        "offset_end": p.offset_end,
        "offset_unit": "unicode_code_points",
        "issues": issues,
        "model": {
            "model_id": p.model_id,
            "model_revision": p.model_revision,
            "prompt_version": p.prompt_version,
            "simulated": p.model_simulated,
        },
        "review_state": p.review_state,
        "review_reason": p.review_reason,
        "reviewer_reference": p.reviewer_reference,
        "reviewed_at": p.reviewed_at,
    }
