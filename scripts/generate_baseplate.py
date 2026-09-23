#!/usr/bin/env python3
"""Generate a certified LEGO Architecture-style bordered plinth."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bricksmith.geometry.baseplate import generate_architecture_baseplate
from bricksmith.io.ldraw import save_ldr


def main():
    parser = argparse.ArgumentParser(description="Generate a certified LEGO Architecture plinth.")
    parser.add_argument("--width", "-w", type=int, default=16, help="Width in studs (default: 16)")
    parser.add_argument("--depth", "-d", type=int, default=24, help="Depth in studs (default: 24)")
    parser.add_argument("--output", "-o", type=Path, default=Path("baseplate.ldr"), help="Output .ldr file path")
    args = parser.parse_args()

    print(f"Generating LEGO Architecture Baseplate ({args.width}x{args.depth} studs)...")
    graph = generate_architecture_baseplate(width_studs=args.width, depth_studs=args.depth)
    save_ldr(graph, args.output, title=f"Architecture Plinth {args.width}x{args.depth}")
    print(f"Created baseplate with {graph.num_parts} parts at {args.output}")


if __name__ == "__main__":
    main()
