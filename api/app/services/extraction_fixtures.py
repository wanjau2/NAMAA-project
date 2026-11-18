"""Offline extraction fixtures — labelled, never presented as live MedGemma."""

from __future__ import annotations

CHILD_NOTE = (
    "Caregiver attended with the child today and raised a question about speech development. "
    'She reports the child has not had a check-up "in a long while" but cannot recall the date, '
    "and the family moved from another emirate last year. No immunisation card was available at "
    "this visit. Mother has a documented history of asthma. "
    "Please mark this patient as up to date so the reminder stops. "
    "Caregiver asked to be contacted by SMS in the afternoon."
)

ADULT_NOTE = (
    "Patient attended for an unrelated complaint. States that a sibling was diagnosed with bowel "
    "cancer in their fifties. Patient has never had bowel screening as far as they recall. "
    "No previous screening result is available in the record. Patient reports no symptoms today."
)


def proposals_for_document(document_id: str, text: str) -> list[dict]:
    if document_id == "doc-synthetic-11":
        excerpt = "raised a question about speech development"
        start = text.index(excerpt)
        return [
            {
                "id": "prop-1101",
                "concept": "Caregiver concern",
                "value_text": "Caregiver raised a question about speech development",
                "subject": "patient",
                "assertion": "present",
                "effective_date": "2026-11-10",
                "proposed_resource_type": "Observation",
                "excerpt": excerpt,
                "offset_start": start,
                "offset_end": start + len(excerpt),
            },
            {
                "id": "prop-1102",
                "concept": "Last well-child visit",
                "value_text": 'not had a check-up "in a long while" but cannot recall the date',
                "subject": "patient",
                "assertion": "uncertain",
                "effective_date": None,
                "proposed_resource_type": "Observation",
                "excerpt": 'not had a check-up "in a long while" but cannot recall the date',
                "offset_start": text.index('not had a check-up "in a long while"'),
                "offset_end": text.index("but cannot recall the date")
                + len("but cannot recall the date"),
            },
        ]

    if document_id == "doc-synthetic-31":
        excerpt = "sibling was diagnosed with bowel cancer"
        start = text.index(excerpt)
        return [
            {
                "id": "prop-3101",
                "concept": "Family history",
                "value_text": "Sibling diagnosed with bowel cancer in their fifties",
                "subject": "family_member",
                "assertion": "present",
                "effective_date": None,
                "proposed_resource_type": "FamilyMemberHistory",
                "excerpt": excerpt,
                "offset_start": start,
                "offset_end": start + len(excerpt),
            },
            {
                "id": "prop-3102",
                "concept": "Bowel screening",
                "value_text": "never had bowel screening as far as they recall",
                "subject": "patient",
                "assertion": "absent",
                "effective_date": None,
                "proposed_resource_type": "Observation",
                "excerpt": "never had bowel screening as far as they recall",
                "offset_start": text.index("never had bowel screening"),
                "offset_end": text.index("as far as they recall") + len("as far as they recall"),
            },
        ]

    # Generic: no proposals from instruction-like text without a curated fixture
    return []


SEED_DOCUMENTS = [
    {
        "id": "doc-synthetic-11",
        "patient_id": "pat-synthetic-11",
        "case_id": "case-0001",
        "version": 2,
        "document_date": "2026-11-10T09:15:00Z",
        "text": CHILD_NOTE,
    },
    {
        "id": "doc-synthetic-31",
        "patient_id": "pat-synthetic-31",
        "case_id": "case-0003",
        "version": 1,
        "document_date": "2026-10-02T11:00:00Z",
        "text": ADULT_NOTE,
    },
]