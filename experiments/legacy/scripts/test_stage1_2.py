#!/usr/bin/env python3
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
        if kx < 0 or kx + w > self.w_studs or mz < 0 or mz + d > self.d_studs:
            raise ValueError(f"Out of bounds: {part} at kx={kx}..{kx+w}, mz={mz}..{mz+d}")
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

ge = GridEngine()

# Stage 1: Plinth (32 plates 4x10 at py=0)
for kx in range(0, 32, 4):
    for mz in range(0, 40, 10):
        ge.add_box("3030", BLACK, kx, mz, 0, 4, 10, 1, rot=R90, comment="Plinth 4x10")

# Stage 2: Outer black border (mz=0, mz=39, kx=0, kx=31)
# South border (mz=0)
ge.add_box("3070b", BLACK, 0, 0, 1, 1, 1, 1, rot=R0)
ge.add_box("6636", BLACK, 1, 0, 1, 6, 1, 1, rot=R0)
ge.add_box("6636", BLACK, 7, 0, 1, 6, 1, 1, rot=R0)
ge.add_box("6636", BLACK, 13, 0, 1, 6, 1, 1, rot=R0)
ge.add_box("6636", BLACK, 19, 0, 1, 6, 1, 1, rot=R0)
ge.add_box("6636", BLACK, 25, 0, 1, 6, 1, 1, rot=R0)
ge.add_box("3070b", BLACK, 31, 0, 1, 1, 1, 1, rot=R0)

# North border (mz=39)
ge.add_box("3070b", BLACK, 0, 39, 1, 1, 1, 1, rot=R0)
ge.add_box("6636", BLACK, 1, 39, 1, 6, 1, 1, rot=R0)
ge.add_box("4162", BLACK, 7, 39, 1, 8, 1, 1, rot=R0)
ge.add_box("4162", BLACK, 15, 39, 1, 8, 1, 1, rot=R0)
ge.add_box("4162", BLACK, 23, 39, 1, 8, 1, 1, rot=R0)
ge.add_box("3070b", BLACK, 31, 39, 1, 1, 1, 1, rot=R0)

# West border (kx=0, mz=1..38)
for mz in [1, 7, 13, 19, 25]:
    ge.add_box("6636", BLACK, 0, mz, 1, 1, 6, 1, rot=R90)
ge.add_box("4162", BLACK, 0, 31, 1, 1, 8, 1, rot=R90)

# East border (kx=31, mz=1..38)
for mz in [1, 7, 13, 19, 25]:
    ge.add_box("6636", BLACK, 31, mz, 1, 1, 6, 1, rot=R90)
ge.add_box("4162", BLACK, 31, 31, 1, 1, 8, 1, rot=R90)

# Interior floor plates:
# Parvis (mz=1..6, kx=1..30 -> 30x6 studs):
# Tiled with 2x4 plates (3020) and 2x2 plates (3022)
for mz in [1, 3, 5]:
    for kx in range(1, 29, 4):
        ge.add_box("3020", LIGHT_BLUISH_GRAY, kx, mz, 1, 4, 2, 1, rot=R0)
    ge.add_box("3022", LIGHT_BLUISH_GRAY, 29, mz, 1, 2, 2, 1, rot=R0)

# Central Nave, Aisle, Transept & Apse subflooring (mz=7..37, kx=1..30):
# Use 2x4 plates (3020) and 4x4 plates (3031) spanning seams
for mz in range(7, 37, 2):
    for kx in range(1, 29, 4):
        color = DARK_TAN if (11 <= kx <= 20 and 7 <= mz <= 35) else (DARK_GREEN if (kx >= 22 and 10 <= mz <= 22) else LIGHT_BLUISH_GRAY)
        ge.add_box("3020", color, kx, mz, 1, 4, 2, 1, rot=R0)
    ge.add_box("3022", LIGHT_BLUISH_GRAY, 29, mz, 1, 2, 2, 1, rot=R0)

# North Apron (mz=37..38, kx=1..30):
for mz in [37]:
    for kx in range(1, 29, 4):
        ge.add_box("3020", LIGHT_BLUISH_GRAY, kx, mz, 1, 4, 2, 1, rot=R0)
    ge.add_box("3022", LIGHT_BLUISH_GRAY, 29, mz, 1, 2, 2, 1, rot=R0)

print(f"Total parts placed: {ge.count()}")
p = Path("test_s1_2.ldr")
p.write_text("\n".join(ge.lines) + "\n")
res = check_model(p)
print("Checks:", res.get("checks"))
print("Passed:", res.get("passed"))
if not res.get("passed"):
    print("Errors:", res.get("errors"))
p.unlink()
