#!/usr/bin/env python3
"""First agent-workbench tools: search, inspect and check LDraw models."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bricksmith.workbench.feedback import check_model
from bricksmith.workbench.prompt import load_system_prompt
from bricksmith.workbench.references import DEFAULT_CORPUS, inspect_model, load_references, search


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prompt", help="print the canonical design-agent system prompt")
    find = sub.add_parser("search", help="find relevant reference models")
    find.add_argument("query")
    find.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    find.add_argument("--limit", type=int, default=5)
    inspect = sub.add_parser("inspect", help="read a bounded LDraw excerpt")
    inspect.add_argument("path", type=Path)
    inspect.add_argument("--start", type=int, default=1)
    inspect.add_argument("--count", type=int, default=60)
    check = sub.add_parser("check", help="run structured physics checks")
    check.add_argument("path", type=Path)
    check.add_argument("--ground-y", type=float, default=8.0)
    args = parser.parse_args()
    try:
        if args.command == "prompt":
            print(load_system_prompt(), end="")
            return 0
        if args.command == "search":
            result = {"schema": "bricksmith-reference-search-v1", "query": args.query,
                      "corpus_size": 0, "results": []}
            references = load_references(args.corpus)
            result["corpus_size"] = len(references)
            result["results"] = search(references, args.query, args.limit)
        elif args.command == "inspect":
            result = inspect_model(args.path, args.start, args.count)
        else:
            result = check_model(args.path, ground_y=args.ground_y)
        print(json.dumps(result, indent=2))
        return 0
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
