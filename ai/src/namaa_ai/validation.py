"""Conservative source checks; these do not establish clinical correctness."""
from __future__ import annotations

import hashlib
import re
from uuid import NAMESPACE_URL, uuid5

from .contracts import ExtractionProposal, ExtractionRequest, ModelIdentity, ProposedFact, ValidationIssue

CONCEPT_WORDS = {
    "last_wcv": r"well.child|check.up|WCV",
    "last_adult_screening": r"screening",
    "caregiver_concern": r"concern|worried|question about",
    "tobacco_use": r"smok|tobacco|cigarette",
    "family_condition": r"asthma|diabetes|cancer|condition|hypertension",
    # This category is restricted to a condition explicitly named as diagnosed
    # in the source; it is not a general-purpose disease recognizer.
    "documented_condition": r"diagnos(?:ed|is)",
}
RELATIVES = r"mother|father|sister|brother|sibling|grandmother|grandfather"


def source_hash(request: ExtractionRequest) -> str:
    return hashlib.sha256(request.note_text.encode("utf-8")).hexdigest()


def check_fact(request: ExtractionRequest, fact: ProposedFact):
    issues: list[ValidationIssue] = []

    def add(code, message, severity="block"):
        issues.append(ValidationIssue(code=code, severity=severity, message=message))

    starts = [m.start() for m in re.finditer(f"(?={re.escape(fact.excerpt)})", request.note_text)]
    start = starts[0] if len(starts) == 1 else None
    end = start + len(fact.excerpt) if start is not None else None
    if not starts:
        add("quote_not_found", "Excerpt must occur exactly in the immutable source")
    elif len(starts) > 1:
        add("ambiguous_quote", "Repeated excerpt requires a longer, unique supporting span")
    if fact.value_text not in fact.excerpt:
        add("unsupported_statement", "Original statement must be verbatim within the excerpt")
    if start is not None:
        # Require complete sentences/lines: a substring must not hide a subject or negation.
        units = list(re.finditer(r"[^.!?\n]+[.!?]?", request.note_text))
        for unit in units:
            left = unit.start() + len(unit.group()) - len(unit.group().lstrip())
            right = unit.end() - len(unit.group()) + len(unit.group().rstrip())
            if left < end and right > start and not (start <= left and end >= right):
                add("incomplete_context", "Include the complete supporting sentence or line")
                break
    text = fact.excerpt.lower()
    if not re.search(CONCEPT_WORDS[fact.concept], text, re.I):
        add("unsupported_concept", "Controlled concept has no supported lexical cue in this slice")
    if re.search(r"ignore .*instructions|system:|assistant:|mark .*up to date|close .*care|execute|invoke|pretend|output .*facts", text):
        add("instruction_like_content", "Instruction-like content is not a supported clinical assertion")
    if fact.subject == "family_member":
        if fact.concept != "family_condition" or fact.proposed_resource_type != "FamilyMemberHistory":
            add("subject_mapping", "Relative conditions must remain FamilyMemberHistory")
        if not fact.relationship or not re.search(rf"\b{fact.relationship}\b", text):
            add("relationship_missing", "An explicit supported relationship is required")
    elif fact.concept == "documented_condition":
        if fact.proposed_resource_type != "Condition" or fact.relationship is not None:
            add("subject_mapping", "Explicit patient diagnosis statements may map only to Condition")
        if fact.assertion != "present" or not re.search(r"\bcurrently\b.{0,40}\bdiagnos(?:ed|is)\b|\bdiagnos(?:ed|is)\b.{0,40}\bcurrently\b", text, re.I):
            add("condition_not_currently_documented", "Condition proposals require explicit current diagnosis wording")
    elif fact.concept == "family_condition" or fact.proposed_resource_type != "Observation" or fact.relationship is not None:
        add("subject_mapping", "Patient findings must use the patient Observation mapping")
    if re.search(rf"\b({RELATIVES})\s+(?:has|had|was diagnosed|denies|does not have|may have)", text) and fact.subject != "family_member":
        add("family_attribution", "The excerpt attributes the condition to a relative")
    if fact.subject == "family_member" and re.search(r"\bpatient\s+(?:has|had|denies|smokes)", text):
        add("mixed_subjects", "Separate patient and family statements with their own context")
    uncertain = re.search(r"unknown|uncertain|cannot recall|can't recall|possible|possibly|may have|unsure", text)
    negative = re.search(r"\bno\b|\bnot\b|\bnever\b|\bdenies\b|\bwithout\b", text)
    historical = re.search(r"previously|used to|in childhood|history of", text)
    if uncertain and fact.assertion != "uncertain":
        add("uncertainty_mismatch", "Uncertainty in the excerpt must be preserved")
    elif negative and not uncertain and fact.assertion not in {"absent", "historical"}:
        add("negation_mismatch", "Negation in the excerpt must be preserved")
    elif historical and not negative and not uncertain and fact.assertion != "historical":
        add("history_mismatch", "Historical wording must be preserved")
    if fact.assertion == "absent" and not negative:
        add("unsupported_negation", "Absent assertion lacks a supported negation cue")
    if fact.assertion == "uncertain":
        add("uncertain_fact", "Uncertainty remains after review", "review")
    if fact.assertion == "historical":
        add("historical_fact", "Historical statements do not establish a current finding", "review")
    explicit_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", fact.excerpt)
    if fact.effective_date and fact.effective_date.isoformat() not in explicit_dates:
        add("unsupported_date", "Event date must occur explicitly in the supporting excerpt")
    elif fact.effective_date and fact.effective_date > request.source_date:
        add("future_event", "A future date cannot establish completed care")
    elif not fact.effective_date:
        add("missing_date", "No supported full event date; source date is not a substitute", "review")
    if len(set(explicit_dates)) > 1:
        add("multiple_dates", "Multiple dates require narrower source context", "review")
    # Check other source statements even when the model omitted a conflicting proposal.
    # This is deliberately conservative lexical reconciliation, not clinical inference.
    for unit in re.finditer(r"[^.!?\n]+[.!?]?", request.note_text):
        other = unit.group().strip()
        if not other or other in fact.excerpt or not re.search(CONCEPT_WORDS[fact.concept], other, re.I):
            continue
        relative = re.search(rf"\b({RELATIVES})\b", other, re.I)
        same_subject = (relative is None) if fact.subject == "patient" else (relative is not None and relative.group().lower() == fact.relationship)
        if same_subject:
            add("conflicting_statements", "Other source statements in this category require reconciliation", "review")
            break
    return start, end, tuple(issues)


def make_proposals(request: ExtractionRequest, facts: tuple[ProposedFact, ...], model: ModelIdentity):
    proposals = []
    for index, fact in enumerate(facts):
        start, end, issues = check_fact(request, fact)
        peers = [f for f in facts if (f.concept, f.subject, f.relationship) == (fact.concept, fact.subject, fact.relationship)]
        if len({(f.assertion, f.effective_date, f.value_text) for f in peers}) > 1 and not any(i.code == "conflicting_statements" for i in issues):
            issues += (ValidationIssue(code="conflicting_statements", severity="review", message="Multiple differing statements require reconciliation; no winner selected"),)
        key = f"{request.workspace_id}/{request.patient_reference}/{request.source_id}/{request.source_version}/{source_hash(request)}/{model.model_revision}/{model.prompt_version}/{index}/{fact.model_dump_json()}"
        proposals.append(ExtractionProposal(
            id=str(uuid5(NAMESPACE_URL, key)), workspace_id=request.workspace_id,
            patient_reference=request.patient_reference, source_document_id=request.source_id,
            source_document_version=request.source_version, source_sha256=source_hash(request),
            fact=fact, offset_start=start, offset_end=end, issues=issues, model=model,
        ))
    return tuple(proposals)
