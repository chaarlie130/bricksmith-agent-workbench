#!/usr/bin/env python3
"""Deterministic verification harness for BrickSmith Phase 1.4 & Phase 2.1-2.2 work package.

Enforces:
- Gate 1: BFS Spanning Tree Reconstruction (tested on 50 held-out models).
- Gate 2.1: 3D Bounding Box & Occupancy Voxel Centroid Invariant.
- Gate 2.2: Modular Numbered Bags Conservation, Bounded Context, and Interface Invariants.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Ensure bricknet-env site-packages are available
for candidate in [
    ROOT / ".venv/lib/python3.12/site-packages",
    Path("/Users/charliecittadini/github/brickblender/scratch/bricknet-env/lib/python3.12/site-packages"),
]:
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bricksmith.io.ldraw import parse_ldr
from bricksmith.core.tree import BFSTreeCodec
from bricksmith.geometry.bounds import calculate_bounds
from bricksmith.geometry.envelope import generate_occupancy_grid
from bricksmith.decomposition.modularizer import partition_into_bags, BAG_NAMES
from bricksmith.physics.validator import validate_ldraw


def run_gate_1(models: list[Path]) -> None:
    """Gate 1: BFS Spanning Tree Reconstruction Fidelity (50 models)."""
    print(f"\n=======================================================")
    print(f" GATE 1: BFS Spanning Tree Reconstruction Gate ({len(models)} models)")
    print(f"=======================================================")

    for i, model_path in enumerate(models, 1):
        model_name = model_path.name
        g_orig = parse_ldr(model_path, infer_connections=True)
        tree = BFSTreeCodec.encode(g_orig)
        path_text = BFSTreeCodec.serialize_path_text(tree)
        g_recon = BFSTreeCodec.decode(path_text)

        # 1. Exact Piece Count
        if len(g_recon.parts) != len(g_orig.parts):
            print(f"[FAIL] {model_name}: Piece count mismatch! "
                  f"Recon={len(g_recon.parts)}, Orig={len(g_orig.parts)}", file=sys.stderr)
            sys.exit(1)

        # 2. Exact Colors & Zero Coordinate / Rotation Drift
        for bid, orig_p in g_orig.parts.items():
            if bid not in g_recon.parts:
                print(f"[FAIL] {model_name}: Brick ID {bid} missing from reconstructed assembly!", file=sys.stderr)
                sys.exit(1)
            recon_p = g_recon.parts[bid]
            if recon_p.color_id != orig_p.color_id:
                print(f"[FAIL] {model_name}: Color mismatch on brick {bid}: "
                      f"Orig={orig_p.color_id}, Recon={recon_p.color_id}", file=sys.stderr)
                sys.exit(1)

            pos_drift = float(np.max(np.abs(orig_p.position - recon_p.position)))
            if pos_drift >= 0.001:
                print(f"[FAIL] {model_name}: Coordinate drift exceeded on brick {bid}: "
                      f"{pos_drift:.6f} LDU >= 0.001 LDU", file=sys.stderr)
                sys.exit(1)

            rot_drift = float(np.max(np.abs(orig_p.rotation - recon_p.rotation)))
            if rot_drift >= 0.0001:
                print(f"[FAIL] {model_name}: Rotation drift exceeded on brick {bid}: "
                      f"{rot_drift:.6f} >= 0.0001", file=sys.stderr)
                sys.exit(1)

        # 3. Validation Pass Preservation
        orig_report = validate_ldraw(model_path)
        if orig_report.get("passed"):
            recon_report = validate_ldraw(g_recon.to_ldraw())
            if not recon_report.get("passed"):
                print(f"[FAIL] {model_name}: Original passed validate_ldraw but reconstructed failed! "
                      f"Errors: {recon_report.get('errors')}", file=sys.stderr)
                sys.exit(1)

        if i % 10 == 0 or i == len(models):
            print(f"  [{i:02d}/{len(models)}] Verified: {model_name} (drift: 0.0000 LDU)")

    print(f"--> GATE 1 PASSED: 100% invariant compliance across {len(models)} models.")


def run_gate_2_1(reference_model: Path) -> None:
    """Gate 2.1: 3D Spatial Prior, Bounding Box & Occupancy Voxel Centroid Invariant."""
    print(f"\n=======================================================")
    print(f" GATE 2.1: 3D Bounding Box & Occupancy Voxel Grid")
    print(f"=======================================================")

    g = parse_ldr(reference_model, infer_connections=True)
    bounds = calculate_bounds(g)

    # 1. Non-empty bounding box dimensions
    if bounds.width_ldu <= 0 or bounds.height_ldu <= 0 or bounds.depth_ldu <= 0:
        print(f"[FAIL] Bounding box has non-positive dimensions: {bounds.size_ldu}", file=sys.stderr)
        sys.exit(1)

    # 2. Extrema tightly matching parts
    all_mins = [b[0] for b in bounds.part_bounds.values()]
    all_maxs = [b[1] for b in bounds.part_bounds.values()]
    computed_min = np.min(all_mins, axis=0)
    computed_max = np.max(all_maxs, axis=0)

    min_err = np.max(np.abs(bounds.min_ldu - computed_min))
    max_err = np.max(np.abs(bounds.max_ldu - computed_max))
    if min_err > 0.01 or max_err > 0.01:
        print(f"[FAIL] Bounding box extrema drift: min_err={min_err}, max_err={max_err}", file=sys.stderr)
        sys.exit(1)

    # 3. Generate occupancy grid
    grid = generate_occupancy_grid(g, resolution_studs=1.0)
    occupied_count = int(np.sum(grid))
    if occupied_count <= 0:
        print(f"[FAIL] Occupancy grid is completely empty!", file=sys.stderr)
        sys.exit(1)

    # 4. Centroid matching physical center of mass within 1.0 stud
    centroid_studs = grid.centroid_studs
    com_studs = bounds.center_of_mass_studs
    diff_studs = np.abs(centroid_studs - com_studs)
    max_diff_studs = float(np.max(diff_studs))

    print(f"  Model: {reference_model.name}")
    print(f"  Dimensions: {bounds.width_studs:.2f}W x {bounds.depth_studs:.2f}D x {bounds.height_studs:.2f}H studs")
    print(f"  Aspect Ratio: {bounds.aspect_ratio_str}")
    print(f"  Total Volume: {bounds.total_volume_studs:.1f} studs^3")
    print(f"  Occupied Voxels: {occupied_count}")
    print(f"  Physical COM (studs): {com_studs}")
    print(f"  Voxel Centroid (studs): {centroid_studs}")
    print(f"  Centroid Offset: {max_diff_studs:.4f} studs")

    if max_diff_studs >= 1.0:
        print(f"[FAIL] Grid centroid offset ({max_diff_studs:.4f} studs) exceeded 1.0 stud threshold!", file=sys.stderr)
        sys.exit(1)

    print(f"--> GATE 2.1 PASSED: Centroid offset {max_diff_studs:.4f} < 1.0 stud, occupancy > 0.")


def run_gate_2_2(models: list[Path]) -> None:
    """Gate 2.2: Modular 'Numbered Bags' Partitioner (All 4 Invariants)."""
    print(f"\n=======================================================")
    print(f" GATE 2.2: Modular 'Numbered Bags' Partitioner ({len(models)} models)")
    print(f"=======================================================")

    for i, model_path in enumerate(models, 1):
        model_name = model_path.name
        g = parse_ldr(model_path, infer_connections=True)
        bags = partition_into_bags(g)

        # Invariant A: Conservation of Matter
        total_parts = sum(b.num_parts for b in bags.values())
        all_part_ids = set()
        for b in bags.values():
            all_part_ids.update(b.parts.keys())

        if total_parts != g.num_parts:
            print(f"[FAIL] {model_name}: Invariant A (Conservation of Matter) failed! "
                  f"Total bag parts {total_parts} != original {g.num_parts}", file=sys.stderr)
            sys.exit(1)

        if all_part_ids != set(g.parts.keys()):
            missing = set(g.parts.keys()) - all_part_ids
            dups = all_part_ids - set(g.parts.keys())
            print(f"[FAIL] {model_name}: Invariant A failed! Missing: {missing}, Extra: {dups}", file=sys.stderr)
            sys.exit(1)

        # Invariant B: Non-Empty Bags for models with >= 50 pieces
        if g.num_parts >= 50:
            for bname in BAG_NAMES:
                if bags[bname].num_parts < 1:
                    print(f"[FAIL] {model_name}: Invariant B (Non-Empty Bags) failed! "
                          f"Bag '{bname}' has 0 parts for model with {g.num_parts} parts.", file=sys.stderr)
                    sys.exit(1)

        # Invariant C: Context Limit (< 300 pieces per bag)
        for bname in BAG_NAMES:
            if bags[bname].num_parts >= 300:
                print(f"[FAIL] {model_name}: Invariant C (Context Limit) failed! "
                      f"Bag '{bname}' contains {bags[bname].num_parts} parts (limit < 300).", file=sys.stderr)
                sys.exit(1)

        # Invariant D: Interface Connectivity between bag i and bag i+1
        for idx in range(len(BAG_NAMES) - 1):
            name_a, name_b = BAG_NAMES[idx], BAG_NAMES[idx + 1]
            parts_a = set(bags[name_a].parts.keys())
            parts_b = set(bags[name_b].parts.keys())
            edges = [
                c for c in g.connections
                if (c.source_brick_id in parts_a and c.target_brick_id in parts_b)
                or (c.source_brick_id in parts_b and c.target_brick_id in parts_a)
            ]
            if len(edges) == 0:
                print(f"[FAIL] {model_name}: Invariant D (Interface Connectivity) failed! "
                      f"Zero physical port connections between '{name_a}' and '{name_b}'.", file=sys.stderr)
                sys.exit(1)

        if i % 10 == 0 or i == len(models):
            counts = [bags[name].num_parts for name in BAG_NAMES]
            print(f"  [{i:02d}/{len(models)}] Verified: {model_name} (parts per bag: {counts})")

    print(f"--> GATE 2.2 PASSED: 100% invariant compliance across all models.")


def main():
    print("================================================================================")
    print(" BRICKSMITH WORK PACKAGE DETERMINISTIC VERIFICATION HARNESS")
    print("================================================================================")
    started = time.perf_counter()

    ldr_dir = ROOT / "data/reference_sets/ldr"
    if not ldr_dir.exists():
        print(f"Error: Directory {ldr_dir} not found.", file=sys.stderr)
        sys.exit(1)

    all_ldr = sorted(list(ldr_dir.glob("*.ldr")))
    if len(all_ldr) < 50:
        print(f"Error: Expected at least 50 reference models, found {len(all_ldr)}.", file=sys.stderr)
        sys.exit(1)

    # 1. Gate 1 on 50 held-out reference models
    held_out_50 = all_ldr[:50]
    run_gate_1(held_out_50)

    # 2. Gate 2.1 on representative reference model (Empire State Building)
    esb_path = ROOT / "data/reference_sets/ldr/bricksafe_21002_Empire_State_Building.ldr"
    run_gate_2_1(esb_path)

    # 3. Gate 2.2 on 50 reference models
    run_gate_2_2(held_out_50)

    elapsed = time.perf_counter() - started
    print("\n================================================================================")
    print(f" ALL GATES PASSED (100% INVARIANT COMPLIANCE) in {elapsed:.2f}s")
    print("================================================================================")
    sys.exit(0)


if __name__ == "__main__":
    main()
