"""Evaluation of labelled synthetic notes. Replay metrics are software evidence only."""
from __future__ import annotations

from collections import Counter
import math
from statistics import median

from .adapters import ExtractionAdapter
from .contracts import ExtractionRequest, ProposedFact


def ratio(n, d):
    return n / d if d else None


async def evaluate_corpus(notes: list[dict], adapter: ExtractionAdapter) -> dict:
    fields = list(ProposedFact.model_fields)
    counts = {field: Counter(tp=0, fp=0, fn=0) for field in fields}
    schema_valid = schema_attempts = quote_valid = quote_count = unsupported = predicted = expected = 0
    latencies, outcomes, models = [], Counter(), set()
    rows = []
    for note in notes:
        result = await adapter.extract(ExtractionRequest.model_validate(note["request"]))
        gold = note["expected"]["facts"]
        actual = [p.fact.model_dump(mode="json") for p in result.proposals]
        expected += len(gold)
        predicted += len(actual)
        schema_attempts += result.status != "transport_failure"
        schema_valid += result.schema_valid
        outcomes[result.status] += 1
        latencies.append(result.latency_ms)
        models.add((result.model.model_revision, result.model.prompt_version, result.model.simulated))
        for field in fields:
            # Multiset exact matching, anchored to source excerpt; duplicates cannot inflate TP.
            a = Counter((f["excerpt"], str(f[field])) for f in actual)
            g = Counter((f["excerpt"], str(f[field])) for f in gold)
            counts[field].update(tp=sum((a & g).values()), fp=sum((a - g).values()), fn=sum((g - a).values()))
        semantic_fields = ("concept", "subject", "assertion", "effective_date", "relationship", "value_text")
        a = Counter(tuple(f[k] for k in semantic_fields) for f in actual)
        g = Counter(tuple(f[k] for k in semantic_fields) for f in gold)
        unsupported += sum((a - g).values())
        for p in result.proposals:
            quote_count += 1
            quote_valid += p.offset_start is not None and p.offset_end is not None and note["request"]["note_text"][p.offset_start:p.offset_end] == p.fact.excerpt
        rows.append({"id": note["id"], "status": result.status, "issues": sorted({i.code for p in result.proposals for i in p.issues})})
    simulated = all(m[2] for m in models)
    return {
        "notice": "SIMULATED label replay: integration checks, NOT MedGemma quality results" if simulated else "Live synthetic endpoint evaluation; not clinical validation",
        "simulated": simulated, "sample_size_notes": len(notes), "expected_facts": expected, "predicted_facts": predicted,
        "splits": dict(Counter(n["split"] for n in notes)), "categories": dict(Counter(n["category"] for n in notes)),
        "models": [{"revision": r, "prompt": p, "simulated": s} for r, p, s in sorted(models)],
        "outcomes": dict(outcomes),
        "fields": {f: dict(c, precision=ratio(c["tp"], c["tp"]+c["fp"]), recall=ratio(c["tp"], c["tp"]+c["fn"])) for f, c in counts.items()},
        "unsupported_additions": {"count": unsupported, "predicted_facts": predicted, "rate": ratio(unsupported, predicted)},
        "quote_validity": {"valid": quote_valid, "sample_size": quote_count, "rate": ratio(quote_valid, quote_count)},
        "schema_validity": {"valid": schema_valid, "sample_size": schema_attempts, "rate": ratio(schema_valid, schema_attempts)},
        "latency_ms": {"sample_size": len(latencies), "median": median(latencies) if latencies else None,
                       "p95": sorted(latencies)[math.ceil(len(latencies)*.95)-1] if latencies else None},
        "cases": rows,
    }
