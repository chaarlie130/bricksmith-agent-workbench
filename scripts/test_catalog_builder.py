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
                        raise ValueError(f"COLLISION: {part} at stud ({x}, {z}), plate {y}. Already occupied!")
                    self.occupied.add((x, z, y))

        xc = self.x_origin + (kx + w / 2.0) * 20.0
        zc = self.z_origin + (mz + d / 2.0) * 20.0
        ytop = 0.0 if py == 0 else -(py + h - 1) * 8.0
        if comment:
            self.lines.append(f"0 // {comment}")
        self.lines.append(f"1 {color} {xc:.1f} {ytop:.1f} {zc:.1f} {rot_mat} {part}.dat")

    def count(self) -> int:
        return sum(1 for l in self.lines if l.startswith("1 "))

ce = CathedralEngine()

# Stage 1: Plinth (32 plates 4x10 at py=0)
for kx in range(0, 32, 4):
    for mz in range(0, 40, 10):
        ce.place("3030", BLACK, kx, mz, 0, rot="R90")

# Stage 2: Display borders & floors (py=1)
# South border
ce.place("3070b", BLACK, 0, 0, 1, "R0")
for kx in [1, 7, 13, 19, 25]:
    ce.place("6636", BLACK, kx, 0, 1, "R0")
ce.place("3070b", BLACK, 31, 0, 1, "R0")

# North border
ce.place("3070b", BLACK, 0, 39, 1, "R0")
ce.place("6636", BLACK, 1, 39, 1, "R0")
for kx in [7, 15, 23]:
    ce.place("4162", BLACK, kx, 39, 1, "R0")
ce.place("3070b", BLACK, 31, 39, 1, "R0")

# West border
for mz in [1, 7, 13, 19, 25]:
    ce.place("6636", BLACK, 0, mz, 1, "R90")
ce.place("4162", BLACK, 0, 31, 1, "R90")

# East border
for mz in [1, 7, 13, 19, 25]:
    ce.place("6636", BLACK, 31, mz, 1, "R90")
ce.place("4162", BLACK, 31, 31, 1, "R90")

# Interior floors
for mz in range(1, 39, 2):
    for kx in range(1, 29, 4):
        if 11 <= kx <= 20 and 7 <= mz <= 35:
            color = DARK_TAN
        elif kx >= 23 and 11 <= mz <= 23:
            color = DARK_GREEN
        elif kx <= 8 and 11 <= mz <= 23:
            color = DARK_BLUISH_GRAY
        else:
            color = LIGHT_BLUISH_GRAY
        ce.place("3020", color, kx, mz, 1, "R0")
    ce.place("3022", LIGHT_BLUISH_GRAY, 29, mz, 1, "R0")

# Stage 3: Lower walls (py=2)
# NW Tower (kx=9..13, mz=7..11)
ce.place("3001", TAN, 9, 7, 2, "R0")
ce.place("3001", TAN, 9, 9, 2, "R0")

# SW Tower (kx=19..23, mz=7..11)
ce.place("3001", TAN, 19, 7, 2, "R0")
ce.place("3001", TAN, 19, 9, 2, "R0")

# Facade Jambs
ce.place("3003", TAN, 13, 7, 2, "R0")
ce.place("3003", TAN, 17, 7, 2, "R0")

# Nave arcade piers (kx=13 and kx=17, mz=11, 15, 19, 23)
for mz in [11, 15, 19, 23]:
    ce.place("3003", LIGHT_BLUISH_GRAY, 13, mz, 2, "R0")
    ce.place("3003", LIGHT_BLUISH_GRAY, 17, mz, 2, "R0")

# North aisle wall & buttresses
for mz in [11, 15, 19]:
    ce.place("3001", TAN, 9, mz, 2, "R90")
    ce.place("3003", DARK_TAN, 7, mz + 1, 2, "R0")
ce.place("3003", TAN, 9, 23, 2, "R0")

# South aisle wall & buttresses
for mz in [11, 15, 19]:
    ce.place("3001", TAN, 21, mz, 2, "R90")
    ce.place("3003", DARK_TAN, 23, mz + 1, 2, "R0")
ce.place("3003", TAN, 21, 23, 2, "R0")

