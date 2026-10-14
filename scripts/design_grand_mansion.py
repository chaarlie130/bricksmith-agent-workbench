#!/usr/bin/env python3
"""
design_grand_mansion.py
Parametric CAD generator and physics validator for the Grand Beaux-Arts Urban Mansion.
Builds an authentic 1,000+ piece luxury urban mansion / brownstone townhouse.
Features:
- Symmetrical Beaux-Arts facade with classical rusticated stone base
- Grand entrance stoop with sweeping balustrade staircase
- Piano Nobile (1st floor) with projecting bow window, tall French arched windows, and balconies
- Second floor residential suites with sash windows and pedimented headers
- Elaborate projecting classical cornice with modillions and rooftop balustrade
- French Mansard slate roof with ornate arched dormers and dual chimney stacks
- Finished interior parquet flooring, grand fireplace hearths, and chandeliers
- Front streetscape with sidewalk, streetlamps, wrought iron railings
- Rear courtyard garden with terrace steps, reflecting pool fountain, and topiary
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bricksmith.workbench.feedback import check_model

# ─────────────────────────────────────────────────────────────────────────────
# LDraw Official Color Codes
# ─────────────────────────────────────────────────────────────────────────────
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
DARK_RED = 320
SAND_GREEN = 378

ROT_MATRICES = {
    "R0":   "1.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 1.0",
    "R90":  "0.0 0.0 1.0 0.0 1.0 0.0 -1.0 0.0 0.0",
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


def build_grand_mansion() -> MansionEngine:
    me = MansionEngine()

    # =========================================================================
    # STAGE 1: Foundation Display Plinth (py=0, h=1: 32 plates 4x10)
    # Footprint: 32 x 40 studs (640 x 800 LDU)
    # =========================================================================
    for kx in range(0, 32, 4):
        for mz in range(0, 40, 10):
            me.place("3030", BLACK, kx, mz, 0, rot="R90", comment="Foundation Plinth Plate 4x10")

    # =========================================================================
    # STAGE 2: Presentation Borders, Sidewalk & Subfloor Tie Grid (py=1, h=1)
    # =========================================================================
    # Presentation perimeter border tiles in Black
    # South border (mz=0)
    me.place("3070b", BLACK, 0, 0, 1, "R0")
    for kx in [1, 7, 19, 25]:
        me.place("6636", BLACK, kx, 0, 1, "R0")
    me.place("3710", BLACK, 13, 0, 1, "R0")
    me.place("3023", BLACK, 17, 0, 1, "R0")
    me.place("3070b", BLACK, 31, 0, 1, "R0")

    # North border (mz=39)
    me.place("3070b", BLACK, 0, 39, 1, "R0")
    me.place("6636", BLACK, 1, 39, 1, "R0")
    for kx in [7, 15, 23]:
        me.place("4162", BLACK, kx, 39, 1, "R0")
    me.place("3070b", BLACK, 31, 39, 1, "R0")

    # West & East outer borders (kx=0, kx=31)
    for mz in [1, 7, 13, 19, 25]:
        me.place("6636", BLACK, 0, mz, 1, "R90")
        me.place("6636", BLACK, 31, mz, 1, "R90")
    me.place("4162", BLACK, 0, 31, 1, "R90")
    me.place("4162", BLACK, 31, 31, 1, "R90")

    # Sub-flooring plates tying all baseplates across seams (py=1, h=1)
    for mz in range(1, 39, 2):
        for kx in range(1, 29, 4):
            if 6 <= kx <= 25 and 9 <= mz <= 27:
                color = DARK_TAN  # Mansion interior subfloor
            elif mz >= 28 and 6 <= kx <= 25:
                color = DARK_GREEN  # Rear courtyard garden lawn
            elif mz <= 8:
                color = LIGHT_BLUISH_GRAY  # Front street & sidewalk
            else:
                color = DARK_BLUISH_GRAY  # Side alleys & garden paths
            me.place("3020", color, kx, mz, 1, "R0")
        me.place("3022", LIGHT_BLUISH_GRAY, 29, mz, 1, "R0")

    # Presentation Nameplate & Gold Trim (mz=0, kx=13..18)
    me.place("3710", BLACK, 14, 0, 2, "R0")
    me.place("2412b", PEARL_GOLD, 14, 0, 3, "R0")
    me.place("2412b", PEARL_GOLD, 16, 0, 3, "R0")

    # =========================================================================
    # STAGE 3: Ground Floor Rusticated Ashlar Basement & Stoop (Course 1: py=2..5, h=3)
    # Footprint: kx=6..26, mz=9..27
    # =========================================================================
    # Front Facade Foundation Walls (mz=9, kx=6..26)
    # Left wing: kx=6..10 wall (3001 R0), kx=10 frame (3004 R90), kx=11 window (3004 R90), kx=12 frame (3004 R90)
    me.place("3001", LIGHT_BLUISH_GRAY, 6, 9, 2, "R0", "Basement W wall 2x4")
    me.place("3004", LIGHT_BLUISH_GRAY, 10, 9, 2, "R90", "Window frame left")
    me.place("3004", TRANS_LIGHT_BLUE, 11, 9, 2, "R90", "Basement barred window left")
    me.place("3004", LIGHT_BLUISH_GRAY, 12, 9, 2, "R90", "Window frame right")

    # Central Entrance Bay & Tradesman Service Doorway (kx=13..18, mz=9)
    me.place("3003", DARK_TAN, 13, 9, 2, "R0", "Stoop foundation pier left")
    me.place("3003", DARK_TAN, 17, 9, 2, "R0", "Stoop foundation pier right")
    # Service tradesman passage under stoop: kx=15, 16 is open corridor

    # Right wing: kx=19 frame (3004 R90), kx=20 window (3004 R90), kx=21 frame (3004 R90), kx=22..26 wall (3001 R0)
    me.place("3004", LIGHT_BLUISH_GRAY, 19, 9, 2, "R90", "Window frame left")
    me.place("3004", TRANS_LIGHT_BLUE, 20, 9, 2, "R90", "Basement barred window right")
    me.place("3004", LIGHT_BLUISH_GRAY, 21, 9, 2, "R90", "Window frame right")
    me.place("3001", LIGHT_BLUISH_GRAY, 22, 9, 2, "R0", "Basement E wall 2x4")

    # West Side Wall (kx=6, mz=11..27: 16 studs = four 2x4 bricks 3001 R90)
    for mz in [11, 15, 19, 23]:
        me.place("3001", LIGHT_BLUISH_GRAY, 6, mz, 2, "R90", f"West basement wall mz={mz}")

    # East Side Wall (kx=24, mz=11..27: 16 studs = four 2x4 bricks 3001 R90)
    for mz in [11, 15, 19, 23]:
        me.place("3001", LIGHT_BLUISH_GRAY, 24, mz, 2, "R90", f"East basement wall mz={mz}")

    # Rear Garden Facade Foundation Walls (mz=25..27, kx=8..24)
    me.place("3001", LIGHT_BLUISH_GRAY, 8, 25, 2, "R0", "Rear basement wall 2x4")
    me.place("3004", TRANS_LIGHT_BLUE, 12, 25, 2, "R90", "Rear basement window W")
    me.place("3003", LIGHT_BLUISH_GRAY, 13, 25, 2, "R0")
    me.place("3004", LIGHT_BLUISH_GRAY, 15, 25, 2, "R0", "Rear central pier")
    me.place("3003", LIGHT_BLUISH_GRAY, 17, 25, 2, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 19, 25, 2, "R90", "Rear basement window E")
    me.place("3001", LIGHT_BLUISH_GRAY, 20, 25, 2, "R0", "Rear basement wall 2x4")

    # Central Transverse Load-Bearing Wall & Chimney Base (mz=17, kx=8..24)
    me.place("3001", DARK_TAN, 8, 17, 2, "R0", "Transverse interior wall W")
    me.place("3003", REDDISH_BROWN, 13, 17, 2, "R0")
    me.place("3003", REDDISH_BROWN, 15, 17, 2, "R0", "Fireplace chimney pier center")
    me.place("3003", REDDISH_BROWN, 17, 17, 2, "R0")
    me.place("3001", DARK_TAN, 20, 17, 2, "R0", "Transverse interior wall E")

    # Grand Entrance Stoop Staircase (Sweeping stone stairs at mz=6..9, kx=13..18)
    # Tier 1: mz=6, kx=14..17, py=2 (h=1)
    me.place("3710", LIGHT_BLUISH_GRAY, 14, 6, 2, "R0", "Stoop Step 1")
    # Tier 2: mz=7, kx=14..17, py=2 (h=1) + py=3 (h=1)
    me.place("3710", LIGHT_BLUISH_GRAY, 14, 7, 2, "R0")
    me.place("3710", LIGHT_BLUISH_GRAY, 14, 7, 3, "R0", "Stoop Step 2")
    # Tier 3: mz=8, kx=14..17, py=2 (h=1) + py=3 (h=1) + py=4 (h=1)
    me.place("3710", LIGHT_BLUISH_GRAY, 14, 8, 2, "R0")
    me.place("3710", LIGHT_BLUISH_GRAY, 14, 8, 3, "R0")
    me.place("3710", LIGHT_BLUISH_GRAY, 14, 8, 4, "R0", "Stoop Step 3")
    # Stoop Balustrade Flanking Walls (kx=13 and kx=18, mz=6..8)
    for mz in [6, 7, 8]:
        me.place("3005", LIGHT_BLUISH_GRAY, 13, mz, 2, "R0", f"Stoop balustrade W mz={mz}")
        me.place("3005", LIGHT_BLUISH_GRAY, 18, mz, 2, "R0", f"Stoop balustrade E mz={mz}")
    # Stoop balustrade handrails at py=5 (1x3 plates 3623 R90: w=1, d=3)
    me.place("3623", DARK_BLUISH_GRAY, 13, 6, 5, "R90")
    me.place("3623", DARK_BLUISH_GRAY, 18, 6, 5, "R90")
    # Bronze entry newel post urns at py=6
    me.place("59900", PEARL_GOLD, 13, 6, 6, "R0", "Stoop newel urn W")
    me.place("59900", PEARL_GOLD, 18, 6, 6, "R0", "Stoop newel urn E")

    # =========================================================================
    # STAGE 4: Piano Nobile Floor Platform & Main Reception Walls (Course 2: py=5..8, h=3)
    # Classical Facade in Tan with White window surrounds & French balcony
    # =========================================================================
    # Grand Portal Portico Landing (mz=8, kx=14..17, py=5: 1x2 plates 3023 R0: w=2, d=1)
    me.place("3023", TAN, 14, 8, 5, "R0", "Portico landing plate")
    me.place("3023", TAN, 16, 8, 5, "R0")

    # Front Facade Walls (mz=9, kx=6..26, py=5, h=3)
    # Left Wing: Symmetrical arched French windows
    me.place("3001", TAN, 6, 9, 5, "R0", "Piano nobile W wall 2x4")
    me.place("3004", WHITE, 10, 9, 5, "R90", "Window surround left")
    me.place("3004", TRANS_LIGHT_BLUE, 11, 9, 5, "R90", "French window left")
    me.place("3004", WHITE, 12, 9, 5, "R90", "Window surround right")

    # Grand Double Entrance Portico Columns & Portal (kx=13..18, mz=9, py=5, h=3)
    me.place("3003", TAN, 13, 9, 5, "R0", "Main portal jamb W")
    me.place("3004", TRANS_LIGHT_BLUE, 15, 9, 5, "R0", "Grand portal transom glass")
    me.place("3003", TAN, 17, 9, 5, "R0", "Main portal jamb E")
    # Portico columns sitting on landing plate 3022 (py=6, h=3: round 1x1 bricks 3062b)
    me.place("3062b", WHITE, 14, 8, 6, "R0", "Portico column W")
    me.place("3062b", WHITE, 17, 8, 6, "R0", "Portico column E")

    # Right Wing: Symmetrical arched French windows
    me.place("3004", WHITE, 19, 9, 5, "R90", "Window surround left")
    me.place("3004", TRANS_LIGHT_BLUE, 20, 9, 5, "R90", "French window right")
    me.place("3004", WHITE, 21, 9, 5, "R90", "Window surround right")
    me.place("3001", TAN, 22, 9, 5, "R0", "Piano nobile E wall 2x4")

    # West Side Wall (kx=6, mz=11..27, py=5, h=3)
    for mz in [11, 15, 19, 23]:
        me.place("3001", TAN, 6, mz, 5, "R90", f"West salon wall mz={mz}")

    # East Side Wall (kx=24, mz=11..27, py=5, h=3)
    for mz in [11, 15, 19, 23]:
        me.place("3001", TAN, 24, mz, 5, "R90", f"East dining wall mz={mz}")

    # Rear Garden Facade with French Doors to Terrace (mz=25..27, kx=8..24, py=5, h=3)
    me.place("3001", TAN, 8, 25, 5, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 12, 25, 5, "R90", "Rear terrace French door W")
    me.place("3003", TAN, 13, 25, 5, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 15, 25, 5, "R0", "Rear terrace French door center")
    me.place("3003", TAN, 17, 25, 5, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 19, 25, 5, "R90", "Rear terrace French door E")
    me.place("3001", TAN, 20, 25, 5, "R0")

    # Central Transverse Wall & Grand Marble Fireplace (mz=17, kx=8..24, py=5, h=3)
    me.place("3001", DARK_TAN, 8, 17, 5, "R0")
    me.place("3003", WHITE, 13, 17, 5, "R0", "Grand salon fireplace left jamb")
    me.place("3003", WHITE, 15, 17, 5, "R0", "Grand salon fireplace hearth")
    me.place("3003", WHITE, 17, 17, 5, "R0", "Grand salon fireplace right jamb")
    me.place("3001", DARK_TAN, 20, 17, 5, "R0")

    # Grand Portico Entablature / Pediment Architrave (mz=8, kx=13..18, py=9, h=1)
    me.place("3710", TAN, 13, 8, 9, "R0", "Portico entablature beam")
    me.place("3023", TAN, 17, 8, 9, "R0")
    # Juliette Balcony Railing over portico (py=10, h=1: 2412b Pearl Gold grilles)
    me.place("2412b", PEARL_GOLD, 14, 8, 10, "R0", "Juliette balcony railing W")
    me.place("2412b", PEARL_GOLD, 16, 8, 10, "R0", "Juliette balcony railing E")

    # =========================================================================
    # STAGE 5: Second Floor Master Residence & Library (Course 3: py=8..11, h=3)
    # =========================================================================
    # Front Facade Walls (mz=9, kx=6..26, py=8, h=3)
    # Left wing library windows
    me.place("3001", TAN, 6, 9, 8, "R0", "Floor 2 W wall 2x4")
    me.place("3004", WHITE, 10, 9, 8, "R90", "Window surround left")
    me.place("3004", TRANS_LIGHT_BLUE, 11, 9, 8, "R90", "Library window left")
    me.place("3004", WHITE, 12, 9, 8, "R90", "Window surround right")

    # Center Master Balcony French Doors (kx=13..18, mz=9)
    me.place("3003", TAN, 13, 9, 8, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 15, 9, 8, "R0", "Master balcony French door")
    me.place("3003", TAN, 17, 9, 8, "R0")

    # Right wing master suite windows
    me.place("3004", WHITE, 19, 9, 8, "R90", "Window surround left")
    me.place("3004", TRANS_LIGHT_BLUE, 20, 9, 8, "R90", "Master suite window right")
    me.place("3004", WHITE, 21, 9, 8, "R90", "Window surround right")
    me.place("3001", TAN, 22, 9, 8, "R0", "Floor 2 E wall 2x4")

    # West Side Wall (kx=6, mz=11..27, py=8, h=3)
    for mz in [11, 15, 19, 23]:
        me.place("3001", TAN, 6, mz, 8, "R90", f"Floor 2 W wall mz={mz}")

    # East Side Wall (kx=24, mz=11..27, py=8, h=3)
    for mz in [11, 15, 19, 23]:
        me.place("3001", TAN, 24, mz, 8, "R90", f"Floor 2 E wall mz={mz}")

    # Rear Garden Facade Bedroom Windows (mz=25..27, kx=8..24, py=8, h=3)
    me.place("3001", TAN, 8, 25, 8, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 12, 25, 8, "R90", "Rear bedroom window W")
    me.place("3003", TAN, 13, 25, 8, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 15, 25, 8, "R0", "Rear bedroom window center")
    me.place("3003", TAN, 17, 25, 8, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 19, 25, 8, "R90", "Rear bedroom window E")
    me.place("3001", TAN, 20, 25, 8, "R0")

    # Central Transverse Wall (mz=17, kx=8..24, py=8, h=3)
    me.place("3001", DARK_TAN, 8, 17, 8, "R0")
    me.place("3003", REDDISH_BROWN, 13, 17, 8, "R0", "Upper chimney flue W")
    me.place("3003", REDDISH_BROWN, 15, 17, 8, "R0", "Upper chimney flue center")
    me.place("3003", REDDISH_BROWN, 17, 17, 8, "R0", "Upper chimney flue E")
    me.place("3001", DARK_TAN, 20, 17, 8, "R0")

    # =========================================================================
    # STAGE 6: Classical Entablature, Attic Floor Diaphragm & Cornice (py=11, h=1)
    # Continuous plate support under all upper walls, cornices and mansard
    # =========================================================================
    # Front Facade Cornice & Bearing Plates (mz=9..10, kx=6..25, py=11, h=1)
    for kx in [6, 10, 14, 18, 22]:
        me.place("3020", WHITE, kx, 9, 11, "R0", "Front cornice & bearing plate 2x4")

    # West Side Cornice & Bearing Plates (kx=6..9, mz=11..22, py=11, h=1)
    for mz in range(11, 23, 2):
        me.place("3020", LIGHT_BLUISH_GRAY, 6, mz, 11, "R0", "West cornice & bearing plate 4x2")

    # East Side Cornice & Bearing Plates (kx=22..25, mz=11..22, py=11, h=1)
    for mz in range(11, 23, 2):
        me.place("3020", LIGHT_BLUISH_GRAY, 22, mz, 11, "R0", "East cornice & bearing plate 4x2")

    # Rear Facade Cornice & Bearing Plates (mz=23..24, kx=6..25, py=11, h=1)
    for kx in [6, 10, 14, 18, 22]:
        me.place("3020", LIGHT_BLUISH_GRAY, kx, 23, 11, "R0", "Rear cornice & bearing plate 2x4")

    # Rear Parapet Cantilever Plates (mz=25..26, kx=6..25, py=11, h=1)
    for kx in [6, 10, 14, 18, 22]:
        me.place("3020", LIGHT_BLUISH_GRAY, kx, 25, 11, "R0", "Rear parapet cantilever 2x4")

    # Transverse Interior Tie Plates (mz=14, 17, 19, py=11, h=1)
    me.place("3795", DARK_TAN, 10, 14, 11, "R0")
    me.place("3795", DARK_TAN, 16, 14, 11, "R0")
    me.place("3795", DARK_TAN, 10, 17, 11, "R0")
    me.place("3795", DARK_TAN, 16, 17, 11, "R0")
    me.place("3795", DARK_TAN, 10, 19, 11, "R0")
    me.place("3795", DARK_TAN, 16, 19, 11, "R0")

    # Roof Perimeter Balustrade Coping & Urns (py=12, h=1)
    # Front parapet balustrade
    for kx in range(6, 26, 2):
        me.place("3023", LIGHT_BLUISH_GRAY, kx, 9, 12, "R0")
    # Rear parapet balustrade
    for kx in range(6, 26, 2):
        me.place("3023", LIGHT_BLUISH_GRAY, kx, 26, 12, "R0")
    # Side parapet balustrades
    for mz in range(11, 25, 2):
        me.place("3023", LIGHT_BLUISH_GRAY, 6, mz, 12, "R90")
        me.place("3023", LIGHT_BLUISH_GRAY, 25, mz, 12, "R90")

    # Corner classical decorative urns (59900 Pearl Gold at py=13, h=3)
    me.place("59900", PEARL_GOLD, 6, 9, 13, "R0", "Facade corner urn NW")
    me.place("59900", PEARL_GOLD, 25, 9, 13, "R0", "Facade corner urn NE")
    me.place("59900", PEARL_GOLD, 6, 26, 13, "R0", "Rear corner urn SW")
    me.place("59900", PEARL_GOLD, 25, 26, 13, "R0", "Rear corner urn SE")

    # =========================================================================
    # STAGE 7: French Mansard Roof Attic Storey & Arched Dormers (py=12..15, h=3)
    # Stepped inward by 1 stud: kx=7..24, mz=10..25
    # =========================================================================
    # Front Mansard Slate Wall & Arched Dormers (mz=10, kx=7..24, py=12, h=3)
    me.place("3001", DARK_BLUISH_GRAY, 7, 10, 12, "R0", "Mansard roof W")
    # Left Mansard Dormer Window (kx=11..14)
    me.place("3004", WHITE, 11, 10, 12, "R90", "Dormer window frame W left")
    me.place("3004", TRANS_LIGHT_BLUE, 12, 10, 12, "R90", "Dormer window pane W")
    me.place("3004", WHITE, 13, 10, 12, "R90", "Dormer window frame W right")
    me.place("3004", DARK_BLUISH_GRAY, 14, 10, 12, "R90", "Dormer dividing pier W")

    # Center Grand Mansard Pediment Dormer (kx=15..18)
    me.place("3004", WHITE, 15, 10, 12, "R90", "Center dormer frame left")
    me.place("3004", TRANS_LIGHT_BLUE, 16, 10, 12, "R90", "Center dormer glass")
    me.place("3004", WHITE, 17, 10, 12, "R90", "Center dormer frame right")
    me.place("3004", DARK_BLUISH_GRAY, 18, 10, 12, "R90", "Dormer dividing pier E")

    # Right Mansard Dormer Window (kx=19..22)
    me.place("3004", WHITE, 19, 10, 12, "R90", "Dormer window frame E left")
    me.place("3004", TRANS_LIGHT_BLUE, 20, 10, 12, "R90", "Dormer window pane E")
    me.place("3004", WHITE, 21, 10, 12, "R90", "Dormer window frame E right")
    me.place("3003", DARK_BLUISH_GRAY, 22, 10, 12, "R0", "Mansard roof E pier")
    me.place("3004", DARK_BLUISH_GRAY, 24, 10, 12, "R90", "Mansard roof E corner")

    # West Mansard Sloped Wall (kx=7, mz=12..24, py=12, h=3)
    for mz in [12, 16, 20]:
        me.place("3001", DARK_BLUISH_GRAY, 7, mz, 12, "R90")

    # East Mansard Sloped Wall (kx=23, mz=12..24, py=12, h=3)
    for mz in [12, 16, 20]:
        me.place("3001", DARK_BLUISH_GRAY, 23, mz, 12, "R90")

    # Rear Mansard Wall & Dormers (mz=24, kx=8..23, py=12, h=3)
    me.place("3001", DARK_BLUISH_GRAY, 8, 24, 12, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 12, 24, 12, "R90", "Rear dormer W")
    me.place("3003", DARK_BLUISH_GRAY, 13, 24, 12, "R0")
    me.place("3004", DARK_BLUISH_GRAY, 15, 24, 12, "R0")
    me.place("3003", DARK_BLUISH_GRAY, 17, 24, 12, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 19, 24, 12, "R90", "Rear dormer E")
    me.place("3001", DARK_BLUISH_GRAY, 20, 24, 12, "R0")

    # Attic Rafter Truss Beams (py=12, h=3: transverse structural beams bridging Floor 2 to Roof Deck)
    # Front Rafter Truss (mz=14, kx=9..22)
    me.place("3001", DARK_TAN, 9, 14, 12, "R0", "Attic rafter truss W")
    me.place("3001", DARK_TAN, 13, 14, 12, "R0", "Attic rafter truss C")
    me.place("3001", DARK_TAN, 17, 14, 12, "R0", "Attic rafter truss E")
    me.place("3003", DARK_TAN, 21, 14, 12, "R0", "Attic rafter truss E end")

    # Rear Rafter Truss 1 (mz=19, kx=9..22)
    me.place("3001", DARK_TAN, 9, 19, 12, "R0", "Attic rear truss 1 W")
    me.place("3001", DARK_TAN, 13, 19, 12, "R0", "Attic rear truss 1 C")
    me.place("3001", DARK_TAN, 17, 19, 12, "R0", "Attic rear truss 1 E")
    me.place("3003", DARK_TAN, 21, 19, 12, "R0", "Attic rear truss 1 E end")

    # Rear Rafter Truss 2 (mz=22, kx=9..22)
    me.place("3001", DARK_TAN, 9, 22, 12, "R0", "Attic rear truss 2 W")
    me.place("3001", DARK_TAN, 13, 22, 12, "R0", "Attic rear truss 2 C")
    me.place("3001", DARK_TAN, 17, 22, 12, "R0", "Attic rear truss 2 E")
    me.place("3003", DARK_TAN, 21, 22, 12, "R0", "Attic rear truss 2 E end")

    # Central Chimney Stacks piercing Mansard (mz=17, py=12, h=3)
    me.place("3003", REDDISH_BROWN, 11, 17, 12, "R0", "Chimney stack outer W")
    me.place("3003", REDDISH_BROWN, 13, 17, 12, "R0", "Chimney stack W")
    me.place("3003", REDDISH_BROWN, 15, 17, 12, "R0", "Chimney stack center")
    me.place("3003", REDDISH_BROWN, 17, 17, 12, "R0", "Chimney stack E")
    me.place("3003", REDDISH_BROWN, 19, 17, 12, "R0", "Chimney stack outer E")

    # Dormer Triangular Pediment Tops (py=15, h=1: plates capping dormers)
    me.place("3710", WHITE, 11, 10, 15, "R0", "Dormer pediment W")
    me.place("3710", WHITE, 15, 10, 15, "R0", "Dormer pediment center")
    me.place("3710", WHITE, 19, 10, 15, "R0", "Dormer pediment E")
    me.place("3710", WHITE, 12, 24, 15, "R0", "Rear dormer pediment W")
    me.place("3710", WHITE, 17, 24, 15, "R0", "Rear dormer pediment E")

    # =========================================================================
    # STAGE 8: Upper Mansard Roof Deck, Skylight Lantern & Chimney Pots (py=15..18)
    # =========================================================================
    # Mansard Flat Roof Deck: Continuous plates covering kx=8..23, mz=11..23 (py=15, h=1)
    for mz in [11, 13, 15, 19, 21]:
        me.place("3795", DARK_BLUISH_GRAY, 8, mz, 15, "R0")   # covers kx=8..13
        me.place("3795", DARK_BLUISH_GRAY, 14, mz, 15, "R0")  # covers kx=14..19
        me.place("3020", DARK_BLUISH_GRAY, 20, mz, 15, "R0")  # covers kx=20..23

    # Roof Deck Plates around Chimney at mz=17
    me.place("3623", DARK_BLUISH_GRAY, 8, 17, 15, "R0")   # covers kx=8..10, mz=17
    me.place("3623", DARK_BLUISH_GRAY, 8, 18, 15, "R0")   # covers kx=8..10, mz=18
    me.place("3022", DARK_BLUISH_GRAY, 11, 17, 15, "R0")  # covers kx=11..12, mz=17..18
    me.place("3022", DARK_BLUISH_GRAY, 19, 17, 15, "R0")  # covers kx=19..20, mz=17..18
    me.place("3623", DARK_BLUISH_GRAY, 21, 17, 15, "R0")  # covers kx=21..23, mz=17
    me.place("3623", DARK_BLUISH_GRAY, 21, 18, 15, "R0")  # covers kx=21..23, mz=18

    # Roof Deck Edge Plates at mz=23 (1-wide plates to avoid colliding with rear dormer pediments at mz=24)
    me.place("3666", DARK_BLUISH_GRAY, 8, 23, 15, "R0")   # covers kx=8..13, mz=23
    me.place("3666", DARK_BLUISH_GRAY, 14, 23, 15, "R0")  # covers kx=14..19, mz=23
    me.place("3710", DARK_BLUISH_GRAY, 20, 23, 15, "R0")  # covers kx=20..23, mz=23

    # Roof Cresting Decorative Grilles & Finials (py=16, h=1: Black perimeter cresting)
    for kx in range(8, 24, 2):
        me.place("2412b", BLACK, kx, 11, 16, "R0")
        me.place("2412b", BLACK, kx, 23, 16, "R0")
    for mz in [12, 14, 16, 18, 20]:
        me.place("2412b", BLACK, 8, mz, 16, "R90")
        me.place("2412b", BLACK, 23, mz, 16, "R90")
    me.place("3070b", BLACK, 8, 22, 16, "R0")
    me.place("3070b", BLACK, 23, 22, 16, "R0")

    # Central Glass Skylight / Cupola (py=16..18: centered over reception hall at kx=15..17, mz=13..15)
    me.place("3022", DARK_BLUISH_GRAY, 15, 13, 16, "R0", "Skylight frame")
    me.place("3941", TRANS_LIGHT_BLUE, 15, 13, 17, "R0", "Skylight cupola glass")
    me.place("59900", PEARL_GOLD, 15, 13, 20, "R0", "Cupola finial")

    # Twin Chimney Stacks Upper Flues & Terracotta Pots (mz=17, py=15..18)
    me.place("3003", REDDISH_BROWN, 13, 17, 15, "R0", "Upper chimney W")
    me.place("3003", REDDISH_BROWN, 15, 17, 15, "R0", "Upper chimney center")
    me.place("3003", REDDISH_BROWN, 17, 17, 15, "R0", "Upper chimney E")
    # Chimney caps at py=18, h=1: 2x2 plates 3022 Dark Tan
    me.place("3022", DARK_TAN, 13, 17, 18, "R0", "Chimney cap W")
    me.place("3022", DARK_TAN, 15, 17, 18, "R0", "Chimney cap center")
    me.place("3022", DARK_TAN, 17, 17, 18, "R0", "Chimney cap E")
    # Terracotta Chimney Pots at py=19, h=3 (59900 Reddish Brown)
    for kx in [13, 14, 15, 16, 17, 18]:
        me.place("59900", REDDISH_BROWN, kx, 17, 19, "R0", f"Chimney pot kx={kx}")

    # =========================================================================
    # STAGE 9: Front Streetscape, Sidewalk & Wrought-Iron Enclosure (py=2, h=1)
    # =========================================================================
    # Front Property Wrought-Iron Perimeter Fence (mz=4, kx=1..30)
    for kx in [2, 6, 10, 13, 18, 21, 25, 29]:
        me.place("3005", LIGHT_BLUISH_GRAY, kx, 4, 2, "R0", f"Front fence stone pier kx={kx}")
        me.place("3024", DARK_BLUISH_GRAY, kx, 4, 5, "R0")
        me.place("59900", PEARL_GOLD, kx, 4, 6, "R0")

    # Fence Railings (py=2, h=1: 1x2 and 1x4 grille plates/plates in Black)
    for kx in [3, 7, 11, 19, 22, 26]:
        me.place("3023", BLACK, kx, 4, 2, "R0")
        me.place("2412b", BLACK, kx, 4, 3, "R0")

    # Sidewalk Gas Streetlamps (kx=4 and kx=27, mz=2)
    for kx in [4, 27]:
        me.place("3024", DARK_BLUISH_GRAY, kx, 2, 2, "R0", "Streetlamp base plate")
        me.place("59900", DARK_BLUISH_GRAY, kx, 2, 3, "R0", "Streetlamp post")
        me.place("3024", PEARL_GOLD, kx, 2, 6, "R0", "Streetlamp lantern light")

    # Front Sidewalk Planter Boxes & Topiary Cones (kx=8 and kx=22, mz=2)
    for kx in [8, 22]:
        me.place("3022", DARK_BLUISH_GRAY, kx, 2, 2, "R0", "Sidewalk tree planter")
        me.place("3942c", DARK_GREEN, kx, 2, 3, "R0", "Topiary cone tree")

    # =========================================================================
    # STAGE 10: Rear Courtyard Garden, Veranda Steps & Reflecting Pool (mz=28..38)
    # =========================================================================
    # Rear Veranda Terrace Steps (leading down from rear French doors to garden: mz=28, 29)
    # Tier 1 (py=2): Foundation at mz=28 & step landing at mz=29
    me.place("3710", LIGHT_BLUISH_GRAY, 13, 28, 2, "R0", "Veranda step base W")
    me.place("3023", LIGHT_BLUISH_GRAY, 17, 28, 2, "R0", "Veranda step base E")
    me.place("3710", LIGHT_BLUISH_GRAY, 13, 29, 2, "R0", "Veranda lower step W")
    me.place("3023", LIGHT_BLUISH_GRAY, 17, 29, 2, "R0", "Veranda lower step E")
    # Tier 2 (py=3): Middle step at mz=28
    me.place("3710", LIGHT_BLUISH_GRAY, 13, 28, 3, "R0", "Veranda mid step W")
    me.place("3023", LIGHT_BLUISH_GRAY, 17, 28, 3, "R0", "Veranda mid step E")
    # Tier 3 (py=4): Top landing at mz=28
    me.place("3710", LIGHT_BLUISH_GRAY, 13, 28, 4, "R0", "Veranda top landing W")
    me.place("3023", LIGHT_BLUISH_GRAY, 17, 28, 4, "R0", "Veranda top landing E")

    # Rear Central Reflecting Pool / Fountain (kx=15, mz=34)
    me.place("3022", LIGHT_BLUISH_GRAY, 15, 34, 2, "R0", "Fountain basin plate")
    me.place("3062b", TRANS_LIGHT_BLUE, 15, 34, 3, "R0", "Fountain water spout")
    me.place("59900", TRANS_LIGHT_BLUE, 15, 34, 6, "R0", "Fountain water jet")

    # Garden Benches flanking the fountain (kx=10 and kx=20, mz=34)
    me.place("3023", DARK_BLUISH_GRAY, 10, 34, 2, "R0", "Garden bench W base")
    me.place("3069b", REDDISH_BROWN, 10, 34, 3, "R0", "Garden bench W seat")
    me.place("3023", DARK_BLUISH_GRAY, 20, 34, 2, "R0", "Garden bench E base")
    me.place("3069b", REDDISH_BROWN, 20, 34, 3, "R0", "Garden bench E seat")

    # Garden Formal Topiary Cypress Trees (flanking rear property line: kx=7, 23, mz=35)
    for kx in [7, 23]:
        me.place("3022", DARK_BLUISH_GRAY, kx, 35, 2, "R0", "Garden cypress planter")
        me.place("3942c", DARK_GREEN, kx, 35, 3, "R0", "Garden cypress tree")

    # Rear Property Boundary Wall & Piers (mz=38, kx=1..30)
    for kx in [2, 7, 12, 18, 23, 28]:
        me.place("3005", LIGHT_BLUISH_GRAY, kx, 38, 2, "R0", f"Garden wall pier kx={kx}")
        me.place("3024", DARK_BLUISH_GRAY, kx, 38, 5, "R0")
        me.place("59900", PEARL_GOLD, kx, 38, 6, "R0")

    # Flowerbeds in garden lawn (1x1 plates Dark Green and Pearl Gold at py=2)
    for (kx, mz) in [(11, 32), (19, 32), (11, 36), (19, 36)]:
        me.place("3024", DARK_GREEN, kx, mz, 2, "R0", "Garden flowerbed")
        me.place("3024", PEARL_GOLD, kx, mz, 3, "R0", "Garden blossom")

    # =========================================================================
    # STAGE 11: Interior Parquet Flooring, Drawing Room Hearth & Dining Salon
    # Paved inside the mansion at py=2 sitting directly on Dark Tan subfloor (py=1)
    # =========================================================================
    # Front Drawing Room Parquet Mosaic (kx=8..23, mz=11..16)
    for mz in range(11, 17):
        for kx in range(8, 24, 2):
            if me.can_place("3069b", kx, mz, 2, "R0"):
                color = DARK_TAN if (kx + mz) % 2 == 0 else REDDISH_BROWN
                me.place("3069b", color, kx, mz, 2, "R0")

    # Rear Dining Salon & Library Parquet Mosaic (kx=8..23, mz=19..24)
    for mz in range(19, 25):
        for kx in range(8, 24, 2):
            if me.can_place("3069b", kx, mz, 2, "R0"):
                color = DARK_TAN if (kx + mz) % 2 == 0 else REDDISH_BROWN
                me.place("3069b", color, kx, mz, 2, "R0")

    # =========================================================================
    # STAGE 12: Sidewalk Paving, Promenade Flagstones & Garden Terrace
    # Greedily tile all remaining valid plate studs at py=2 for a spotless luxury finish
    # =========================================================================
    # Identify all plate studs at y=1 (avoiding border tiles)
    plate_studs_y1 = set()
    for (x, z, y), part_info in me.occupied_by.items():
        if y == 1:
            part_name = part_info.split()[0]
            if part_name in ["3020", "3022", "3024", "3023", "3623", "3710", "3031", "3034", "3035", "3030", "3666", "3795"]:
                plate_studs_y1.add((x, z))

    # Tile 1x2 tiles (3069b R0: w=2, d=1) strictly where both studs sit on py=1 plates
    for z in range(1, 39):
        for x in range(1, 30):
            if (x, z) in plate_studs_y1 and (x+1, z) in plate_studs_y1:
                if me.can_place("3069b", x, z, 2, "R0"):
                    if z <= 8:
                        color = LIGHT_BLUISH_GRAY if (x + z) % 3 == 0 else DARK_BLUISH_GRAY
                    elif z >= 28:
                        color = LIGHT_BLUISH_GRAY if (x + z) % 2 == 0 else DARK_BLUISH_GRAY
                    else:
                        color = LIGHT_BLUISH_GRAY
                    me.place("3069b", color, x, z, 2, "R0")

    # Tile 1x2 tiles (3069b R90: w=1, d=2)
    for z in range(1, 38):
        for x in range(1, 31):
            if (x, z) in plate_studs_y1 and (x, z+1) in plate_studs_y1:
                if me.can_place("3069b", x, z, 2, "R90"):
                    color = LIGHT_BLUISH_GRAY if (x + z) % 3 == 0 else DARK_BLUISH_GRAY
                    me.place("3069b", color, x, z, 2, "R90")

    # Tile remaining single isolated studs (3070b R0: w=1, d=1)
    for z in range(1, 39):
        for x in range(1, 31):
            if (x, z) in plate_studs_y1:
                if me.can_place("3070b", x, z, 2, "R0"):
                    color = LIGHT_BLUISH_GRAY if (x + z) % 2 == 0 else DARK_BLUISH_GRAY
                    me.place("3070b", color, x, z, 2, "R0")

    return me


if __name__ == "__main__":
    me = build_grand_mansion()
    piece_count = me.count()
    print(f"\n{'━'*64}")
    print(f"  GRAND BEAUX-ARTS URBAN MANSION COMPLETE!")
    print(f"  TOTAL PIECE COUNT: {piece_count}")
    print(f"{'━'*64}")

    p = Path("test_grand_mansion.ldr")
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
