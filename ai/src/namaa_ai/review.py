"""Review logic; authorization and durable compare-and-swap belong to Ismail."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .contracts import ExtractionProposal, ExtractionRequest, ReviewCommand, ReviewDecision, ReviewedFact
from .validation import check_fact, source_hash


class ReviewError(ValueError):
    """Codes map to backend 403/409/422 without exposing note text."""


class ReviewAuthorizer(Protocol):
    def require_review(self, command: ReviewCommand, proposal: ExtractionProposal) -> None:
        """Raise PermissionError unless current authenticated principal is allowed.

        Bind reviewer identity, workspace, patient and proposal to the backend session.
        This object must never be constructed from a browser authorization flag.
        """
        ...


class DenyReview:
    def require_review(self, command, proposal):
        raise PermissionError("Backend review authorization is required")


def apply_review(request: ExtractionRequest, proposal: ExtractionProposal, command: ReviewCommand,
                 *, current_version: int, reviewed_at: datetime,
                 authorizer: ReviewAuthorizer | None = None) -> ReviewDecision:
    (authorizer or DenyReview()).require_review(command, proposal)
    if command.proposal_id != proposal.id or command.expected_proposal_version != current_version or proposal.version != current_version:
        raise ReviewError("stale_proposal_version")
    if (request.workspace_id, request.patient_reference, request.source_id, request.source_version, source_hash(request)) != (
            proposal.workspace_id, proposal.patient_reference, proposal.source_document_id,
            proposal.source_document_version, proposal.source_sha256):
        raise ReviewError("source_version_mismatch")
    fact = None
    if command.action != "reject":
        selected = command.correction if command.action == "correct" else proposal.fact
        start, end, issues = check_fact(request, selected)
        # Batch conflict information survives correction; editing one proposal cannot erase it.
        issues += tuple(i for i in proposal.issues if i.code == "conflicting_statements")
        if any(i.severity == "block" for i in issues):
            raise ReviewError("source_validation_blocked")
        required = {i.code for i in issues if i.severity == "review"}
        if not required.issubset(command.acknowledged_issues):
            raise ReviewError("review_issues_not_acknowledged")
        fact = ReviewedFact(proposal=proposal, fact=selected, review=command, reviewed_at=reviewed_at,
                            source_date=request.source_date, offset_start=start, offset_end=end)
    return ReviewDecision(command=command, resulting_proposal_version=current_version + 1,
                          state={"accept": "accepted", "correct": "corrected", "reject": "rejected"}[command.action], fact=fact)
