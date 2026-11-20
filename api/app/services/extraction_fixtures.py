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
        concern = (
            "Caregiver attended with the child today and raised a question about speech development."
        )
        last_wcv = (
            'She reports the child has not had a check-up "in a long while" but cannot recall the date, '
            "and the family moved from another emirate last year."
        )
        return [
            {
                "id": "prop-1101",
                "concept": "Caregiver concern",
                "value_text": "raised a question about speech development",
                "subject": "patient",
                "assertion": "present",
                "effective_date": None,
                "proposed_resource_type": "Observation",
                "excerpt": concern,
                "offset_start": text.index(concern),
                "offset_end": text.index(concern) + len(concern),
            },
            {
                "id": "prop-1102",
                "concept": "Last well-child visit",
                "value_text": 'not had a check-up "in a long while" but cannot recall the date',
                "subject": "patient",
                "assertion": "uncertain",
                "effective_date": None,
                "proposed_resource_type": "Observation",
                "excerpt": last_wcv,
                "offset_start": text.index(last_wcv),
                "offset_end": text.index(last_wcv) + len(last_wcv),
            },
        ]

    if document_id == "doc-synthetic-31":
        family = "States that a sibling was diagnosed with bowel cancer in their fifties."
        screening = "Patient has never had bowel screening as far as they recall."
        return [
            {
                "id": "prop-3101",
                "concept": "Family history",
                "value_text": "sibling was diagnosed with bowel cancer",
                "subject": "family_member",
                "assertion": "present",
                "effective_date": None,
                "proposed_resource_type": "FamilyMemberHistory",
                "excerpt": family,
                "offset_start": text.index(family),
                "offset_end": text.index(family) + len(family),
            },
            {
                "id": "prop-3102",
                "concept": "Bowel screening",
                "value_text": "never had bowel screening as far as they recall",
                "subject": "patient",
                "assertion": "absent",
                "effective_date": None,
                "proposed_resource_type": "Observation",
                "excerpt": screening,
                "offset_start": text.index(screening),
                "offset_end": text.index(screening) + len(screening),
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
        "id": "doc-synthetic-01",
        "patient_id": "pat-synthetic-12",
        "case_id": "case-0002",
        "version": 1,
        "document_date": "2024-03-02T00:00:00Z",
        "text": "Synthetic child note: last well-child visit recorded as 2024-03-02. Not a live extraction source.",
    },
    {
        "id": "doc-synthetic-31",
        "patient_id": "pat-synthetic-31",
        "case_id": "case-0003",
        "version": 1,
        "document_date": "2026-10-02T11:00:00Z",
        "text": ADULT_NOTE,
    },
    {
        "id": "doc-synthetic-04",
        "patient_id": "pat-synthetic-32",
        "case_id": "case-0004",
        "version": 1,
        "document_date": "2023-01-15T00:00:00Z",
        "text": "Synthetic adult note: last recorded preventive visit 2023-01-15. Not a live extraction source.",
    },
    {
        "id": "doc-synthetic-05",
        "patient_id": "pat-synthetic-33",
        "case_id": "case-0005",
        "version": 1,
        "document_date": "2022-08-20T00:00:00Z",
        "text": "Synthetic adult note: last adult screening 2022-08-20. Not a live extraction source.",
    },
    {
        "id": "doc-synthetic-06",
        "patient_id": "pat-synthetic-13",
        "case_id": "case-0006",
        "version": 1,
        "document_date": "2025-01-10T00:00:00Z",
        "text": "Synthetic child note: last well-child visit 2026-11-01. Not a live extraction source.",
    },
]