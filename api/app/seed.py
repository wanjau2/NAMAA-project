"""Synthetic seed aligned with web/lib/mock-data.ts case IDs."""

from __future__ import annotations

import json

SEED_PATIENTS = [
    {
        "id": "pat-synthetic-11",
        "label": "Child A (synthetic)",
        "age_band": "2–4 years",
        "caregiver_authority": "verified_caregiver",
    },
    {
        "id": "pat-synthetic-12",
        "label": "Child B (synthetic)",
        "age_band": "0–1 years",
        "caregiver_authority": "verified_caregiver",
    },
    {
        "id": "pat-synthetic-31",
        "label": "Adult C (synthetic)",
        "age_band": "45–49 years",
        "caregiver_authority": "self",
    },
    {
        "id": "pat-synthetic-32",
        "label": "Adult D (synthetic)",
        "age_band": "50–54 years",
        "caregiver_authority": "self",
    },
    {
        "id": "pat-synthetic-33",
        "label": "Adult E (synthetic)",
        "age_band": "55–59 years",
        "caregiver_authority": "self",
    },
    {
        "id": "pat-synthetic-13",
        "label": "Child F (synthetic)",
        "age_band": "5–9 years",
        "caregiver_authority": "verified_caregiver",
    },
]

SEED_OBSERVATIONS = [
    {
        "id": "obs-11-age",
        "patient_id": "pat-synthetic-11",
        "type": "age_band",
        "value": "2–4 years",
        "source": "Patient/pat-synthetic-11",
        "observed_time": "2026-11-10T09:15:00Z",
        "verified": True,
    },
    {
        "id": "obs-11-elig",
        "patient_id": "pat-synthetic-11",
        "type": "demo_eligibility",
        "value": "true",
        "source": "Patient/pat-synthetic-11",
        "observed_time": "2026-11-10T09:15:00Z",
        "verified": True,
    },
    {
        "id": "obs-11-visit",
        "patient_id": "pat-synthetic-11",
        "type": "last_wcv",
        "value": "Not documented in available records",
        "source": "DocumentReference/doc-synthetic-11",
        "observed_time": "2026-11-10T09:15:00Z",
        "missing_or_conflict": True,
        "verified": False,
    },
    {
        "id": "obs-12-elig",
        "patient_id": "pat-synthetic-12",
        "type": "demo_eligibility",
        "value": "true",
        "source": "Patient/pat-synthetic-12",
        "observed_time": "2024-03-02T00:00:00Z",
        "verified": True,
    },
    {
        "id": "obs-12-visit",
        "patient_id": "pat-synthetic-12",
        "type": "last_wcv",
        "value": "2024-03-02",
        "source": "DocumentReference/doc-synthetic-01",
        "observed_time": "2024-03-02T00:00:00Z",
        "verified": True,
    },
    {
        "id": "obs-13-elig",
        "patient_id": "pat-synthetic-13",
        "type": "demo_eligibility",
        "value": "true",
        "source": "Patient/pat-synthetic-13",
        "observed_time": "2026-11-01T00:00:00Z",
        "verified": True,
    },
    {
        "id": "obs-13-visit",
        "patient_id": "pat-synthetic-13",
        "type": "last_wcv",
        "value": "2026-11-01",
        "source": "DocumentReference/doc-synthetic-06",
        "observed_time": "2026-11-01T00:00:00Z",
        "verified": True,
    },
    {
        "id": "obs-31-elig",
        "patient_id": "pat-synthetic-31",
        "type": "demo_eligibility",
        "value": "true",
        "source": "Patient/pat-synthetic-31",
        "observed_time": "2026-10-02T11:00:00Z",
        "verified": True,
    },
    {
        "id": "obs-31-screening",
        "patient_id": "pat-synthetic-31",
        "type": "screening_window",
        "value": "None found in available records",
        "source": "Patient/pat-synthetic-31",
        "observed_time": "2026-10-02T11:00:00Z",
        "verified": True,
    },
    {
        "id": "obs-32-elig",
        "patient_id": "pat-synthetic-32",
        "type": "demo_eligibility",
        "value": "false",
        "source": "Patient/pat-synthetic-32",
        "observed_time": "2023-01-15T00:00:00Z",
        "verified": True,
    },
    {
        "id": "obs-33-elig",
        "patient_id": "pat-synthetic-33",
        "type": "demo_eligibility",
        "value": "true",
        "source": "Patient/pat-synthetic-33",
        "observed_time": "2022-08-20T00:00:00Z",
        "verified": True,
    },
    {
        "id": "obs-33-screening",
        "patient_id": "pat-synthetic-33",
        "type": "last_adult_screening",
        "value": "2022-08-20",
        "source": "DocumentReference/doc-synthetic-05",
        "observed_time": "2022-08-20T00:00:00Z",
        "verified": True,
    },
]

