"""Backend-only adapter. The custom wire protocol must be implemented by the host."""
from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from .contracts import EndpointResponse, ExtractionRequest, ExtractionResult, ModelIdentity, ModelOutput
from .validation import make_proposals

PROTOCOL = "namaa-extraction-v1"
PROMPT_VERSION = "extract-v1.0.0"
MODEL_ID = "google/medgemma-1.5-4b-it"
TIMEOUT_SECONDS = 90.0  # entire extraction, including all attempts
MAX_RESPONSE_BYTES = 131072


class ExtractionAdapter(Protocol):
    async def extract(self, request: ExtractionRequest) -> ExtractionResult: ...


def finish(request, identity, output, started, attempts):
    proposals = make_proposals(request, output.facts, identity)
    blocked = any(i.severity == "block" for p in proposals for i in p.issues)
    return ExtractionResult(
        status="invalid_output" if blocked else ("success" if proposals else "no_supported_facts"),
        model=identity, proposals=proposals, error_code="source_validation" if blocked else None,
        latency_ms=(time.monotonic() - started) * 1000, attempts=attempts, schema_valid=True,
    )


@dataclass(frozen=True)
class HostedConfig:
    endpoint_url: str = field(repr=False)
    token: str = field(repr=False)
    model_revision: str
    protocol: str = PROTOCOL

    def __post_init__(self):
        url = urlsplit(self.endpoint_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("Endpoint must be an HTTPS URL without embedded credentials, query or fragment")
        if not self.token.strip():
            raise ValueError("Backend endpoint token is required")
        if not re.fullmatch(r"[a-f0-9]{40}", self.model_revision):
            raise ValueError("Set the actual immutable 40-character deployed model commit")
        if self.protocol != PROTOCOL:
            raise ValueError("Unsupported endpoint protocol; implement an explicit codec for a different host")

    @classmethod
    def from_env(cls):
        return cls(os.getenv("NAMAA_HF_ENDPOINT_URL", ""), os.getenv("NAMAA_HF_TOKEN", ""),
                   os.getenv("NAMAA_MODEL_REVISION", ""), os.getenv("NAMAA_ENDPOINT_PROTOCOL", PROTOCOL))


class MockAdapter:
    """Explicit scripted replay, never a language model or a quality benchmark."""
    def __init__(self, responses: dict[str, dict]):
        self.responses = responses

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        request = ExtractionRequest.model_validate(request.model_dump())
        started = time.monotonic()
        identity = ModelIdentity(model_revision="simulated-fixture-v1", simulated=True)
        if request.note_text not in self.responses:
            return ExtractionResult(status="invalid_output", model=identity, error_code="mock_fixture_missing", latency_ms=0, attempts=1, schema_valid=False)
        try:
            output = ModelOutput.model_validate(self.responses[request.note_text])
        except ValidationError:
            return ExtractionResult(status="invalid_output", model=identity, error_code="output_schema", latency_ms=0, attempts=1, schema_valid=False)
        return finish(request, identity, output, started, 1)


class HostedAdapter:
    def __init__(self, config: HostedConfig, *, transport: httpx.AsyncBaseTransport | None = None):
        self.config = config
        self.transport = transport

    def payload(self, request: ExtractionRequest, repair: bool):
        # No patient/workspace IDs are needed by the model. No context, tools or actions.
        return {
            "protocol": PROTOCOL,
            "model_id": MODEL_ID,
            "model_revision": self.config.model_revision,
            "prompt_version": PROMPT_VERSION,
            "inputs": {
                "instruction": files("namaa_ai").joinpath(f"prompts/{PROMPT_VERSION}.txt").read_text(),
                "source": {"id": request.source_id, "version": request.source_version,
                           "date": request.source_date.isoformat(), "language": "en", "note_text": request.note_text},
                "output_schema": ModelOutput.model_json_schema(),
                "format_repair": repair,
            },
            "parameters": {"do_sample": False, "max_new_tokens": 2048},
        }

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        request = ExtractionRequest.model_validate(request.model_dump())
        started = time.monotonic()
        identity = ModelIdentity(model_revision=self.config.model_revision, simulated=False)
        attempts, retried, repaired = 0, False, False

        def fail(status, code):
            return ExtractionResult(status=status, model=identity, error_code=code, attempts=max(1, attempts),
                                    latency_ms=(time.monotonic() - started) * 1000, schema_valid=False)

        try:
            async with asyncio.timeout(TIMEOUT_SECONDS):
                async with httpx.AsyncClient(transport=self.transport, timeout=httpx.Timeout(90, connect=10),
                                             follow_redirects=False, trust_env=False) as client:
                    while attempts < 3:
                        attempts += 1
                        try:
                            async with client.stream("POST", self.config.endpoint_url,
                                    headers={"Authorization": f"Bearer {self.config.token}", "Content-Type": "application/json"},
                                    json=self.payload(request, repaired)) as response:
                                if response.status_code in {408, 429, 500, 502, 503, 504}:
                                    if not retried:
                                        retried = True
                                        await asyncio.sleep(0.1)
                                        continue
                                    return fail("transport_failure", "transient_http_exhausted")
                                if response.status_code != 200:
                                    return fail("transport_failure", "endpoint_http_error")
                                body = bytearray()
                                async for chunk in response.aiter_bytes():
                                    body.extend(chunk)
                                    if len(body) > MAX_RESPONSE_BYTES:
                                        return fail("invalid_output", "output_too_large")
                        except (httpx.TimeoutException, httpx.TransportError):
                            if not retried:
                                retried = True
                                continue
                            return fail("transport_failure", "transport_retry_exhausted")
                        try:
                            envelope = EndpointResponse.model_validate_json(bytes(body))
                            if envelope.model_revision != self.config.model_revision:
                                return fail("invalid_output", "model_revision_mismatch")
                        except (ValidationError, ValueError):
                            if not repaired and attempts < 3:
                                repaired = True
                                continue  # regenerate from source; do not echo untrusted malformed output
                            return fail("invalid_output", "output_schema")
                        return finish(request, identity, envelope.output, started, attempts)
        except TimeoutError:
            return fail("transport_failure", "deadline_exceeded")
        return fail("transport_failure", "attempt_limit")
