import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.test_bel_air_v2 import (
    BelAirEngineV2, BLACK, WHITE, TRANS_LIGHT_BLUE, REDDISH_BROWN,
    LIGHT_BLUISH_GRAY, DARK_BLUISH_GRAY, DARK_GREEN, PEARL_GOLD,
    MEDIUM_AZURE, TAN, DARK_TAN
)
from bricksmith.workbench.feedback import check_model

def build_bel_air_v3() -> BelAirEngineV2:
    me = BelAirEngineV2()

    # =========================================================================
    # STAGE 1: Hillside Terraced Foundation Plinth (py=0, h=1)
    # =========================================================================
    for mz in [0, 4, 8, 12, 16, 20, 24, 28, 32]:
        for kx in [0, 8, 16, 24, 32, 40]:
            me.place("3035", DARK_BLUISH_GRAY, kx, mz, 0, "R0")

    # =========================================================================
    # STAGE 2: Subfloor Tying Matrix & Polished Obsidian Borders (py=1, h=1)
    # =========================================================================
    # South border
    me.place("3070b", BLACK, 0, 0, 1, "R0")
    for kx in [1, 9, 25, 33]:
        me.place("4162", BLACK, kx, 0, 1, "R0")
    me.place("3710", BLACK, 17, 0, 1, "R0")
    me.place("3023", BLACK, 21, 0, 1, "R0")
    me.place("3024", BLACK, 23, 0, 1, "R0")
    me.place("3024", BLACK, 24, 0, 1, "R0")
    me.place("6636", BLACK, 41, 0, 1, "R0")
    me.place("3070b", BLACK, 47, 0, 1, "R0")

    # North border
    me.place("3070b", BLACK, 0, 35, 1, "R0")
    for kx in [1, 9, 17, 25, 33]:
        me.place("4162", BLACK, kx, 35, 1, "R0")
    me.place("6636", BLACK, 41, 35, 1, "R0")
    me.place("3070b", BLACK, 47, 35, 1, "R0")

    # West & East outer borders
    for mz in [1, 9, 17, 25]:
        me.place("4162", BLACK, 0, mz, 1, "R90")
        me.place("4162", BLACK, 47, mz, 1, "R90")
    me.place("3069b", BLACK, 0, 33, 1, "R90")
    me.place("3069b", BLACK, 47, 33, 1, "R90")

    # Subfloor plates tying across baseplate seams (py=1)
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

    # Bronze Inscription Plaque
    me.place("3710", BLACK, 18, 0, 2, "R0")
    me.place("2412b", PEARL_GOLD, 18, 0, 3, "R0")
    me.place("2412b", PEARL_GOLD, 20, 0, 3, "R0")

    # =========================================================================
    # STAGE 3: Cantilevered Hillside Infinity Pool & Sunken Jacuzzi Spa (py=2..3)
    # =========================================================================
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

    # =========================================================================
    # STAGE 4: Cantilevered Teak Sun Deck Furniture & Topiary (py=2..6)
    # =========================================================================
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

    # =========================================================================
    # STAGE 5: Mature Olive / Magnolia Trees (py=2..13)
    # =========================================================================
    for (tx, tz) in [(10, 15), (22, 15), (34, 15)]:
        me.place("3022", DARK_TAN, tx, tz, 2, "R0")
        me.place("3941", REDDISH_BROWN, tx, tz, 3, "R0")
        me.place("3942c", DARK_GREEN, tx, tz, 6, "R0")
        me.place("3022", DARK_GREEN, tx, tz, 12, "R0")
        me.place("59900", DARK_GREEN, tx, tz, 13, "R0")

    # =========================================================================
    # STAGE 6: Main Residence Ground Floor Walls & Loggia (py=2..4, h=3)
    # =========================================================================
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

    # =========================================================================
    # STAGE 7: Main Residence Second Floor Platform & Balcony Beams (py=5, h=1)
    # =========================================================================
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

    # =========================================================================
    # STAGE 8: Main Residence Second Floor Suites (py=6..8, h=3)
    # =========================================================================
    me.place("3001", WHITE, 4, 21, 6, "R0")
    me.place("3004", TRANS_LIGHT_BLUE, 8, 21, 6, "R0")
    me.place("3004", WHITE, 10, 21, 6, "R0")

    for kx in range(12, 26, 2):
        me.place("3004", TRANS_LIGHT_BLUE if kx in [14, 18, 22] else WHITE, kx, 23, 6, "R0")

    test_balcony_railings = True
    if test_balcony_railings:
        # Glass balcony railing tiles at the edge of the loggia overhang
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

    # =========================================================================
    # STAGE 9: Roof System, Sky Lounge Terrace & Cupola Tower (py=9..12)
    # =========================================================================
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

    # Rooftop safety balustrade tiles (2412b along the roof perimeter)
    for kx in [12, 16, 20, 24]:
        me.place("2412b", BLACK, kx, 23, 10, "R0")

    for kx in [4, 8, 12, 16, 20, 24, 28]:
        me.place("2412b", BLACK, kx, 33, 10, "R0")
        me.place("2412b", BLACK, kx+2, 33, 10, "R0")

    # Observation Cupola / Skylight Lanterns (sitting right over bearing column intersections)
    for kx in [12, 20, 28]:
        me.place("3022", DARK_BLUISH_GRAY, kx, 25, 10, "R0")
        me.place("3941", TRANS_LIGHT_BLUE, kx, 25, 11, "R0")
        me.place("59900", PEARL_GOLD, kx, 25, 14, "R0")

        me.place("3022", DARK_BLUISH_GRAY, kx, 29, 10, "R0")
        me.place("3941", TRANS_LIGHT_BLUE, kx, 29, 11, "R0")
        me.place("59900", PEARL_GOLD, kx, 29, 14, "R0")

    # =========================================================================
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
    me.place("3023", DARK_BLUISH_GRAY, 44, 31, 9, "R0")

    # =========================================================================
    # STAGE 11: Cobblestone Paving, Walkways & Garden Details (py=2)
    # =========================================================================
    plate_studs_y1 = set()
    for (px, pz, py) in me.occupied:
        if py == 1:
            if 1 <= px <= 46 and 1 <= pz <= 34:
                plate_studs_y1.add((px, pz))

    # 2x1 tiles horizontally (R0)
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

    # 1x2 tiles vertically (R90)
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

    # Fill single studs with 1x1 tiles (3070b)
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

    return me

if __name__ == "__main__":
    me = build_bel_air_v3()
    piece_count = me.count()
    print(f"\n{'━'*64}")
    print(f"  {me.name.upper()}")
    print(f"  TOTAL PIECE COUNT: {piece_count}")
    print(f"{'━'*64}")

    p = Path("test_bel_air_v3.ldr")
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
