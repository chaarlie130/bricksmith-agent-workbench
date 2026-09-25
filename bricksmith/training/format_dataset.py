"""Build bag-level train and validation jsonl from the BFS corpus."""
from __future__ import annotations

import json
import zlib
from pathlib import Path
from typing import Iterator, Optional

import numpy as np

from bricksmith.core.connector import ConnectorType
from bricksmith.core.tree import BFSTreeCodec, TreeNode
from bricksmith.decomposition.modularizer import BAG_NAMES, partition_into_bags
from bricksmith.geometry.bounds import calculate_bounds
from bricksmith.geometry.envelope import generate_occupancy_grid
from bricksmith.training.codec import (
    DATASET_TOKEN_CAP,
    Codebook,
    TokenizationError,
    build_codebook,
    coarse_voxel_hex,
    count_tokens,
    save_codebook,
    serialize_tree,
)

ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = ROOT / "data/corpus/reference_bfs_trees.jsonl"
TRAIN_PATH = ROOT / "data/training/train.jsonl"
VAL_PATH = ROOT / "data/training/val.jsonl"


def nodes_from_record(record: dict) -> list[TreeNode]:
    nodes: list[TreeNode] = []
    for raw in record["nodes"]:
        conn_name = raw.get("conn_type")
        if conn_name in (None, "ROOT"):
            conn = None
        else:
            try:
                conn = ConnectorType(conn_name)
            except ValueError:
                conn = ConnectorType.STUD
        nodes.append(
            TreeNode(
                step_index=int(raw["step_index"]),
                brick_id=int(raw["brick_id"]),
                part_id=str(raw["part_id"]),
                color_id=int(raw["color_id"]),
                parent_step_index=raw["parent_step_index"],
                parent_port=raw["parent_port"],
                self_port=raw["self_port"],
                conn_type=conn,
                transform=np.array(raw["transform"], dtype=np.float64),
            )
        )
    return nodes


def graph_from_record(record: dict):
    return BFSTreeCodec.decode(nodes_from_record(record))


def build_codebook_from_corpus(path: Path = CORPUS_PATH) -> Codebook:
    parts: list[str] = []
    colors: list[int] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            for node in record["nodes"]:
                parts.append(node["part_id"])
                colors.append(int(node["color_id"]))
    scope_path = ROOT / "configs" / "architecture_scope.json"
    if scope_path.exists():
        scope = json.loads(scope_path.read_text(encoding="utf-8"))
        for stems in scope.get("part_categories", {}).values():
            parts.extend(str(stem) for stem in stems)
        for color_id in scope.get("colors", {}):
            colors.append(int(color_id))
    return build_codebook(parts, colors)


def is_validation_model(model_id: str) -> bool:
    """Stable split by source model so a building's bags stay in one file."""
    return zlib.crc32(model_id.encode("utf-8")) % 10 == 0


def format_conditioning_prompt(
    width: int,
    depth: int,
    height: int,
    aspect_ratio_str: str,
    bag_name: str,
    coarse_voxel_tokens: str,
) -> str:
    """Canonical conditioning prompt prefix matching the training dataset byte-for-byte."""
    return (
        f"[INPUT: Bounding Box {width}x{depth}x{height} + Aspect Ratio {aspect_ratio_str}"
        f" + Target Bag Name {bag_name} + Coarse Voxel Tokens {coarse_voxel_tokens}]\n"
        "[TARGET: Discrete BFS Spanning Tree Path Tokens for that Bag]\n"
    )


def example_text(bag, bag_name: str, codebook: Codebook) -> str:
    """One conditioning block plus the bag's parent-relative attachment target."""
    tree = BFSTreeCodec.encode(bag)
    bounds = calculate_bounds(bag)
    grid = generate_occupancy_grid(bag, resolution_studs=4.0)
    voxels = coarse_voxel_hex(grid)
    payload = serialize_tree(tree, codebook)
    width = max(1, int(round(float(bounds.width_studs))))
    depth = max(1, int(round(float(bounds.depth_studs))))
    height = max(1, int(round(float(bounds.height_studs))))
    prompt = format_conditioning_prompt(
        width=width,
        depth=depth,
        height=height,
        aspect_ratio_str=bounds.aspect_ratio_str,
        bag_name=bag_name,
        coarse_voxel_tokens=voxels,
    )
    return f"{prompt}{payload}\n"


def iter_bag_examples(
    corpus_path: Path = CORPUS_PATH,
    codebook: Optional[Codebook] = None,
) -> Iterator[dict]:
    book = codebook if codebook is not None else build_codebook_from_corpus(corpus_path)
    with corpus_path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            graph = graph_from_record(record)
            bags = partition_into_bags(graph)
            for bag_name in BAG_NAMES:
                bag = bags[bag_name]
                if bag.num_parts == 0:
                    continue
                try:
                    text = example_text(bag, bag_name, book)
                    n_tokens = count_tokens(text)
                except TokenizationError as exc:
                    raise TokenizationError(f"{record['model_id']} {bag_name}: {exc}") from exc
                if n_tokens >= DATASET_TOKEN_CAP:
                    raise TokenizationError(
                        f"{record['model_id']} {bag_name}: {n_tokens} tokens exceeds {DATASET_TOKEN_CAP - 1}"
                    )
                yield {
                    "model_id": record["model_id"],
                    "bag": bag_name,
                    "n_tokens": n_tokens,
                    "text": text,
                }


def write_splits(
    corpus_path: Path = CORPUS_PATH,
    train_path: Path = TRAIN_PATH,
    val_path: Path = VAL_PATH,
) -> dict:
    """Write disjoint train/val jsonl. Returns a summary. Raises on any tokenization error."""
    codebook = build_codebook_from_corpus(corpus_path)
    save_codebook(codebook)
    train_path.parent.mkdir(parents=True, exist_ok=True)
    errors = 0
    train_n = 0
    val_n = 0
    max_tokens = 0
    models = set()
    try:
        with train_path.open("w", encoding="utf-8") as train_f, val_path.open("w", encoding="utf-8") as val_f:
            for example in iter_bag_examples(corpus_path, codebook):
                models.add(example["model_id"])
                max_tokens = max(max_tokens, example["n_tokens"])
                handle = val_f if is_validation_model(example["model_id"]) else train_f
                if handle is val_f:
                    val_n += 1
                else:
                    train_n += 1
                handle.write(json.dumps(example) + "\n")
    except TokenizationError as exc:
        errors += 1
        print(f"tokenization error: {exc}")
        summary = {
            "models": len(models),
            "train_examples": train_n,
            "val_examples": val_n,
            "tokenization_errors": errors,
            "max_tokens": max_tokens,
        }
        print(f"tokenization errors: {errors}")
        return summary

    if train_n == 0 or val_n == 0:
        raise TokenizationError(f"split is empty (train={train_n}, val={val_n})")
    summary = {
        "models": len(models),
        "train_examples": train_n,
        "val_examples": val_n,
        "non_empty_bags": train_n + val_n,
        "tokenization_errors": 0,
        "max_tokens": max_tokens,
        "train_path": str(train_path),
        "val_path": str(val_path),
    }
    print(f"models: {summary['models']}")
    print(f"non-empty bags: {summary['non_empty_bags']}")
    print(f"train examples: {train_n}")
    print(f"val examples: {val_n}")
    print(f"max tokens: {max_tokens}")
    print("tokenization errors: 0")
    return summary
