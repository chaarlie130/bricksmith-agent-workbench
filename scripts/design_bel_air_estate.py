#!/usr/bin/env python3
"""
design_bel_air_estate.py
Architectural generator for:
"The Bel Air Promontory - Ultra-Luxury Hillside Modern Estate"
Directly inspired by the user's reference photograph:
- Cantilevered infinity pool & sunken jacuzzi spa
- Teak sun deck with outdoor lounge sectionals & glass railings
- Sprawling manicured emerald lawn with stepping stones & olive trees
- Crisp white 2-story transitional modern mansion with upper glass balcony
- Rooftop sky lounge & observation tower
- Detached modern pool house / guest cabana with rooftop solar panel array
- Exterior hillside staircase
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bricksmith.workbench.feedback import check_model

BLACK = 0
WHITE = 15
TRANS_LIGHT_BLUE = 47
REDDISH_BROWN = 70
LIGHT_BLUISH_GRAY = 71
DARK_BLUISH_GRAY = 72
DARK_GREEN = 288
PEARL_GOLD = 297
MEDIUM_AZURE = 322
TAN = 19
DARK_TAN = 28

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

class BelAirEngine:
    def __init__(self, name="The Bel Air Promontory - Modern Hillside Estate", w_studs=48, d_studs=36):
        self.name = name
        self.w_studs = w_studs
        self.d_studs = d_studs
        self.lines = [
            f"0 {name}",
            "0 Name: bel_air_estate.ldr",
            "0 Author: Antigravity Agent",
            "0 !LICENSE Redistributable under CCAL version 2.0 : see CAreadme.txt",
        ]
        self.occupied = set()

    def count(self):
        return len([l for l in self.lines if l.startswith("1 ")])

    def can_place(self, part, x, z, y, rot="R0"):
        info = PARTS_INFO[part]
        dx, dz = info[rot]
        h = info["h"]
        if x < 0 or x + dx > self.w_studs or z < 0 or z + dz > self.d_studs:
            return False
        for dy in range(h):
            for px in range(x, x + dx):
                for pz in range(z, z + dz):
                    if (px, pz, y + dy) in self.occupied:
                        return False
        return True

    def place(self, part, color, x, z, y, rot="R0", comment=""):
        info = PARTS_INFO[part]
        dx, dz = info[rot]
        h = info["h"]
        for dy in range(h):
            for px in range(x, x + dx):
                for pz in range(z, z + dz):
                    if (px, pz, y + dy) in self.occupied:
                        raise ValueError(f"COLLISION: {part} at stud ({px}, {pz}), plate {y + dy}!")
                    self.occupied.add((px, pz, y + dy))

        x_ldu = (x + dx / 2.0 - self.w_studs / 2.0) * 20.0
        z_ldu = (z + dz / 2.0 - self.d_studs / 2.0) * 20.0
        y_ldu = - (y * 8.0)
        matrix = ROT_MATRICES[rot]
        line = f"1 {color} {x_ldu:.1f} {y_ldu:.1f} {z_ldu:.1f} {matrix} {part}.dat"
        if comment:
            line += f" // {comment}"
        self.lines.append(line)


def build_bel_air_estate():
    me = BelAirEngine()

    # =========================================================================
    # STAGE 1: Hillside Terraced Foundation (py=0, h=1)
    # 48 studs wide x 36 studs deep (six 8-wide cols x nine 4-deep rows = 54 4x8 plates 3035)
    # =========================================================================
    for mz in [0, 4, 8, 12, 16, 20, 24, 28, 32]:
        for kx in [0, 8, 16, 24, 32, 40]:
            me.place("3035", DARK_BLUISH_GRAY, kx, mz, 0, "R0")

    # =========================================================================
    # STAGE 2: Subfloor Tying Matrix & Polished Obsidian Borders (py=1, h=1)
    # =========================================================================
    # South border (mz=0, kx=0..47)
    me.place("3070b", BLACK, 0, 0, 1, "R0")
    for kx in [1, 9, 17, 25, 33]:
        me.place("4162", BLACK, kx, 0, 1, "R0")
    me.place("6636", BLACK, 41, 0, 1, "R0")
    me.place("3070b", BLACK, 47, 0, 1, "R0")

    # North border (mz=35, kx=0..47)
    me.place("3070b", BLACK, 0, 35, 1, "R0")
    for kx in [1, 9, 17, 25, 33]:
        me.place("4162", BLACK, kx, 35, 1, "R0")
    me.place("6636", BLACK, 41, 35, 1, "R0")
    me.place("3070b", BLACK, 47, 35, 1, "R0")

    # West & East outer borders (kx=0 and kx=47, mz=1..34)
    for mz in [1, 9, 17, 25]:
        me.place("4162", BLACK, 0, mz, 1, "R90")
        me.place("4162", BLACK, 47, mz, 1, "R90")
    me.place("3069b", BLACK, 0, 33, 1, "R90")
    me.place("3069b", BLACK, 47, 33, 1, "R90")

    # Subfloor plates tying across baseplate seams (py=1)
    for mz in range(1, 35, 2):
        for kx in range(1, 45, 4):
            # Zone colors:
            if z_in_range := (1 <= mz <= 11):
                if 2 <= kx <= 18:
                    color = MEDIUM_AZURE  # Infinity pool foundation
                elif 18 <= kx <= 36:
                    color = REDDISH_BROWN # Teak deck foundation
                else:
                    color = DARK_BLUISH_GRAY # Hillside slope
            elif 12 <= mz <= 20:
                color = DARK_GREEN        # Emerald lawn foundation
            elif 21 <= mz <= 33:
                if 4 <= kx <= 32:
                    color = TAN           # Main mansion foundation
                elif 36 <= kx <= 46:
                    color = LIGHT_BLUISH_GRAY # Guest house cabana foundation
                else:
                    color = DARK_GREEN    # Side privacy gardens
            else:
                color = DARK_BLUISH_GRAY
            me.place("3020", color, kx, mz, 1, "R0")
        me.place("3022", LIGHT_BLUISH_GRAY, 45, mz, 1, "R0")

    # Presentation Bronze Estate Inscription (mz=0, kx=21..26)
    me.place("3710", BLACK, 22, 0, 2, "R0")
    me.place("2412b", PEARL_GOLD, 22, 0, 3, "R0")
    me.place("2412b", PEARL_GOLD, 24, 0, 3, "R0")

    # =========================================================================
    # STAGE 3: Cantilevered Hillside Infinity Pool & Spa (py=2..3)
    # Located at x=2..18, z=2..11
    # =========================================================================
    # Infinity pool coping borders
    for kx in [2, 6, 10, 14]:
        me.place("3020", LIGHT_BLUISH_GRAY, kx, 2, 2, "R0")
        me.place("3020", LIGHT_BLUISH_GRAY, kx, 10, 2, "R0")
    me.place("3795", LIGHT_BLUISH_GRAY, 2, 4, 2, "R90")

    # Pool Water (Translucent blue waters at py=2..3)
    for mz in [4, 6, 8]:
        for kx in [4, 6, 8, 10, 12]:
            me.place("3022", MEDIUM_AZURE, kx, mz, 2, "R0")
            me.place("3069b", TRANS_LIGHT_BLUE, kx, mz, 3, "R0")

    # Sunken Jacuzzi Spa (at x=14..17, z=4..9)
    for mz in [4, 6, 8]:
        for kx in [14, 16]:
            me.place("3022", DARK_BLUISH_GRAY, kx, mz, 2, "R0")
            me.place("3069b", TRANS_LIGHT_BLUE, kx, mz, 3, "R0")

    # =========================================================================
    # STAGE 4: Cantilevered Teak Sun Deck & Modern Outdoor Lounge (py=2..5)
    # Located at x=18..37, z=2..11
    # =========================================================================
    # Teak Decking Substructure
    for kx in [18, 22, 26, 30, 34]:
        me.place("3031", TAN, kx, 2, 2, "R0")
        me.place("3031", TAN, kx, 6, 2, "R0")
        me.place("3020", TAN, kx, 10, 2, "R0")

    # Outdoor Sectional Sofas (White & Tan contemporary furniture)
    # L-shaped sofa 1
    me.place("3023", WHITE, 24, 5, 3, "R0")
    me.place("3023", WHITE, 26, 5, 3, "R0")
    me.place("3023", WHITE, 28, 5, 3, "R0")
    me.place("3023", WHITE, 24, 7, 3, "R90")
    me.place("3069b", TAN, 24, 5, 4, "R0")
    me.place("3069b", TAN, 26, 5, 4, "R0")
    me.place("3069b", TAN, 28, 5, 4, "R0")
    me.place("3069b", TAN, 24, 7, 4, "R90")

    # Modern Low Coffee Table
    me.place("3022", DARK_BLUISH_GRAY, 26, 7, 3, "R0")
    me.place("3069b", WHITE, 26, 7, 4, "R0")

    # Luxury Sun Loungers facing the infinity view (x=20..22, z=4..9)
    for mz in [4, 6, 8]:
        me.place("3023", WHITE, 20, mz, 3, "R0")
        me.place("3069b", TAN, 20, mz, 4, "R0")

    # Outdoor Dining Table & Chairs (x=32..35, z=5..8)
    me.place("3022", REDDISH_BROWN, 33, 6, 3, "R0")
    me.place("3069b", REDDISH_BROWN, 33, 6, 4, "R0")
    me.place("3024", TAN, 32, 6, 3, "R0")
    me.place("3024", TAN, 35, 6, 3, "R0")
    me.place("3024", TAN, 33, 5, 3, "R0")
    me.place("3024", TAN, 33, 8, 3, "R0")

    # Frameless Glass Balustrades around the Deck Perimeter (py=3..4)
    for kx in range(18, 38, 2):
        me.place("2412b", BLACK, kx, 2, 3, "R0")
    for mz in range(3, 12, 2):
        me.place("2412b", BLACK, 37, mz, 3, "R90")

    # Large Terracotta Planter Pots with Topiary Shrubs on Deck
    for (px, pz) in [(18, 3), (30, 3), (36, 3), (36, 11)]:
        me.place("3024", REDDISH_BROWN, px, pz, 3, "R0")
        me.place("3062b", REDDISH_BROWN, px, pz, 4, "R0")
        me.place("3942c", DARK_GREEN, px, pz, 7, "R0")

    # Exterior Hillside Staircase on the far right (x=43..45, z=3..11)
    for step_z in range(3, 11, 2):
        me.place("3023", DARK_BLUISH_GRAY, 43, step_z, 2, "R0")
        me.place("3069b", BLACK, 43, step_z, 3, "R0")

    # =========================================================================
    # STAGE 5: Sprawling Manicured Emerald Lawn & Olive Trees (py=2..8)
    # Located at x=2..46, z=12..21
    # =========================================================================
    # Emerald lawn baseplates & tiling (mz=12..20)
    for mz in [12, 14, 16, 18]:
        for kx in range(2, 46, 4):
            me.place("3020", DARK_GREEN, kx, mz, 2, "R0")
    for kx in range(2, 46, 4):
        me.place("3710", DARK_GREEN, kx, 20, 2, "R0")

    # Travertine Stepping Stones embedded in the grass
    for sz in [13, 15, 17, 19]:
        me.place("3069b", LIGHT_BLUISH_GRAY, 16, sz, 3, "R0")
        me.place("3069b", LIGHT_BLUISH_GRAY, 26, sz, 3, "R0")

    # Symmetrical Mature Olive / Magnolia Trees
    for (tx, tz) in [(10, 16), (22, 16), (34, 16)]:
        me.place("3022", DARK_TAN, tx, tz, 3, "R0")
        me.place("3062b", REDDISH_BROWN, tx, tz, 4, "R0")
        me.place("3942c", DARK_GREEN, tx, tz, 7, "R0")
        me.place("59900", DARK_GREEN, tx, tz, 13, "R0")

    # =========================================================================
    # STAGE 6: Main Residence — Ground Floor (py=2..4, h=3)
    # Footprint: x=4..32, z=21..33 (Width 28 studs x Depth 12 studs)
    # =========================================================================
    # Front Facade: Panoramic Floor-to-Ceiling Sliding Glass & Covered Loggia
    # Left Wing (x=4..11, z=21):
    me.place("3001", WHITE, 4, 21, 2, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 8, 21, 2, "R0")
    me.place("3004", WHITE, 10, 21, 2, "R0")

    # Covered Loggia Recessed Glass Wall (x=12..25, z=23)
    # Recessed glass wall behind loggia columns:
    for kx in range(12, 26, 2):
        if kx in [14, 18, 22]:
            me.place("3004", TRANS_LIGHT_BLUE, kx, 23, 2, "R0")
        else:
            me.place("3004", WHITE, kx, 23, 2, "R0")

    # Loggia Front Architectural Stilt Pillars (at z=21, x=14, 18, 22)
    for kx in [14, 18, 22]:
        me.place("3005", BLACK, kx, 21, 2, "R0")

    # Right Wing (x=26..32, z=21):
    me.place("3004", WHITE, 26, 21, 2, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 28, 21, 2, "R0")
    me.place("3003", WHITE, 30, 21, 2, "R0")

    # West Wall (x=4..5, z=23..32)
    me.place("3001", WHITE, 4, 23, 2, "R90")
    me.place("3001", WHITE, 4, 27, 2, "R90")
    me.place("3003", WHITE, 4, 31, 2, "R0")

    # East Wall (x=31..32, z=23..32)
    me.place("3001", WHITE, 31, 23, 2, "R90")
    me.place("3001", WHITE, 31, 27, 2, "R90")
    me.place("3003", WHITE, 31, 31, 2, "R0")

    # Rear Facade Wall (mz=33..34, x=4..31)
    for kx in [4, 8, 12, 16, 20, 24, 28]:
        me.place("3001", WHITE, kx, 33, 2, "R0")

    # Continuous Interior Structural Bearing Walls (x=12, 20, 28 across z=25, 29)
    for kx in [12, 20, 28]:
        me.place("3001", DARK_TAN, kx, 25, 2, "R90")
        me.place("3001", DARK_TAN, kx, 29, 2, "R90")

    # =========================================================================
    # STAGE 7: Main Residence — Second Floor Platform & Balcony (py=5, h=1)
    # =========================================================================
    # Floor platform plates spanning across walls
    for mz in [21, 25, 29, 33]:
        for kx in [4, 8, 12, 16, 20, 24, 28]:
            me.place("3020", WHITE, kx, mz, 5, "R0")

    # Cantilevered Upper Terrace Balcony Overhang (at z=19..20, x=6..30)
    for kx in range(6, 30, 4):
        me.place("3020", WHITE, kx, 19, 5, "R0")

    # Balcony Glass Railing (py=6, h=1: trans-blue and black tiles)
    for kx in range(6, 30, 2):
        me.place("2412b", BLACK, kx, 19, 6, "R0")
    me.place("3070b", BLACK, 6, 20, 6, "R0")
    me.place("3070b", BLACK, 29, 20, 6, "R0")

    # =========================================================================
    # STAGE 8: Main Residence — Second Floor Residence & Suites (py=6..8, h=3)
    # =========================================================================
    # Front Facade Wall with Picture Windows & French Balcony Doors (z=21)
    me.place("3001", WHITE, 4, 21, 6, "R0")
    for kx in range(8, 28, 2):
        if kx in [10, 14, 18, 22, 26]:
            me.place("3004", TRANS_LIGHT_BLUE, kx, 21, 6, "R0")
        else:
            me.place("3004", WHITE, kx, 21, 6, "R0")
    me.place("3003", WHITE, 28, 21, 6, "R0")
    me.place("3003", WHITE, 30, 21, 6, "R0")

    # West Wall (x=4..5, z=23..32)
    me.place("3001", WHITE, 4, 23, 6, "R90")
    me.place("3001", WHITE, 4, 27, 6, "R90")
    me.place("3003", WHITE, 4, 31, 6, "R0")

    # East Wall (x=31..32, z=23..32)
    me.place("3001", WHITE, 31, 23, 6, "R90")
    me.place("3001", WHITE, 31, 27, 6, "R90")
    me.place("3003", WHITE, 31, 31, 6, "R0")

    # Rear Wall (mz=33..34, x=4..31)
    for kx in [4, 8, 12, 16, 20, 24, 28]:
        me.place("3001", WHITE, kx, 33, 6, "R0")

    # Interior Bearing Walls (x=12, 20, 28 across z=25, 29)
    for kx in [12, 20, 28]:
        me.place("3001", DARK_TAN, kx, 25, 6, "R90")
        me.place("3001", DARK_TAN, kx, 29, 6, "R90")

    # =========================================================================
    # STAGE 9: Roof System, Sky Lounge Terrace & Cupola Tower (py=9..13)
    # =========================================================================
    # Roof Deck Plates spanning across all walls (py=9, h=1)
    for mz in [21, 25, 29, 33]:
        for kx in [4, 8, 12, 16, 20, 24, 28]:
            me.place("3020", DARK_BLUISH_GRAY, kx, mz, 9, "R0")

    # Left Gabled Wing Roof Shingles (x=4..12, z=21..33, py=10)
    for mz in [21, 25, 29, 33]:
        me.place("3020", DARK_BLUISH_GRAY, 4, mz, 10, "R0")
        me.place("3020", DARK_BLUISH_GRAY, 8, mz, 10, "R0")

    # Right Cross-Gabled Wing Roof Shingles (x=24..32, z=21..33, py=10)
    for mz in [21, 25, 29, 33]:
        me.place("3020", DARK_BLUISH_GRAY, 24, mz, 10, "R0")
        me.place("3020", DARK_BLUISH_GRAY, 28, mz, 10, "R0")

    # Central Flat Rooftop Sky Lounge / Observation Terrace (x=12..24, z=21..33, py=10)
    for kx in range(12, 24, 2):
        me.place("2412b", BLACK, kx, 21, 10, "R0") # Glass safety railing front
        me.place("2412b", BLACK, kx, 33, 10, "R0") # Glass safety railing rear

    # Architectural Observation Cupola / Skylight Tower (x=16..20, z=25..29, py=10..13)
    me.place("3003", WHITE, 16, 25, 10, "R0")
    me.place("3003", WHITE, 18, 25, 10, "R0")
    me.place("3003", WHITE, 16, 27, 10, "R0")
    me.place("3003", WHITE, 18, 27, 10, "R0")

    # Cupola Slate Pyramidal Roof Cap (py=13, h=1)
    me.place("3022", DARK_BLUISH_GRAY, 16, 25, 13, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 18, 25, 13, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 16, 27, 13, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 18, 27, 13, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 17, 26, 14, "R0")

    # =========================================================================
    # STAGE 10: Detached Guest House / Cabana with Solar Roof (py=2..8)
    # Footprint: x=36..46, z=21..32 (10 studs wide x 11 studs deep)
    # =========================================================================
    # Ground Floor Walls (py=2..4, h=3)
    me.place("3004", WHITE, 36, 21, 2, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 38, 21, 2, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 40, 21, 2, "R0")
    me.place("3004", WHITE, 42, 21, 2, "R0")
    me.place("3003", WHITE, 44, 21, 2, "R0")

    # Side walls
    for mz in [23, 27, 31]:
        me.place("3004", WHITE, 36, mz, 2, "R90")
        me.place("3004", WHITE, 45, mz, 2, "R90")

    # Rear wall
    me.place("3001", WHITE, 37, 32, 2, "R0")
    me.place("3001", WHITE, 41, 32, 2, "R0")

    # Interior partition
    me.place("3001", DARK_TAN, 38, 27, 2, "R0")
    me.place("3003", DARK_TAN, 42, 27, 2, "R0")

    # Cabana Roof Platform (py=5, h=1)
    for mz in [21, 25, 29]:
        me.place("3020", DARK_BLUISH_GRAY, 36, mz, 5, "R0")
        me.place("3020", DARK_BLUISH_GRAY, 40, mz, 5, "R0")
        me.place("3022", DARK_BLUISH_GRAY, 44, mz, 5, "R0")

    # Cabana Pitched Roof & Rooftop Photovoltaic Solar Panel Array (py=6, h=1)
    # Slate shingles
    for mz in [21, 25, 29]:
        me.place("3020", DARK_BLUISH_GRAY, 36, mz, 6, "R0")
        me.place("3022", DARK_BLUISH_GRAY, 44, mz, 6, "R0")

    # Solar Panels (Black grille tiles 2412b simulating photovoltaic glass)
    for mz in [22, 24, 26, 28]:
        me.place("2412b", BLACK, 40, mz, 6, "R0")
        me.place("2412b", BLACK, 42, mz, 6, "R0")

    # Cabana Masonry Chimney Stack (x=44, z=31, py=6..9)
    me.place("3003", WHITE, 44, 31, 6, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 44, 31, 9, "R0")

    # =========================================================================
    # STAGE 11: Cobblestone Paving, Walkways & Garden Details (py=2)
    # =========================================================================
    plate_studs_y1 = set()
    for (px, pz, py) in me.occupied:
        if py == 1:
            plate_studs_y1.add((px, pz))

    for z in range(1, 35):
        for x in range(1, 47):
            if (x, z) in plate_studs_y1 and (x+1, z) in plate_studs_y1:
                if me.can_place("3069b", x, z, 2, "R0"):
                    if 1 <= z <= 11 and 18 <= x <= 36:
                        color = TAN # Teak sun deck tiles
                    elif 12 <= z <= 20:
                        color = DARK_GREEN # Lawn grass tiles
                    else:
                        color = LIGHT_BLUISH_GRAY # Travertine & stone pavers
                    me.place("3069b", color, x, z, 2, "R0")

    for z in range(1, 34):
        for x in range(1, 47):
            if (x, z) in plate_studs_y1 and (x, z+1) in plate_studs_y1:
                if me.can_place("3069b", x, z, 2, "R90"):
                    if 1 <= z <= 11 and 18 <= x <= 36:
                        color = TAN
                    elif 12 <= z <= 20:
                        color = DARK_GREEN
                    else:
                        color = LIGHT_BLUISH_GRAY
                    me.place("3069b", color, x, z, 2, "R90")

    for z in range(1, 35):
        for x in range(1, 47):
            if (x, z) in plate_studs_y1:
                if me.can_place("3070b", x, z, 2, "R0"):
                    if 1 <= z <= 11 and 18 <= x <= 36:
                        color = TAN
                    elif 12 <= z <= 20:
                        color = DARK_GREEN
                    else:
                        color = LIGHT_BLUISH_GRAY
                    me.place("3070b", color, x, z, 2, "R0")

    return me

if __name__ == "__main__":
    me = build_bel_air_estate()
    piece_count = me.count()
    print(f"\n{'━'*64}")
    print(f"  {me.name.upper()}")
    print(f"  TOTAL PIECE COUNT: {piece_count}")
    print(f"{'━'*64}")

    p = Path("test_bel_air.ldr")
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