def _factors(*items: dict) -> str:
    return json.dumps(items)


def _missing(*items: dict) -> str:
    return json.dumps(items)


SEED_GAPS = [
    {
        "id": "gap-0001",
        "patient_id": "pat-synthetic-11",
        "pathway": "child_wcv",
        "rule_id_version": "DEMO_WCV_01",
        "flag_status": "needs_review",
        "explanation": (
            "DEMO_WCV_01 could not establish whether a well-child visit is due, because the "
            "last visit date is unknown. The rule returns needs review rather than an invitation."
        ),
        "suggested_review_action": (
            "Resolve the unknown last-visit date, then re-evaluate before any invitation"
        ),
        "uncertainty": "Last visit date unknown",
        "factors_json": _factors(
            {
                "label": "Caregiver concern recorded",
                "value": "Caregiver raised a developmental question at intake",
                "source": "DocumentReference/doc-synthetic-11",
                "observed_time": "2026-11-10T09:15:00Z",
                "verified": True,
            },
            {
                "label": "Age band",
                "value": "2–4 years",
                "source": "Patient/pat-synthetic-11",
                "observed_time": "2026-11-10T09:15:00Z",
                "verified": True,
            },
            {
                "label": "Last well-child visit",
                "value": "Not documented in available records",
                "source": "DocumentReference/doc-synthetic-11",
                "observed_time": "2026-11-10T09:15:00Z",
                "verified": False,
            },
        ),
        "missing_json": _missing(
            {
                "label": "Last well-child visit date is unknown",
                "consequence": (
                    "Cannot determine whether a visit is overdue. Unknown is not the same as up to date."
                ),
            },
            {
                "label": "External provider history not reconciled",
                "consequence": (
                    "A visit may exist outside these records. Do not invite before this is resolved."
                ),
            },
        ),
    },
    {
        "id": "gap-0002",
        "patient_id": "pat-synthetic-12",
        "pathway": "child_wcv",
        "rule_id_version": "DEMO_WCV_01",
        "flag_status": "gap",
        "explanation": (
            "Demonstration rule matched on the available verified records. This is a "
            "prioritization signal for human review, not a diagnosis or a screening instruction."
        ),
        "suggested_review_action": "Clinical reviewer to confirm eligibility",
        "factors_json": _factors(
            {
                "label": "Last recorded preventive visit",
                "value": "2024-03-02",
                "source": "DocumentReference/doc-synthetic-01",
                "observed_time": "2024-03-02T00:00:00Z",
                "verified": True,
            }
        ),
        "missing_json": _missing(
            {
                "label": "Completeness of external visit history not verified",
                "consequence": (
                    "An absent record means incomplete information, not that care was not needed."
                ),
            }
        ),
    },
    {
        "id": "gap-0003",
        "patient_id": "pat-synthetic-31",
        "pathway": "adult_screening",
        "rule_id_version": "DEMO_ADULT_01",
        "flag_status": "gap",
        "explanation": (
            "DEMO_ADULT_01 identified a screening gap from verified records. A referral was "
            "authorized after clinical review, then rejected by the receiving service."
        ),
        "suggested_review_action": (
            "Reassign the referral to an available service and record the rejection reason"
        ),
        "factors_json": _factors(
            {
                "label": "Family history recorded for a relative",
                "value": "Recorded as FamilyMemberHistory — not a patient diagnosis",
                "source": "FamilyMemberHistory/fmh-synthetic-31",
                "observed_time": "2026-10-02T11:00:00Z",
                "verified": True,
            },
            {
                "label": "No screening record within the configured window",
                "value": "None found in available records",
                "source": "Patient/pat-synthetic-31",
                "observed_time": "2026-10-02T11:00:00Z",
                "verified": True,
            },
        ),
        "missing_json": _missing(
            {
                "label": "Reason for referral rejection not yet recorded",
                "consequence": "The case stays owned and open. Rejection does not close it.",
            }
        ),
    },
    {
        "id": "gap-0004",
        "patient_id": "pat-synthetic-32",
        "pathway": "adult_screening",
        "rule_id_version": "DEMO_ADULT_01",
        "flag_status": "gap",
        "explanation": "Demonstration adult screening gap with a recorded decline.",
        "suggested_review_action": "Retain in eligible denominator; no further contact",
        "factors_json": _factors(
            {
                "label": "Last recorded preventive visit",
                "value": "2023-01-15",
                "source": "DocumentReference/doc-synthetic-04",
                "observed_time": "2023-01-15T00:00:00Z",
                "verified": True,
            }
        ),
        "missing_json": "[]",
    },
    {
        "id": "gap-0005",
        "patient_id": "pat-synthetic-33",
        "pathway": "adult_screening",
        "rule_id_version": "DEMO_ADULT_01",
        "flag_status": "gap",
        "explanation": "Demonstration adult screening gap with failed contact attempts.",
        "suggested_review_action": "Offer phone-assisted support",
        "factors_json": _factors(
            {
                "label": "Last recorded preventive visit",
                "value": "2022-08-20",
                "source": "DocumentReference/doc-synthetic-05",
                "observed_time": "2022-08-20T00:00:00Z",
                "verified": True,
            }
        ),
        "missing_json": "[]",
    },
    {
        "id": "gap-0006",
        "patient_id": "pat-synthetic-13",
        "pathway": "child_wcv",
        "rule_id_version": "DEMO_WCV_01",
        "flag_status": "gap",
        "explanation": "Demonstration child pathway closed with attendance evidence.",
        "suggested_review_action": "None — closed with evidence",
        "factors_json": _factors(
            {
                "label": "Last recorded preventive visit",
                "value": "2025-01-10",
                "source": "DocumentReference/doc-synthetic-06",
                "observed_time": "2025-01-10T00:00:00Z",
                "verified": True,
            }
        ),
        "missing_json": "[]",
    },
]

