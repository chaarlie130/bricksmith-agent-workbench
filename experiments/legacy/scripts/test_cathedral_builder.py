#!/usr/bin/env python3
"""Prototype test script for 1000+ piece Grand Romanesque Cathedral."""
from __future__ import annotations
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bricksmith.workbench.feedback import check_model

# Colors
BLACK = 0
WHITE = 15
TAN = 19
DARK_TAN = 28
TRANS_LIGHT_BLUE = 47
REDDISH_BROWN = 70
LIGHT_BLUISH_GRAY = 71
DARK_BLUISH_GRAY = 72
DARK_GREEN = 288
PEARL_GOLD = 297

# Rotations
R0 = "1.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 1.0"
R90 = "0.0 0.0 1.0 0.0 1.0 0.0 -1.0 0.0 0.0"
R180 = "-1.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 -1.0"
R270 = "0.0 0.0 -1.0 0.0 1.0 0.0 1.0 0.0 0.0"

class GridEngine:
    def __init__(self, name="Grand Romanesque Cathedral & Cloister Complex", w_studs=32, d_studs=40):
        self.name = name
        self.w_studs = w_studs
        self.d_studs = d_studs
        self.x_origin = -((w_studs * 20.0) / 2.0)
        self.z_origin = -((d_studs * 20.0) / 2.0)
        self.lines = [
            f"0 {name}",
            "0 Name: build.ldr",
            "0 Author: Antigravity Architect",
            "0 !LICENSE CC BY 4.0",
        ]
        self.occupied = set()

    def add_box(self, part: str, color: int, kx: int, mz: int, py: int, w: int, d: int, h: int, rot: str = R0, comment: str = ""):
        # Check boundaries
        if kx < 0 or kx + w > self.w_studs or mz < 0 or mz + d > self.d_studs:
            raise ValueError(f"Out of bounds: {part} at kx={kx}..{kx+w}, mz={mz}..{mz+d}")
        
        # Check collision
        for x in range(kx, kx + w):
            for z in range(mz, mz + d):
                for y in range(py, py + h):
                    if (x, z, y) in self.occupied:
                        raise ValueError(f"COLLISION: {part} at stud ({x}, {z}), plate {y}. Already occupied!")
                    self.occupied.add((x, z, y))

        xc = self.x_origin + (kx + w / 2.0) * 20.0
        zc = self.z_origin + (mz + d / 2.0) * 20.0
        ytop = 0.0 if py == 0 else -(py + h - 1) * 8.0
        if comment:
            self.lines.append(f"0 // {comment}")
        self.lines.append(f"1 {color} {xc:.1f} {ytop:.1f} {zc:.1f} {rot} {part}.dat")

    def count(self) -> int:
        return sum(1 for l in self.lines if l.startswith("1 "))

print("GridEngine defined.")
