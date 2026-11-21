from pathlib import Path

script = Path("scripts/test_bel_air_v3.py").read_text()

old_stage10 = """    # =========================================================================
    # STAGE 10: Detached Guest House / Cabana with Solar Roof (py=2..9)
    # =========================================================================
    me.place("3004", WHITE, 36, 21, 2, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 38, 21, 2, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 40, 21, 2, "R0")
    me.place("3004", WHITE, 42, 21, 2, "R0")
    me.place("3003", WHITE, 44, 21, 2, "R0")

    me.place("3001", WHITE, 36, 23, 2, "R90")
    me.place("3001", WHITE, 36, 27, 2, "R90")
    me.place("3004", WHITE, 36, 31, 2, "R90")

    me.place("3001", WHITE, 44, 23, 2, "R90")
    me.place("3001", WHITE, 44, 27, 2, "R90")
    me.place("3004", WHITE, 44, 31, 2, "R90")

    me.place("3001", WHITE, 37, 32, 2, "R0")
    me.place("3001", WHITE, 41, 32, 2, "R0")

    # Cabana roof platform (py=5, h=1: spanning between east and west walls)
    me.place("3020", DARK_BLUISH_GRAY, 36, 21, 5, "R0")
    me.place("3020", DARK_BLUISH_GRAY, 40, 21, 5, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 44, 21, 5, "R0")

    for mz in [23, 25, 27, 29]:
        me.place("3034", DARK_BLUISH_GRAY, 37, mz, 5, "R0")
        me.place("3023", DARK_BLUISH_GRAY, 36, mz, 5, "R90")
        me.place("3023", DARK_BLUISH_GRAY, 45, mz, 5, "R90")

    me.place("3020", DARK_BLUISH_GRAY, 37, 31, 5, "R0")
    me.place("3020", DARK_BLUISH_GRAY, 41, 31, 5, "R0")

    # Photovoltaic Solar Panels on Cabana Roof (py=6, 2412b grille tiles)
    for mz in [22, 24, 26, 28]:
        me.place("2412b", BLACK, 38, mz, 6, "R0")
        me.place("2412b", BLACK, 42, mz, 6, "R0")

    # Modern Masonry Chimney Stack (py=6..9)
    me.place("3003", WHITE, 44, 30, 6, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 44, 30, 9, "R0")"""

new_stage10 = """    # =========================================================================
    # STAGE 10: Detached Guest House / Cabana with Solar Roof (py=2..9)
    # Footprint: x=36..45, z=21..32
    # =========================================================================
    # Front facade
    me.place("3004", WHITE, 36, 21, 2, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 38, 21, 2, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 40, 21, 2, "R0")
    me.place("3004", WHITE, 42, 21, 2, "R0")
    me.place("3003", WHITE, 44, 21, 2, "R0")

    # West wall (x=36..37, z=23..30)
    me.place("3001", WHITE, 36, 23, 2, "R90")
    me.place("3001", WHITE, 36, 27, 2, "R90")

    # East wall (x=44..45, z=23..30)
    me.place("3001", WHITE, 44, 23, 2, "R90")
    me.place("3001", WHITE, 44, 27, 2, "R90")

    # Rear wall (mz=31, x=36..45)
    me.place("3003", WHITE, 36, 31, 2, "R0")
    me.place("3001", WHITE, 38, 31, 2, "R0")
    me.place("3003", WHITE, 42, 31, 2, "R0")
    me.place("3004", WHITE, 44, 31, 2, "R0")

    # Cabana roof platform (py=5, h=1)
    me.place("3020", DARK_BLUISH_GRAY, 36, 21, 5, "R0")
    me.place("3020", DARK_BLUISH_GRAY, 40, 21, 5, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 44, 21, 5, "R0")

    # Transverse roof plates spanning west to east walls (kx=37..44)
    for mz in [23, 25, 27, 29]:
        me.place("3034", DARK_BLUISH_GRAY, 37, mz, 5, "R0")
        me.place("3023", DARK_BLUISH_GRAY, 36, mz, 5, "R90")
        me.place("3023", DARK_BLUISH_GRAY, 45, mz, 5, "R90")

    me.place("3020", DARK_BLUISH_GRAY, 36, 31, 5, "R0")
    me.place("3020", DARK_BLUISH_GRAY, 40, 31, 5, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 44, 31, 5, "R0")

    # Photovoltaic Solar Panels on Cabana Roof (py=6, 2412b grille tiles)
    for mz in [23, 25, 27, 29]:
        me.place("2412b", BLACK, 38, mz, 6, "R0")
        me.place("2412b", BLACK, 41, mz, 6, "R0")

    # Modern Masonry Chimney Stack (py=6..9)
    me.place("3004", WHITE, 44, 31, 6, "R0")
    me.place("3023", DARK_BLUISH_GRAY, 44, 31, 9, "R0")"""

script = script.replace(old_stage10, new_stage10)
Path("scripts/test_bel_air_v3.py").write_text(script)
print("Updated Stage 10 successfully.")
