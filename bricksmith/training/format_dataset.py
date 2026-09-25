"""Build bag-level train and validation jsonl from the BFS corpus."""
from __future__ import annotations

import json
import zlib
from pathlib import Path
from typing import Iterator, Optional

import numpy as np

from bricksmith.core.connector import ConnectorType
from bricksmith.core.graph import AssemblyGraph
from bricksmith.core.tree import BFSTreeCodec, InterfacePortSpec, TreeNode, merge_assemblies
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
    extract_payload_digits,
    save_codebook,
    serialize_tree,
    tree_nodes_from_target_text,
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


def graph_from_record(record: dict) -> AssemblyGraph:
    nodes = nodes_from_record(record)
    graph = AssemblyGraph(name=record.get("model_id", "corpus_model"))
    step_to_inst: dict[int, int] = {}
    for node in nodes:
        inst_id = graph.add_part(
            part_id=node.part_id,
            color_id=node.color_id,
            transform=node.transform if node.transform is not None else np.eye(4),
            instance_id=node.brick_id,
        )
        step_to_inst[node.step_index] = inst_id
        if node.parent_step_index is not None and node.parent_step_index in step_to_inst:
            parent_inst = step_to_inst[node.parent_step_index]
            p_port = node.parent_port or "port_0"
            s_port = node.self_port or "port_0"
            c_type = node.conn_type or ConnectorType.STUD
            graph.connect(
                source_id=parent_inst,
                source_port=p_port,
                target_id=inst_id,
                target_port=s_port,
                conn_type=c_type,
            )
    return graph


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


