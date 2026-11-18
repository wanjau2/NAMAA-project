from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ExtractionAccepted(BaseModel):
    job_id: str
    state: Literal["queued", "running", "succeeded", "failed", "cancelled", "timed_out"]
    events_url: str
    status_url: str
    notice: str = (
        "Subscribe to events_url (SSE). Do not poll status_url more than as a fallback."
    )


class ExtractionJobOut(BaseModel):
    event: str | None = None
    job_id: str
    document_id: str
    document_version: int
    state: str
    progress_percent: int = 0
    message: str = ""
    elapsed_ms: int = 0
    timeout_ms: int = 90_000
    model_revision: str
    prompt_version: str
    error_code: str | None = None
    error_message: str | None = None
    synthetic: bool = True
    inference_mode: str = "offline_fixture"
    proposals: list[dict[str, Any]] = Field(default_factory=list)


class OutboxRow(BaseModel):
    id: str
    request_id: str
    action: str
    state: str
    attempts: int
    max_attempts: int
    last_error: str | None = None
    case_id: str | None = None
    created_at: str
    updated_at: str
    dead_lettered_at: str | None = None
    compensation_reason: str | None = None


class OutboxRetryOut(BaseModel):
    id: str
    state: str
    message: str
