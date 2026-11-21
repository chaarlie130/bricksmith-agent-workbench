#!/usr/bin/env python3
"""Build and validate full 1000+ piece cathedral with BrickSmith physics."""
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

# =============================================================================
# STAGE 1: Plinth (32 plates 4x10 at py=0)
# =============================================================================
for kx in range(0, 32, 4):
    for mz in range(0, 40, 10):
        ge.add_box("3030", BLACK, kx, mz, 0, 4, 10, 1, rot=R90)

# =============================================================================
# STAGE 2: Display Borders & Pavement (Layer 1, py=1)
# =============================================================================
# South border (mz=0)
ge.add_box("3070b", BLACK, 0, 0, 1, 1, 1, 1, rot=R0)
for kx in [1, 7, 13, 19, 25]:
    ge.add_box("6636", BLACK, kx, 0, 1, 6, 1, 1, rot=R0)
ge.add_box("3070b", BLACK, 31, 0, 1, 1, 1, 1, rot=R0)

# North border (mz=39)
ge.add_box("3070b", BLACK, 0, 39, 1, 1, 1, 1, rot=R0)
ge.add_box("6636", BLACK, 1, 39, 1, 6, 1, 1, rot=R0)
for kx in [7, 15, 23]:
    ge.add_box("4162", BLACK, kx, 39, 1, 8, 1, 1, rot=R0)
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
for mz in range(1, 39, 2):
    for kx in range(1, 29, 4):
        # Determine floor color based on architectural zone
        if 11 <= kx <= 20 and 7 <= mz <= 35:
            color = DARK_TAN  # Cathedral interior
        elif kx >= 23 and 11 <= mz <= 23:
            color = DARK_GREEN  # Cloister garden lawn
        elif kx <= 8 and 11 <= mz <= 23:
            color = DARK_BLUISH_GRAY  # North town plaza
        else:
            color = LIGHT_BLUISH_GRAY  # Parvis and ambulatory apron
        ge.add_box("3020", color, kx, mz, 1, 4, 2, 1, rot=R0)
    ge.add_box("3022", LIGHT_BLUISH_GRAY, 29, mz, 1, 2, 2, 1, rot=R0)

print(f"Stage 1-2 Piece Count: {ge.count()}")

# =============================================================================
# STAGE 3: Lower Walls, Compound Piers & Buttresses (Course 1: py=2, h=3)
# =============================================================================
# A. Twin West Towers (NW: kx=9..13, mz=7..11; SW: kx=19..23, mz=7..11)
# NW Tower Base (4x4 studs):
ge.add_box("3001", TAN, 9, 7, 2, 4, 2, 3, rot=R0, comment="NW Tower S wall 2x4")
ge.add_box("3001", TAN, 9, 9, 2, 4, 2, 3, rot=R0, comment="NW Tower N wall 2x4")

# SW Tower Base (4x4 studs):
ge.add_box("3001", TAN, 19, 7, 2, 4, 2, 3, rot=R0, comment="SW Tower S wall 2x4")
ge.add_box("3001", TAN, 19, 9, 2, 4, 2, 3, rot=R0, comment="SW Tower N wall 2x4")

# B. Triple Portal Jambs (mz=7, kx=13..19):
ge.add_box("3003", TAN, 13, 7, 2, 2, 2, 3, rot=R0, comment="Left portal pier 2x2")
ge.add_box("3003", TAN, 17, 7, 2, 2, 2, 3, rot=R0, comment="Right portal pier 2x2")

# C. Nave Arcade Piers (flanking nave along kx=13 and kx=17, mz=11..25):
for mz in [11, 15, 19, 23]:
    ge.add_box("3003", LIGHT_BLUISH_GRAY, 13, mz, 2, 2, 2, 3, rot=R0, comment="Nave arcade pier N 2x2")
    ge.add_box("3003", LIGHT_BLUISH_GRAY, 17, mz, 2, 2, 2, 3, rot=R0, comment="Nave arcade pier S 2x2")

# D. North Aisle Wall & Outer Buttresses (kx=9..11, mz=11..25):
for mz in [11, 15, 19]:
    ge.add_box("3001", TAN, 9, mz, 2, 2, 4, 3, rot=R90, comment="North aisle wall 2x4")
    ge.add_box("3003", DARK_TAN, 7, mz + 1, 2, 2, 2, 3, rot=R0, comment="North buttress pier 2x2")
ge.add_box("3001", TAN, 9, 23, 2, 2, 2, 3, rot=R0, comment="North aisle corner 2x2")

