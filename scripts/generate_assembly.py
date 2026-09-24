#!/usr/bin/env python3
"""Sample a validity-masked attachment assembly from a coarse 3D bound."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bricksmith.generation.assemble import generate_guided_assembly, module_box_from_studs
from bricksmith.io.ldraw import save_ldr


def main() -> None:
    parser = argparse.ArgumentParser(description="Guided BFS attachment generation inside a coarse 3D bound.")
    parser.add_argument("--width", type=float, default=16.0, help="Module width in studs")
    parser.add_argument("--depth", type=float, default=16.0, help="Module depth in studs")
    parser.add_argument("--height", type=float, default=12.0, help="Module height in studs")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("-o", "--output", type=Path, required=True, help="Destination .ldr path")
    args = parser.parse_args()

    module_min, module_max = module_box_from_studs(args.width, args.depth, args.height)
    graph = generate_guided_assembly(module_min, module_max, seed=args.seed)
    save_ldr(graph, args.output, title=graph.name)
    print("realized with BFSTreeCodec.decode")
    print(f"Wrote {args.output}")
    print(f"Piece count: {graph.num_parts}")
    print(f"Seed: {args.seed}")
    print(
        "Bound LDU: "
        f"{module_min[0]:.1f},{module_min[1]:.1f},{module_min[2]:.1f} -> "
        f"{module_max[0]:.1f},{module_max[1]:.1f},{module_max[2]:.1f}"
    )


if __name__ == "__main__":
    main()
