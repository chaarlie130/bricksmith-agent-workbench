import sys
import time
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

class BelAirEngineV2:
    def __init__(self, name="The Bel Air Promontory - Modern Hillside Estate", w_studs=48, d_studs=36):
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


def build_bel_air_full() -> BelAirEngineV2:
    me = BelAirEngineV2()

    # =========================================================================
    # STAGE 1: Hillside Terraced Foundation Plinth (py=0, h=1)
    # 48 studs wide x 36 studs deep (six 8-wide cols x nine 4-deep rows = 54 plates 3035)
    # =========================================================================
    for mz in [0, 4, 8, 12, 16, 20, 24, 28, 32]:
        for kx in [0, 8, 16, 24, 32, 40]:
            me.place("3035", DARK_BLUISH_GRAY, kx, mz, 0, "R0")

    # =========================================================================
    # STAGE 2: Subfloor Tying Matrix & Polished Obsidian Borders (py=1, h=1)
    # =========================================================================
    # South border (mz=0, kx=0..47)
    me.place("3070b", BLACK, 0, 0, 1, "R0")
    for kx in [1, 9, 25, 33]:
        me.place("4162", BLACK, kx, 0, 1, "R0")
    # Plates under nameplate (kx=17..24)
    me.place("3710", BLACK, 17, 0, 1, "R0")
    me.place("3023", BLACK, 21, 0, 1, "R0")
    me.place("3024", BLACK, 23, 0, 1, "R0")
    me.place("3024", BLACK, 24, 0, 1, "R0")
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
            if 1 <= mz <= 11:
                if 2 <= kx <= 18:
                    color = MEDIUM_AZURE
                elif 18 <= kx <= 36:
                    color = TAN
                else:
                    color = DARK_BLUISH_GRAY
            elif 12 <= mz <= 20:
                color = DARK_GREEN
            elif 21 <= mz <= 33:
                if 4 <= kx <= 32:
                    color = TAN
                elif 36 <= kx <= 46:
                    color = LIGHT_BLUISH_GRAY
                else:
                    color = DARK_GREEN
            else:
                color = DARK_BLUISH_GRAY
            me.place("3020", color, kx, mz, 1, "R0")
        me.place("3022", LIGHT_BLUISH_GRAY, 45, mz, 1, "R0")

    # Presentation Bronze Estate Inscription (mz=0, kx=18..22, py=2..3)
    me.place("3710", BLACK, 18, 0, 2, "R0")
    me.place("2412b", PEARL_GOLD, 18, 0, 3, "R0")
    me.place("2412b", PEARL_GOLD, 20, 0, 3, "R0")

    # =========================================================================
    # STAGE 3: Cantilevered Hillside Infinity Pool & Spa Coping (py=2..3)
    # =========================================================================
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
    # STAGE 4: Teak Sun Deck Furniture, Loungers & Topiary (py=2..6)
    # =========================================================================
    # L-shaped sectional sofa (py=2..3)
    me.place("3023", WHITE, 24, 5, 2, "R0")
    me.place("3023", WHITE, 26, 5, 2, "R0")
    me.place("3023", WHITE, 28, 5, 2, "R0")
    me.place("3023", WHITE, 24, 7, 2, "R90")
    me.place("3069b", TAN, 24, 5, 3, "R0")
    me.place("3069b", TAN, 26, 5, 3, "R0")
    me.place("3069b", TAN, 28, 5, 3, "R0")
    me.place("3069b", TAN, 24, 7, 3, "R90")

    # Modern Low Coffee Table
    me.place("3022", DARK_BLUISH_GRAY, 26, 7, 2, "R0")
    me.place("3069b", WHITE, 26, 7, 3, "R0")

    # Luxury Sun Loungers facing the infinity view (x=20..22, z=4..9)
    for mz in [4, 6, 8]:
        me.place("3023", WHITE, 20, mz, 2, "R0")
        me.place("3069b", TAN, 20, mz, 3, "R0")

    # Outdoor Dining Table & Chairs (x=32..35, z=5..8)
    me.place("3022", REDDISH_BROWN, 33, 6, 2, "R0")
    me.place("3069b", REDDISH_BROWN, 33, 6, 3, "R0")
    me.place("3024", TAN, 32, 6, 2, "R0")
    me.place("3024", TAN, 35, 6, 2, "R0")
    me.place("3024", TAN, 33, 5, 2, "R0")
    me.place("3024", TAN, 33, 8, 2, "R0")

    # Terracotta Planter Pots with Topiary Shrubs on Deck (2x2 matching geometry)
    for (px, pz) in [(18, 3), (30, 3), (36, 3), (36, 10)]:
        me.place("3022", REDDISH_BROWN, px, pz, 2, "R0")
        me.place("3941", REDDISH_BROWN, px, pz, 3, "R0")
        me.place("3942c", DARK_GREEN, px, pz, 6, "R0")

    # Exterior Hillside Staircase on the far right (x=43..45, z=3..11)
    for step_z in range(3, 11, 2):
        me.place("3023", DARK_BLUISH_GRAY, 43, step_z, 2, "R0")
        me.place("3069b", BLACK, 43, step_z, 3, "R0")

    # =========================================================================
    # STAGE 5: Mature Olive / Magnolia Trees (py=2..12)
    # =========================================================================
    for (tx, tz) in [(10, 15), (22, 15), (34, 15)]:
        me.place("3022", DARK_TAN, tx, tz, 2, "R0")
        me.place("3941", REDDISH_BROWN, tx, tz, 3, "R0")
        me.place("3942c", DARK_GREEN, tx, tz, 6, "R0")
        me.place("3022", DARK_GREEN, tx, tz, 12, "R0")
        me.place("59900", DARK_GREEN, tx, tz, 13, "R0")

    # =========================================================================
    # STAGE 6: Main Residence Ground Floor (py=2..4, h=3)
    # Footprint: x=4..32, z=21..33 (Width 28 studs x Depth 12 studs)
    # =========================================================================
    # Front Facade: Panoramic Floor-to-Ceiling Sliding Glass & Covered Loggia
    me.place("3001", WHITE, 4, 21, 2, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 8, 21, 2, "R0")
    me.place("3004", WHITE, 10, 21, 2, "R0")

    for kx in range(12, 26, 2):
        if kx in [14, 18, 22]:
            me.place("3004", TRANS_LIGHT_BLUE, kx, 23, 2, "R0")
        else:
            me.place("3004", WHITE, kx, 23, 2, "R0")

    for kx in [14, 18, 22]:
        me.place("3005", BLACK, kx, 21, 2, "R0")

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
    # STAGE 7: Main Residence Second Floor Platform & Balcony (py=5, h=1)
    # =========================================================================
    for mz in [21, 25, 29, 33]:
        for kx in [4, 8, 12, 16, 20, 24, 28]:
            me.place("3020", WHITE, kx, mz, 5, "R0")

    # Cantilevered Upper Terrace Balcony Overhang (at z=19..20, x=6..30)
    for kx in range(6, 30, 4):
        me.place("3020", WHITE, kx, 19, 5, "R0")

    # Balcony Glass Railing (py=6, h=1)
    for kx in range(6, 30, 2):
        me.place("2412b", BLACK, kx, 19, 6, "R0")
    me.place("3070b", BLACK, 6, 20, 6, "R0")
    me.place("3070b", BLACK, 29, 20, 6, "R0")

    # =========================================================================
    # STAGE 8: Main Residence Second Floor Residence & Suites (py=6..8, h=3)
    # =========================================================================
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
    # STAGE 9: Roof System, Sky Lounge Terrace & Cupola Tower (py=9..14)
    # =========================================================================
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
        me.place("2412b", BLACK, kx, 21, 10, "R0")
        me.place("2412b", BLACK, kx, 33, 10, "R0")

    # Architectural Observation Cupola / Skylight Tower (x=16..20, z=25..29, py=10..14)
    me.place("3003", WHITE, 16, 25, 10, "R0")
    me.place("3003", WHITE, 18, 25, 10, "R0")
    me.place("3003", WHITE, 16, 27, 10, "R0")
    me.place("3003", WHITE, 18, 27, 10, "R0")

    # Cupola Slate Pyramidal Roof Cap (py=13..14)
    me.place("3022", DARK_BLUISH_GRAY, 16, 25, 13, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 18, 25, 13, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 16, 27, 13, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 18, 27, 13, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 17, 26, 14, "R0")

    # =========================================================================
    # STAGE 10: Detached Guest House / Cabana with Solar Roof (py=2..9)
    # =========================================================================
    me.place("3004", WHITE, 36, 21, 2, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 38, 21, 2, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 40, 21, 2, "R0")
    me.place("3004", WHITE, 42, 21, 2, "R0")
    me.place("3003", WHITE, 44, 21, 2, "R0")

    for mz in [23, 27, 31]:
        me.place("3004", WHITE, 36, mz, 2, "R90")
        me.place("3004", WHITE, 45, mz, 2, "R90")

    me.place("3001", WHITE, 37, 32, 2, "R0")
    me.place("3001", WHITE, 41, 32, 2, "R0")

    me.place("3001", DARK_TAN, 38, 27, 2, "R0")
    me.place("3003", DARK_TAN, 42, 27, 2, "R0")

    for mz in [21, 25, 29]:
        me.place("3020", DARK_BLUISH_GRAY, 36, mz, 5, "R0")
        me.place("3020", DARK_BLUISH_GRAY, 40, mz, 5, "R0")
        me.place("3022", DARK_BLUISH_GRAY, 44, mz, 5, "R0")

    for mz in [21, 25, 29]:
        me.place("3020", DARK_BLUISH_GRAY, 36, mz, 6, "R0")
        me.place("3022", DARK_BLUISH_GRAY, 44, mz, 6, "R0")

    for mz in [22, 24, 26, 28]:
        me.place("2412b", BLACK, 40, mz, 6, "R0")
        me.place("2412b", BLACK, 42, mz, 6, "R0")

    me.place("3003", WHITE, 44, 31, 6, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 44, 31, 9, "R0")

    # =========================================================================
    # STAGE 11: Cobblestone Paving, Walkways & Garden Details (py=2)
    # =========================================================================
    plate_studs_y1 = set()
    for (px, pz, py) in me.occupied:
        if py == 1:
            # Only consider subfloor plates (not the border tiles which have no studs!)
            if 1 <= px <= 46 and 1 <= pz <= 34:
                plate_studs_y1.add((px, pz))

    # Place 2x1 tiles horizontally (R0)
    for z in range(1, 35):
        for x in range(1, 46):
            if (x, z) in plate_studs_y1 and (x+1, z) in plate_studs_y1:
                if me.can_place("3069b", x, z, 2, "R0"):
                    if 1 <= z <= 11 and 18 <= x <= 36:
                        color = TAN # Teak sun deck
                    elif 12 <= z <= 20:
                        # Lawn with travertine stepping stone paths at x=16 and x=26
                        if x in [16, 26]:
                            color = LIGHT_BLUISH_GRAY
                        else:
                            color = DARK_GREEN
                    elif z <= 11 and x <= 18:
                        color = LIGHT_BLUISH_GRAY # Pool surround travertine
                    else:
                        color = LIGHT_BLUISH_GRAY if (x + z) % 3 == 0 else DARK_BLUISH_GRAY
                    me.place("3069b", color, x, z, 2, "R0")

    # Place 1x2 tiles vertically (R90)
    for z in range(1, 34):
        for x in range(1, 47):
            if (x, z) in plate_studs_y1 and (x, z+1) in plate_studs_y1:
                if me.can_place("3069b", x, z, 2, "R90"):
                    if 1 <= z <= 11 and 18 <= x <= 36:
                        color = TAN
                    elif 12 <= z <= 20:
                        if x in [16, 26]:
                            color = LIGHT_BLUISH_GRAY
                        else:
                            color = DARK_GREEN
                    elif z <= 11 and x <= 18:
                        color = LIGHT_BLUISH_GRAY
                    else:
                        color = LIGHT_BLUISH_GRAY if (x + z) % 3 == 0 else DARK_BLUISH_GRAY
                    me.place("3069b", color, x, z, 2, "R90")

    # Fill remaining single studs with 1x1 tiles (3070b)
    for z in range(1, 35):
        for x in range(1, 47):
            if (x, z) in plate_studs_y1:
                if me.can_place("3070b", x, z, 2, "R0"):
                    if 1 <= z <= 11 and 18 <= x <= 36:
                        color = TAN
                    elif 12 <= z <= 20:
                        if x in [16, 26]:
                            color = LIGHT_BLUISH_GRAY
                        else:
                            color = DARK_GREEN
                    elif z <= 11 and x <= 18:
                        color = LIGHT_BLUISH_GRAY
                    else:
                        color = LIGHT_BLUISH_GRAY if (x + z) % 2 == 0 else DARK_BLUISH_GRAY
                    me.place("3070b", color, x, z, 2, "R0")

    return me

if __name__ == "__main__":
    me = build_bel_air_full()
    piece_count = me.count()
    print(f"\n{'━'*64}")
    print(f"  {me.name.upper()}")
    print(f"  TOTAL PIECE COUNT: {piece_count}")
    print(f"{'━'*64}")

    p = Path("test_bel_air_v2.ldr")
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
