import pytest

from namaa_ai.context_assembler import GuidelinePassage, ScopedContextAssembler, VerifiedGuidelines, render_bounded_context
from namaa_ai.context_engineering import ContextAssembler, ReciprocalRankFusion
from namaa_ai.contracts import ContextQuery
from test_context_engineering import NOW, assemble, record, verified


def guidelines(**changes):
    passage = GuidelinePassage(source={"reference": "Library/approved-demo", "version": "v3"},
        title="Fictional preventive guidance", text="Adult screening guidance.", offset_start=0,
        offset_end=len("Adult screening guidance."), approved=True, approved_by="Practitioner/reviewer",
        approved_at="2026-11-18T08:00:00Z")
    return VerifiedGuidelines.model_validate(dict(workspace_id="ws-demo", permission_revision="perm-1",
        state="current", authorized=True, source_verified=True, verified_at="2026-11-18T08:55:00Z",
        expires_at="2026-11-18T09:10:00Z", passages=[passage]) | changes)


def scoped(ctx, guides, query=None, retriever=None):
    return ScopedContextAssembler(enabled=True, retriever=retriever).assemble(ctx,
        query or ContextQuery(query="screening"), workspace_id="ws-demo", patient_reference="Patient/pat-demo",
        permission_revision="perm-1", generation_id="gen-1", now=NOW, guidelines=guides)


def test_same_document_passages_remain_separate_and_exact_duplicates_are_deduplicated():
    first = record("DocumentReference", "note", "Screening occurred.", offset_start=0, offset_end=19)
    second = record("DocumentReference", "note", "Screening discussed.", offset_start=20, offset_end=40)
    result = assemble(verified(records=[first, second, first]), "screening")
    assert len(result.items) == len({item.item_id for item in result.items}) == 2
    assert {i.text for i in result.items} == {first["text"], second["text"]}
    assert result.character_count == 39


def test_conflicting_versions_and_conflicting_passages_fail_closed():
    first = record("DocumentReference", "note", "Screening occurred.", offset_start=0, offset_end=19)
    second = record("DocumentReference", "note", "Screening occurred.", version="v2", offset_start=0, offset_end=19)
    with pytest.raises(ValueError, match="versions"):
        assemble(verified(records=[first, second]), "screening")
    second = first | {"text": "Screening reported."}
    with pytest.raises(ValueError, match="passages"):
        assemble(verified(records=[first, second]), "screening")


def test_assembler_ignores_ranker_fabrications_and_duplicate_ids():
    class Ranker:
        def rank(self, query, items):
            return ["invented", items[0].item_id, items[0].item_id]
    result = ContextAssembler(enabled=True, retriever=Ranker()).assemble(
        verified(records=[record("Observation", "a", "Screening history.")]), ContextQuery(query="screening"),
        workspace_id="ws-demo", patient_reference="Patient/pat-demo", permission_revision="perm-1", generation_id="gen-1", now=NOW)
    assert len(result.items) == 1


def test_guidelines_share_budget_without_becoming_patient_facts():
    ctx = verified(records=[record("Observation", "history", "Screening reported.")])
    result = scoped(ctx, guidelines())
    assert len(result.patient_context.items) == len(result.guidelines) == 1
    assert result.guideline_state == "current"
    assert all(i.source.reference.startswith("Observation/") for i in result.patient_context.items)
    assert result.character_count == sum(len(i.text) for i in (*result.guidelines, *result.patient_context.items))
    limited = scoped(ctx, guidelines(), ContextQuery(query="screening", max_items=1))
    assert len(limited.guidelines) + len(limited.patient_context.items) == 1
    assert not result.absence_claims_allowed
    rendered = render_bounded_context(result)
    assert "untrusted source data" in rendered and "not patient facts" in rendered
    assert '"Library/approved-demo"' in rendered and '"version":"v3"' in rendered


@pytest.mark.parametrize("changes", [{"state": "stale"}, {"authorized": False}, {"source_verified": False},
    {"workspace_id": "foreign"}, {"permission_revision": "old"}, {"expires_at": "2026-11-18T08:59:00Z"}])
def test_stale_or_unauthorized_guidelines_never_reach_ranker(changes):
    class Ranker:
        def rank(self, query, items):
            assert not any(isinstance(item, GuidelinePassage) for item in items)
            return [i.item_id for i in items]
    result = scoped(verified(), guidelines(**changes), retriever=Ranker())
    assert result.guidelines == () and result.guideline_state == "unknown"


def test_unapproved_guideline_version_is_not_retrieved():
    passage = guidelines().passages[0].model_copy(update={"approved": False})
    result = scoped(verified(), guidelines(passages=[passage]))
    assert not result.guidelines and result.guideline_state == "unknown"


def test_hybrid_retrieval_ranks_only_approved_candidates():
    class Dense:
        def rank(self, query, items):
            return ["unauthorized", *(i.item_id for i in items if isinstance(i, GuidelinePassage))]
    result = scoped(verified(), guidelines(), ContextQuery(query="semantic match"),
                    retriever=ReciprocalRankFusion(dense=Dense()))
    assert len(result.guidelines) == 1
    assert result.patient_context.state == "empty_unknown"
