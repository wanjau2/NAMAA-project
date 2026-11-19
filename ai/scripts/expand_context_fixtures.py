"""Expand the eight hand-authored retrieval scenarios into query paraphrase cases.

All cases reuse their scenario's fictional source candidates; this measures
synthetic retrieval behavior across phrasing, not independent corpus coverage.
"""
import json
from pathlib import Path

PATH = Path("fixtures/context-queries.json")
data = json.loads(PATH.read_text())
variants = {
    "dev-wcv-date": [
        "when was the last well-child visit",
        "date of the most recent well child visit",
        "which source records the last child health check date",
        "find the documented WCV date",
        "retrieve the source for the patient's most recent well-child visit",
    ],
    "dev-family-history": [
        "what family history of diabetes is documented",
        "show the father's recorded diabetes history",
        "find source evidence of a relative with diabetes",
        "which family member history mentions diabetes",
        "retrieve the documented paternal condition",
    ],
    "dev-care-plan": [
        "current care plan and assigned preventive follow-up",
        "show the active prevention plan and follow-up task",
        "find current plan and assigned screening work",
        "which task is assigned for preventive follow-up",
        "retrieve current care plan status and owner task",
    ],
    "dev-source-conflict": [
        "conflicting documented last adult screening dates",
        "show both source versions with different screening dates",
        "find inconsistent history for the last adult screen",
        "which records report conflicting screening dates",
        "retrieve contradictory adult screening history sources",
    ],
    "heldout-tobacco": [
        "patient report about smoking tobacco or cigarettes",
        "find the patient's statement about cigarette use",
        "retrieve evidence about tobacco use or smoking",
        "which note and observation describe tobacco history",
        "show the source for the patient's smoking assertion",
    ],
    "heldout-caregiver-concern": [
        "caregiver concern or question about a child's preventive visit",
        "find the caregiver's question about the child's checkup",
        "retrieve the source describing caregiver worry about prevention",
        "which note records a family concern about the well-child visit",
        "show caregiver feedback related to the child's preventive care",
    ],
    "heldout-booking-evidence": [
        "verified procedure attendance evidence for the preventive service",
        "find the completed procedure record for attendance",
        "retrieve diagnostic evidence that the patient attended",
        "which source proves attendance rather than appointment booking",
        "show verified service completion evidence",
    ],
    "heldout-empty-scope": [
        "current active adult screening service request",
        "find the current service request for adult screening",
        "retrieve active preventive screening order request",
        "which current request supports the adult screening pathway",
        "show the authorized active screening service request",
    ],
}

seeds = {}
for case in data["queries"]:
    base_id = case["id"].rsplit("-", 1)[0] if case["id"].rsplit("-", 1)[-1].isdigit() else case["id"]
    if base_id in variants:
        seeds.setdefault(base_id, {**case, "id": base_id})

expanded = []
for base_id, base in seeds.items():
    prompts = variants[base_id]
    assert len(prompts) == 5 and len(set(prompts)) == 5
    for index, query in enumerate(prompts, start=1):
        expanded.append({**base, "id": f"{base['id']}-{index:02d}", "query": query})

assert len(seeds) == 8
assert len(expanded) == 40
assert len({case["query"] for case in expanded}) == 40
assert sum(case["split"] == "development" for case in expanded) == 20
assert sum(case["split"] == "held_out" for case in expanded) == 20
PATH.write_text(json.dumps({**data, "queries": expanded}, indent=2, ensure_ascii=False) + "\n")
