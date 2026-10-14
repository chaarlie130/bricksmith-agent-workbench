#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bricksmith.workbench.feedback import check_model
from scripts.diagnose_stages import get_stage_builders, MansionEngine, DARK_BLUISH_GRAY, WHITE, TRANS_LIGHT_BLUE, DARK_TAN, LIGHT_BLUISH_GRAY

def test_front_wall_r0():
    stages = get_stage_builders()
    me = MansionEngine()
    for i in range(6):
        stages[i][1](me)
    
    # Add partitions and side walls
    for mz in [13, 17, 21]:
        me.place("3001", DARK_TAN, 9, mz, 12, "R0")
        me.place("3001", DARK_TAN, 13, mz, 12, "R0")
        me.place("3001", DARK_TAN, 17, mz, 12, "R0")
        me.place("3003", DARK_TAN, 21, mz, 12, "R0")
    for mz in [12, 16, 20]:
        me.place("3001", DARK_BLUISH_GRAY, 7, mz, 12, "R90")
        me.place("3001", DARK_BLUISH_GRAY, 23, mz, 12, "R90")

    # Front wall in R0 at z=10
    for kx in range(8, 24, 2):
        if kx in [10, 14, 18]:
            me.place("3004", TRANS_LIGHT_BLUE, kx, 10, 12, "R0")
        elif kx in [8, 22]:
            me.place("3004", DARK_BLUISH_GRAY, kx, 10, 12, "R0")
        else:
            me.place("3004", WHITE, kx, 10, 12, "R0")

    # Rear wall in R0 at z=25 (sits solidly on z=25 of cornice plate, balustrade is at z=26)
    for kx in range(8, 24, 2):
        if kx in [12, 18]:
            me.place("3004", TRANS_LIGHT_BLUE, kx, 25, 12, "R0")
        else:
            me.place("3004", DARK_BLUISH_GRAY, kx, 25, 12, "R0")

    # STAGE 8: Upper Mansard Roof Deck (py=15, h=1)
    for mz in [10, 14, 18, 22]:
        for kx in [8, 10, 12, 14, 16, 18, 20, 22]:
            me.place("3020", DARK_BLUISH_GRAY, kx, mz, 15, "R90")

    # Dormer pediments at py=16 sitting on the roof edge
    from scripts.diagnose_stages import BLACK, REDDISH_BROWN, PEARL_GOLD
    me.place("3710", WHITE, 10, 10, 16, "R0")
    me.place("3710", WHITE, 14, 10, 16, "R0")
    me.place("3710", WHITE, 18, 10, 16, "R0")
    me.place("3710", WHITE, 12, 25, 16, "R0")
    me.place("3710", WHITE, 18, 25, 16, "R0")

    # Roof Cresting Grilles (py=16, h=1)
    for kx in [8, 12, 16, 20]:
        me.place("2412b", BLACK, kx, 11, 16, "R0")
        me.place("2412b", BLACK, kx, 24, 16, "R0")
    for mz in [13, 15, 17, 19, 21]:
        me.place("2412b", BLACK, 8, mz, 16, "R90")
        me.place("2412b", BLACK, 23, mz, 16, "R90")

    # Central Cupola (py=16..20)
    me.place("3022", DARK_BLUISH_GRAY, 15, 15, 16, "R0")
    me.place("3941", TRANS_LIGHT_BLUE, 15, 15, 17, "R0")
    me.place("59900", PEARL_GOLD, 15, 15, 20, "R0")

    # Chimneys (py=16..20)
    me.place("3003", REDDISH_BROWN, 14, 17, 16, "R0")
    me.place("3003", REDDISH_BROWN, 16, 17, 16, "R0")
    me.place("3022", DARK_TAN, 14, 17, 19, "R0")
    me.place("3022", DARK_TAN, 16, 17, 19, "R0")
    for kx in [14, 15, 16, 17]:
        me.place("59900", REDDISH_BROWN, kx, 17, 20, "R0")

    # STAGE 9: Front Streetscape (py=2)
    from scripts.diagnose_stages import DARK_GREEN
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

    # STAGE 10: Rear Courtyard Garden (py=2)
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

    # STAGE 11: Paving Tiles (py=2)
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

    test_ldr = Path("test_fw_r0.ldr")
    test_ldr.write_text("\n".join(me.lines) + "\n")
    res = check_model(test_ldr)
    piece_count = me.count()
    print(f"\n{'━'*64}")
    print(f"  GRAND BEAUX-ARTS URBAN MANSION - FULL TEST")
    print(f"  TOTAL PIECE COUNT: {piece_count}")
    print(f"{'━'*64}")
    print("\nValidation Results:")
    print("Passed:", res.get("passed"))
    for k, v in res.get("checks", {}).items():
        mark = "✓" if v else "·"
        print(f"  {mark} {k}: {v}")
    if not res.get("passed"):
        import pprint
        pprint.pprint(res.get("errors", []))

if __name__ == "__main__":
    test_front_wall_r0()
