import asyncio
import json

import httpx
import pytest

from namaa_ai import adapters
from namaa_ai.adapters import HostedAdapter, HostedConfig, MODEL_ID, PROMPT_VERSION, PROTOCOL


@pytest.fixture
def config():
    return HostedConfig("https://example.invalid/extract", "test-token-not-a-secret", "a" * 40)


def envelope(facts):
    return {"protocol": PROTOCOL, "model_id": MODEL_ID, "model_revision": "a"*40,
            "prompt_version": PROMPT_VERSION, "output": {"facts": facts}}


def test_hosted_wire_contract_and_no_facts(request_note, config):
    seen = []
    def handle(request):
        data = json.loads(request.content)
        seen.append(data)
        assert data["inputs"]["source"]["note_text"] == request_note.note_text
        assert data["parameters"] == {"do_sample": False, "max_new_tokens": 2048}
        assert "tools" not in data and "patient_reference" not in data["inputs"]["source"]
        assert request.headers["authorization"] == "Bearer test-token-not-a-secret"
        return httpx.Response(200, json=envelope([]))
    result = asyncio.run(HostedAdapter(config, transport=httpx.MockTransport(handle)).extract(request_note))
    assert result.status == "no_supported_facts" and not result.model.simulated
    assert len(seen) == 1
    assert "test-token" not in repr(config) and "example.invalid" not in repr(config)


def test_format_repair_is_bounded(request_note, config):
    calls = []
    def handle(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json=[{"generated_text": "not the agreed protocol"}])
    result = asyncio.run(HostedAdapter(config, transport=httpx.MockTransport(handle)).extract(request_note))
    assert result.status == "invalid_output" and result.attempts == 2
    assert not calls[0]["inputs"]["format_repair"] and calls[1]["inputs"]["format_repair"]


def test_transient_then_repair_then_success(request_note, config, fact):
    responses = [httpx.Response(503), httpx.Response(200, text="invalid-json"), httpx.Response(200, json=envelope([fact.model_dump(mode="json")]))]
    result = asyncio.run(HostedAdapter(config, transport=httpx.MockTransport(lambda _: responses.pop(0))).extract(request_note))
    assert result.status == "success" and result.attempts == 3


@pytest.mark.parametrize("status,attempts", [(401, 1), (403, 1), (302, 1), (429, 2), (503, 2)])
def test_http_failures(request_note, config, status, attempts):
    result = asyncio.run(HostedAdapter(config, transport=httpx.MockTransport(lambda _: httpx.Response(status))).extract(request_note))
    assert result.status == "transport_failure" and result.attempts == attempts


def test_timeout_retry_and_global_deadline(request_note, config, monkeypatch):
    def fail(request):
        raise httpx.ReadTimeout("sensitive detail must not escape", request=request)
    result = asyncio.run(HostedAdapter(config, transport=httpx.MockTransport(fail)).extract(request_note))
    assert result.attempts == 2 and result.status == "transport_failure"
    assert "sensitive" not in result.model_dump_json()
    monkeypatch.setattr(adapters, "TIMEOUT_SECONDS", .01)
    async def slow(request):
        await asyncio.sleep(.1)
        return httpx.Response(200, json=envelope([]))
    result = asyncio.run(HostedAdapter(config, transport=httpx.MockTransport(slow)).extract(request_note))
    assert result.error_code == "deadline_exceeded" and result.latency_ms < 100


def test_revision_and_response_size(request_note, config):
    wrong = envelope([]) | {"model_revision": "b"*40}
    result = asyncio.run(HostedAdapter(config, transport=httpx.MockTransport(lambda _: httpx.Response(200, json=wrong))).extract(request_note))
    assert result.error_code == "model_revision_mismatch"
    result = asyncio.run(HostedAdapter(config, transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"x"*131073))).extract(request_note))
    assert result.error_code == "output_too_large"


@pytest.mark.parametrize("url,revision,protocol", [
    ("http://example.invalid", "a"*40, PROTOCOL),
    ("https://secret@example.invalid", "a"*40, PROTOCOL),
    ("https://example.invalid?token=secret", "a"*40, PROTOCOL),
    ("https://example.invalid", "main", PROTOCOL),
    ("https://example.invalid", "a"*40, "openai"),
])
def test_invalid_config(url, revision, protocol):
    with pytest.raises(ValueError):
        HostedConfig(url, "test", revision, protocol)