# Transept wings (mz=25..31)
# North transept
ce.place("3001", TAN, 5, 25, 2, "R0")
ce.place("3001", TAN, 5, 29, 2, "R0")
ce.place("3003", TAN, 5, 27, 2, "R0")
ce.place("3001", TAN, 9, 25, 2, "R0")
ce.place("3001", TAN, 9, 29, 2, "R0")

# South transept
ce.place("3001", TAN, 23, 25, 2, "R0")
ce.place("3001", TAN, 23, 29, 2, "R0")
ce.place("3003", TAN, 25, 27, 2, "R0")
ce.place("3001", TAN, 19, 25, 2, "R0")
ce.place("3001", TAN, 19, 29, 2, "R0")

# Crossing piers
for kx in [13, 17]:
    for mz in [25, 29]:
        ce.place("3003", TAN, kx, mz, 2, "R0")

# Choir & Apse
ce.place("3001", TAN, 13, 31, 2, "R90")
ce.place("3001", TAN, 17, 31, 2, "R90")
ce.place("3001", TAN, 14, 35, 2, "R0")
ce.place("3004", DARK_TAN, 13, 35, 2, "R90")  # 1x2 brick at R90: w=1, d=2
ce.place("3004", DARK_TAN, 18, 35, 2, "R90")  # 1x2 brick at R90: w=1, d=2

# Cloister East & South walls
for mz in [13, 17, 21]:
    ce.place("3001", TAN, 27, mz, 2, "R90")
ce.place("3001", TAN, 23, 23, 2, "R0")

# Cloister columns & fountain
ce.place("3062b", WHITE, 25, 14, 2, "R0")
ce.place("3062b", WHITE, 25, 22, 2, "R0")
ce.place("3062b", WHITE, 26, 14, 2, "R0")
ce.place("3022", LIGHT_BLUISH_GRAY, 25, 17, 2, "R0")
ce.place("3062b", TRANS_LIGHT_BLUE, 25, 17, 3, "R0")

print(f"Total parts placed: {ce.count()}")
p = Path("test_catalog_run.ldr")
p.write_text("\n".join(ce.lines) + "\n")
res = check_model(p)
print("Checks:", res.get("checks"))
print("Passed:", res.get("passed"))
if not res.get("passed"):
    for err in res.get("errors", []):
        print("ERR:", err.get("kind"), err.get("count", ""))
if not res.get("passed"):
    for err in res.get("errors", []):
        if err.get("kind") == "gravity_equilibrium_infeasible":
            print("EQ details:", err.get("details"))
        if "component_members" in err:
            for c in err["component_members"]:
                print("Disconnected comp:", [ce.lines[idx+4].strip() for idx in c if idx+4 < len(ce.lines)])
else:
    p.unlink()


# =============================================================================
# STAGE 4: Window Gallery & Triforium (Course 2: py=5, h=3)
# =============================================================================
# NW Tower
ce.place("3001", TAN, 9, 7, 5, "R0")
ce.place("3001", TAN, 9, 9, 5, "R0")

# SW Tower
ce.place("3001", TAN, 19, 7, 5, "R0")
ce.place("3001", TAN, 19, 9, 5, "R0")

# Facade Portal Lintel (spans across open portal from kx=13 to 19):
ce.place("3009", TAN, 13, 7, 5, "R0")

# Nave arcade piers (py=5)
for mz in [11, 15, 19, 23]:
    ce.place("3003", LIGHT_BLUISH_GRAY, 13, mz, 5, "R0")
    ce.place("3003", LIGHT_BLUISH_GRAY, 17, mz, 5, "R0")

# North aisle wall & lancets
for mz in [11, 15, 19]:
    ce.place("3004", TAN, 9, mz, 5, "R90")
    ce.place("3004", TRANS_LIGHT_BLUE, 9, mz + 2, 5, "R90")
    ce.place("3003", DARK_TAN, 7, mz + 1, 5, "R0")
ce.place("3003", TAN, 9, 23, 5, "R0")

# South aisle wall & lancets
for mz in [11, 15, 19]:
    ce.place("3004", TAN, 21, mz, 5, "R90")
    ce.place("3004", TRANS_LIGHT_BLUE, 21, mz + 2, 5, "R90")
    ce.place("3003", DARK_TAN, 23, mz + 1, 5, "R0")
ce.place("3003", TAN, 21, 23, 5, "R0")

