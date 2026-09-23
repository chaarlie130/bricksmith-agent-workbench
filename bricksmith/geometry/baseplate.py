"""Certified LEGO Architecture-style bordered baseplate and plinth generator."""
from __future__ import annotations

from bricksmith.core.graph import AssemblyGraph
import numpy as np
from bricksmith.core.part import LDU_PER_STUD, LDU_PER_PLATE


def generate_architecture_baseplate(
    width_studs: int = 16,
    depth_studs: int = 24,
    nameplate_title: str = "ARCHITECTURE",
) -> AssemblyGraph:
    """Generate an authentic LEGO Architecture plinth.
    Structure:
    - Layer 0 (Foundation Plates at y=8 LDU, color=0 Black): Interlocked baseplates.
    - Layer 1 (Surface Tiles at y=0 LDU, color=0 Black): Perimeter border of smooth tiles.
    - Interior building bed with exposed studs for building mounting.
    """
    graph = AssemblyGraph(name=f"baseplate_{width_studs}x{depth_studs}")

    half_w = (width_studs * LDU_PER_STUD) / 2.0
    half_d = (depth_studs * LDU_PER_STUD) / 2.0

    # 1. Foundation layer: standard plates placed at y=8.0 LDU
    # Tile the area using 8x16, 6x12, 4x8, or 2x4 plates
    # For simplicity, we lay a stable grid of 4x8 (3035) or 2x4 (3020) plates
    for x_idx in range(0, width_studs, 4):
        for z_idx in range(0, depth_studs, 4):
            w_step = min(4, width_studs - x_idx)
            d_step = min(4, depth_studs - z_idx)
            
            # Select part stem
            if w_step == 4 and d_step == 4:
                part = "3031" # Plate 4x4
            elif w_step == 2 and d_step == 4:
                part = "3020" # Plate 2x4
            else:
                part = "3022" # Plate 2x2 fallback

            cx = (x_idx + w_step / 2.0) * LDU_PER_STUD - half_w
            cz = (z_idx + d_step / 2.0) * LDU_PER_STUD - half_d

            graph.add_part(
                part_id=part,
                color_id=0, # Black
                transform=np.array([
                    [1, 0, 0, cx],
                    [0, 1, 0, 8.0],
                    [0, 0, 1, cz],
                    [0, 0, 0, 1],
                ], dtype=np.float64),
                metadata={"role": "foundation_plate"}
            )

    # 2. Smooth Tile Border (Layer at y=0 LDU, color=0 Black)
    # North and South edges
    for x_idx in range(0, width_studs, 2):
        cx = (x_idx + 1.0) * LDU_PER_STUD - half_w
        # North border
        cz_n = (0.5) * LDU_PER_STUD - half_d
        graph.add_part(
            part_id="3069b", # 1x2 Tile
            color_id=0,
            transform=np.array([
                [1, 0, 0, cx],
                [0, 1, 0, 0.0],
                [0, 0, 1, cz_n],
                [0, 0, 0, 1],
            ], dtype=np.float64),
            metadata={"role": "border_tile"}
        )
        # South border
        cz_s = (depth_studs - 0.5) * LDU_PER_STUD - half_d
        graph.add_part(
            part_id="3069b", # 1x2 Tile
            color_id=0,
            transform=np.array([
                [1, 0, 0, cx],
                [0, 1, 0, 0.0],
                [0, 0, 1, cz_s],
                [0, 0, 0, 1],
            ], dtype=np.float64),
            metadata={"role": "border_tile"}
        )

    # East and West inner edges
    for z_idx in range(1, depth_studs - 1, 2):
        cz = (z_idx + 1.0) * LDU_PER_STUD - half_d
        # West border
        cx_w = (0.5) * LDU_PER_STUD - half_w
        graph.add_part(
            part_id="3069b", # 1x2 Tile (rotated 90 deg)
            color_id=0,
            transform=np.array([
                [0, 0, -1, cx_w],
                [0, 1, 0, 0.0],
                [1, 0, 0, cz],
                [0, 0, 0, 1],
            ], dtype=np.float64),
            metadata={"role": "border_tile"}
        )
        # East border
        cx_e = (width_studs - 0.5) * LDU_PER_STUD - half_w
        graph.add_part(
            part_id="3069b", # 1x2 Tile (rotated 90 deg)
            color_id=0,
            transform=np.array([
                [0, 0, -1, cx_e],
                [0, 1, 0, 0.0],
                [1, 0, 0, cz],
                [0, 0, 0, 1],
            ], dtype=np.float64),
            metadata={"role": "border_tile"}
        )

    return graph
