from scripts.design_bel_air_estate import BelAirEngine, PARTS_INFO, ROT_MATRICES, BLACK, WHITE, TRANS_LIGHT_BLUE, REDDISH_BROWN, LIGHT_BLUISH_GRAY, DARK_BLUISH_GRAY, DARK_GREEN, PEARL_GOLD, MEDIUM_AZURE, TAN, DARK_TAN
from pathlib import Path
from bricksmith.workbench.feedback import check_model

def run_test(max_stage=11):
    me = BelAirEngine()
    
    # STAGE 1
    for mz in [0, 4, 8, 12, 16, 20, 24, 28, 32]:
        for kx in [0, 8, 16, 24, 32, 40]:
            me.place("3035", DARK_BLUISH_GRAY, kx, mz, 0, "R0")

    # STAGE 2
    me.place("3070b", BLACK, 0, 0, 1, "R0")
    for kx in [1, 9, 17, 25, 33]:
        me.place("4162", BLACK, kx, 0, 1, "R0")
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
            me.place("3020", DARK_BLUISH_GRAY, kx, mz, 1, "R0")
        me.place("3022", LIGHT_BLUISH_GRAY, 45, mz, 1, "R0")

    # inscription removed

    if max_stage == 2:
        return me

    # STAGE 3: Infinity pool
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

    if max_stage == 3:
        return me

    # STAGE 4: Teak sun deck & outdoor lounge
    for kx in [18, 22, 26, 30, 34]:
        me.place("3031", TAN, kx, 2, 2, "R0")
        me.place("3031", TAN, kx, 6, 2, "R0")
        me.place("3020", TAN, kx, 10, 2, "R0")

    me.place("3023", WHITE, 24, 5, 3, "R0")
    me.place("3023", WHITE, 26, 5, 3, "R0")
    me.place("3023", WHITE, 28, 5, 3, "R0")
    me.place("3023", WHITE, 24, 7, 3, "R90")
    me.place("3069b", TAN, 24, 5, 4, "R0")
    me.place("3069b", TAN, 26, 5, 4, "R0")
    me.place("3069b", TAN, 28, 5, 4, "R0")
    me.place("3069b", TAN, 24, 7, 4, "R90")

    me.place("3022", DARK_BLUISH_GRAY, 26, 7, 3, "R0")
    me.place("3069b", WHITE, 26, 7, 4, "R0")

    for mz in [4, 6, 8]:
        me.place("3023", WHITE, 20, mz, 3, "R0")
        me.place("3069b", TAN, 20, mz, 4, "R0")

    me.place("3022", REDDISH_BROWN, 33, 6, 3, "R0")
    me.place("3069b", REDDISH_BROWN, 33, 6, 4, "R0")
    me.place("3024", TAN, 32, 6, 3, "R0")
    me.place("3024", TAN, 35, 6, 3, "R0")
    me.place("3024", TAN, 33, 5, 3, "R0")
    me.place("3024", TAN, 33, 8, 3, "R0")

    for kx in range(18, 38, 2):
        me.place("2412b", BLACK, kx, 2, 3, "R0")
    for mz in range(3, 12, 2):
        me.place("2412b", BLACK, 37, mz, 3, "R90")

    for (px, pz) in [(18, 3), (30, 3), (36, 3), (36, 11)]:
        me.place("3024", REDDISH_BROWN, px, pz, 3, "R0")
        me.place("3062b", REDDISH_BROWN, px, pz, 4, "R0")
        me.place("59900", DARK_GREEN, px, pz, 7, "R0")

    for step_z in range(3, 11, 2):
        me.place("3023", DARK_BLUISH_GRAY, 43, step_z, 2, "R0")
        me.place("3069b", BLACK, 43, step_z, 3, "R0")

    if max_stage == 4:
        return me

    # STAGE 5: Emerald lawn
    for mz in [12, 14, 16, 18]:
        for kx in range(2, 46, 4):
            me.place("3020", DARK_GREEN, kx, mz, 2, "R0")
    for kx in range(2, 46, 4):
        me.place("3710", DARK_GREEN, kx, 20, 2, "R0")

    for sz in [13, 15, 17, 19]:
        me.place("3069b", LIGHT_BLUISH_GRAY, 16, sz, 3, "R0")
        me.place("3069b", LIGHT_BLUISH_GRAY, 26, sz, 3, "R0")

    for (tx, tz) in [(10, 16), (22, 16), (34, 16)]:
        me.place("3022", DARK_TAN, tx, tz, 3, "R0")
        me.place("3062b", REDDISH_BROWN, tx, tz, 4, "R0")
        me.place("3942c", DARK_GREEN, tx, tz, 7, "R0")
        me.place("59900", DARK_GREEN, tx, tz, 13, "R0")

    if max_stage == 5:
        return me

    # STAGE 6: Ground floor
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

    if max_stage == 6:
        return me

    # STAGE 7: Second floor platform
    for mz in [21, 25, 29, 33]:
        for kx in [4, 8, 12, 16, 20, 24, 28]:
            me.place("3020", WHITE, kx, mz, 5, "R0")

    for kx in range(6, 30, 4):
        me.place("3020", WHITE, kx, 19, 5, "R0")

    for kx in range(6, 30, 2):
        me.place("2412b", BLACK, kx, 19, 6, "R0")
    me.place("3070b", BLACK, 6, 20, 6, "R0")
    me.place("3070b", BLACK, 29, 20, 6, "R0")

    if max_stage == 7:
        return me

    # STAGE 8: Second floor
    me.place("3001", WHITE, 4, 21, 6, "R0")
    for kx in range(8, 28, 2):
        if kx in [10, 14, 18, 22, 26]:
            me.place("3004", TRANS_LIGHT_BLUE, kx, 21, 6, "R0")
        else:
            me.place("3004", WHITE, kx, 21, 6, "R0")
    me.place("3003", WHITE, 28, 21, 6, "R0")
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

    if max_stage == 8:
        return me

    # STAGE 9: Roof
    for mz in [21, 25, 29, 33]:
        for kx in [4, 8, 12, 16, 20, 24, 28]:
            me.place("3020", DARK_BLUISH_GRAY, kx, mz, 9, "R0")

    for mz in [21, 25, 29, 33]:
        me.place("3020", DARK_BLUISH_GRAY, 4, mz, 10, "R0")
        me.place("3020", DARK_BLUISH_GRAY, 8, mz, 10, "R0")

    for mz in [21, 25, 29, 33]:
        me.place("3020", DARK_BLUISH_GRAY, 24, mz, 10, "R0")
        me.place("3020", DARK_BLUISH_GRAY, 28, mz, 10, "R0")

    for kx in range(12, 24, 2):
        me.place("2412b", BLACK, kx, 21, 10, "R0")
        me.place("2412b", BLACK, kx, 33, 10, "R0")

    me.place("3003", WHITE, 16, 25, 10, "R0")
    me.place("3003", WHITE, 18, 25, 10, "R0")
    me.place("3003", WHITE, 16, 27, 10, "R0")
    me.place("3003", WHITE, 18, 27, 10, "R0")

    me.place("3022", DARK_BLUISH_GRAY, 16, 25, 13, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 18, 25, 13, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 16, 27, 13, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 18, 27, 13, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 17, 26, 14, "R0")

    if max_stage == 9:
        return me

    # STAGE 10: Cabana
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

    return me

for stg in range(2, 11):
    me = run_test(stg)
    p = Path(f"test_stg_{stg}.ldr")
    p.write_text("\n".join(me.lines) + "\n")
    res = check_model(p)
    status = "PASS" if res.get("passed") else "FAIL"
    print(f"Stage 1..{stg}: {status} (parts: {me.count()})")
    if not res.get("passed"):
        for k, v in res.get("checks", {}).items():
            if not v:
                print(f"   Fail: {k}")
        break
