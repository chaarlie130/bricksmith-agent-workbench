import sys
from pathlib import Path
sys.path.insert(0, ".")

from scripts.test_bel_air_v2 import (
    BelAirEngineV2, BLACK, WHITE, TRANS_LIGHT_BLUE, REDDISH_BROWN,
    LIGHT_BLUISH_GRAY, DARK_BLUISH_GRAY, DARK_GREEN, PEARL_GOLD,
    MEDIUM_AZURE, TAN, DARK_TAN
)
from bricksmith.workbench.feedback import check_model

def get_stages():
    stages = []

    # 1. Foundation
    def s1(me):
        for mz in [0, 4, 8, 12, 16, 20, 24, 28, 32]:
            for kx in [0, 8, 16, 24, 32, 40]:
                me.place("3035", DARK_BLUISH_GRAY, kx, mz, 0, "R0")
    stages.append(("Stage 1 (Plinth Foundation)", s1))

    # 2. Subfloor & borders
    def s2(me):
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
    stages.append(("Stage 2 (Subfloor & Borders)", s2))

    # 3. Infinity Pool
    def s3(me):
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
    stages.append(("Stage 3 (Infinity Pool & Spa)", s3))

    # 4. Teak Deck Furniture
    def s4(me):
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
    stages.append(("Stage 4 (Teak Deck Furniture)", s4))

    # 5. Olive Trees
    def s5(me):
        for (tx, tz) in [(10, 15), (22, 15), (34, 15)]:
            me.place("3022", DARK_TAN, tx, tz, 2, "R0")
            me.place("3941", REDDISH_BROWN, tx, tz, 3, "R0")
            me.place("3942c", DARK_GREEN, tx, tz, 6, "R0")
            me.place("3022", DARK_GREEN, tx, tz, 12, "R0")
            me.place("59900", DARK_GREEN, tx, tz, 13, "R0")
    stages.append(("Stage 5 (Olive Trees)", s5))

    # 6. Main Residence Ground Floor
    def s6(me):
        me.place("3001", WHITE, 4, 21, 2, "R0")
        me.place("3004", TRANS_LIGHT_BLUE, 8, 21, 2, "R0")
        me.place("3004", WHITE, 10, 21, 2, "R0")

        # Recessed glass wall behind loggia columns:
        for kx in range(12, 26, 2):
            if kx in [14, 18, 22]:
                me.place("3004", TRANS_LIGHT_BLUE, kx, 23, 2, "R0")
            else:
                me.place("3004", WHITE, kx, 23, 2, "R0")

        # Loggia front pillars
        for kx in [14, 18, 22]:
            me.place("3005", BLACK, kx, 21, 2, "R0")

        me.place("3004", WHITE, 26, 21, 2, "R0")
        me.place("3004", TRANS_LIGHT_BLUE, 28, 21, 2, "R0")
        me.place("3003", WHITE, 30, 21, 2, "R0")

        me.place("3001", WHITE, 4, 23, 2, "R90")
        me.place("3001", WHITE, 4, 27, 2, "R90")
        me.place("3003", WHITE, 4, 31, 2, "R0")

        me.place("3001", WHITE, 31, 23, 2, "R90")
        me.place("3001", WHITE, 31, 27, 2, "R90")
        me.place("3003", WHITE, 31, 31, 2, "R0")

        for kx in [4, 8, 12, 16, 20, 24, 28]:
            me.place("3001", WHITE, kx, 33, 2, "R0")

        for kx in [12, 20, 28]:
            me.place("3001", DARK_TAN, kx, 25, 2, "R90")
            me.place("3001", DARK_TAN, kx, 29, 2, "R90")
    stages.append(("Stage 6 (Ground Floor Walls)", s6))

    # 7. Main Residence Second Floor Platform & Balcony (py=5, h=1)
    def s7(me):
        # West and east wings front wall plates
        me.place("3020", WHITE, 4, 21, 5, "R0")
        me.place("3020", WHITE, 8, 21, 5, "R0")
        me.place("3020", WHITE, 26, 21, 5, "R0")
        me.place("3022", WHITE, 30, 21, 5, "R0")

        # Loggia ceiling beams spanning from front pillars (z=21) back to rear loggia wall (z=23..24)
        for kx in [14, 18, 22]:
            me.place("3020", WHITE, kx, 21, 5, "R90")

        # Tie along rear facade (mz=33)
        for kx in [4, 8, 12, 16, 20, 24, 28]:
            me.place("3020", WHITE, kx, 33, 5, "R0")

        # Tie along west wall (kx=4, mz=23..30)
        me.place("3020", WHITE, 4, 23, 5, "R90")
        me.place("3020", WHITE, 4, 27, 5, "R90")
        me.place("3022", WHITE, 4, 31, 5, "R0")

        # Tie along east wall (kx=31, mz=23..30)
        me.place("3020", WHITE, 31, 23, 5, "R90")
        me.place("3020", WHITE, 31, 27, 5, "R90")
        me.place("3022", WHITE, 31, 31, 5, "R0")

        # Tie along interior bearing walls (kx=12, 20, 28)
        for kx in [12, 20, 28]:
            me.place("3020", WHITE, kx, 25, 5, "R90")
            me.place("3020", WHITE, kx, 29, 5, "R90")
    stages.append(("Stage 7 (Second Floor Platform)", s7))

    return stages

stages = get_stages()
me = BelAirEngineV2()
for i, (name, fn) in enumerate(stages, 1):
    fn(me)
    if i < 2:
        continue
    p = Path(f"test_v2_stg{i}.ldr")
    p.write_text("\n".join(me.lines) + "\n")
    res = check_model(p)
    status = "✓ PASS" if res.get("passed") else "✗ FAIL"
    print(f"{status} | {name} (count: {me.count()})")
    if not res.get("passed"):
        for k, v in res.get("checks", {}).items():
            if not v:
                print(f"   Fail: {k}")
        if "errors" in res:
            import pprint
            pprint.pprint(res["errors"])
        break
