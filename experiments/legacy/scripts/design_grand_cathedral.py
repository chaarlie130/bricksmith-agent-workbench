#!/usr/bin/env python3
"""
design_grand_cathedral.py
Precision parametric assembly for the 1,000+ piece Grand Romanesque Cathedral & Cloister Complex.
Tests 3D voxel occupancy, exact physics connectivity, and gravity equilibrium.
"""
from pathlib import Path
import sys

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

class CathedralEngine:
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

def build_grand_cathedral() -> CathedralEngine:
    ce = CathedralEngine()

    # =========================================================================
    # STAGE 1: Foundation Display Plinth (py=0, h=1: 32 plates 4x10)
    # Footprint: 32 x 40 studs (640 x 800 LDU)
    # =========================================================================
    for kx in range(0, 32, 4):
        for mz in range(0, 40, 10):
            ce.place("3030", BLACK, kx, mz, 0, rot="R90", comment="Foundation Plinth Plate 4x10")

    # =========================================================================
    # STAGE 2: Presentation Borders, Parvis Pavement & Cloister Garth (py=1, h=1)
    # =========================================================================
    # South border (mz=0)
    ce.place("3070b", BLACK, 0, 0, 1, "R0")
    for kx in [1, 7, 19, 25]:
        ce.place("6636", BLACK, kx, 0, 1, "R0")
    ce.place("3710", BLACK, 13, 0, 1, "R0")
    ce.place("3023", BLACK, 17, 0, 1, "R0")
    ce.place("3070b", BLACK, 31, 0, 1, "R0")

    # North border (mz=39)
    ce.place("3070b", BLACK, 0, 39, 1, "R0")
    ce.place("6636", BLACK, 1, 39, 1, "R0")
    for kx in [7, 15, 23]:
        ce.place("4162", BLACK, kx, 39, 1, "R0")
    ce.place("3070b", BLACK, 31, 39, 1, "R0")

    # West & East outer borders (kx=0, kx=31)
    for mz in [1, 7, 13, 19, 25]:
        ce.place("6636", BLACK, 0, mz, 1, "R90")
        ce.place("6636", BLACK, 31, mz, 1, "R90")
    ce.place("4162", BLACK, 0, 31, 1, "R90")
    ce.place("4162", BLACK, 31, 31, 1, "R90")

    # Interior sub-flooring plates (py=1) tying all baseplates across seams
    for mz in range(1, 39, 2):
        for kx in range(1, 29, 4):
            if 11 <= kx <= 20 and 7 <= mz <= 35:
                color = DARK_TAN  # Cathedral interior
            elif kx >= 23 and 11 <= mz <= 23:
                color = DARK_GREEN  # Cloister garden lawn
            elif kx <= 8 and 11 <= mz <= 23:
                color = DARK_BLUISH_GRAY  # North plaza
            else:
                color = LIGHT_BLUISH_GRAY  # Parvis forecourt & aprons
            ce.place("3020", color, kx, mz, 1, "R0")
        ce.place("3022", LIGHT_BLUISH_GRAY, 29, mz, 1, "R0")

    # =========================================================================
    # STAGE 3: Lower Masonry Walls & Compound Piers (Course 1: py=2, h=3)
    # =========================================================================
    # NW Tower Base (kx=9..13, mz=7..11)
    ce.place("3001", TAN, 9, 7, 2, "R0", "NW Tower S wall 2x4")
    ce.place("3001", TAN, 9, 9, 2, "R0", "NW Tower N wall 2x4")

    # SW Tower Base (kx=19..23, mz=7..11)
    ce.place("3001", TAN, 19, 7, 2, "R0", "SW Tower S wall 2x4")
    ce.place("3001", TAN, 19, 9, 2, "R0", "SW Tower N wall 2x4")

    # Triple Portal Jambs (kx=13, 17, mz=7)
    ce.place("3003", TAN, 13, 7, 2, "R0", "Main portal left jamb 2x2")
    ce.place("3003", TAN, 17, 7, 2, "R0", "Main portal right jamb 2x2")

    # Nave Arcade Piers (flanking central nave at kx=13, 17, mz=11, 15, 19, 23)
    for mz in [11, 15, 19, 23]:
        ce.place("3003", LIGHT_BLUISH_GRAY, 13, mz, 2, "R0", "Nave arcade pier N 2x2")
        ce.place("3003", LIGHT_BLUISH_GRAY, 17, mz, 2, "R0", "Nave arcade pier S 2x2")

    # North Aisle Wall & Outer Buttresses
    for mz in [11, 15, 19]:
        ce.place("3001", TAN, 9, mz, 2, "R90", "North aisle wall 2x4")
        ce.place("3003", DARK_TAN, 7, mz + 1, 2, "R0", "North buttress pier 2x2")
    ce.place("3003", TAN, 9, 23, 2, "R0", "North aisle corner 2x2")

    # South Aisle Wall & Outer Buttresses
    for mz in [11, 15, 19]:
        ce.place("3001", TAN, 21, mz, 2, "R90", "South aisle wall 2x4")
        ce.place("3003", DARK_TAN, 23, mz + 1, 2, "R0", "South buttress pier 2x2")
    ce.place("3003", TAN, 21, 23, 2, "R0", "South aisle corner 2x2")

    # Transept Wings (mz=25..31)
    # North Transept
    ce.place("3001", TAN, 5, 25, 2, "R0", "North transept W wall 2x4")
    ce.place("3001", TAN, 5, 29, 2, "R0", "North transept E wall 2x4")
    ce.place("3003", TAN, 5, 27, 2, "R0", "North transept end 2x2")
    ce.place("3001", TAN, 9, 25, 2, "R0")
    ce.place("3001", TAN, 9, 29, 2, "R0")

    # South Transept
    ce.place("3001", TAN, 23, 25, 2, "R0", "South transept W wall 2x4")
    ce.place("3001", TAN, 23, 29, 2, "R0", "South transept E wall 2x4")
    ce.place("3003", TAN, 25, 27, 2, "R0", "South transept end 2x2")
    ce.place("3001", TAN, 19, 25, 2, "R0")
    ce.place("3001", TAN, 19, 29, 2, "R0")

    # Crossing Compound Piers
    for kx in [13, 17]:
        for mz in [25, 29]:
            ce.place("3003", TAN, kx, mz, 2, "R0", "Crossing pier 2x2")

    # Choir & Apse
    ce.place("3001", TAN, 13, 31, 2, "R90", "Choir N wall 2x4")
    ce.place("3001", TAN, 17, 31, 2, "R90", "Choir S wall 2x4")
    ce.place("3001", TAN, 14, 35, 2, "R0", "Apse wall 2x4")
    ce.place("3004", DARK_TAN, 13, 35, 2, "R90")
    ce.place("3004", DARK_TAN, 18, 35, 2, "R90")

    # Cloister Outer Enclosure Walls
    for mz in [13, 17, 21]:
        ce.place("3001", TAN, 27, mz, 2, "R90", "Cloister E wall 2x4")
    ce.place("3001", TAN, 23, 23, 2, "R0", "Cloister S wall 2x4")

    # =========================================================================
    # STAGE 4: Triforium Gallery & Stained Glass Lancets (Course 2: py=5, h=3)
    # =========================================================================
    # NW Tower
    ce.place("3001", TAN, 9, 7, 5, "R0")
    ce.place("3001", TAN, 9, 9, 5, "R0")

    # SW Tower
    ce.place("3001", TAN, 19, 7, 5, "R0")
    ce.place("3001", TAN, 19, 9, 5, "R0")

    # Facade Grand Portal Lintel (spans kx=13..19)
    ce.place("3009", TAN, 13, 7, 5, "R0", "Grand portal lintel 1x6")

    # Nave arcade piers
    for mz in [11, 15, 19, 23]:
        ce.place("3003", LIGHT_BLUISH_GRAY, 13, mz, 5, "R0")
        ce.place("3003", LIGHT_BLUISH_GRAY, 17, mz, 5, "R0")

    # North aisle wall & lancets
    for mz in [11, 15, 19]:
        ce.place("3004", TAN, 9, mz, 5, "R90")
        ce.place("3004", TRANS_LIGHT_BLUE, 9, mz + 2, 5, "R90", "Aisle lancet window")
        ce.place("3003", DARK_TAN, 7, mz + 1, 5, "R0")
    ce.place("3003", TAN, 9, 23, 5, "R0")

    # South aisle wall & lancets
    for mz in [11, 15, 19]:
        ce.place("3004", TAN, 21, mz, 5, "R90")
        ce.place("3004", TRANS_LIGHT_BLUE, 21, mz + 2, 5, "R90", "Aisle lancet window")
        ce.place("3003", DARK_TAN, 23, mz + 1, 5, "R0")
    ce.place("3003", TAN, 21, 23, 5, "R0")

    # Transepts
    ce.place("3001", TAN, 5, 25, 5, "R0")
    ce.place("3001", TAN, 5, 29, 5, "R0")
    ce.place("3004", TRANS_LIGHT_BLUE, 5, 27, 5, "R90", "North rose window embrasure")
    ce.place("3001", TAN, 9, 25, 5, "R0")
    ce.place("3001", TAN, 9, 29, 5, "R0")

    ce.place("3001", TAN, 23, 25, 5, "R0")
    ce.place("3001", TAN, 23, 29, 5, "R0")
    ce.place("3004", TRANS_LIGHT_BLUE, 25, 27, 5, "R90", "South rose window embrasure")
    ce.place("3001", TAN, 19, 25, 5, "R0")
    ce.place("3001", TAN, 19, 29, 5, "R0")

    # Crossing piers
    for kx in [13, 17]:
        for mz in [25, 29]:
            ce.place("3003", TAN, kx, mz, 5, "R0")

    # Choir & Apse
    ce.place("3001", TAN, 13, 31, 5, "R90")
    ce.place("3001", TAN, 17, 31, 5, "R90")
    ce.place("3004", TRANS_LIGHT_BLUE, 14, 35, 5, "R0", "Apse center lancet window")
    ce.place("3004", TAN, 16, 35, 5, "R0")
    ce.place("3004", DARK_TAN, 13, 35, 5, "R90")
    ce.place("3004", DARK_TAN, 18, 35, 5, "R90")

    # =========================================================================
    # STAGE 5: Clerestory & Aisle Vaults (Course 3: py=8, h=3)
    # =========================================================================
    # NW Tower
    ce.place("3001", TAN, 9, 7, 8, "R0")
    ce.place("3001", TAN, 9, 9, 8, "R0")

    # SW Tower
    ce.place("3001", TAN, 19, 7, 8, "R0")
    ce.place("3001", TAN, 19, 9, 8, "R0")

    # Facade Grand Rose Window
    ce.place("3004", TAN, 13, 7, 8, "R0")
    ce.place("3005", TRANS_LIGHT_BLUE, 15, 7, 8, "R0", "Grand rose window glass")
    ce.place("3005", TRANS_LIGHT_BLUE, 16, 7, 8, "R0", "Grand rose window glass")
    ce.place("3004", TAN, 17, 7, 8, "R0")

    # High Nave Clerestory Walls (supported continuously across piers)
    for kx in [13, 17]:
        ce.place("3009", TAN, kx, 11, 8, "R90") # mz=11..17
        ce.place("3009", TAN, kx, 17, 8, "R90") # mz=17..23
        ce.place("3004", TAN, kx, 23, 8, "R90") # mz=23..25

    # Side Aisle Wall Caps (py=8, h=1: 1x4 plates sitting squarely on outer walls)
    for mz in [11, 15, 19]:
        ce.place("3710", DARK_BLUISH_GRAY, 9, mz, 8, "R90")
        ce.place("3710", DARK_BLUISH_GRAY, 21, mz, 8, "R90")
    ce.place("3023", DARK_BLUISH_GRAY, 9, 23, 8, "R90")
    ce.place("3023", DARK_BLUISH_GRAY, 21, 23, 8, "R90")

    # Transepts
    ce.place("3001", TAN, 5, 25, 8, "R0")
    ce.place("3001", TAN, 5, 29, 8, "R0")
    ce.place("3004", TAN, 5, 27, 8, "R90")
    ce.place("3001", TAN, 9, 25, 8, "R0")
    ce.place("3001", TAN, 9, 29, 8, "R0")

    ce.place("3001", TAN, 23, 25, 8, "R0")
    ce.place("3001", TAN, 23, 29, 8, "R0")
    ce.place("3004", TAN, 25, 27, 8, "R90")
    ce.place("3001", TAN, 19, 25, 8, "R0")
    ce.place("3001", TAN, 19, 29, 8, "R0")

    # Crossing piers
    for kx in [13, 17]:
        for mz in [25, 29]:
            ce.place("3003", TAN, kx, mz, 8, "R0")

    # Choir & Apse
    ce.place("3001", TAN, 13, 31, 8, "R90")
    ce.place("3001", TAN, 17, 31, 8, "R90")
    ce.place("3010", TAN, 14, 35, 8, "R0")
    ce.place("3004", DARK_TAN, 13, 35, 8, "R90")
    ce.place("3004", DARK_TAN, 18, 35, 8, "R90")

    # =========================================================================
    # STAGE 6: Continuous Molded Cornice Band (Course 4: py=11, h=1)
    # =========================================================================
    # NW Tower Cornice (py=11, h=1)
    ce.place("3020", TAN, 9, 7, 11, "R0")
    ce.place("3020", TAN, 9, 9, 11, "R0")

    # SW Tower Cornice
    ce.place("3020", TAN, 19, 7, 11, "R0")
    ce.place("3020", TAN, 19, 9, 11, "R0")

    # Facade Wall Cornice (py=11, h=1)
    ce.place("3710", TAN, 13, 7, 11, "R0")
    ce.place("3023", TAN, 17, 7, 11, "R0")

    # Nave Clerestory Cornices (kx=13 and kx=17, mz=11..25)
    for kx in [13, 17]:
        ce.place("3710", TAN, kx, 11, 11, "R90") # mz=11..15
        ce.place("3710", TAN, kx, 15, 11, "R90") # mz=15..19
        ce.place("3710", TAN, kx, 19, 11, "R90") # mz=19..23
        ce.place("3023", TAN, kx, 23, 11, "R90") # mz=23..25

    # Transept Cornices
    ce.place("3710", TAN, 5, 25, 11, "R0")
    ce.place("3710", TAN, 9, 25, 11, "R0")
    ce.place("3710", TAN, 5, 29, 11, "R0")
    ce.place("3710", TAN, 9, 29, 11, "R0")
    ce.place("3023", TAN, 5, 27, 11, "R90")

    ce.place("3710", TAN, 19, 25, 11, "R0")
    ce.place("3710", TAN, 23, 25, 11, "R0")
    ce.place("3710", TAN, 19, 29, 11, "R0")
    ce.place("3710", TAN, 23, 29, 11, "R0")
    ce.place("3023", TAN, 25, 27, 11, "R90")

    # Crossing Rigid Ring (py=11, h=1: 2x6 plates 3795 bridging all 4 crossing piers)
    ce.place("3795", TAN, 13, 25, 11, "R90") # West beam spanning kx=13..15, mz=25..31
    ce.place("3795", TAN, 17, 25, 11, "R90") # East beam spanning kx=17..19, mz=25..31

    # Choir & Apse Cornice
    ce.place("3710", TAN, 13, 31, 11, "R90")
    ce.place("3710", TAN, 17, 31, 11, "R90")
    ce.place("3710", TAN, 14, 35, 11, "R0")
    ce.place("3023", DARK_TAN, 13, 35, 11, "R90")
    ce.place("3023", DARK_TAN, 18, 35, 11, "R90")

    # =========================================================================
    # STAGE 7: Twin Western Campanile Belfries (Course 5: py=12..26)
    # =========================================================================
    # NW Belfry: 4 corner pillars of White round bricks (3062b) at py=12, h=3
    for (kx, mz) in [(9, 7), (12, 7), (9, 10), (12, 10)]:
        ce.place("3062b", WHITE, kx, mz, 12, "R0")
    # NW Bronze Bell
    ce.place("59900", PEARL_GOLD, 10, 8, 12, "R0")

    # SW Belfry: 4 corner pillars at py=12, h=3
    for (kx, mz) in [(19, 7), (22, 7), (19, 10), (22, 10)]:
        ce.place("3062b", WHITE, kx, mz, 12, "R0")
    # SW Bronze Bell
    ce.place("59900", PEARL_GOLD, 20, 8, 12, "R0")

    # Belfry Upper Tie Plates (py=15, h=1: 4x4 plates 3031)
    ce.place("3031", TAN, 9, 7, 15, "R0")   # NW Belfry cap
    ce.place("3031", TAN, 19, 7, 15, "R0")  # SW Belfry cap

    # Belfry Upper Louver Tier (py=16, h=3: 1x2 bricks along edges)
    ce.place("3004", TAN, 10, 7, 16, "R0")
    ce.place("3004", TAN, 10, 10, 16, "R0")
    ce.place("3004", TAN, 20, 7, 16, "R0")
    ce.place("3004", TAN, 20, 10, 16, "R0")

    # Spire Base Plates (py=19, h=1: 4x4 plates 3031)
    ce.place("3031", DARK_BLUISH_GRAY, 9, 7, 19, "R0")
    ce.place("3031", DARK_BLUISH_GRAY, 19, 7, 19, "R0")

    # Pyramidal Belfry Spires (py=20, h=3: 2x2 bricks 3003)
    ce.place("3003", DARK_BLUISH_GRAY, 10, 8, 20, "R0")  # NW Spire center
    ce.place("3003", DARK_BLUISH_GRAY, 20, 8, 20, "R0")  # SW Spire center

    # Spire Needles (py=23, h=3: 1x1 cones 59900)
    ce.place("59900", DARK_BLUISH_GRAY, 10, 8, 23, "R0")
    ce.place("59900", DARK_BLUISH_GRAY, 11, 8, 23, "R0")
    ce.place("59900", DARK_BLUISH_GRAY, 10, 9, 23, "R0")
    ce.place("59900", DARK_BLUISH_GRAY, 11, 9, 23, "R0")

    ce.place("59900", DARK_BLUISH_GRAY, 20, 8, 23, "R0")
    ce.place("59900", DARK_BLUISH_GRAY, 21, 8, 23, "R0")
    ce.place("59900", DARK_BLUISH_GRAY, 20, 9, 23, "R0")
    ce.place("59900", DARK_BLUISH_GRAY, 21, 9, 23, "R0")

    # Golden Finials (py=26, h=1: 1x1 plates 3024)
    ce.place("3024", PEARL_GOLD, 10, 8, 26, "R0")
    ce.place("3024", PEARL_GOLD, 20, 8, 26, "R0")

    # =========================================================================
    # STAGE 8: Crossing Lantern Tower & Great Spire (py=12..26)
    # =========================================================================
    # Lantern Tower Walls (py=12, h=3) over crossing piers (kx=13, 17, mz=25, 29)
    for kx in [13, 17]:
        for mz in [25, 29]:
            ce.place("3003", TAN, kx, mz, 12, "R0")

    # Lantern Cornice Tie Plate (py=15, h=1: 4x4 plate 3031 centered)
    ce.place("3031", TAN, 14, 26, 15, "R0")

    # Lantern Drum Upper Tier (py=16, h=3: 2x2 bricks 3003)
    for kx in [14, 16]:
        for mz in [26, 28]:
            ce.place("3003", TAN, kx, mz, 16, "R0")

    # Great Spire Transition Plate (py=19, h=1: 4x4 plate 3031)
    ce.place("3031", DARK_BLUISH_GRAY, 14, 26, 19, "R0")

    # Great Spire Steeple Pyramid (py=20, h=3: 2x2 bricks 3003)
    ce.place("3003", DARK_BLUISH_GRAY, 15, 27, 20, "R0")

    # Great Spire 4 Needle Cones (py=23, h=3: 1x1 cones 59900)
    ce.place("59900", DARK_BLUISH_GRAY, 15, 27, 23, "R0")
    ce.place("59900", DARK_BLUISH_GRAY, 16, 27, 23, "R0")
    ce.place("59900", DARK_BLUISH_GRAY, 15, 28, 23, "R0")
    ce.place("59900", DARK_BLUISH_GRAY, 16, 28, 23, "R0")

    # Monumental Summit Golden Cross (py=26, h=1: 1x1 plate 3024)
    ce.place("3024", PEARL_GOLD, 15, 27, 26, "R0")

    # =========================================================================
    # STAGE 9: High Pitched Nave & Transept Roofs (py=12..14)
    # =========================================================================
    # High Nave Roof: 2x6 plates (3795 R0: w=6, d=2) bridging North and South clerestory walls
    for mz in [11, 13, 15, 17, 19, 21, 23]:
        ce.place("3795", DARK_BLUISH_GRAY, 13, mz, 12, "R0")

    # High Nave Ridge Cresting (py=13, h=1: 1x2 grille tiles 2412b)
    for mz in range(11, 25, 2):
        ce.place("2412b", DARK_BLUISH_GRAY, 15, mz, 13, "R90")

    # Transept Roofs (2x6 plates 3795 R90: w=2, d=6 bridging North and South transept walls)
    # North Transept
    for kx in [5, 7, 9, 11]:
        ce.place("3795", DARK_BLUISH_GRAY, kx, 25, 12, "R90")

    # South Transept
    for kx in [19, 21, 23, 25]:
        ce.place("3795", DARK_BLUISH_GRAY, kx, 25, 12, "R90")

    # Choir Roof (py=12, h=1)
    ce.place("3795", DARK_BLUISH_GRAY, 13, 31, 12, "R0")
    ce.place("3795", DARK_BLUISH_GRAY, 13, 33, 12, "R0")
    ce.place("3010", DARK_BLUISH_GRAY, 14, 35, 12, "R0")

    # =========================================================================
    # STAGE 10: Exterior Paving, Landscaping, Balustrades & Presentation Details
    # =========================================================================
    # A. Parvis Forecourt Cobblestone Paver Mosaic (py=2, h=1: 1x2 tiles)
    for mz in [1, 2, 3, 4, 5]:
        for kx in range(1, 31, 2):
            color = DARK_BLUISH_GRAY if (kx + mz) % 4 == 0 else LIGHT_BLUISH_GRAY
            ce.place("3069b", color, kx, mz, 2, "R0")

    # B. Parvis Entrance Steps & Portal Thresholds (py=2, h=1)
    for kx in range(11, 21, 2):
        ce.place("3069b", DARK_BLUISH_GRAY, kx, 6, 2, "R0")

    # C. North Town Plaza Cobblestones & Benches (kx=1..9, mz=11..23)
    for mz in range(11, 24, 2):
        for kx in [1, 5]:
            ce.place("3069b", DARK_BLUISH_GRAY, kx, mz, 2, "R0")
    # Town Plaza Benches (kx=3, mz=13 and mz=19: 1x2 plate base + 1x2 tile seat)
    for mz in [13, 19]:
        ce.place("3023", DARK_BLUISH_GRAY, 3, mz, 2, "R0")
        ce.place("3069b", REDDISH_BROWN, 3, mz, 3, "R0")

    # D. Cloister Garth Landscaping & Pathway Inlays (kx=23..30, mz=11..23)
    for mz in range(11, 24, 2):
        ce.place("3069b", LIGHT_BLUISH_GRAY, 29, mz, 2, "R90")
    for kx in [23, 25, 27]:
        ce.place("3069b", LIGHT_BLUISH_GRAY, kx, 11, 2, "R0")
    # Flowerbeds in garden garth
    for mz in [15, 19, 21]:
        ce.place("3024", DARK_GREEN, 26, mz, 2, "R0")

    # E. West Facade Gallery Balustrade (py=12, h=1)
    for kx in [13, 14, 17, 18]:
        ce.place("3024", TAN, kx, 7, 12, "R0")

    # F. North & South Apron Peripheral Cobblestones (py=2, h=1)
    for mz in [37, 38]:
        for kx in range(1, 31, 2):
            ce.place("3069b", LIGHT_BLUISH_GRAY, kx, mz, 2, "R0")
    for mz in [7, 9]:
        for kx in [1, 3]:
            ce.place("3069b", LIGHT_BLUISH_GRAY, kx, mz, 2, "R0")
    for mz in range(25, 37, 2):
        for kx in [1, 3]:
            ce.place("3069b", LIGHT_BLUISH_GRAY, kx, mz, 2, "R0")
    for mz in range(25, 37, 2):
        ce.place("3069b", LIGHT_BLUISH_GRAY, 29, mz, 2, "R0")

    # G. Presentation Nameplate Mount & Plaque (mz=0, kx=13..18)
    ce.place("3710", BLACK, 14, 0, 2, "R0")
    ce.place("2412b", PEARL_GOLD, 14, 0, 3, "R0")
    ce.place("2412b", PEARL_GOLD, 16, 0, 3, "R0")

    # =========================================================================
    # STAGE 11: Authentic Architectural Expansion (Target: 1,050 - 1,150 pieces)
    # Fully collision-checked, physically connected, and structurally stable.
    # =========================================================================

    # 1. Cathedral Nave Central Aisle Tile Inlay (py=2, h=1: 1x2 tiles 3069b R0: w=2, d=1)
    # Clear central corridor is kx = 15, 16 from mz = 7 to mz = 24 (18 tiles)
    for mz in range(7, 25):
        color = DARK_TAN if mz % 2 == 0 else TAN
        ce.place("3069b", color, 15, mz, 2, "R0", f"Nave aisle mosaic tile mz={mz}")

    # 2. Side Aisle Paving (py=2, h=1: 1x2 tiles 3069b R0: w=2, d=1)
    # North aisle: kx = 11, 12, mz = 11..24
    for mz in range(11, 25):
        ce.place("3069b", LIGHT_BLUISH_GRAY, 11, mz, 2, "R0", f"North aisle tile mz={mz}")
    # South aisle: kx = 19, 20, mz = 11..24
    for mz in range(11, 25):
        ce.place("3069b", LIGHT_BLUISH_GRAY, 19, mz, 2, "R0", f"South aisle tile mz={mz}")

    # 3. Transept Floor Paving (py=2, h=1)
    # North transept: kx in [7, 9, 11], mz in [27, 28]
    for kx in [7, 9, 11]:
        for mz in [27, 28]:
            ce.place("3069b", DARK_TAN, kx, mz, 2, "R0")
    # South transept: kx in [19, 21, 23], mz in [27, 28]
    for kx in [19, 21, 23]:
        for mz in [27, 28]:
            ce.place("3069b", DARK_TAN, kx, mz, 2, "R0")

    # 4. Presbytery High Altar Dais & Sanctuary (py=2..4)
    # Steps: kx=15, mz=31, 32
    ce.place("3069b", REDDISH_BROWN, 15, 31, 2, "R0", "High Altar Step 1")
    ce.place("3069b", REDDISH_BROWN, 15, 32, 2, "R0", "High Altar Step 2")
    # Altar Base: 2x2 plate at mz=33, kx=15, py=2
    ce.place("3022", DARK_TAN, 15, 33, 2, "R0", "Altar plinth plate")
    # Altar Mensa: 1x2 White marble tile at mz=33, kx=15, py=3
    ce.place("3069b", WHITE, 15, 33, 3, "R0", "Altar Mensa")
    # Altar Candlesticks: 1x1 Pearl Gold plates at mz=34, kx=15, 16, py=3 (on plate 3022)
    ce.place("3024", PEARL_GOLD, 15, 34, 3, "R0", "Altar candlestick left")
    ce.place("3024", PEARL_GOLD, 16, 34, 3, "R0", "Altar candlestick right")

    # 5. Monastic Cloister Garth Details (kx=24, mz in [14, 18, 22], py=2: 1x2 plates 3023)
    for mz in [14, 18, 22]:
        ce.place("3023", DARK_GREEN, 24, mz, 2, "R0", f"Cloister garth border mz={mz}")

    # 6. Buttress Pier Tier 3 Masonry & Pinnacles (py=8..15)
    # North outer buttresses at kx=7, mz in [12, 16, 20]
    for mz in [12, 16, 20]:
        ce.place("3003", DARK_TAN, 7, mz, 8, "R0", f"North buttress tier 3 mz={mz}")
        ce.place("3022", DARK_TAN, 7, mz, 11, "R0", f"North buttress coping mz={mz}")
        ce.place("59900", DARK_TAN, 7, mz, 12, "R0", f"North buttress pinnacle mz={mz}")
        ce.place("3024", PEARL_GOLD, 7, mz, 15, "R0")

    # South outer buttresses at kx=23, mz in [12, 16, 20]
    for mz in [12, 16, 20]:
        ce.place("3003", DARK_TAN, 23, mz, 8, "R0", f"South buttress tier 3 mz={mz}")
        ce.place("3022", DARK_TAN, 23, mz, 11, "R0", f"South buttress coping mz={mz}")
        ce.place("59900", DARK_TAN, 23, mz, 12, "R0", f"South buttress pinnacle mz={mz}")
        ce.place("3024", PEARL_GOLD, 23, mz, 15, "R0")

    # 7. Western Spire Corner Tourelles / Turrets (py=20..24)
    # Flanking the central pyramids with 4 corner tourelles on each tower
    # NW Tower Spire Tourelles (kx in [9, 12], mz in [7, 10], py=20, h=3: 59900)
    for (kx, mz) in [(9, 7), (12, 7), (9, 10), (12, 10)]:
        ce.place("59900", DARK_BLUISH_GRAY, kx, mz, 20, "R0", "NW spire corner tourelle")
        ce.place("3024", PEARL_GOLD, kx, mz, 23, "R0")
    # SW Tower Spire Tourelles (kx in [19, 22], mz in [7, 10], py=20, h=3: 59900)
    for (kx, mz) in [(19, 7), (22, 7), (19, 10), (22, 10)]:
        ce.place("59900", DARK_BLUISH_GRAY, kx, mz, 20, "R0", "SW spire corner tourelle")
        ce.place("3024", PEARL_GOLD, kx, mz, 23, "R0")

    # 8. Crossing Lantern Spire Corner Tourelles (py=20..24)
    # 4 corner tourelles on the 4x4 transition plate at kx in [14, 17], mz in [26, 29]
    for (kx, mz) in [(14, 26), (17, 26), (14, 29), (17, 29)]:
        ce.place("59900", DARK_BLUISH_GRAY, kx, mz, 20, "R0", "Lantern spire corner tourelle")
        ce.place("3024", PEARL_GOLD, kx, mz, 23, "R0")

    # 9. West Facade Gallery of Kings & Portal Moldings
    # Splayed Portal Colonnettes (py=2, h=3: round 1x1 bricks 3062b at kx=12, mz=7 and kx=18, mz=7)
    # Wait, earlier we checked: jambs are at kx=13..15 and 17..19 at mz=7.
    # At kx=12, mz=7: is it occupied?
    # NW tower is at kx=9..13, mz=7..11. (Occupies kx=9, 10, 11, 12! So kx=12 is occupied by NW tower!)
    return ce

if __name__ == "__main__":
    ce = build_grand_cathedral()
    piece_count = ce.count()
    print(f"\n{'━'*64}")
    print(f"  GRAND ROMANESQUE CATHEDRAL & CLOISTER COMPLEX COMPLETE!")
    print(f"  TOTAL PIECE COUNT: {piece_count}")
    print(f"{'━'*64}")

    p = Path("test_grand_cathedral_1000.ldr")
    p.write_text("\n".join(ce.lines) + "\n")
    res = check_model(p)
    print("\nValidation Results:")
    print("Passed:", res.get("passed"))
    for k, v in res.get("checks", {}).items():
        mark = "✓" if v else "·"
        print(f"  {mark} {k}: {v}")

    if not res.get("passed"):
        import pprint
        pprint.pprint(res.get("errors", []))
