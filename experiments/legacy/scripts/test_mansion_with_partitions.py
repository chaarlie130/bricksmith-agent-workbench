#!/usr/bin/env python3
"""
test_mansion_with_partitions.py
Test Grand Beaux-Arts Mansion with full continuous interior bearing walls
and direct load paths from foundation to roof deck.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bricksmith.workbench.feedback import check_model

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

ROT_MATRICES = {
    "R0": "1.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 1.0",
    "R90": "0.0 0.0 1.0 0.0 1.0 0.0 -1.0 0.0 0.0",
    "R180": "-1.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 -1.0",
    "R270": "0.0 0.0 -1.0 0.0 1.0 0.0 1.0 0.0 0.0",
}

PARTS_INFO = {
    # Bricks (height = 3 plates)
    "3001": {"h": 3, "R0": (4, 2), "R90": (2, 4), "R180": (4, 2), "R270": (2, 4)},
    "3003": {"h": 3, "R0": (2, 2), "R90": (2, 2), "R180": (2, 2), "R270": (2, 2)},
    "3004": {"h": 3, "R0": (2, 1), "R90": (1, 2), "R180": (2, 1), "R270": (1, 2)},
    "3005": {"h": 3, "R0": (1, 1), "R90": (1, 1), "R180": (1, 1), "R270": (1, 1)},
    "3010": {"h": 3, "R0": (4, 1), "R90": (1, 4), "R180": (4, 1), "R270": (1, 4)},
    "3622": {"h": 3, "R0": (3, 1), "R90": (1, 3), "R180": (3, 1), "R270": (1, 3)},
    "3009": {"h": 3, "R0": (6, 1), "R90": (1, 6), "R180": (6, 1), "R270": (1, 6)},
    "3008": {"h": 3, "R0": (8, 1), "R90": (1, 8), "R180": (8, 1), "R270": (1, 8)},
    "3062b": {"h": 3, "R0": (1, 1), "R90": (1, 1), "R180": (1, 1), "R270": (1, 1)},
    "3941": {"h": 3, "R0": (2, 2), "R90": (2, 2), "R180": (2, 2), "R270": (2, 2)},
    # Plates (height = 1 plate)
    "3024": {"h": 1, "R0": (1, 1), "R90": (1, 1), "R180": (1, 1), "R270": (1, 1)},
    "3023": {"h": 1, "R0": (2, 1), "R90": (1, 2), "R180": (2, 1), "R270": (1, 2)},
    "3623": {"h": 1, "R0": (3, 1), "R90": (1, 3), "R180": (3, 1), "R270": (1, 3)},
    "3710": {"h": 1, "R0": (4, 1), "R90": (1, 4), "R180": (4, 1), "R270": (1, 4)},
    "3022": {"h": 1, "R0": (2, 2), "R90": (2, 2), "R180": (2, 2), "R270": (2, 2)},
    "3020": {"h": 1, "R0": (4, 2), "R90": (2, 4), "R180": (4, 2), "R270": (2, 4)},
    "3031": {"h": 1, "R0": (4, 4), "R90": (4, 4), "R180": (4, 4), "R270": (4, 4)},
    "3034": {"h": 1, "R0": (8, 2), "R90": (2, 8), "R180": (8, 2), "R270": (2, 8)},
    "3035": {"h": 1, "R0": (8, 4), "R90": (4, 8), "R180": (8, 4), "R270": (4, 8)},
    "3030": {"h": 1, "R0": (10, 4), "R90": (4, 10), "R180": (10, 4), "R270": (4, 10)},
    "3666": {"h": 1, "R0": (6, 1), "R90": (1, 6), "R180": (6, 1), "R270": (1, 6)},
    "3795": {"h": 1, "R0": (6, 2), "R90": (2, 6), "R180": (6, 2), "R270": (2, 6)},
    # Tiles (height = 1 plate)
    "3070b": {"h": 1, "R0": (1, 1), "R90": (1, 1), "R180": (1, 1), "R270": (1, 1)},
    "3069b": {"h": 1, "R0": (2, 1), "R90": (1, 2), "R180": (2, 1), "R270": (1, 2)},
    "2412b": {"h": 1, "R0": (2, 1), "R90": (1, 2), "R180": (2, 1), "R270": (1, 2)},
    "2431": {"h": 1, "R0": (4, 1), "R90": (1, 4), "R180": (4, 1), "R270": (1, 4)},
    "6636": {"h": 1, "R0": (6, 1), "R90": (1, 6), "R180": (6, 1), "R270": (1, 6)},
    "4162": {"h": 1, "R0": (8, 1), "R90": (1, 8), "R180": (8, 1), "R270": (1, 8)},
    # Cones
    "3942c": {"h": 6, "R0": (2, 2), "R90": (2, 2), "R180": (2, 2), "R270": (2, 2)},
    "59900": {"h": 3, "R0": (1, 1), "R90": (1, 1), "R180": (1, 1), "R270": (1, 1)},
}

class MansionEngine:
    def __init__(self, name="Grand Beaux-Arts Urban Mansion", w_studs=32, d_studs=40):
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
        self.occupied_by = {}

    def place(self, part: str, color: int, kx: int, mz: int, py: int, rot: str = "R0", comment: str = ""):
        if part not in PARTS_INFO:
            raise KeyError(f"Unknown part {part}")
        info = PARTS_INFO[part]
        w, d = info[rot]
        h = info["h"]
        rot_mat = ROT_MATRICES[rot]

        if kx < 0 or kx + w > self.w_studs or mz < 0 or mz + d > self.d_studs:
            raise ValueError(f"Out of bounds: {part} at kx={kx}..{kx+w}, mz={mz}..{mz+d}")
        for x in range(kx, kx + w):
            for z in range(mz, mz + d):
                for y in range(py, py + h):
                    if (x, z, y) in self.occupied:
                        occupier = self.occupied_by.get((x, z, y), "unknown")
                        raise ValueError(f"COLLISION: {part} at stud ({x}, {z}), plate {y}. Already occupied by {occupier}!")
                    self.occupied.add((x, z, y))
                    self.occupied_by[(x, z, y)] = f"{part} (kx={kx}, mz={mz}, py={py})"

        xc = self.x_origin + (kx + w / 2.0) * 20.0
        zc = self.z_origin + (mz + d / 2.0) * 20.0
        ytop = 0.0 if py == 0 else -(py + h - 1) * 8.0
        if comment:
            self.lines.append(f"0 // {comment}")
        self.lines.append(f"1 {color} {xc:.1f} {ytop:.1f} {zc:.1f} {rot_mat} {part}.dat")

    def count(self) -> int:
        return sum(1 for l in self.lines if l.startswith("1 "))

    def can_place(self, part: str, kx: int, mz: int, py: int, rot: str = "R0") -> bool:
        if part not in PARTS_INFO:
            return False
        info = PARTS_INFO[part]
        w, d = info[rot]
        h = info["h"]
        if kx < 0 or kx + w > self.w_studs or mz < 0 or mz + d > self.d_studs:
            return False
        for x in range(kx, kx + w):
            for z in range(mz, mz + d):
                for y in range(py, py + h):
                    if (x, z, y) in self.occupied:
                        return False
        return True


def build_mansion() -> MansionEngine:
    me = MansionEngine()

    # =========================================================================
    # STAGE 1: Foundation Display Plinth (py=0, h=1: 32 plates 4x10)
    # =========================================================================
    for kx in range(0, 32, 4):
        for mz in range(0, 40, 10):
            me.place("3030", BLACK, kx, mz, 0, rot="R90", comment="Foundation Plinth Plate 4x10")

    # =========================================================================
    # STAGE 2: Presentation Borders, Sidewalk & Subfloor Tie Grid (py=1, h=1)
    # =========================================================================
    me.place("3070b", BLACK, 0, 0, 1, "R0")
    for kx in [1, 7, 19, 25]:
        me.place("6636", BLACK, kx, 0, 1, "R0")
    me.place("3710", BLACK, 13, 0, 1, "R0")
    me.place("3023", BLACK, 17, 0, 1, "R0")
    me.place("3070b", BLACK, 31, 0, 1, "R0")

    me.place("3070b", BLACK, 0, 39, 1, "R0")
    me.place("6636", BLACK, 1, 39, 1, "R0")
    for kx in [7, 15, 23]:
        me.place("4162", BLACK, kx, 39, 1, "R0")
    me.place("3070b", BLACK, 31, 39, 1, "R0")

    for mz in [1, 7, 13, 19, 25]:
        me.place("6636", BLACK, 0, mz, 1, "R90")
        me.place("6636", BLACK, 31, mz, 1, "R90")
    me.place("4162", BLACK, 0, 31, 1, "R90")
    me.place("4162", BLACK, 31, 31, 1, "R90")

    for mz in range(1, 39, 2):
        for kx in range(1, 29, 4):
            if 6 <= kx <= 25 and 9 <= mz <= 27:
                color = DARK_TAN
            elif mz >= 28 and 6 <= kx <= 25:
                color = DARK_GREEN
            elif mz <= 8:
                color = LIGHT_BLUISH_GRAY
            else:
                color = DARK_BLUISH_GRAY
            me.place("3020", color, kx, mz, 1, "R0")
        me.place("3022", LIGHT_BLUISH_GRAY, 29, mz, 1, "R0")

    me.place("3710", BLACK, 14, 0, 2, "R0")
    me.place("2412b", PEARL_GOLD, 14, 0, 3, "R0")
    me.place("2412b", PEARL_GOLD, 16, 0, 3, "R0")

    # =========================================================================
    # STAGE 3: Rusticated Stone Basement (py=2..4, h=3)
    # Footprint: kx=6..25, mz=9..26 (20 x 18 studs)
    # =========================================================================
    # Front Facade Wall (mz=9..10)
    me.place("3001", LIGHT_BLUISH_GRAY, 6, 9, 2, "R0")
    me.place("3004", LIGHT_BLUISH_GRAY, 10, 9, 2, "R90")
    me.place("3004", TRANS_LIGHT_BLUE, 11, 9, 2, "R90")
    me.place("3004", LIGHT_BLUISH_GRAY, 12, 9, 2, "R90")
    me.place("3003", LIGHT_BLUISH_GRAY, 13, 9, 2, "R0")
    me.place("3003", DARK_TAN, 15, 9, 2, "R0", "Basement service door")
    me.place("3003", LIGHT_BLUISH_GRAY, 17, 9, 2, "R0")
    me.place("3004", LIGHT_BLUISH_GRAY, 19, 9, 2, "R90")
    me.place("3004", TRANS_LIGHT_BLUE, 20, 9, 2, "R90")
    me.place("3004", LIGHT_BLUISH_GRAY, 21, 9, 2, "R90")
    me.place("3001", LIGHT_BLUISH_GRAY, 22, 9, 2, "R0")

    # West Side Wall (kx=6..7, mz=11..24)
    for mz in [11, 15, 19, 23]:
        me.place("3001", LIGHT_BLUISH_GRAY, 6, mz, 2, "R90")

    # East Side Wall (kx=24..25, mz=11..24)
    for mz in [11, 15, 19, 23]:
        me.place("3001", LIGHT_BLUISH_GRAY, 24, mz, 2, "R90")

    # Rear Facade Wall (mz=25..26, kx=8..23)
    me.place("3001", LIGHT_BLUISH_GRAY, 8, 25, 2, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 12, 25, 2, "R90")
    me.place("3003", LIGHT_BLUISH_GRAY, 13, 25, 2, "R0")
    me.place("3004", LIGHT_BLUISH_GRAY, 15, 25, 2, "R0")
    me.place("3003", LIGHT_BLUISH_GRAY, 17, 25, 2, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 19, 25, 2, "R90")
    me.place("3001", LIGHT_BLUISH_GRAY, 20, 25, 2, "R0")

    # Continuous Interior Transverse Bearing Walls (mz=13, 17, 21)
    for mz in [13, 17, 21]:
        me.place("3001", DARK_TAN, 8, mz, 2, "R0")
        me.place("3001", DARK_TAN, 12, mz, 2, "R0")
        me.place("3001", DARK_TAN, 16, mz, 2, "R0")
        me.place("3001", DARK_TAN, 20, mz, 2, "R0")

    # Grand Entrance Stoop Staircase (mz=6..8, kx=13..18)
    me.place("3710", LIGHT_BLUISH_GRAY, 14, 6, 2, "R0")
    me.place("3710", LIGHT_BLUISH_GRAY, 14, 7, 2, "R0")
    me.place("3710", LIGHT_BLUISH_GRAY, 14, 7, 3, "R0")
    me.place("3710", LIGHT_BLUISH_GRAY, 14, 8, 2, "R0")
    me.place("3710", LIGHT_BLUISH_GRAY, 14, 8, 3, "R0")
    me.place("3710", LIGHT_BLUISH_GRAY, 14, 8, 4, "R0")
    for mz in [6, 7, 8]:
        me.place("3005", LIGHT_BLUISH_GRAY, 13, mz, 2, "R0")
        me.place("3005", LIGHT_BLUISH_GRAY, 18, mz, 2, "R0")
    me.place("3623", DARK_BLUISH_GRAY, 13, 6, 5, "R90")
    me.place("3623", DARK_BLUISH_GRAY, 18, 6, 5, "R90")
    me.place("59900", PEARL_GOLD, 13, 6, 6, "R0")
    me.place("59900", PEARL_GOLD, 18, 6, 6, "R0")

    # =========================================================================
    # STAGE 4: Piano Nobile Main Reception Walls (py=5..7, h=3)
    # =========================================================================
    me.place("3001", TAN, 6, 9, 5, "R0")
    me.place("3004", WHITE, 10, 9, 5, "R90")
    me.place("3004", TRANS_LIGHT_BLUE, 11, 9, 5, "R90")
    me.place("3004", WHITE, 12, 9, 5, "R90")
    me.place("3003", TAN, 13, 9, 5, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 15, 9, 5, "R0")
    me.place("3003", TAN, 17, 9, 5, "R0")
    me.place("3004", WHITE, 19, 9, 5, "R90")
    me.place("3004", TRANS_LIGHT_BLUE, 20, 9, 5, "R90")
    me.place("3004", WHITE, 21, 9, 5, "R90")
    me.place("3001", TAN, 22, 9, 5, "R0")

    for mz in [11, 15, 19, 23]:
        me.place("3001", TAN, 6, mz, 5, "R90")
        me.place("3001", TAN, 24, mz, 5, "R90")

    me.place("3001", TAN, 8, 25, 5, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 12, 25, 5, "R90")
    me.place("3003", TAN, 13, 25, 5, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 15, 25, 5, "R0")
    me.place("3003", TAN, 17, 25, 5, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 19, 25, 5, "R90")
    me.place("3001", TAN, 20, 25, 5, "R0")

    for mz in [13, 17, 21]:
        me.place("3001", DARK_TAN, 8, mz, 5, "R0")
        me.place("3001", DARK_TAN, 12, mz, 5, "R0")
        me.place("3001", DARK_TAN, 16, mz, 5, "R0")
        me.place("3001", DARK_TAN, 20, mz, 5, "R0")

    # =========================================================================
    # STAGE 5: Second Floor Master Residence & Library (py=8..10, h=3)
    # =========================================================================
    me.place("3001", TAN, 6, 9, 8, "R0")
    me.place("3004", WHITE, 10, 9, 8, "R90")
    me.place("3004", TRANS_LIGHT_BLUE, 11, 9, 8, "R90")
    me.place("3004", WHITE, 12, 9, 8, "R90")
    me.place("3003", TAN, 13, 9, 8, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 15, 9, 8, "R0")
    me.place("3003", TAN, 17, 9, 8, "R0")
    me.place("3004", WHITE, 19, 9, 8, "R90")
    me.place("3004", TRANS_LIGHT_BLUE, 20, 9, 8, "R90")
    me.place("3004", WHITE, 21, 9, 8, "R90")
    me.place("3001", TAN, 22, 9, 8, "R0")

    for mz in [11, 15, 19, 23]:
        me.place("3001", TAN, 6, mz, 8, "R90")
        me.place("3001", TAN, 24, mz, 8, "R90")

    me.place("3001", TAN, 8, 25, 8, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 12, 25, 8, "R90")
    me.place("3003", TAN, 13, 25, 8, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 15, 25, 8, "R0")
    me.place("3003", TAN, 17, 25, 8, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 19, 25, 8, "R90")
    me.place("3001", TAN, 20, 25, 8, "R0")

    for mz in [13, 17, 21]:
        me.place("3001", DARK_TAN, 8, mz, 8, "R0")
        me.place("3001", DARK_TAN, 12, mz, 8, "R0")
        me.place("3001", DARK_TAN, 16, mz, 8, "R0")
        me.place("3001", DARK_TAN, 20, mz, 8, "R0")

    # =========================================================================
    # STAGE 6: Classical Cornice & Wall Capping (py=11, h=1)
    # =========================================================================
    for kx in [6, 10, 14, 18, 22]:
        me.place("3020", WHITE, kx, 9, 11, "R0")
    for mz in [11, 15, 19, 23]:
        me.place("3020", LIGHT_BLUISH_GRAY, 6, mz, 11, "R90")
        me.place("3020", LIGHT_BLUISH_GRAY, 24, mz, 11, "R90")
    for kx in [8, 12, 16, 20]:
        me.place("3020", LIGHT_BLUISH_GRAY, kx, 25, 11, "R0")

    for mz in [13, 17, 21]:
        me.place("3795", DARK_TAN, 10, mz, 11, "R0")
        me.place("3795", DARK_TAN, 16, mz, 11, "R0")

    # Parapet Balustrades at py=12, h=1
    for kx in range(6, 26, 2):
        me.place("3023", LIGHT_BLUISH_GRAY, kx, 9, 12, "R0")
        me.place("3023", LIGHT_BLUISH_GRAY, kx, 26, 12, "R0")
    for mz in range(11, 25, 2):
        me.place("3023", LIGHT_BLUISH_GRAY, 6, mz, 12, "R90")
        me.place("3023", LIGHT_BLUISH_GRAY, 25, mz, 12, "R90")

    me.place("59900", PEARL_GOLD, 6, 9, 13, "R0")
    me.place("59900", PEARL_GOLD, 25, 9, 13, "R0")
    me.place("59900", PEARL_GOLD, 6, 26, 13, "R0")
    me.place("59900", PEARL_GOLD, 25, 26, 13, "R0")

    # =========================================================================
    # STAGE 7: French Mansard Roof Attic Storey (py=12..14, h=3)
    # =========================================================================
    me.place("3001", DARK_BLUISH_GRAY, 7, 10, 12, "R0")
    me.place("3004", WHITE, 11, 10, 12, "R90")
    me.place("3004", TRANS_LIGHT_BLUE, 12, 10, 12, "R90")
    me.place("3004", WHITE, 13, 10, 12, "R90")
    me.place("3004", DARK_BLUISH_GRAY, 14, 10, 12, "R90")
    me.place("3004", WHITE, 15, 10, 12, "R90")
    me.place("3004", TRANS_LIGHT_BLUE, 16, 10, 12, "R90")
    me.place("3004", WHITE, 17, 10, 12, "R90")
    me.place("3004", DARK_BLUISH_GRAY, 18, 10, 12, "R90")
    me.place("3004", WHITE, 19, 10, 12, "R90")
    me.place("3004", TRANS_LIGHT_BLUE, 20, 10, 12, "R90")
    me.place("3004", WHITE, 21, 10, 12, "R90")
    me.place("3003", DARK_BLUISH_GRAY, 22, 10, 12, "R0")
    me.place("3004", DARK_BLUISH_GRAY, 24, 10, 12, "R90")

    for mz in [12, 16, 20]:
        me.place("3001", DARK_BLUISH_GRAY, 7, mz, 12, "R90")
        me.place("3001", DARK_BLUISH_GRAY, 23, mz, 12, "R90")

    me.place("3001", DARK_BLUISH_GRAY, 8, 24, 12, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 12, 24, 12, "R90")
    me.place("3003", DARK_BLUISH_GRAY, 13, 24, 12, "R0")
    me.place("3004", DARK_BLUISH_GRAY, 15, 24, 12, "R0")
    me.place("3003", DARK_BLUISH_GRAY, 17, 24, 12, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 19, 24, 12, "R90")
    me.place("3001", DARK_BLUISH_GRAY, 20, 24, 12, "R0")

    for mz in [13, 17, 21]:
        me.place("3001", DARK_TAN, 9, mz, 12, "R0")
        me.place("3001", DARK_TAN, 13, mz, 12, "R0")
        me.place("3001", DARK_TAN, 17, mz, 12, "R0")
        me.place("3003", DARK_TAN, 21, mz, 12, "R0")

    # Dormer pediments (py=15, h=1)
    me.place("3710", WHITE, 11, 10, 15, "R0")
    me.place("3710", WHITE, 15, 10, 15, "R0")
    me.place("3710", WHITE, 19, 10, 15, "R0")
    me.place("3710", WHITE, 12, 24, 15, "R0")
    me.place("3710", WHITE, 18, 24, 15, "R0")

    # =========================================================================
    # STAGE 8: Upper Mansard Roof Deck (py=15, h=1)
    # Supported continuously by the bearing walls at mz=10, 13, 17, 21, 24!
    # =========================================================================
    for mz in [11, 13, 15, 17, 19, 21]:
        me.place("3795", DARK_BLUISH_GRAY, 8, mz, 15, "R0")
        me.place("3795", DARK_BLUISH_GRAY, 14, mz, 15, "R0")
        me.place("3020", DARK_BLUISH_GRAY, 20, mz, 15, "R0")
    me.place("3666", DARK_BLUISH_GRAY, 8, 23, 15, "R0")
    me.place("3666", DARK_BLUISH_GRAY, 14, 23, 15, "R0")
    me.place("3710", DARK_BLUISH_GRAY, 20, 23, 15, "R0")

    # Roof Cresting Grilles (py=16, h=1)
    for kx in range(8, 24, 2):
        me.place("2412b", BLACK, kx, 11, 16, "R0")
        me.place("2412b", BLACK, kx, 23, 16, "R0")
    for mz in [13, 15, 17, 19, 21]:
        me.place("2412b", BLACK, 8, mz, 16, "R90")
        me.place("2412b", BLACK, 23, mz, 16, "R90")

    # Central Cupola
    me.place("3022", DARK_BLUISH_GRAY, 15, 13, 16, "R0")
    me.place("3941", TRANS_LIGHT_BLUE, 15, 13, 17, "R0")
    me.place("59900", PEARL_GOLD, 15, 13, 20, "R0")

    # Chimneys
    me.place("3003", REDDISH_BROWN, 14, 17, 16, "R0")
    me.place("3003", REDDISH_BROWN, 16, 17, 16, "R0")
    me.place("3022", DARK_TAN, 14, 17, 19, "R0")
    me.place("3022", DARK_TAN, 16, 17, 19, "R0")
    for kx in [14, 15, 16, 17]:
        me.place("59900", REDDISH_BROWN, kx, 17, 20, "R0")

    # =========================================================================
    # STAGE 9: Front Streetscape (py=2)
    # =========================================================================
    for kx in [2, 6, 10, 13, 18, 21, 25, 29]:
        me.place("3005", LIGHT_BLUISH_GRAY, kx, 4, 2, "R0")
        me.place("3024", DARK_BLUISH_GRAY, kx, 4, 5, "R0")
        me.place("59900", PEARL_GOLD, kx, 4, 6, "R0")
    for kx in [3, 7, 11, 19, 22, 26]:
        me.place("3023", BLACK, kx, 4, 2, "R0")
        me.place("2412b", BLACK, kx, 4, 3, "R0")
    for kx in [4, 27]:
        me.place("3024", DARK_BLUISH_GRAY, kx, 2, 2, "R0")
        me.place("59900", DARK_BLUISH_GRAY, kx, 2, 3, "R0")
        me.place("3024", PEARL_GOLD, kx, 2, 6, "R0")
    for kx in [8, 22]:
        me.place("3022", DARK_BLUISH_GRAY, kx, 2, 2, "R0")
        me.place("3942c", DARK_GREEN, kx, 2, 3, "R0")

    # =========================================================================
    # STAGE 10: Rear Courtyard Garden (py=2)
    # =========================================================================
    me.place("3710", LIGHT_BLUISH_GRAY, 13, 28, 2, "R0")
    me.place("3023", LIGHT_BLUISH_GRAY, 17, 28, 2, "R0")
    me.place("3710", LIGHT_BLUISH_GRAY, 13, 29, 2, "R0")
    me.place("3023", LIGHT_BLUISH_GRAY, 17, 29, 2, "R0")
    me.place("3710", LIGHT_BLUISH_GRAY, 13, 28, 3, "R0")
    me.place("3023", LIGHT_BLUISH_GRAY, 17, 28, 3, "R0")
    me.place("3710", LIGHT_BLUISH_GRAY, 13, 28, 4, "R0")
    me.place("3023", LIGHT_BLUISH_GRAY, 17, 28, 4, "R0")

    me.place("3022", LIGHT_BLUISH_GRAY, 15, 34, 2, "R0")
    me.place("3062b", TRANS_LIGHT_BLUE, 15, 34, 3, "R0")
    me.place("59900", TRANS_LIGHT_BLUE, 15, 34, 6, "R0")

    me.place("3023", DARK_BLUISH_GRAY, 10, 34, 2, "R0")
    me.place("3069b", REDDISH_BROWN, 10, 34, 3, "R0")
    me.place("3023", DARK_BLUISH_GRAY, 20, 34, 2, "R0")
    me.place("3069b", REDDISH_BROWN, 20, 34, 3, "R0")

    for kx in [7, 23]:
        me.place("3022", DARK_BLUISH_GRAY, kx, 35, 2, "R0")
        me.place("3942c", DARK_GREEN, kx, 35, 3, "R0")

    for kx in [2, 7, 12, 18, 23, 28]:
        me.place("3005", LIGHT_BLUISH_GRAY, kx, 38, 2, "R0")
        me.place("3024", DARK_BLUISH_GRAY, kx, 38, 5, "R0")
        me.place("59900", PEARL_GOLD, kx, 38, 6, "R0")

    for (kx, mz) in [(11, 32), (19, 32), (11, 36), (19, 36)]:
        me.place("3024", DARK_GREEN, kx, mz, 2, "R0")
        me.place("3024", PEARL_GOLD, kx, mz, 3, "R0")

    # =========================================================================
    # STAGE 11: Interior Parquet Flooring
    # =========================================================================
    for mz in range(11, 17):
        for kx in range(8, 24, 2):
            if me.can_place("3069b", kx, mz, 2, "R0"):
                color = DARK_TAN if (kx + mz) % 2 == 0 else REDDISH_BROWN
                me.place("3069b", color, kx, mz, 2, "R0")

    for mz in range(19, 25):
        for kx in range(8, 24, 2):
            if me.can_place("3069b", kx, mz, 2, "R0"):
                color = DARK_TAN if (kx + mz) % 2 == 0 else REDDISH_BROWN
                me.place("3069b", color, kx, mz, 2, "R0")

    # =========================================================================
    # STAGE 12: Sidewalk Paving & Flagstones
    # =========================================================================
    plate_studs_y1 = set()
    for (x, z, y), part_info in me.occupied_by.items():
        if y == 1:
            part_name = part_info.split()[0]
            if part_name in ["3020", "3022", "3024", "3023", "3623", "3710", "3031", "3034", "3035", "3030", "3666", "3795"]:
                plate_studs_y1.add((x, z))

    for z in range(1, 39):
        for x in range(1, 30):
            if (x, z) in plate_studs_y1 and (x+1, z) in plate_studs_y1:
                if me.can_place("3069b", x, z, 2, "R0"):
                    if z <= 8:
                        color = LIGHT_BLUISH_GRAY if (x + z) % 3 == 0 else DARK_BLUISH_GRAY
                    elif z >= 27:
                        color = LIGHT_BLUISH_GRAY if (x + z) % 2 == 0 else DARK_BLUISH_GRAY
                    else:
                        color = LIGHT_BLUISH_GRAY
                    me.place("3069b", color, x, z, 2, "R0")

    for z in range(1, 38):
        for x in range(1, 31):
            if (x, z) in plate_studs_y1 and (x, z+1) in plate_studs_y1:
                if me.can_place("3069b", x, z, 2, "R90"):
                    color = LIGHT_BLUISH_GRAY if (x + z) % 3 == 0 else DARK_BLUISH_GRAY
                    me.place("3069b", color, x, z, 2, "R90")

    for z in range(1, 39):
        for x in range(1, 31):
            if (x, z) in plate_studs_y1:
                if me.can_place("3070b", x, z, 2, "R0"):
                    color = LIGHT_BLUISH_GRAY if (x + z) % 2 == 0 else DARK_BLUISH_GRAY
                    me.place("3070b", color, x, z, 2, "R0")

    return me


if __name__ == "__main__":
    me = build_mansion()
    piece_count = me.count()
    print(f"\n{'━'*64}")
    print(f"  TEST MANSION WITH CONTINUOUS PARTITIONS")
    print(f"  TOTAL PIECE COUNT: {piece_count}")
    print(f"{'━'*64}")

    p = Path("test_mansion_partitions.ldr")
    p.write_text("\n".join(me.lines) + "\n")
    res = check_model(p)
    print("\nValidation Results:")
    print("Passed:", res.get("passed"))
    for k, v in res.get("checks", {}).items():
        mark = "✓" if v else "·"
        print(f"  {mark} {k}: {v}")

    if not res.get("passed"):
        import pprint
        pprint.pprint(res.get("errors", []))
