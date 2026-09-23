#!/usr/bin/env python3
"""Convert an LDraw model into a BFS spanning tree attachment path sequence."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bricksmith.io.ldraw import parse_ldr
from bricksmith.core.tree import BFSTreeCodec


def main():
    parser = argparse.ArgumentParser(description="Convert an LDraw model into a BFS spanning tree path sequence.")
    parser.add_argument("ldr_file", type=Path, help="Path to input .ldr file")
    parser.add_argument("--limit", "-n", type=int, default=25, help="Number of steps to display")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Save path-text to file")
    args = parser.parse_args()

    if not args.ldr_file.exists():
        print(f"Error: {args.ldr_file} does not exist.", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing {args.ldr_file.name} into AssemblyGraph...")
    graph = parse_ldr(args.ldr_file)
    print(f"Graph loaded: {graph.num_parts} parts.")

    print("Traversing BFS Spanning Tree...")
    tree = BFSTreeCodec.encode(graph)
    path_text = BFSTreeCodec.serialize_path_text(tree)

    print(f"\n=== First {min(args.limit, len(tree))} BFS Spanning Tree Steps ===")
    lines = path_text.splitlines()
    for line in lines[:args.limit]:
        print(line)
    if len(lines) > args.limit:
        print(f"... and {len(lines) - args.limit} more steps.")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(path_text, encoding="utf-8")
        print(f"\nSaved full BFS tree path text to: {args.output}")


if __name__ == "__main__":
    main()
