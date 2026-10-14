#!/usr/bin/env python3
"""
Test script to develop The Bel Air Promontory v3 (Proper Architectural Height).
Validates physics, connectivity, equilibrium, and collision at every step.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bricksmith.workbench.feedback import check_model
from scripts.build_bel_air_estate import PARTS_INFO, ROT_MATRICES

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

class BelAirEngineV3:
    def __init__(self, name="The Bel Air Promontory - Grand Architecture", w_studs=48, d_studs=36):
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

def test_tall_mansion():
    me = BelAirEngineV3(w_studs=48, d_studs=36)

    # 1. Foundation Baseplates (py=0)
    for mz in [0, 4, 8, 12, 16, 20, 24, 28, 32]:
        for kx in [0, 8, 16, 24, 32, 40]:
            me.place("3035", DARK_BLUISH_GRAY, kx, mz, 0, "R0")

    # 2. Subfloor Grid & Borders (py=1)
    me.place("3070b", BLACK, 0, 0, 1, "R0")
    for kx in [1, 9, 25, 33]:
        me.place("4162", BLACK, kx, 0, 1, "R0")
    me.place("3710", BLACK, 17, 0, 1, "R0")
    me.place("3023", BLACK, 21, 0, 1, "R0")
    me.place("3024", BLACK, 23, 0, 1, "R0")
    me.place("3024", BLACK, 24, 0, 1, "R0")
    me.place("6636", BLACK, 41, 0, 1, "R0")
    me.place("3070b", BLACK, 47, 0, 1, "R0")

    me.place("3070b", BLACK, 0, 35, 1, "R0")
    for kx in [1, 9, 17, 25, 33]:
        me.place("4162", BLACK, kx, 35, 1, "R0")
    me.place("6636", BLACK, 41, 35, 1, "R0")
    me.place("3070b", BLACK, 47, 35, 1, "R0")

    for mz in [1, 9, 17, 25]:
        me.place("4162", BLACK, 0, mz, 1, "R90")
        me.place("4162", BLACK, 47, mz, 1, "R90")
    me.place("3069b", BLACK, 0, 33, 1, "R90")
    me.place("3069b", BLACK, 47, 33, 1, "R90")

    for mz in range(1, 35, 2):
        for kx in range(1, 45, 4):
            if 1 <= mz <= 11:
                color = MEDIUM_AZURE if 2 <= kx <= 18 else TAN if 18 <= kx <= 36 else DARK_BLUISH_GRAY
            elif 12 <= mz <= 20:
                color = DARK_GREEN
            elif 21 <= mz <= 33:
                color = TAN if 4 <= kx <= 32 else LIGHT_BLUISH_GRAY if 36 <= kx <= 46 else DARK_GREEN
            else:
                color = DARK_BLUISH_GRAY
            me.place("3020", color, kx, mz, 1, "R0")
        me.place("3022", LIGHT_BLUISH_GRAY, 45, mz, 1, "R0")

    me.place("3710", BLACK, 18, 0, 2, "R0")
    me.place("2412b", PEARL_GOLD, 18, 0, 3, "R0")
    me.place("2412b", PEARL_GOLD, 20, 0, 3, "R0")

    # 3. Pool & Spa (py=2..3)
    for kx in [2, 6, 10, 14]:
        me.place("3020", LIGHT_BLUISH_GRAY, kx, 2, 2, "R0")
        me.place("3020", LIGHT_BLUISH_GRAY, kx, 10, 2, "R0")
    me.place("3795", LIGHT_BLUISH_GRAY, 2, 4, 2, "R90")

    for mz in [4, 6, 8]:
        for kx in [4, 6, 8, 10, 12]:
            me.place("3022", MEDIUM_AZURE, kx, mz, 2, "R0")
            me.place("3069b", TRANS_LIGHT_BLUE, kx, mz, 3, "R0")

    for mz in [4, 6, 8]:
        for kx in [14, 16]:
            me.place("3022", DARK_BLUISH_GRAY, kx, mz, 2, "R0")
            me.place("3069b", TRANS_LIGHT_BLUE, kx, mz, 3, "R0")

    # 4. Furniture & Trees
    me.place("3023", WHITE, 24, 5, 2, "R0")
    me.place("3023", WHITE, 26, 5, 2, "R0")
    me.place("3023", WHITE, 28, 5, 2, "R0")
    me.place("3023", WHITE, 24, 7, 2, "R90")
    me.place("3069b", TAN, 24, 5, 3, "R0")
    me.place("3069b", TAN, 26, 5, 3, "R0")
    me.place("3069b", TAN, 28, 5, 3, "R0")
    me.place("3069b", TAN, 24, 7, 3, "R90")

    me.place("3022", DARK_BLUISH_GRAY, 26, 7, 2, "R0")
    me.place("3069b", WHITE, 26, 7, 3, "R0")

    for mz in [4, 6, 8]:
        me.place("3023", WHITE, 20, mz, 2, "R0")
        me.place("3069b", TAN, 20, mz, 3, "R0")

    me.place("3022", REDDISH_BROWN, 33, 6, 2, "R0")
    me.place("3069b", REDDISH_BROWN, 33, 6, 3, "R0")
    me.place("3024", TAN, 32, 6, 2, "R0")
    me.place("3024", TAN, 35, 6, 2, "R0")
    me.place("3024", TAN, 33, 5, 2, "R0")
    me.place("3024", TAN, 33, 8, 2, "R0")

    for (px, pz) in [(18, 3), (30, 3), (36, 3), (36, 10)]:
        me.place("3022", REDDISH_BROWN, px, pz, 2, "R0")
        me.place("3941", REDDISH_BROWN, px, pz, 3, "R0")
        me.place("3942c", DARK_GREEN, px, pz, 6, "R0")

    for step_z in range(3, 11, 2):
        me.place("3023", DARK_BLUISH_GRAY, 43, step_z, 2, "R0")
        me.place("3069b", BLACK, 43, step_z, 3, "R0")

    for (tx, tz) in [(10, 15), (22, 15), (34, 15)]:
        me.place("3022", DARK_TAN, tx, tz, 2, "R0")
        me.place("3941", REDDISH_BROWN, tx, tz, 3, "R0")
        me.place("3942c", DARK_GREEN, tx, tz, 6, "R0")
        me.place("3022", DARK_GREEN, tx, tz, 12, "R0")
        me.place("59900", DARK_GREEN, tx, tz, 13, "R0")

    # 5. Helper function for Ground Floor wall row
    def place_gf_walls(row_py):
        me.place("3001", WHITE, 4, 21, row_py, "R0")
        me.place("3004", TRANS_LIGHT_BLUE, 8, 21, row_py, "R0")
        me.place("3004", WHITE, 10, 21, row_py, "R0")

        for kx in range(12, 26, 2):
            me.place("3004", TRANS_LIGHT_BLUE if kx in [14, 18, 22] else WHITE, kx, 23, row_py, "R0")

        for kx in [14, 18, 22]:
            me.place("3005", BLACK, kx, 21, row_py, "R0")

        me.place("3004", WHITE, 26, 21, row_py, "R0")
        me.place("3004", TRANS_LIGHT_BLUE, 28, 21, row_py, "R0")
        me.place("3003", WHITE, 30, 21, row_py, "R0")

        me.place("3001", WHITE, 4, 23, row_py, "R90")
        me.place("3001", WHITE, 4, 27, row_py, "R90")
        me.place("3003", WHITE, 4, 31, row_py, "R0")

        me.place("3001", WHITE, 31, 23, row_py, "R90")
        me.place("3001", WHITE, 31, 27, row_py, "R90")
        me.place("3003", WHITE, 31, 31, row_py, "R0")

        for kx in [4, 8, 12, 16, 20, 24, 28]:
            me.place("3001", WHITE, kx, 33, row_py, "R0")

        for kx in [12, 20, 28]:
            me.place("3001", DARK_TAN, kx, 25, row_py, "R90")
            me.place("3001", DARK_TAN, kx, 29, row_py, "R90")

    # BUILD 4 ROWS FOR GROUND FLOOR: py=2, py=5, py=8, py=11!
    for r in [2, 5, 8, 11]:
        place_gf_walls(r)

    # 6. Floor 2 Platform & Balcony Beams at py=14 (h=1)
    me.place("3020", WHITE, 4, 21, 14, "R0")
    me.place("3710", WHITE, 8, 21, 14, "R0")
    me.place("3710", WHITE, 26, 21, 14, "R0")
    me.place("3022", WHITE, 30, 21, 14, "R0")

    me.place("3710", WHITE, 14, 21, 14, "R90")
    me.place("3710", WHITE, 18, 21, 14, "R90")
    me.place("3710", WHITE, 22, 21, 14, "R90")

    me.place("3023", WHITE, 12, 23, 14, "R0")
    me.place("3623", WHITE, 15, 23, 14, "R0")
    me.place("3623", WHITE, 19, 23, 14, "R0")
    me.place("3623", WHITE, 23, 23, 14, "R0")

    me.place("3020", WHITE, 4, 23, 14, "R90")
    me.place("3020", WHITE, 4, 27, 14, "R90")
    me.place("3022", WHITE, 4, 31, 14, "R0")

    me.place("3020", WHITE, 31, 23, 14, "R90")
    me.place("3020", WHITE, 31, 27, 14, "R90")
    me.place("3022", WHITE, 31, 31, 14, "R0")

    for kx in [4, 8, 12, 16, 20, 24, 28]:
        me.place("3020", WHITE, kx, 33, 14, "R0")

    for kx in [12, 20, 28]:
        me.place("3020", WHITE, kx, 25, 14, "R90")
        me.place("3020", WHITE, kx, 29, 14, "R90")

    # 7. Helper function for Upper Floor wall row
    def place_uf_walls(row_py, is_top=False):
        me.place("3001", WHITE, 4, 21, row_py, "R0")
        me.place("3004", TRANS_LIGHT_BLUE, 8, 21, row_py, "R0")
        me.place("3004", WHITE, 10, 21, row_py, "R0")

        for kx in range(12, 26, 2):
            me.place("3004", TRANS_LIGHT_BLUE if kx in [14, 18, 22] else WHITE, kx, 23, row_py, "R0")

        for kx in [14, 18, 22]:
            if is_top:
                me.place("3070b", BLACK, kx, 21, row_py, "R0")
            else:
                me.place("3005", BLACK, kx, 21, row_py, "R0")

        me.place("3004", WHITE, 26, 21, row_py, "R0")
        me.place("3004", TRANS_LIGHT_BLUE, 28, 21, row_py, "R0")
        me.place("3003", WHITE, 30, 21, row_py, "R0")

        me.place("3001", WHITE, 4, 23, row_py, "R90")
        me.place("3001", WHITE, 4, 27, row_py, "R90")
        me.place("3003", WHITE, 4, 31, row_py, "R0")

        me.place("3001", WHITE, 31, 23, row_py, "R90")
        me.place("3001", WHITE, 31, 27, row_py, "R90")
        me.place("3003", WHITE, 31, 31, row_py, "R0")

        for kx in [4, 8, 12, 16, 20, 24, 28]:
            me.place("3001", WHITE, kx, 33, row_py, "R0")

        for kx in [12, 20, 28]:
            me.place("3001", DARK_TAN, kx, 25, row_py, "R90")
            me.place("3001", DARK_TAN, kx, 29, row_py, "R90")

    # BUILD 4 ROWS FOR UPPER FLOOR: py=15, py=18, py=21, py=24!
    place_uf_walls(15, is_top=False)
    place_uf_walls(18, is_top=False)
    place_uf_walls(21, is_top=False)
    place_uf_walls(24, is_top=True)

    # 8. Ceiling Slab & Roof Support at py=27 (h=1)
    me.place("3020", DARK_BLUISH_GRAY, 4, 21, 27, "R0")
    me.place("3710", DARK_BLUISH_GRAY, 8, 21, 27, "R0")
    me.place("3710", DARK_BLUISH_GRAY, 26, 21, 27, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 30, 21, 27, "R0")

    me.place("3710", DARK_BLUISH_GRAY, 12, 23, 27, "R0")
    me.place("3710", DARK_BLUISH_GRAY, 16, 23, 27, "R0")
    me.place("3710", DARK_BLUISH_GRAY, 20, 23, 27, "R0")
    me.place("3023", DARK_BLUISH_GRAY, 24, 23, 27, "R0")

    me.place("3020", DARK_BLUISH_GRAY, 4, 23, 27, "R90")
    me.place("3020", DARK_BLUISH_GRAY, 4, 27, 27, "R90")
    me.place("3022", DARK_BLUISH_GRAY, 4, 31, 27, "R0")

    me.place("3020", DARK_BLUISH_GRAY, 31, 23, 27, "R90")
    me.place("3020", DARK_BLUISH_GRAY, 31, 27, 27, "R90")
    me.place("3022", DARK_BLUISH_GRAY, 31, 31, 27, "R0")

    for kx in [4, 8, 12, 16, 20, 24, 28]:
        me.place("3020", DARK_BLUISH_GRAY, kx, 33, 27, "R0")

    for kx in [12, 20, 28]:
        me.place("3020", DARK_BLUISH_GRAY, kx, 25, 27, "R90")
        me.place("3020", DARK_BLUISH_GRAY, kx, 29, 27, "R90")

    # 9. Roof Features & Observation Lanterns at py=28..32
    for kx in [12, 20, 28]:
        me.place("3022", DARK_BLUISH_GRAY, kx, 25, 28, "R0")
        me.place("3941", TRANS_LIGHT_BLUE, kx, 25, 29, "R0")
        me.place("59900", PEARL_GOLD, kx, 25, 32, "R0")

        me.place("3022", DARK_BLUISH_GRAY, kx, 29, 28, "R0")
        me.place("3941", TRANS_LIGHT_BLUE, kx, 29, 29, "R0")
        me.place("59900", PEARL_GOLD, kx, 29, 32, "R0")

    # 10. Cabana - 4 brick rows tall (py=2, 5, 8, 11)
    def place_cabana_walls(row_py):
        me.place("3004", WHITE, 36, 21, row_py, "R0")
        me.place("3004", TRANS_LIGHT_BLUE, 38, 21, row_py, "R0")
        me.place("3004", TRANS_LIGHT_BLUE, 40, 21, row_py, "R0")
        me.place("3004", WHITE, 42, 21, row_py, "R0")
        me.place("3003", WHITE, 44, 21, row_py, "R0")

        me.place("3001", WHITE, 36, 23, row_py, "R90")
        me.place("3001", WHITE, 36, 27, row_py, "R90")
        me.place("3001", WHITE, 44, 23, row_py, "R90")
        me.place("3001", WHITE, 44, 27, row_py, "R90")

        me.place("3003", WHITE, 36, 31, row_py, "R0")
        me.place("3001", WHITE, 38, 31, row_py, "R0")
        me.place("3003", WHITE, 42, 31, row_py, "R0")
        me.place("3004", WHITE, 44, 31, row_py, "R0")

    for r in [2, 5, 8, 11]:
        place_cabana_walls(r)

    # Cabana roof caps & transverse beams at py=14 (h=1)
    me.place("3710", DARK_BLUISH_GRAY, 36, 21, 14, "R0")
    me.place("3710", DARK_BLUISH_GRAY, 40, 21, 14, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 44, 21, 14, "R0")

    me.place("3022", DARK_BLUISH_GRAY, 36, 31, 14, "R0")
    me.place("3020", DARK_BLUISH_GRAY, 38, 31, 14, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 42, 31, 14, "R0")
    me.place("3023", DARK_BLUISH_GRAY, 44, 31, 14, "R0")

    for mz in [23, 25, 27, 29]:
        me.place("3034", DARK_BLUISH_GRAY, 37, mz, 14, "R0")
        me.place("3023", DARK_BLUISH_GRAY, 36, mz, 14, "R90")
        me.place("3023", DARK_BLUISH_GRAY, 45, mz, 14, "R90")

    # Cabana solar panels
    for mz in [23, 25, 27, 29]:
        me.place("2412b", BLACK, 38, mz, 15, "R0")
        me.place("2412b", BLACK, 41, mz, 15, "R0")

    # Chimney stack
    me.place("3004", WHITE, 44, 31, 15, "R0")
    me.place("3023", DARK_BLUISH_GRAY, 44, 31, 18, "R0")

    # 11. Paving
    plate_studs_y1 = set()
    for (px, pz, py) in me.occupied:
        if py == 1 and 1 <= px <= 46 and 1 <= pz <= 34:
            plate_studs_y1.add((px, pz))

    for z in range(1, 35):
        for x in range(1, 46):
            if (x, z) in plate_studs_y1 and (x+1, z) in plate_studs_y1:
                if me.can_place("3069b", x, z, 2, "R0"):
                    if 1 <= z <= 11 and 18 <= x <= 36:
                        color = TAN
                    elif 12 <= z <= 20:
                        color = LIGHT_BLUISH_GRAY if x in [16, 26] else DARK_GREEN
                    elif z <= 11 and x <= 18:
                        color = LIGHT_BLUISH_GRAY
                    else:
                        color = LIGHT_BLUISH_GRAY if (x + z) % 3 == 0 else DARK_BLUISH_GRAY
                    me.place("3069b", color, x, z, 2, "R0")

    for z in range(1, 34):
        for x in range(1, 47):
            if (x, z) in plate_studs_y1 and (x, z+1) in plate_studs_y1:
                if me.can_place("3069b", x, z, 2, "R90"):
                    if 1 <= z <= 11 and 18 <= x <= 36:
                        color = TAN
                    elif 12 <= z <= 20:
                        color = LIGHT_BLUISH_GRAY if x in [16, 26] else DARK_GREEN
                    elif z <= 11 and x <= 18:
                        color = LIGHT_BLUISH_GRAY
                    else:
                        color = LIGHT_BLUISH_GRAY if (x + z) % 3 == 0 else DARK_BLUISH_GRAY
                    me.place("3069b", color, x, z, 2, "R90")

    for z in range(1, 35):
        for x in range(1, 47):
            if (x, z) in plate_studs_y1:
                if me.can_place("3070b", x, z, 2, "R0"):
                    if 1 <= z <= 11 and 18 <= x <= 36:
                        color = TAN
                    elif 12 <= z <= 20:
                        color = LIGHT_BLUISH_GRAY if x in [16, 26] else DARK_GREEN
                    elif z <= 11 and x <= 18:
                        color = LIGHT_BLUISH_GRAY
                    else:
                        color = LIGHT_BLUISH_GRAY if (x + z) % 2 == 0 else DARK_BLUISH_GRAY
                    me.place("3070b", color, x, z, 2, "R0")

    out_path = Path("test_bel_air_tall.ldr")
    out_path.write_text("\n".join(me.lines) + "\n")
    print(f"Model saved to {out_path}, piece count: {me.count()}")
    report = check_model(out_path)
    print("Report passed:", report.get("passed"))
    print("Checks:", report.get("checks"))
    if not report.get("passed"):
        print("Errors:", report.get("errors"))
    return report

if __name__ == "__main__":
    test_tall_mansion()
