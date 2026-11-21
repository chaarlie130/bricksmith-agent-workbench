import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.test_bel_air_v2 import (
    BelAirEngineV2, BLACK, WHITE, TRANS_LIGHT_BLUE, REDDISH_BROWN,
    LIGHT_BLUISH_GRAY, DARK_BLUISH_GRAY, DARK_GREEN, PEARL_GOLD,
    MEDIUM_AZURE, TAN, DARK_TAN
)
from bricksmith.workbench.feedback import check_model

def get_stage_fns():
    fns = []

    def s1(me):
        for mz in [0, 4, 8, 12, 16, 20, 24, 28, 32]:
            for kx in [0, 8, 16, 24, 32, 40]:
                me.place("3035", DARK_BLUISH_GRAY, kx, mz, 0, "R0")
    fns.append(("Stage 1", s1))

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
    fns.append(("Stage 2", s2))

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
    fns.append(("Stage 3", s3))

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
    fns.append(("Stage 4", s4))

    def s5(me):
        for (tx, tz) in [(10, 15), (22, 15), (34, 15)]:
            me.place("3022", DARK_TAN, tx, tz, 2, "R0")
            me.place("3941", REDDISH_BROWN, tx, tz, 3, "R0")
            me.place("3942c", DARK_GREEN, tx, tz, 6, "R0")
            me.place("3022", DARK_GREEN, tx, tz, 12, "R0")
            me.place("59900", DARK_GREEN, tx, tz, 13, "R0")
    fns.append(("Stage 5", s5))

    def s6(me):
        me.place("3001", WHITE, 4, 21, 2, "R0")
        me.place("3004", TRANS_LIGHT_BLUE, 8, 21, 2, "R0")
        me.place("3004", WHITE, 10, 21, 2, "R0")

        for kx in range(12, 26, 2):
            me.place("3004", TRANS_LIGHT_BLUE if kx in [14, 18, 22] else WHITE, kx, 23, 2, "R0")

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
    fns.append(("Stage 6", s6))

    def s7(me):
        me.place("3020", WHITE, 4, 21, 5, "R0")
        me.place("3710", WHITE, 8, 21, 5, "R0")
        me.place("3710", WHITE, 26, 21, 5, "R0")
        me.place("3022", WHITE, 30, 21, 5, "R0")

        me.place("3710", WHITE, 14, 21, 5, "R90")
        me.place("3710", WHITE, 18, 21, 5, "R90")
        me.place("3710", WHITE, 22, 21, 5, "R90")

        me.place("3023", WHITE, 12, 23, 5, "R0")
        me.place("3623", WHITE, 15, 23, 5, "R0")
        me.place("3623", WHITE, 19, 23, 5, "R0")
        me.place("3623", WHITE, 23, 23, 5, "R0")

        me.place("3020", WHITE, 4, 23, 5, "R90")
        me.place("3020", WHITE, 4, 27, 5, "R90")
        me.place("3022", WHITE, 4, 31, 5, "R0")

        me.place("3020", WHITE, 31, 23, 5, "R90")
        me.place("3020", WHITE, 31, 27, 5, "R90")
        me.place("3022", WHITE, 31, 31, 5, "R0")

        for kx in [4, 8, 12, 16, 20, 24, 28]:
            me.place("3020", WHITE, kx, 33, 5, "R0")

        for kx in [12, 20, 28]:
            me.place("3020", WHITE, kx, 25, 5, "R90")
            me.place("3020", WHITE, kx, 29, 5, "R90")
    fns.append(("Stage 7", s7))

    def s8(me):
        me.place("3001", WHITE, 4, 21, 6, "R0")
        me.place("3004", TRANS_LIGHT_BLUE, 8, 21, 6, "R0")
        me.place("3004", WHITE, 10, 21, 6, "R0")

        for kx in range(12, 26, 2):
            me.place("3004", TRANS_LIGHT_BLUE if kx in [14, 18, 22] else WHITE, kx, 23, 6, "R0")

        me.place("2412b", BLACK, 14, 21, 6, "R0")
        me.place("2412b", BLACK, 18, 21, 6, "R0")
        me.place("2412b", BLACK, 22, 21, 6, "R0")

        me.place("3004", WHITE, 26, 21, 6, "R0")
        me.place("3004", TRANS_LIGHT_BLUE, 28, 21, 6, "R0")
        me.place("3003", WHITE, 30, 21, 6, "R0")

        me.place("3001", WHITE, 4, 23, 6, "R90")
        me.place("3001", WHITE, 4, 27, 6, "R90")
        me.place("3003", WHITE, 4, 31, 6, "R0")

        me.place("3001", WHITE, 31, 23, 6, "R90")
        me.place("3001", WHITE, 31, 27, 6, "R90")
        me.place("3003", WHITE, 31, 31, 6, "R0")

        for kx in [4, 8, 12, 16, 20, 24, 28]:
            me.place("3001", WHITE, kx, 33, 6, "R0")

        for kx in [12, 20, 28]:
            me.place("3001", DARK_TAN, kx, 25, 6, "R90")
            me.place("3001", DARK_TAN, kx, 29, 6, "R90")
    fns.append(("Stage 8", s8))

    def s9(me):
        me.place("3020", DARK_BLUISH_GRAY, 4, 21, 9, "R0")
        me.place("3710", DARK_BLUISH_GRAY, 8, 21, 9, "R0")
        me.place("3710", DARK_BLUISH_GRAY, 26, 21, 9, "R0")
        me.place("3022", DARK_BLUISH_GRAY, 30, 21, 9, "R0")

        for kx in [12, 16, 20, 24]:
            me.place("3710", DARK_BLUISH_GRAY, kx, 23, 9, "R0")

        me.place("3020", DARK_BLUISH_GRAY, 4, 23, 9, "R90")
        me.place("3020", DARK_BLUISH_GRAY, 4, 27, 9, "R90")
        me.place("3022", DARK_BLUISH_GRAY, 4, 31, 9, "R0")

        me.place("3020", DARK_BLUISH_GRAY, 31, 23, 9, "R90")
        me.place("3020", DARK_BLUISH_GRAY, 31, 27, 9, "R90")
        me.place("3022", DARK_BLUISH_GRAY, 31, 31, 9, "R0")

        for kx in [4, 8, 12, 16, 20, 24, 28]:
            me.place("3020", DARK_BLUISH_GRAY, kx, 33, 9, "R0")

        for kx in [12, 20, 28]:
            me.place("3020", DARK_BLUISH_GRAY, kx, 25, 9, "R90")
            me.place("3020", DARK_BLUISH_GRAY, kx, 29, 9, "R90")

        for kx in [12, 16, 20, 24]:
            me.place("2412b", BLACK, kx, 23, 10, "R0")

        for kx in [4, 8, 12, 16, 20, 24, 28]:
            me.place("2412b", BLACK, kx, 33, 10, "R0")
            me.place("2412b", BLACK, kx+2, 33, 10, "R0")

        for kx in [12, 20, 28]:
            me.place("3022", DARK_BLUISH_GRAY, kx, 25, 10, "R0")
            me.place("3941", TRANS_LIGHT_BLUE, kx, 25, 11, "R0")
            me.place("59900", PEARL_GOLD, kx, 25, 14, "R0")

            me.place("3022", DARK_BLUISH_GRAY, kx, 29, 10, "R0")
            me.place("3941", TRANS_LIGHT_BLUE, kx, 29, 11, "R0")
            me.place("59900", PEARL_GOLD, kx, 29, 14, "R0")
    fns.append(("Stage 9", s9))

    def s10(me):
        me.place("3004", WHITE, 36, 21, 2, "R0")
        me.place("3004", TRANS_LIGHT_BLUE, 38, 21, 2, "R0")
        me.place("3004", TRANS_LIGHT_BLUE, 40, 21, 2, "R0")
        me.place("3004", WHITE, 42, 21, 2, "R0")
        me.place("3003", WHITE, 44, 21, 2, "R0")

        me.place("3001", WHITE, 36, 23, 2, "R90")
        me.place("3001", WHITE, 36, 27, 2, "R90")
        me.place("3001", WHITE, 44, 23, 2, "R90")
        me.place("3001", WHITE, 44, 27, 2, "R90")

        me.place("3003", WHITE, 36, 31, 2, "R0")
        me.place("3001", WHITE, 38, 31, 2, "R0")
        me.place("3003", WHITE, 42, 31, 2, "R0")
        me.place("3004", WHITE, 44, 31, 2, "R0")

        me.place("3020", DARK_BLUISH_GRAY, 36, 21, 5, "R0")
        me.place("3020", DARK_BLUISH_GRAY, 40, 21, 5, "R0")
        me.place("3022", DARK_BLUISH_GRAY, 44, 21, 5, "R0")

        for mz in [23, 25, 27, 29]:
            me.place("3034", DARK_BLUISH_GRAY, 37, mz, 5, "R0")
            me.place("3023", DARK_BLUISH_GRAY, 36, mz, 5, "R90")
            me.place("3023", DARK_BLUISH_GRAY, 45, mz, 5, "R90")

        me.place("3020", DARK_BLUISH_GRAY, 36, 31, 5, "R0")
        me.place("3020", DARK_BLUISH_GRAY, 40, 31, 5, "R0")
        me.place("3022", DARK_BLUISH_GRAY, 44, 31, 5, "R0")

        for mz in [23, 25, 27, 29]:
            me.place("2412b", BLACK, 38, mz, 6, "R0")
            me.place("2412b", BLACK, 41, mz, 6, "R0")

        me.place("3004", WHITE, 44, 31, 6, "R0")
        me.place("3023", DARK_BLUISH_GRAY, 44, 31, 9, "R0")
    fns.append(("Stage 10", s10))

    return fns

stage_fns = get_stage_fns()
me = BelAirEngineV2()
for i, (name, fn) in enumerate(stage_fns, 1):
    fn(me)
    if i < 2:
        continue
    p = Path("test_step.ldr")
    p.write_text("\n".join(me.lines) + "\n")
    res = check_model(p)
    eq = res.get("checks", {}).get("approximate_gravity_equilibrium")
    conn = res.get("checks", {}).get("actual_connectivity")
    print(f"{name} (parts: {me.count()}): eq={eq}, conn={conn}")
    if not eq:
        break
