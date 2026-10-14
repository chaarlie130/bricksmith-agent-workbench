#!/usr/bin/env python3
"""Run the final acceptance gate for a BrickSmith LDraw build."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bricksmith.workbench.acceptance import make_acceptance_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path, help="Final .ldr model")
    parser.add_argument("--ground-y", type=float, default=8.0)
    parser.add_argument("--min-pieces", type=int, default=500,
                        help="Minimum physical pieces for acceptance (default: 500)")
    parser.add_argument("--max-pieces", type=int, default=1000,
                        help="Maximum physical pieces for acceptance (default: 1000)")
    parser.add_argument("--stage-model", action="append", default=[], type=Path, metavar="LDR",
                        help="Saved major-stage .ldr to validate (repeat for foundation/walls, openings, roof)")
    parser.add_argument("--inspected-view", action="append", default=[], choices=["front_left", "front_right"],
                        help="Record a final render actually inspected; repeat for both views")
    parser.add_argument("--render-dir", type=Path, required=True,
                        help="Directory for final front-left and front-right renders")
    parser.add_argument("--report", type=Path, default=None, help="JSON report path (default: <render-dir>/acceptance.json)")
    args = parser.parse_args()
    if args.min_pieces < 1 or args.max_pieces < args.min_pieces:
        parser.error("piece target must have 1 <= --min-pieces <= --max-pieces")
    report = make_acceptance_report(args.model, ground_y=args.ground_y,
                                    min_pieces=args.min_pieces, max_pieces=args.max_pieces,
                                    stage_models=args.stage_model,
                                    inspected_views=args.inspected_view,
                                    render_dir=args.render_dir)
    report_path = args.report or args.render_dir / "acceptance.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Acceptance report: {report_path}")
    return 0 if report["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