SEED_CASES = [
    {
        "id": "case-0001",
        "care_gap_id": "gap-0001",
        "patient_id": "pat-synthetic-11",
        "patient_label": "Child A (synthetic)",
        "age_band": "2–4 years",
        "pathway": "child_wcv",
        "rule_id_version": "DEMO_WCV_01",
        "flag_status": "needs_review",
        "stage": "identified",
        "disposition": "active",
        "owner": "Coordinator 1",
        "next_action": "Resolve unknown last-visit date before inviting",
        "due_time": "2026-11-18T12:00:00Z",
        "overdue": False,
        "revision": 1,
    },
    {
        "id": "case-0002",
        "care_gap_id": "gap-0002",
        "patient_id": "pat-synthetic-12",
        "patient_label": "Child B (synthetic)",
        "age_band": "0–1 years",
        "pathway": "child_wcv",
        "rule_id_version": "DEMO_WCV_01",
        "flag_status": "gap",
        "stage": "booked",
        "disposition": "active",
        "owner": "Coordinator 1",
        "next_action": "Confirm attendance after simulated appointment",
        "due_time": "2026-11-19T08:30:00Z",
        "overdue": False,
        "revision": 4,
        "contact_channel": "sms",
        "contact_language": "en",
        "contact_preferred_time": "morning",
    },
    {
        "id": "case-0003",
        "care_gap_id": "gap-0003",
        "patient_id": "pat-synthetic-31",
        "patient_label": "Adult C (synthetic)",
        "age_band": "45–49 years",
        "pathway": "adult_screening",
        "rule_id_version": "DEMO_ADULT_01",
        "flag_status": "gap",
        "stage": "follow_up",
        "disposition": "active",
        "owner": "Coordinator 2",
        "next_action": "Referral rejected — reassign owner",
        "due_time": "2026-11-16T15:00:00Z",
        "overdue": True,
        "revision": 7,
        "referral_outcome": "rejected",
        "contact_channel": "phone",
        "contact_language": "en",
        "contact_preferred_time": "afternoon",
    },
    {
        "id": "case-0004",
        "care_gap_id": "gap-0004",
        "patient_id": "pat-synthetic-32",
        "patient_label": "Adult D (synthetic)",
        "age_band": "50–54 years",
        "pathway": "adult_screening",
        "rule_id_version": "DEMO_ADULT_01",
        "flag_status": "gap",
        "stage": "invited",
        "disposition": "declined",
        "owner": "Coordinator 2",
        "next_action": "Record decline reason; remains in eligible denominator",
        "due_time": None,
        "overdue": False,
        "revision": 3,
        "contact_channel": "email",
        "contact_language": "en",
        "contact_preferred_time": "evening",
    },
    {
        "id": "case-0005",
        "care_gap_id": "gap-0005",
        "patient_id": "pat-synthetic-33",
        "patient_label": "Adult E (synthetic)",
        "age_band": "55–59 years",
        "pathway": "adult_screening",
        "rule_id_version": "DEMO_ADULT_01",
        "flag_status": "gap",
        "stage": "invited",
        "disposition": "unreachable",
        "owner": "Coordinator 1",
        "next_action": "Three contact attempts failed — offer phone-assisted support",
        "due_time": "2026-11-15T10:00:00Z",
        "overdue": True,
        "revision": 5,
        "contact_channel": "sms",
        "contact_language": "en",
        "contact_preferred_time": "morning",
    },
    {
        "id": "case-0006",
        "care_gap_id": "gap-0006",
        "patient_id": "pat-synthetic-13",
        "patient_label": "Child F (synthetic)",
        "age_band": "5–9 years",
        "pathway": "child_wcv",
        "rule_id_version": "DEMO_WCV_01",
        "flag_status": "gap",
        "stage": "closed",
        "disposition": "completed",
        "owner": "Coordinator 1",
        "next_action": "None — closed with attendance evidence",
        "due_time": None,
        "overdue": False,
        "revision": 9,
        "evidence_type": "Encounter",
        "evidence_reference": "Encounter/enc-synthetic-06",
        "contact_channel": "sms",
        "contact_language": "en",
        "contact_preferred_time": "morning",
    },
]

