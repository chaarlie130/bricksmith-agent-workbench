#!/usr/bin/env python3
"""Run construction, collision, and static equilibrium validation on an LDraw model."""
import argparse
import json
import sys
from pathlib import Path

# Add repo root to sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bricksmith.physics.validator import validate_ldraw


def main():
    parser = argparse.ArgumentParser(description="Validate an LDraw file for physical stability, collisions, and syntax.")
    parser.add_argument("ldr_file", type=Path, help="Path to .ldr file to validate")
    parser.add_argument("--json", action="store_true", help="Output full JSON validation report")
    parser.add_argument("--scope", type=Path, default=None, help="Custom scope JSON config")
    args = parser.parse_args()

    if not args.ldr_file.exists():
        print(f"Error: File {args.ldr_file} does not exist.", file=sys.stderr)
        sys.exit(1)

    report = validate_ldraw(args.ldr_file, scope_path=str(args.scope) if args.scope else None)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status = "PASSED" if report.get("passed") else "FAILED"
        color = "\033[92m" if report.get("passed") else "\033[91m"
        reset = "\033[0m"

        print(f"\n{color}=== Validation Result: {status} ==={reset}")
        print(f"File: {args.ldr_file.name}")
        print(f"Piece Count: {report.get('physical_piece_count', 0)}")
        print(f"Checks:")
        for check, res in report.get("checks", {}).items():
            print(f"  - {check}: {'✓' if res else '✗'}")

        if report.get("errors"):
            print(f"\nErrors ({len(report['errors'])}):")
            for err in report["errors"]:
                print(f"  ! [{err.get('kind')}]: {err}")
        print(f"Elapsed: {report.get('elapsed_seconds', 0):.4f}s\n")

    sys.exit(0 if report.get("passed") else 1)


if __name__ == "__main__":
    main()
