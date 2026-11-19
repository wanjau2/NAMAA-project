# MedGemma endpoint agreement

Checked official documentation on 2026-11-18 before implementing the adapter:

- [Google MedGemma 1.5 model card and usage](https://huggingface.co/google/medgemma-1.5-4b-it)
- [Hugging Face custom handlers](https://huggingface.co/docs/inference-endpoints/guides/custom_handler)
- [Hugging Face custom containers](https://huggingface.co/docs/inference-endpoints/guides/custom_container)
- [Sending authenticated endpoint requests](https://huggingface.co/docs/inference-endpoints/guides/test_endpoint)

The model produces text, and its usage documentation shows chat-template
processing and decoding generated tokens. Hugging Face custom handlers receive
request dictionaries and can return custom serializable output. Therefore
**`namaa-extraction-v1` below is a proposed Namaa serving agreement**, not a claim
about a provisioned endpoint, a universal Hugging Face response shape, or a native
MedGemma JSON API. No inference container or paid infrastructure is provisioned.

## Configuration and request

Environment: `NAMAA_HF_ENDPOINT_URL` (HTTPS, no credentials/query/fragment),
`NAMAA_HF_TOKEN` (backend secret), `NAMAA_MODEL_REVISION` (actual 40-character
immutable deployed commit), `NAMAA_ENDPOINT_PROTOCOL=namaa-extraction-v1`.
The model ID is fixed to `google/medgemma-1.5-4b-it`. No usable model commit is
guessed. The all-zero revision in examples is a schema placeholder, not a tested
checkpoint. Mock identity is `simulated-fixture-v1` and always `simulated=true`.

The adapter POSTs JSON with Bearer authentication. Examples:
[`endpoint-request.json`](../examples/endpoint-request.json) and
[`endpoint-response.json`](../examples/endpoint-response.json). No token is in
either file. The request contains `protocol`, `model_id`, `model_revision`,
`prompt_version`, an `inputs` object and generation `parameters`. Inputs contain
the pinned instruction, authorized source ID/version/date/English text, generated
ModelOutput schema and `format_repair`. Only source metadata is sent; patient and
workspace IDs are not needed by the model. There are no tools or graph queries.

The endpoint owner must implement and test this agreement:

1. Verify protocol and deployment/model revision, validate source length, enforce
   greedy generation (`do_sample=false`) and `max_new_tokens=2048` on the server.
2. Use the actual MedGemma processor/chat template to separate application
   instructions and the untrusted note. Delimiters alone are not an injection
   defense. Grant the model no tools or write authority.
3. Decode only generated tokens and parse a ModelOutput object. Do not invent
   missing fields or convert parser failures into an empty facts array.
4. Return the explicit response envelope. Populate model revision/prompt metadata
   from trusted serving configuration, never from generated text. Output is
   `{"facts": [...]}`. Reject unknown fields and protocol/version mismatches.
5. On `format_repair=true`, request valid schema-conforming JSON from the original
   source again. There is only one repair generation; malformed model output is
   not echoed into another prompt.

If Ismail's actual container returns another envelope, implement a named codec
and its mocked HTTP tests. Do not guess among `generated_text`, OpenAI `choices`,
arrays and raw strings. A generic endpoint without this serving agreement is
expected to fail validation.

## Failure and logging behavior

The input limit is 6,000 Python Unicode characters; oversized notes are rejected,
not truncated. The 90-second **total** deadline covers retries and repair. HTTP
connect timeout is 10 seconds inside that deadline. One transient retry is allowed
for transport/timeouts or HTTP 408/429/500/502/503/504. Other HTTP errors and redirects
are terminal. One invalid-schema regeneration is allowed. Three attempts maximum
across both allowances; the deadline may stop earlier. Response body is bounded
to 128 KiB. Cancellation propagates; there is no local background inference job.

The decoder rejects duplicate JSON keys and non-JSON numeric constants. Event
dates must be explicit `YYYY-MM-DD` strings (or actual Python dates internally);
numeric timestamps and midnight datetime coercions are refused. A mismatched
model ID/revision, prompt version or protocol is terminal and does not consume
the formatting-repair allowance. Source ID, patient and workspace are checked
against the worker's authenticated source request before model dispatch.

Valid empty facts are distinct from schema failure, source-validation failure,
HTTP/transport failure and deadline expiry. Source errors are not repaired by
making another model call. They remain blocked proposals for explicit correction
or rejection. The adapter emits sanitized error codes and no logs. Keep verbose
HTTP logging disabled in the embedding worker; logging infrastructure remains a
backend responsibility. Credential fields are excluded from configuration repr.

Hosted HTTP tests use `httpx.MockTransport` only. They establish payload, validation
and failure behavior, not actual serving compatibility, latency or model quality.

## FHIR references checked

Mappings were checked against the official R4 definitions for
[Observation](https://hl7.org/fhir/R4/observation.html),
[Condition](https://hl7.org/fhir/R4/condition.html),
[FamilyMemberHistory](https://hl7.org/fhir/R4/familymemberhistory.html),
[Provenance](https://hl7.org/fhir/R4/provenance.html), and
[Bundle request fields](https://hl7.org/fhir/R4/bundle-definitions.html).
This documentation review is not an official validator run. In particular,
`ifNoneMatch` is not used as an assumed create-only PUT guarantee; the backend must
resolve resource state and implement validated transaction preconditions.