SEED_EVENTS = [
    {
        "id": "evt-0001-a",
        "case_id": "case-0001",
        "timestamp": "2026-11-10T09:20:00Z",
        "actor_role": "system",
        "action": "note_queued",
        "prior_state": "",
        "new_state": "identified/active",
    },
    {
        "id": "evt-0001-b",
        "case_id": "case-0001",
        "timestamp": "2026-11-14T08:00:00Z",
        "actor_role": "system",
        "action": "rule_evaluation",
        "prior_state": "identified/active",
        "new_state": "identified/active",
        "reason": "DEMO_WCV_01 returned needs_review (missing last-visit date)",
    },
    {
        "id": "evt-0003-a",
        "case_id": "case-0003",
        "timestamp": "2026-10-02T11:30:00Z",
        "actor_role": "system",
        "action": "rule_evaluation",
        "prior_state": "",
        "new_state": "identified/active",
        "reason": "DEMO_ADULT_01 identified a screening gap",
    },
    {
        "id": "evt-0003-b",
        "case_id": "case-0003",
        "timestamp": "2026-10-03T08:10:00Z",
        "actor_role": "clinical_reviewer",
        "action": "approve_pathway",
        "prior_state": "identified/active",
        "new_state": "reviewed/active",
    },
    {
        "id": "evt-0003-c",
        "case_id": "case-0003",
        "timestamp": "2026-10-05T10:00:00Z",
        "actor_role": "coordinator",
        "action": "send_invitation",
        "prior_state": "reviewed/active",
        "new_state": "invited/active",
        "reason": "Simulated invitation",
    },
    {
        "id": "evt-0003-d",
        "case_id": "case-0003",
        "timestamp": "2026-11-16T15:00:00Z",
        "actor_role": "system",
        "action": "record_referral_outcome",
        "prior_state": "attended/active",
        "new_state": "follow_up/active",
        "reason": "Capacity unavailable (synthetic)",
    },
    {
        "id": "evt-0002-a",
        "case_id": "case-0002",
        "timestamp": "2026-11-12T09:00:00Z",
        "actor_role": "coordinator",
        "action": "send_invitation",
        "prior_state": "reviewed/active",
        "new_state": "invited/active",
    },
    {
        "id": "evt-0002-b",
        "case_id": "case-0002",
        "timestamp": "2026-11-13T09:00:00Z",
        "actor_role": "coordinator",
        "action": "book_appointment",
        "prior_state": "invited/active",
        "new_state": "booked/active",
    },
    {
        "id": "evt-0004-a",
        "case_id": "case-0004",
        "timestamp": "2026-11-08T09:00:00Z",
        "actor_role": "coordinator",
        "action": "send_invitation",
        "prior_state": "reviewed/active",
        "new_state": "invited/active",
    },
    {
        "id": "evt-0005-a",
        "case_id": "case-0005",
        "timestamp": "2026-11-08T09:00:00Z",
        "actor_role": "coordinator",
        "action": "send_invitation",
        "prior_state": "reviewed/active",
        "new_state": "invited/active",
    },
    {
        "id": "evt-0006-invite",
        "case_id": "case-0006",
        "timestamp": "2026-10-20T10:00:00Z",
        "actor_role": "coordinator",
        "action": "send_invitation",
        "prior_state": "reviewed/active",
        "new_state": "invited/active",
    },
    {
        "id": "evt-0006-book",
        "case_id": "case-0006",
        "timestamp": "2026-10-22T10:00:00Z",
        "actor_role": "coordinator",
        "action": "book_appointment",
        "prior_state": "invited/active",
        "new_state": "booked/active",
    },
    {
        "id": "evt-0006-attend",
        "case_id": "case-0006",
        "timestamp": "2026-10-25T10:00:00Z",
        "actor_role": "coordinator",
        "action": "record_attendance",
        "prior_state": "booked/active",
        "new_state": "attended/active",
        "outcome": "attended",
    },
    {
        "id": "evt-0006-a",
        "case_id": "case-0006",
        "timestamp": "2026-11-01T10:00:00Z",
        "actor_role": "clinical_reviewer",
        "action": "close_as_completed",
        "prior_state": "attended/active",
        "new_state": "closed/completed",
        "evidence_reference": "Encounter/enc-synthetic-06",
    },
]