# E. South Aisle Wall & Buttresses (kx=21..23, mz=11..25):
for mz in [11, 15, 19]:
    ge.add_box("3001", TAN, 21, mz, 2, 2, 4, 3, rot=R90, comment="South aisle wall 2x4")
    ge.add_box("3003", DARK_TAN, 23, mz + 1, 2, 2, 2, 3, rot=R0, comment="South buttress pier 2x2")
ge.add_box("3001", TAN, 21, 23, 2, 2, 2, 3, rot=R0, comment="South aisle corner 2x2")

# F. Transept Wings (mz=25..31, 6 studs deep):
# North Transept (kx=5..13):
ge.add_box("3001", TAN, 5, 25, 2, 4, 2, 3, rot=R0, comment="North transept W wall 2x4")
ge.add_box("3001", TAN, 5, 29, 2, 4, 2, 3, rot=R0, comment="North transept E wall 2x4")
ge.add_box("3001", TAN, 5, 27, 2, 2, 2, 3, rot=R0, comment="North transept end 2x2")

ge.add_box("3001", TAN, 9, 25, 2, 4, 2, 3, rot=R0, comment="North transept inner W 2x4")
ge.add_box("3001", TAN, 9, 29, 2, 4, 2, 3, rot=R0, comment="North transept inner E 2x4")

# South Transept (kx=19..27):
ge.add_box("3001", TAN, 23, 25, 2, 4, 2, 3, rot=R0, comment="South transept W wall 2x4")
ge.add_box("3001", TAN, 23, 29, 2, 4, 2, 3, rot=R0, comment="South transept E wall 2x4")
ge.add_box("3001", TAN, 25, 27, 2, 2, 2, 3, rot=R0, comment="South transept end 2x2")

ge.add_box("3001", TAN, 19, 25, 2, 4, 2, 3, rot=R0, comment="South transept inner W 2x4")
ge.add_box("3001", TAN, 19, 29, 2, 4, 2, 3, rot=R0, comment="South transept inner E 2x4")

# Crossing Compound Piers (kx=13, 17, mz=25, 29):
for kx in [13, 17]:
    for mz in [25, 29]:
        ge.add_box("3003", TAN, kx, mz, 2, 2, 2, 3, rot=R0, comment="Crossing pier 2x2")

# G. Choir Presbytery & Apse (mz=31..37):
# Choir walls (mz=31..33):
ge.add_box("3001", TAN, 13, 31, 2, 2, 4, 3, rot=R90, comment="Choir N wall 2x4")
ge.add_box("3001", TAN, 17, 31, 2, 2, 4, 3, rot=R90, comment="Choir S wall 2x4")
# Apse walls (mz=35..37):
ge.add_box("3001", TAN, 14, 35, 2, 4, 2, 3, rot=R0, comment="Apse curved wall 2x4")
ge.add_box("3003", DARK_TAN, 13, 35, 2, 1, 2, 3, rot=R0, comment="Apse buttress L")
ge.add_box("3003", DARK_TAN, 18, 35, 2, 1, 2, 3, rot=R0, comment="Apse buttress R")

# H. Cloister Arcade Colonnade (kx=25..29, mz=12..24):
# East cloister wall:
for mz in [13, 17, 21]:
    ge.add_box("3001", TAN, 27, mz, 2, 2, 4, 3, rot=R90, comment="Cloister E wall 2x4")
# South cloister wall:
ge.add_box("3001", TAN, 23, 23, 2, 4, 2, 3, rot=R0, comment="Cloister S wall 2x4")
# Cloister Colonnade Columns (White round bricks 3062b):
for mz in [14, 22]:
    ge.add_box("3062b", WHITE, 25, mz, 2, 1, 1, 3, rot=R0, comment="Cloister column")
ge.add_box("3062b", WHITE, 26, 14, 2, 1, 1, 3, rot=R0, comment="Cloister N column")

# Cloister Center Fountain:
ge.add_box("3022", LIGHT_BLUISH_GRAY, 25, 17, 2, 2, 2, 1, rot=R0, comment="Fountain basin 2x2")
ge.add_box("3062b", TRANS_LIGHT_BLUE, 25, 17, 3, 1, 1, 3, rot=R0, comment="Fountain water jet")

print(f"Stage 1-3 Piece Count: {ge.count()}")

p = Path("test_s1_3.ldr")
p.write_text("\n".join(ge.lines) + "\n")
res = check_model(p)
print("Checks:", res.get("checks"))
print("Passed:", res.get("passed"))
if not res.get("passed"):
    print("Errors:", res.get("errors"))
if not res.get("passed"):
    for err in res.get("errors", []):
        if "line_pairs" in err:
            for lp in err["line_pairs"]:
                print(f"COLLISION: {ge.lines[lp[0]-1].strip()} VS {ge.lines[lp[1]-1].strip()}")
else:
    p.unlink()
