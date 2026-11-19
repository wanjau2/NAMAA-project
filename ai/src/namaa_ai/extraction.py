"""Strict model wire decoding; worker persistence/leases remain backend-owned."""
import json

from .contracts import EndpointResponse


class EndpointIdentityMismatch(ValueError):
    """Identity failures are not formatting failures and must not be repaired."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError("non_json_number")


def decode_response(body: bytes, *, model_id: str, model_revision: str,
                    prompt_version: str, protocol: str) -> EndpointResponse:
    """Reject duplicate keys/coerced dates; do not choose a conflicting statement."""
    data = json.loads(body, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    if isinstance(data, dict):
        for key, expected in (("model_id", model_id), ("model_revision", model_revision),
                              ("prompt_version", prompt_version), ("protocol", protocol)):
            if key in data and data[key] != expected:
                raise EndpointIdentityMismatch(f"{key}_mismatch")
    return EndpointResponse.model_validate(data)
