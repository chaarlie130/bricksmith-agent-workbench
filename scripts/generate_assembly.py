#!/usr/bin/env python3
"""Sample a validity-masked attachment assembly from a coarse 3D bound."""
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bricksmith.core.tree import BFSTreeCodec
from bricksmith.decomposition.modularizer import partition_into_bags
from bricksmith.generation.assemble import generate_guided_assembly, module_box_from_studs
from bricksmith.geometry.bounds import calculate_bounds
from bricksmith.io.ldraw import save_ldr
from bricksmith.training.format_dataset import CORPUS_PATH, TRAIN_PATH, VAL_PATH, graph_from_record


def held_out_model_id() -> str:
    train_ids = set()
    with TRAIN_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                train_ids.add(json.loads(line)["model_id"])
    with VAL_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            model_id = json.loads(line)["model_id"]
            if model_id not in train_ids:
                return model_id
    raise SystemExit("no validation model is absent from the training split")


def bound_from_model(model_id: str) -> tuple:
    with CORPUS_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record["model_id"] != model_id:
                continue
            graph = graph_from_record(record)
            bags = partition_into_bags(graph)
            host = max(bags.values(), key=lambda bag: bag.num_parts)
            bounds = calculate_bounds(host)
            width = max(16.0, math.ceil(bounds.width_studs))
            depth = max(16.0, math.ceil(bounds.depth_studs))
            height = max(18.0, math.ceil(bounds.height_studs))
            return model_id, module_box_from_studs(width, depth, height)
    raise SystemExit(f"{model_id} is not in the BFS corpus")


def main() -> None:
    parser = argparse.ArgumentParser(description="Guided BFS attachment generation inside a coarse 3D bound.")
    parser.add_argument("--width", type=float, default=None, help="Module width in studs")
    parser.add_argument("--depth", type=float, default=None, help="Module depth in studs")
    parser.add_argument("--height", type=float, default=None, help="Module height in studs")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--pieces", type=int, default=8)
    parser.add_argument("--adapter-path", type=Path, default=ROOT / "adapters" / "phase3a")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Destination .ldr path")
    args = parser.parse_args()

    if args.width and args.depth and args.height:
        model_id = held_out_model_id()
        module_min, module_max = module_box_from_studs(args.width, args.depth, args.height)
    else:
        model_id, (module_min, module_max) = bound_from_model(held_out_model_id())
    print(f"held-out model: {model_id}")
    graph = generate_guided_assembly(
        module_min,
        module_max,
        seed=args.seed,
        adapter_path=str(args.adapter_path),
        target_pieces=args.pieces,
    )
    save_ldr(graph, args.output, title=graph.name)
    print("realized with BFSTreeCodec.decode")
    print(f"Wrote {args.output}")
    root = min(graph.parts.values(), key=lambda part: part.instance_id)
    print(f"Base plate: {root.part_id}")
    print(f"Piece count: {graph.num_parts}")
    print(f"Part ids: {sorted({part.part_id for part in graph.parts.values()})}")
    print(f"Seed: {args.seed}")
    print(
        "Bound LDU: "
        f"{module_min[0]:.1f},{module_min[1]:.1f},{module_min[2]:.1f} -> "
        f"{module_max[0]:.1f},{module_max[1]:.1f},{module_max[2]:.1f}"
    )
    # Touch the codec name so the log records the decoder that realized the graph.
    assert graph.num_parts == len(BFSTreeCodec.encode(graph))


if __name__ == "__main__":
    main()
