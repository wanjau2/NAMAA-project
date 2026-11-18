from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .adapters import HostedAdapter, HostedConfig, MockAdapter
from .demo import run_demo
from .evaluation import evaluate_context_retrieval, evaluate_corpus


def main():
    parser = argparse.ArgumentParser(description="Namaa synthetic AI module; no clinical validation")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="Explicit scripted review and simulated FHIR commit")
    ev = sub.add_parser("evaluate")
    ev.add_argument("--corpus", type=Path, default=Path("fixtures/notes.json"))
    ev.add_argument("--split", choices=["development", "held_out", "all"], default="development")
    ev.add_argument("--adapter", choices=["mock", "hosted"], default="mock")
    ctx_ev = sub.add_parser("evaluate-context")
    ctx_ev.add_argument("--corpus", type=Path, default=Path("fixtures/context-queries.json"))
    ctx_ev.add_argument("--split", choices=["development", "held_out", "all"], default="development")
    ctx_ev.add_argument("--k", type=int, default=3)
    schema = sub.add_parser("schemas")
    schema.add_argument("--output", type=Path, default=Path("examples/schemas"))
    args = parser.parse_args()
    if args.command == "demo":
        result = asyncio.run(run_demo())
    elif args.command == "schemas":
        from . import contracts
        args.output.mkdir(parents=True, exist_ok=True)
        for name, obj in vars(contracts).items():
            if isinstance(obj, type) and issubclass(obj, contracts.Contract) and obj is not contracts.Contract:
                (args.output / f"{name}.json").write_text(json.dumps(obj.model_json_schema(), indent=2) + "\n")
        result = {"schemas_written": str(args.output)}
    elif args.command == "evaluate-context":
        cases = json.loads(args.corpus.read_text())["queries"]
        cases = [c for c in cases if args.split == "all" or c["split"] == args.split]
        result = evaluate_context_retrieval(cases, k=args.k)
    else:
        notes = json.loads(args.corpus.read_text())["notes"]
        notes = [n for n in notes if args.split == "all" or n["split"] == args.split]
        adapter = MockAdapter({n["request"]["note_text"]: n["expected"] for n in notes}) if args.adapter == "mock" else HostedAdapter(HostedConfig.from_env())
        result = asyncio.run(evaluate_corpus(notes, adapter))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
