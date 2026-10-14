#!/usr/bin/env python3
"""Start or advance a BrickSmith design session by exactly one model request."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bricksmith.workbench.agent_session import load_session, queue_renders, run_session, start_session, step_session


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start", help="create a saved session without model usage")
    start.add_argument("directory", type=Path)
    start.add_argument("--brief", required=True)
    start.add_argument("--model", default="gpt-5.6-sol")
    start.add_argument("--target-pieces", default="500–1000")
    start.add_argument("--ground-y", type=float, default=8.0,
                       help="LDraw ground plane (8 for a 3811 baseplate, 0 for plate-built plinths)")
    start.add_argument("--reference-image", type=Path, help="optional PNG/JPEG/WebP design reference")
    run = sub.add_parser("step", help="make one model request and execute bounded local tools")
    run.add_argument("directory", type=Path)
    run.add_argument("--message", help="optional operator follow-up for this step")
    loop = sub.add_parser("run", help="continue bounded model/tool turns; each request and tool result is saved")
    loop.add_argument("directory", type=Path)
    loop.add_argument("--message", help="optional operator follow-up for the first request")
    loop.add_argument("--max-requests", type=int, default=4, help="hard limit of 1-8 model requests (default 4)")
    loop.add_argument("--max-total-tokens", type=int, default=60000,
                      help="soft aggregate token ceiling; one request may exceed it")
    queue = sub.add_parser("queue-render", help="render views locally for the next step; no model usage")
    queue.add_argument("directory", type=Path)
    queue.add_argument("--view", action="append", required=True,
                       choices=["front_left", "front_right", "back_left", "back_right", "top"])
    status = sub.add_parser("status", help="inspect saved session without model usage")
    status.add_argument("directory", type=Path)
    status.add_argument("--full-events", action="store_true",
                        help="include complete event usage attribution instead of a compact recent summary")
    args = parser.parse_args()
    try:
        if args.command == "start":
            state = start_session(args.directory, args.brief, model=args.model,
                                  target_pieces=args.target_pieces,
                                  reference_image=args.reference_image, ground_y=args.ground_y)
            result = {"directory": str(args.directory.resolve()), "model": state["model"],
                      "ground_y": state["ground_y"], "step": 0}
        elif args.command == "step":
            result = step_session(args.directory, message=args.message)
        elif args.command == "run":
            result = run_session(args.directory, max_requests=args.max_requests,
                                 max_total_tokens=args.max_total_tokens, message=args.message)
        elif args.command == "queue-render":
            result = queue_renders(args.directory, args.view)
        else:
            state = load_session(args.directory)
            events = state["events"] if args.full_events else [
                {"step": event.get("step"), "tools": event.get("tools", []),
                 "input_tokens": (event.get("usage") or {}).get("input_tokens"),
                 "output_tokens": (event.get("usage") or {}).get("output_tokens")}
                for event in state["events"][-12:]
            ]
            result = {"model": state["model"], "brief": state["brief"],
                      "ground_y": state.get("ground_y", 8.0),
                      "step": state["step"], "modules": state["module_order"],
                      "last_validation": state["last_validation"],
                      "pending_images": state.get("pending_images", []),
                      "events_total": len(state["events"]),
                      "events": events}
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
