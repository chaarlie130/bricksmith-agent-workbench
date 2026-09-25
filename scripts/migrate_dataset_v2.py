"""Migrate training and validation JSONL datasets from v1 to v2 codec format."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from bricksmith.training.codec import (
    count_tokens,
    load_codebook,
    serialize_tree,
    tree_nodes_from_target_text,
)

ROOT = Path(__file__).resolve().parents[1]


def migrate_file(path: Path) -> int:
    codebook = load_codebook()
    migrated_lines = []
    with path.open(encoding="utf-8") as f:
        for idx, line in enumerate(f):
            data = json.loads(line)
            old_text = data["text"]
            nodes = tree_nodes_from_target_text(old_text, codebook)

            # Re-serialize to v2
            v2_payload = serialize_tree(nodes, codebook, version=2)
            prefix = old_text.split("[TARGET:")[0] + "[TARGET: Discrete BFS Spanning Tree Path Tokens for that Bag]\n"
            new_text = f"{prefix}{v2_payload}\n"

            # Verify identical node reconstruction
            v2_nodes = tree_nodes_from_target_text(new_text, codebook)
            assert len(nodes) == len(v2_nodes), f"Length mismatch on line {idx}"
            for n1, n2 in zip(nodes, v2_nodes):
                assert n1.part_id == n2.part_id
                assert n1.color_id == n2.color_id
                assert n1.parent_step_index == n2.parent_step_index
                assert n1.parent_port == n2.parent_port
                assert n1.self_port == n2.self_port
                assert n1.conn_type == n2.conn_type
                assert n1.rotation_quarters == n2.rotation_quarters

            data["text"] = new_text
            data["n_tokens"] = count_tokens(new_text)
            migrated_lines.append(json.dumps(data) + "\n")

    # Write back
    with path.open("w", encoding="utf-8") as f:
        f.writelines(migrated_lines)

    return len(migrated_lines)


def main():
    train_path = ROOT / "data/training/train.jsonl"
    val_path = ROOT / "data/training/val.jsonl"
    n_train = migrate_file(train_path)
    print(f"Migrated {n_train} examples in {train_path.name} to v2.")
    n_val = migrate_file(val_path)
    print(f"Migrated {n_val} examples in {val_path.name} to v2.")


if __name__ == "__main__":
    main()
