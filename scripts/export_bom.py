#!/usr/bin/env python3
"""Extract Pick-a-Brick / BrickLink Bill of Materials (BOM) from an LDraw file."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bricksmith.io.ldraw import parse_ldr
from bricksmith.io.bom import BillOfMaterials


def main():
    parser = argparse.ArgumentParser(description="Extract Bill of Materials from an LDraw file.")
    parser.add_argument("ldr_file", type=Path, help="Path to input .ldr file")
    parser.add_argument("--csv", type=Path, default=None, help="Output CSV path")
    parser.add_argument("--xml", type=Path, default=None, help="Output BrickLink XML path")
    args = parser.parse_args()

    if not args.ldr_file.exists():
        print(f"Error: {args.ldr_file} does not exist.", file=sys.stderr)
        sys.exit(1)

    graph = parse_ldr(args.ldr_file)
    bom = BillOfMaterials(graph)

    print(f"\n=== Bill of Materials: {args.ldr_file.name} ===")
    print(f"Total Pieces: {bom.total_pieces}")
    print(f"Unique Elements: {bom.unique_elements}\n")
    print(f"{'Part ID':<10} {'Color':<6} {'Color Name':<25} {'Qty':<6}")
    print("-" * 50)
    for entry in bom.entries()[:15]:
        print(f"{entry.part_id:<10} {entry.color_id:<6} {entry.color_name:<25} {entry.quantity:<6}")
    if len(bom.entries()) > 15:
        print(f"... and {len(bom.entries()) - 15} more elements.")

    if args.csv:
        bom.to_csv(args.csv)
        print(f"\nSaved CSV inventory to: {args.csv}")

    if args.xml:
        bom.to_bricklink_xml(args.xml)
        print(f"Saved BrickLink XML to: {args.xml}")


if __name__ == "__main__":
    main()
