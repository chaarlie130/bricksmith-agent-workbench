#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bricksmith.workbench.feedback import check_model

from scripts.test_mansion_with_partitions import (
    MansionEngine, BLACK, WHITE, TAN, DARK_TAN, TRANS_LIGHT_BLUE,
    REDDISH_BROWN, LIGHT_BLUISH_GRAY, DARK_BLUISH_GRAY, DARK_GREEN, PEARL_GOLD
)

def get_stage_builders():
    stages = []

    # S1
    def s1(me):
        for mz in [0, 4, 8, 12, 16, 20, 24, 28, 32, 36]:
            for kx in [0, 8, 16, 24]:
                me.place("3035", DARK_BLUISH_GRAY, kx, mz, 0, "R0")
    stages.append(("Stage 1 (Plinth Foundation)", s1))

    # S2
    def s2(me):
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
    stages.append(("Stage 2 (Subfloor & Borders)", s2))

    # S3
    def s3(me):
        me.place("3001", DARK_BLUISH_GRAY, 6, 9, 2, "R0")
        me.place("3004", DARK_BLUISH_GRAY, 10, 9, 2, "R90")
        me.place("3004", TRANS_LIGHT_BLUE, 11, 9, 2, "R90")
        me.place("3004", DARK_BLUISH_GRAY, 12, 9, 2, "R90")
        me.place("3003", DARK_BLUISH_GRAY, 13, 9, 2, "R0")
        me.place("3003", DARK_BLUISH_GRAY, 15, 9, 2, "R0")
        me.place("3003", DARK_BLUISH_GRAY, 17, 9, 2, "R0")
        me.place("3004", DARK_BLUISH_GRAY, 19, 9, 2, "R90")
        me.place("3004", TRANS_LIGHT_BLUE, 20, 9, 2, "R90")
        me.place("3004", DARK_BLUISH_GRAY, 21, 9, 2, "R90")
        me.place("3001", DARK_BLUISH_GRAY, 22, 9, 2, "R0")

        for mz in [11, 15, 19, 23]:
            me.place("3001", DARK_BLUISH_GRAY, 6, mz, 2, "R90")
            me.place("3001", DARK_BLUISH_GRAY, 24, mz, 2, "R90")

        me.place("3001", DARK_BLUISH_GRAY, 8, 25, 2, "R0")
        me.place("3004", TRANS_LIGHT_BLUE, 12, 25, 2, "R90")
        me.place("3003", DARK_BLUISH_GRAY, 13, 25, 2, "R0")
        me.place("3004", TRANS_LIGHT_BLUE, 15, 25, 2, "R0")
        me.place("3003", DARK_BLUISH_GRAY, 17, 25, 2, "R0")
        me.place("3004", TRANS_LIGHT_BLUE, 19, 25, 8 if False else 2, "R90")
        me.place("3001", DARK_BLUISH_GRAY, 20, 25, 2, "R0")

        for mz in [13, 17, 21]:
            me.place("3001", DARK_BLUISH_GRAY, 8, mz, 2, "R0")
            me.place("3001", DARK_BLUISH_GRAY, 12, mz, 2, "R0")
            me.place("3001", DARK_BLUISH_GRAY, 16, mz, 2, "R0")
            me.place("3001", DARK_BLUISH_GRAY, 20, mz, 2, "R0")

        # Stoop
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
    stages.append(("Stage 3 (Basement & Stoop)", s3))

    # S4
    def s4(me):
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
    stages.append(("Stage 4 (Piano Nobile)", s4))

    # S5
    def s5(me):
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
    stages.append(("Stage 5 (Floor 2 Master)", s5))

    # S6
    def s6(me):
        for kx in [6, 10, 14, 18, 22]:
            me.place("3020", WHITE, kx, 9, 11, "R0")
        for mz in [11, 15, 19, 23]:
            me.place("3020", LIGHT_BLUISH_GRAY, 6, mz, 11, "R90")
            me.place("3020", LIGHT_BLUISH_GRAY, 24, mz, 11, "R90")
        for kx in [8, 12, 16, 20]:
            me.place("3020", LIGHT_BLUISH_GRAY, kx, 25, 11, "R0")

        for mz in [13, 17, 21]:
            me.place("3795", DARK_TAN, 8, mz, 11, "R0")
            me.place("3795", DARK_TAN, 14, mz, 11, "R0")
            me.place("3020", DARK_TAN, 20, mz, 11, "R0")

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
    stages.append(("Stage 6 (Cornice & Balustrade)", s6))

    # S7
    def s7(me):
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
        me.place("3003", DARK_BLUISH_GRAY, 15, 24, 12, "R0")
        me.place("3003", DARK_BLUISH_GRAY, 17, 24, 12, "R0")
        me.place("3004", TRANS_LIGHT_BLUE, 19, 24, 12, "R90")
        me.place("3001", DARK_BLUISH_GRAY, 20, 24, 12, "R0")

        for mz in [13, 17, 21]:
            me.place("3001", DARK_TAN, 9, mz, 12, "R0")
            me.place("3001", DARK_TAN, 13, mz, 12, "R0")
            me.place("3001", DARK_TAN, 17, mz, 12, "R0")
            me.place("3003", DARK_TAN, 21, mz, 12, "R0")
    stages.append(("Stage 7 (Attic)", s7))

    # S8
    def s8(me):
        for mz in [10, 14, 18, 22]:
            for kx in [8, 10, 12, 14, 16, 18, 20, 22]:
                me.place("3020", DARK_BLUISH_GRAY, kx, mz, 15, "R90")

        me.place("3710", WHITE, 11, 10, 16, "R0")
        me.place("3710", WHITE, 15, 10, 16, "R0")
        me.place("3710", WHITE, 19, 10, 16, "R0")
        me.place("3710", WHITE, 12, 24, 16, "R0")
        me.place("3710", WHITE, 18, 24, 16, "R0")

        for kx in [10, 12, 14, 16, 18, 20]:
            me.place("2412b", BLACK, kx, 11, 16, "R0")
            me.place("2412b", BLACK, kx, 23, 16, "R0")
        for mz in [13, 15, 17, 19, 21]:
            me.place("2412b", BLACK, 8, mz, 16, "R90")
            me.place("2412b", BLACK, 23, mz, 16, "R90")

        me.place("3022", DARK_BLUISH_GRAY, 15, 15, 16, "R0")
        me.place("3941", TRANS_LIGHT_BLUE, 15, 15, 17, "R0")
        me.place("59900", PEARL_GOLD, 15, 15, 20, "R0")

        me.place("3003", REDDISH_BROWN, 14, 17, 16, "R0")
        me.place("3003", REDDISH_BROWN, 16, 17, 16, "R0")
        me.place("3022", DARK_TAN, 14, 17, 19, "R0")
        me.place("3022", DARK_TAN, 16, 17, 19, "R0")
        for kx in [14, 15, 16, 17]:
            me.place("59900", REDDISH_BROWN, kx, 17, 20, "R0")
    stages.append(("Stage 8 (Roof Deck & Cupola)", s8))

    # S9
    def s9(me):
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
    stages.append(("Stage 9 (Streetscape)", s9))

    # S10
    def s10(me):
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
        me.place("3023", DARK_BLUISH_GRAY, 10, 36, 2, "R0")
        me.place("3069b", REDDISH_BROWN, 10, 36, 3, "R0")

        me.place("3022", DARK_BLUISH_GRAY, 6, 30, 2, "R0")
        me.place("3942c", DARK_GREEN, 6, 30, 3, "R0")
        me.place("3022", DARK_BLUISH_GRAY, 24, 30, 2, "R0")
        me.place("3942c", DARK_GREEN, 24, 30, 3, "R0")

        me.place("3022", DARK_BLUISH_GRAY, 6, 36, 2, "R0")
        me.place("3942c", DARK_GREEN, 6, 36, 3, "R0")
        me.place("3022", DARK_BLUISH_GRAY, 24, 36, 2, "R0")
        me.place("3942c", DARK_GREEN, 24, 36, 3, "R0")
    stages.append(("Stage 10 (Garden)", s10))

    # S11
    def s11(me):
        plate_studs_y1 = set()
        for (px, pz, py) in me.occupied:
            if py == 1:
                plate_studs_y1.add((px, pz))

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
    stages.append(("Stage 11 (Paving Tiles)", s11))

    return stages

def diagnose():
    stages = get_stage_builders()
    me = MansionEngine()
    test_ldr = Path("test_diag.ldr")

    for i, (name, fn) in enumerate(stages, 1):
        fn(me)
        test_ldr.write_text("\n".join(me.lines) + "\n")
        res = check_model(test_ldr)
        checks = res.get("checks", {})
        conn = checks.get("actual_connectivity")
        eq = checks.get("approximate_gravity_equilibrium")
        coll = checks.get("mesh_collision_free")
        count = me.count()
        print(f"Stage 1..{i:2d} ({name:30s}): {count:4d} parts | Coll={coll} | Conn={conn} | Eq={eq}")
        if i >= 2 and (not eq or not conn):
            print("  Failure here! Errors:")
            import pprint
            pprint.pprint(res.get("errors", []))
            break

if __name__ == "__main__":
    diagnose()
