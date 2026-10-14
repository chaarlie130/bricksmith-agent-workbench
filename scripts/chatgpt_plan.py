#!/usr/bin/env python3
"""Use ChatGPT plan-usage OAuth for real BrickSmith Responses API requests."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bricksmith.workbench.chatgpt_plan import ask, list_models, login
from bricksmith.workbench.prompt import load_system_prompt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="authorize actual ChatGPT plan usage in the browser")
    sub.add_parser("models", help="list models exposed to the signed-in plan")
    run = sub.add_parser("ask", help="make one real, streamed Responses API request")
    run.add_argument("--model", required=True, help="model ID from the models command")
    run.add_argument("--prompt", required=True)
    run.add_argument("--no-system-prompt", action="store_true",
                     help="tiny transport smoke test only; not a BrickSmith design run")
    args = parser.parse_args()
    try:
        if args.command == "login":
            print(json.dumps(login(), indent=2))
        elif args.command == "models":
            print(json.dumps({"models": list_models()}, indent=2))
        else:
            instructions = "" if args.no_system_prompt else load_system_prompt()
            print(ask(args.model, args.prompt, instructions))
        return 0
    except (RuntimeError, ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