# Transepts
ce.place("3001", TAN, 5, 25, 5, "R0")
ce.place("3001", TAN, 5, 29, 5, "R0")
ce.place("3004", TRANS_LIGHT_BLUE, 5, 27, 5, "R90")
ce.place("3001", TAN, 9, 25, 5, "R0")
ce.place("3001", TAN, 9, 29, 5, "R0")

ce.place("3001", TAN, 23, 25, 5, "R0")
ce.place("3001", TAN, 23, 29, 5, "R0")
ce.place("3004", TRANS_LIGHT_BLUE, 25, 27, 5, "R90")
ce.place("3001", TAN, 19, 25, 5, "R0")
ce.place("3001", TAN, 19, 29, 5, "R0")

# Crossing piers
for kx in [13, 17]:
    for mz in [25, 29]:
        ce.place("3003", TAN, kx, mz, 5, "R0")

# Choir & Apse
ce.place("3001", TAN, 13, 31, 5, "R90")
ce.place("3001", TAN, 17, 31, 5, "R90")
ce.place("3004", TRANS_LIGHT_BLUE, 14, 35, 5, "R0")
ce.place("3004", TAN, 16, 35, 5, "R0")
ce.place("3004", DARK_TAN, 13, 35, 5, "R90")
ce.place("3004", DARK_TAN, 18, 35, 5, "R90")

print(f"Stage 1-4 Piece Count: {ce.count()}")
p = Path("test_catalog_run.ldr")
p.write_text("\n".join(ce.lines) + "\n")
res = check_model(p)
print("Checks:", res.get("checks"))
print("Passed:", res.get("passed"))
if not res.get("passed"):
    for err in res.get("errors", []):
        if err.get("kind") == "gravity_equilibrium_infeasible":
            print("EQ details:", err.get("details"))
        if "component_members" in err:
            for c in err["component_members"]:
                print("Disconnected comp:", [ce.lines[idx+4].strip() for idx in c if idx+4 < len(ce.lines)])


# =============================================================================
# STAGE 5: Clerestory & Aisle Vaults (Course 3: py=8, h=3)
# =============================================================================
# NW Tower
ce.place("3001", TAN, 9, 7, 8, "R0")
ce.place("3001", TAN, 9, 9, 8, "R0")

# SW Tower
ce.place("3001", TAN, 19, 7, 8, "R0")
ce.place("3001", TAN, 19, 9, 8, "R0")

# Facade Grand Rose Window (sits on lintel at py=5)
ce.place("3004", TAN, 13, 7, 8, "R0")
ce.place("3005", TRANS_LIGHT_BLUE, 15, 7, 8, "R0")
ce.place("3005", TRANS_LIGHT_BLUE, 16, 7, 8, "R0")
ce.place("3004", TAN, 17, 7, 8, "R0")

# High Nave Clerestory Walls (kx=13 and kx=17, mz=11..25)
# Supported continuously across piers
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

# Transepts (py=8)
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

# Crossing piers (py=8)
for kx in [13, 17]:
    for mz in [25, 29]:
        ce.place("3003", TAN, kx, mz, 8, "R0")

# Choir & Apse (py=8)
ce.place("3001", TAN, 13, 31, 8, "R90")
ce.place("3001", TAN, 17, 31, 8, "R90")
ce.place("3010", TAN, 14, 35, 8, "R0")
ce.place("3004", DARK_TAN, 13, 35, 8, "R90")
ce.place("3004", DARK_TAN, 18, 35, 8, "R90")

print(f"Stage 1-5 Piece Count: {ce.count()}")
p = Path("test_catalog_run.ldr")
p.write_text("\n".join(ce.lines) + "\n")
res = check_model(p)
print("Checks:", res.get("checks"))
print("Passed:", res.get("passed"))
if not res.get("passed"):
    for err in res.get("errors", []):
        if "line_pairs" in err:
            for lp in err["line_pairs"]:
                print(f"COLLISION: {ce.lines[lp[0]-1].strip()} VS {ce.lines[lp[1]-1].strip()}")
if not res.get("passed"):
    for err in res.get("errors", []):
        if err.get("kind") == "gravity_equilibrium_infeasible":
            print("EQ details:", err.get("details"))
        if "component_members" in err:
            for c in err["component_members"]:
                print("Disconnected comp:", [ce.lines[idx+4].strip() for idx in c if idx+4 < len(ce.lines)])
else:
    p.unlink()