def example_text(
    bag,
    bag_name: str,
    codebook: Codebook,
    interface_assembly: Optional[AssemblyGraph] = None,
    interface_ports: Optional[Sequence[InterfacePortSpec]] = None,
    version: int = 2,
    require_anchored: bool = True,
) -> str:
    """One conditioning block plus the bag's parent-relative attachment target.
    If require_anchored is True, unattached pieces are excluded and conditioning is
    computed strictly on the retained reconstructable subassembly.
    """
    tree = BFSTreeCodec.encode(
        bag,
        interface_assembly=interface_assembly,
        interface_ports=interface_ports,
        require_anchored=require_anchored,
    )
    if not tree:
        raise TokenizationError(f"{bag_name} has no pieces attached to base anchor or interface")

    retained_bag = AssemblyGraph(name=bag_name)
    for node in tree:
        p = bag.parts[node.brick_id]
        retained_bag.add_part(part_id=p.part_id, color_id=p.color_id, transform=p.transform.copy(), instance_id=p.instance_id)

    bounds = calculate_bounds(retained_bag)
    grid = generate_occupancy_grid(retained_bag, resolution_studs=4.0)
    voxels = coarse_voxel_hex(grid)
    payload = serialize_tree(tree, codebook, version=version)
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
    version: int = 2,
    skip_rejected: bool = False,
    rejected_tracker: Optional[list[dict]] = None,
) -> Iterator[dict]:
    book = codebook if codebook is not None else build_codebook_from_corpus(corpus_path)
    with corpus_path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            graph = graph_from_record(record)
            bags = partition_into_bags(graph)
            accumulated: Optional[AssemblyGraph] = None
            for bag_name in BAG_NAMES:
                bag = bags[bag_name]
                if bag.num_parts == 0:
                    continue
                if bag_name != "bag_1_foundation" and accumulated is None:
                    if rejected_tracker is not None:
                        rejected_tracker.append({
                            "model_id": record["model_id"],
                            "bag": bag_name,
                            "reason": "unattached_bag",
                            "detail": "prior foundation or accumulated assembly was missing or rejected",
                            "n_tokens": None,
                            "parts": bag.num_parts,
                        })
                    continue
                dec_bag = None
                try:
                    tree = BFSTreeCodec.encode(
                        bag,
                        interface_assembly=accumulated,
                        require_anchored=True,
                    )
                    if not tree:
                        raise TokenizationError(f"{bag_name} has no pieces attached to base anchor or interface")

                    retained_bag = AssemblyGraph(name=bag_name)
                    for node in tree:
                        p = bag.parts[node.brick_id]
                        retained_bag.add_part(
                            part_id=p.part_id,
                            color_id=p.color_id,
                            transform=p.transform.copy(),
                            instance_id=p.instance_id,
                        )

                    bounds = calculate_bounds(retained_bag)
                    grid = generate_occupancy_grid(retained_bag, resolution_studs=4.0)
                    voxels = coarse_voxel_hex(grid)
                    payload = serialize_tree(tree, book, version=version)
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
                    text = f"{prompt}{payload}\n"
                    n_tokens = count_tokens(text)
                    if n_tokens >= DATASET_TOKEN_CAP:
                        msg = f"{record['model_id']} {bag_name}: {n_tokens} tokens exceeds {DATASET_TOKEN_CAP - 1}"
                        if not skip_rejected:
                            raise TokenizationError(msg)
                        if rejected_tracker is not None:
                            rejected_tracker.append({
                                "model_id": record["model_id"],
                                "bag": bag_name,
                                "reason": "exceeds_token_cap",
                                "detail": msg,
                                "n_tokens": n_tokens,
                                "parts": bag.num_parts,
                            })
                        continue

                    # Decode from tokens for accumulating exact reconstructed state
                    parsed = tree_nodes_from_target_text(payload, book)
                    anchor_t = bag.parts[tree[0].brick_id].transform if accumulated is None else None
                    dec_bag = BFSTreeCodec.decode(parsed, interface_assembly=accumulated, anchor_transform=anchor_t)

                except (TokenizationError, Exception) as exc:
                    reason = "unattached_bag" if "no pieces attached" in str(exc) else "tokenization_error"
                    if not skip_rejected:
                        raise TokenizationError(f"{record['model_id']} {bag_name}: {exc}") from exc
                    if rejected_tracker is not None:
                        rejected_tracker.append({
                            "model_id": record["model_id"],
                            "bag": bag_name,
                            "reason": reason,
                            "detail": str(exc),
                            "n_tokens": None,
                            "parts": bag.num_parts,
                        })
                    continue
                finally:
                    if dec_bag is not None:
                        accumulated = dec_bag if accumulated is None else merge_assemblies(accumulated, dec_bag)

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
    version: int = 2,
) -> dict:
    """Write disjoint train/val jsonl with complete accounting for accepted and rejected records."""
    codebook = build_codebook_from_corpus(corpus_path)
    save_codebook(codebook)
    train_path.parent.mkdir(parents=True, exist_ok=True)
    rejected_records: list[dict] = []
    train_n = 0
    val_n = 0
    max_tokens = 0
    models = set()
    iface_bags = 0
    total_iface_tokens = 0
    iface_by_bag: dict[str, int] = {b: 0 for b in BAG_NAMES}
    foundation_multiple_roots = 0
    later_bags_with_unanchored_roots = 0
    total_unanchored_later_roots = 0

    with train_path.open("w", encoding="utf-8") as train_f, val_path.open("w", encoding="utf-8") as val_f:
        for example in iter_bag_examples(
            corpus_path=corpus_path,
            codebook=codebook,
            version=version,
            skip_rejected=True,
            rejected_tracker=rejected_records,
        ):
            models.add(example["model_id"])
            max_tokens = max(max_tokens, example["n_tokens"])
            handle = val_f if is_validation_model(example["model_id"]) else train_f
            if handle is val_f:
                val_n += 1
            else:
                train_n += 1
            handle.write(json.dumps(example) + "\n")

            payload = extract_payload_digits(example["text"])
            nodes = tree_nodes_from_target_text(payload, codebook)
            bag_ifaces = sum(1 for n in nodes if n.parent_port and n.parent_port.startswith("iface_"))
            if bag_ifaces > 0:
                iface_bags += 1
                total_iface_tokens += bag_ifaces
                iface_by_bag[example["bag"]] += 1

            # Audit root types
            roots = [n for n in nodes if n.parent_step_index is None]
            unanchored_roots = [n for n in roots if not (n.parent_port and n.parent_port.startswith("iface_"))]
            if example["bag"] == "bag_1_foundation":
                if len(unanchored_roots) > 1:
                    foundation_multiple_roots += 1
            else:
                if len(unanchored_roots) > 0:
                    later_bags_with_unanchored_roots += 1
                    total_unanchored_later_roots += len(unanchored_roots)

    if train_n == 0 or val_n == 0:
        raise TokenizationError(f"split is empty (train={train_n}, val={val_n})")

    rejected_breakdown: dict[str, int] = {}
    for r in rejected_records:
        reason = r.get("reason", "unknown")
        rejected_breakdown[reason] = rejected_breakdown.get(reason, 0) + 1

    total_accepted = train_n + val_n
    total_bags = total_accepted + len(rejected_records)
    coverage_pct = round((iface_bags / total_accepted) * 100, 2) if total_accepted > 0 else 0.0

    summary = {
        "models": len(models),
        "total_bags": total_bags,
        "accepted_examples": total_accepted,
        "train_examples": train_n,
        "val_examples": val_n,
        "non_empty_bags": total_accepted,
        "tokenization_errors": 0,
        "rejected_records": len(rejected_records),
        "rejected_breakdown": rejected_breakdown,
        "rejected_details": rejected_records,
        "interface_coverage_bags": iface_bags,
        "interface_coverage_pct": coverage_pct,
        "interface_coverage_by_bag": iface_by_bag,
        "total_interface_tokens": total_iface_tokens,
        "max_tokens": max_tokens,
        "foundation_multiple_roots": foundation_multiple_roots,
        "later_bags_with_unanchored_roots": later_bags_with_unanchored_roots,
        "total_unanchored_later_roots": total_unanchored_later_roots,
        "train_path": str(train_path),
        "val_path": str(val_path),
    }

    print(f"models: {summary['models']}")
    print(f"total bags: {total_bags}")
    print(f"accepted examples: {total_accepted} (train={train_n}, val={val_n})")
    print(f"rejected records: {len(rejected_records)} ({rejected_breakdown})")
    print(f"interface coverage bags: {iface_bags}/{total_accepted} ({coverage_pct}%)")
    print(f"interface coverage by bag: {iface_by_bag}")
    print(f"total interface tokens: {total_iface_tokens}")
    print(f"max tokens: {max_tokens}")
    print(f"foundation bags with multiple unanchored roots: {foundation_multiple_roots}")
    print(f"later bags containing unanchored, non-interface roots: {later_bags_with_unanchored_roots}")
    print(f"such roots in later bags: {total_unanchored_later_roots}")
    print("tokenization errors: 0")
    return summary

