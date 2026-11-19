import asyncio

import httpx
import pytest

from namaa_ai.contracts import RelateCandidateBatch
from namaa_ai.relate_graph import RelateResolver
from test_context_engineering import NOW, record, verified


def batch(**changes):
    return RelateCandidateBatch.model_validate(dict(workspace_id="ws-demo", patient_reference="Patient/pat-demo",
        generation_id="gen-1", permission_revision="perm-1", state="current", candidates=[{
            "patient_reference": "Patient/pat-demo", "candidate_kind": "family_history",
            "supporting_references": ["FamilyMemberHistory/mother"]}]) | changes)


def test_every_graph_resolution_calls_current_source_and_policy_verifier():
    calls, refreshes = [], []
    async def verify(**kwargs):
        calls.append(kwargs)
        return verified(records=[record("FamilyMemberHistory", "mother", "Mother has diabetes.",
                                       version=f"current-{len(calls)}")])
    async def refresh(**kwargs):
        refreshes.append(kwargs)
    resolver = RelateResolver(verify, refresh, enabled=True, clock=lambda: NOW)
    async def run():
        outputs = [await resolver.resolve(batch(), workspace_id="ws-demo", patient_reference="Patient/pat-demo",
                                        permission_revision="perm-1") for _ in range(2)]
        assert [o.items[0].source.version for o in outputs] == ["current-1", "current-2"]
        assert all(o.state == "verified" and o.refresh == "not_required" for o in outputs)
    asyncio.run(run())
    assert len(calls) == 2 and refreshes == []
    assert calls[0]["references"] == ("FamilyMemberHistory/mother",)


@pytest.mark.parametrize("failure", ["stale", "unauthorized", "absent", "expired", "wrong_generation", "timeout", "http_error"])
def test_failed_verification_suppresses_all_candidates_and_requests_refresh(failure):
    refreshes = []
    async def verify(**kwargs):
        if failure == "timeout":
            raise TimeoutError("Do not disclose this message")
        if failure == "http_error":
            raise httpx.ConnectError("Private endpoint details")
        changes = {"stale": {"state": "stale"}, "unauthorized": {"authorized": False},
            "expired": {"expires_at": "2026-11-18T08:59:00Z"}, "wrong_generation": {"generation_id": "gen-old"}}
        records = [] if failure == "absent" else [record("FamilyMemberHistory", "mother", "Mother has diabetes.")]
        return verified(records=records, **changes.get(failure, {}))
    async def refresh(**kwargs):
        refreshes.append(kwargs)
    result = asyncio.run(RelateResolver(verify, refresh, enabled=True, clock=lambda: NOW).resolve(
        batch(), workspace_id="ws-demo", patient_reference="Patient/pat-demo", permission_revision="perm-1"))
    assert result.state == "unknown" and result.items == () and result.refresh == "requested"
    assert refreshes == [{"workspace_id": "ws-demo", "patient_reference": "Patient/pat-demo"}]
    assert "mother" not in result.model_dump_json() and "Private" not in result.model_dump_json()


@pytest.mark.parametrize("changes", [{"state": "stale"}, {"workspace_id": "foreign"}, {"candidates": []},
                                      {"permission_revision": "revoked"}])
def test_stale_or_foreign_graph_hints_never_select_verification_scope(changes):
    async def verify(**kwargs):
        assert kwargs == {"workspace_id": "ws-demo", "patient_reference": "Patient/pat-demo", "references": ()}
        return verified()
    async def refresh(**kwargs):
        assert kwargs["workspace_id"] == "ws-demo"
    result = asyncio.run(RelateResolver(verify, refresh, enabled=True, clock=lambda: NOW).resolve(
        batch(**changes), workspace_id="ws-demo", patient_reference="Patient/pat-demo", permission_revision="perm-1"))
    assert result.state == "unknown" and result.refresh == "requested"


def test_refresh_failure_remains_explicit_unknown():
    async def verify(**kwargs):
        return verified()
    async def refresh(**kwargs):
        raise OSError("Unavailable queue")
    result = asyncio.run(RelateResolver(verify, refresh, enabled=True, clock=lambda: NOW).resolve(
        batch(), workspace_id="ws-demo", patient_reference="Patient/pat-demo", permission_revision="perm-1"))
    assert result.state == "unknown" and result.refresh == "failed" and not result.items
