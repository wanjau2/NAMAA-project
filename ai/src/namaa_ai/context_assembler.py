"""Read-only hybrid retrieval of patient context and separately approved guidance.

All envelopes are internal assertions from a per-request backend PEP/PDP and
source verifier. These schemas are not public request-body authorization claims.
"""
from datetime import datetime
from hashlib import sha256
import json
from typing import Literal

from pydantic import AwareDatetime, Field, StrictBool, model_validator

from .context_engineering import ContextAssembler, RankedRetriever, ReciprocalRankFusion, select_bounded
from .contracts import (AssembledContext, Contract, ContextItem, ContextQuery, LogicalId,
                        ResourceVersion, ReviewerRef, Text, VerifiedContext, Version)


class GuidelinePassage(Contract):
    source: ResourceVersion
    title: str = Field(min_length=1, max_length=256)
    text: Text
    offset_start: int = Field(ge=0, strict=True)
    offset_end: int = Field(ge=1, strict=True)
    approved: StrictBool
    approved_by: ReviewerRef
    approved_at: AwareDatetime

    @model_validator(mode="after")
    def source_span(self):
        if self.source.reference.split("/")[0] not in {"Library", "DocumentReference"}:
            raise ValueError("guideline_requires_versioned_document_or_library")
        if self.offset_end - self.offset_start != len(self.text):
            raise ValueError("guideline_requires_exact_unicode_span")
        return self

    @property
    def item_id(self) -> str:
        return "guide-" + sha256(self.model_dump_json().encode()).hexdigest()[:24]


class VerifiedGuidelines(Contract):
    """Backend verifies both source version and approval of that exact version."""
    workspace_id: LogicalId
    permission_revision: Version
    state: Literal["current", "stale", "unavailable"]
    authorized: StrictBool
    source_verified: StrictBool
    verified_at: AwareDatetime
    expires_at: AwareDatetime
    passages: tuple[GuidelinePassage, ...] = Field(max_length=200)


class BoundedContext(Contract):
    patient_context: AssembledContext
    guidelines: tuple[GuidelinePassage, ...]
    guideline_state: Literal["current", "unknown", "not_requested"]
    character_count: int = Field(ge=0)
    absence_claims_allowed: Literal[False] = False
    notice: str = "Guidelines are reference material, not patient facts or authority to order care."


class ScopedContextAssembler:
    """One shared item/text budget, BM25 plus an optional injected dense ranker."""

    def __init__(self, *, enabled: bool = False, retriever: RankedRetriever | None = None):
        self.patient_assembler = ContextAssembler(enabled=enabled)
        self.retriever = retriever or ReciprocalRankFusion()

    def assemble(self, verified: VerifiedContext, query: ContextQuery, *, workspace_id: str,
                 patient_reference: str, permission_revision: str, generation_id: str,
                 now: datetime, guidelines: VerifiedGuidelines | None = None) -> BoundedContext:
        query = ContextQuery.model_validate(query.model_dump())
        patient_items = self.patient_assembler.candidates(verified, query,
            workspace_id=workspace_id, patient_reference=patient_reference,
            permission_revision=permission_revision, generation_id=generation_id, now=now)
        guidance, guideline_state = (), "not_requested"
        if guidelines is not None:
            guidelines = VerifiedGuidelines.model_validate(guidelines.model_dump())
            valid = (guidelines.authorized and guidelines.source_verified
                and guidelines.state == "current" and guidelines.workspace_id == workspace_id
                and guidelines.permission_revision == permission_revision
                and guidelines.verified_at <= now < guidelines.expires_at)
            # A corpus containing contradictory versions cannot be current.
            versions = {}
            spans = {}
            for passage in guidelines.passages:
                reference = passage.source.reference
                if reference in versions and versions[reference] != passage.source.version:
                    valid = False
                versions[reference] = passage.source.version
                key = (reference, passage.offset_start, passage.offset_end)
                if key in spans and spans[key] != passage.text:
                    valid = False
                spans[key] = passage.text
            if valid:
                guidance = tuple({p.item_id: p for p in guidelines.passages
                    if p.approved and p.approved_at <= guidelines.verified_at}.values())
            guideline_state = "current" if valid and guidance else "unknown"
        candidates = (*patient_items, *guidance)
        selected, characters, _ = select_bounded(
            self.retriever.rank(query.query, candidates), candidates, query)
        selected_patients = tuple(item for item in selected if isinstance(item, ContextItem))
        selected_guidelines = tuple(item for item in selected if isinstance(item, GuidelinePassage))
        patient_context = AssembledContext(query=query.query, workspace_id=workspace_id,
            patient_reference=patient_reference, generation_id=generation_id,
            permission_revision=permission_revision, state="assembled" if selected_patients else "empty_unknown",
            completeness="partial" if selected_patients else "unknown", items=selected_patients,
            character_count=sum(len(item.text) for item in selected_patients))
        return BoundedContext(patient_context=patient_context, guidelines=selected_guidelines,
            guideline_state=guideline_state, character_count=characters)


def render_bounded_context(context: BoundedContext) -> str:
    """Serialize evidence as untrusted data; no extraction/model call is made."""
    from .context_engineering import render_explanation_context

    payload = json.loads(render_explanation_context(context.patient_context))
    payload["guideline_notice"] = context.notice
    payload["guideline_state"] = context.guideline_state
    payload["guidelines"] = [{"source": item.source.model_dump(), "title": item.title,
        "excerpt": item.text, "offset_start": item.offset_start, "offset_end": item.offset_end}
        for item in context.guidelines]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
