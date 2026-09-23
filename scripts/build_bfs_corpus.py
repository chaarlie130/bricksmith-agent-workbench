#!/usr/bin/env python3
"""Batch convert reference architecture models into BFS spanning tree token sequences."""
import argparse
import json
import sys
from pathlib import Path
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, desc=""):
        return iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bricksmith.io.ldraw import parse_ldr
from bricksmith.core.tree import BFSTreeCodec


def main():
    parser = argparse.ArgumentParser(description="Build BFS Spanning Tree Corpus from Reference LDraw Models.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=ROOT / "data/reference_sets/ldr",
        help="Directory containing reference .ldr models",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=ROOT / "data/corpus/reference_bfs_trees.jsonl",
        help="Destination .jsonl corpus path",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional limit on number of models to process")
    args = parser.parse_args()

    if not args.input_dir.exists():
        print(f"Error: input directory {args.input_dir} not found.", file=sys.stderr)
        sys.exit(1)

    ldr_files = sorted(list(args.input_dir.glob("*.ldr")))
    if args.limit:
        ldr_files = ldr_files[:args.limit]

    print(f"Processing {len(ldr_files)} reference models into BFS spanning tree corpus...")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    success_count = 0
    total_parts = 0

    with open(args.output, "w", encoding="utf-8") as out_f:
        for f in tqdm(ldr_files, desc="Encoding BFS Trees"):
            try:
                graph = parse_ldr(f, infer_connections=True)
                tree = BFSTreeCodec.encode(graph)
                path_text = BFSTreeCodec.serialize_path_text(tree)

                record = {
                    "model_id": f.name,
                    "num_parts": len(graph.parts),
                    "num_steps": len(tree),
                    "path_text": path_text,
                    "nodes": [
                        {
                            "step_index": n.step_index,
                            "brick_id": n.brick_id,
                            "part_id": n.part_id,
                            "color_id": n.color_id,
                            "parent_step_index": n.parent_step_index,
                            "parent_port": n.parent_port,
                            "self_port": n.self_port,
                            "conn_type": n.conn_type.value if n.conn_type else None,
                            "transform": n.transform.tolist(),
                        }
                        for n in tree
                    ],
                }
                out_f.write(json.dumps(record) + "\n")
                success_count += 1
                total_parts += len(tree)
            except Exception as e:
                print(f"Error processing {f.name}: {e}", file=sys.stderr)

    print(f"\nCorpus successfully built:")
    print(f"  - Output file: {args.output}")
    print(f"  - Models converted: {success_count}/{len(ldr_files)}")
    print(f"  - Total BFS tree steps: {total_parts:,}")


if __name__ == "__main__":
    main()
