#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bricksmith.workbench.feedback import check_model

from scripts.diagnose_stages import get_stage_builders, MansionEngine
from scripts.diagnose_stages import (
    BLACK, WHITE, TAN, DARK_TAN, TRANS_LIGHT_BLUE,
    REDDISH_BROWN, LIGHT_BLUISH_GRAY, DARK_BLUISH_GRAY, DARK_GREEN, PEARL_GOLD
)

def build_grand_mansion():
    stages = get_stage_builders()
    me = MansionEngine(name="The Vanderbilt - Grand Beaux-Arts Urban Mansion", w_studs=32, d_studs=40)

    # 1. Foundation
    stages[0][1](me)

    # 2. Subfloor & Plinth Borders
    stages[1][1](me)

    # 3. Basement & Stoop
    stages[2][1](me)

    # 4. Piano Nobile (First Floor)
    stages[3][1](me)

    # 5. Floor 2 (Master Residence & Library)
    stages[4][1](me)

    # 6. Cornice & Balustrades
    stages[5][1](me)

    # 7. French Mansard Attic Storey
    # Partitions at mz=13, 17, 21
    for mz in [13, 17, 21]:
        me.place("3001", DARK_TAN, 9, mz, 12, "R0")
        me.place("3001", DARK_TAN, 13, mz, 12, "R0")
        me.place("3001", DARK_TAN, 17, mz, 12, "R0")
        me.place("3003", DARK_TAN, 21, mz, 12, "R0")

    # Side walls
    for mz in [12, 16, 20]:
        me.place("3001", DARK_BLUISH_GRAY, 7, mz, 12, "R90")
        me.place("3001", DARK_BLUISH_GRAY, 23, mz, 12, "R90")

    # Front wall in R0 on z=10
    for kx in range(8, 24, 2):
        if kx in [10, 14, 18]:
            me.place("3004", TRANS_LIGHT_BLUE, kx, 10, 12, "R0")
        elif kx in [8, 22]:
            me.place("3004", DARK_BLUISH_GRAY, kx, 10, 12, "R0")
        else:
            me.place("3004", WHITE, kx, 10, 12, "R0")

    # Rear wall in R0 on z=25
    for kx in range(8, 24, 2):
        if kx in [12, 18]:
            me.place("3004", TRANS_LIGHT_BLUE, kx, 25, 12, "R0")
        else:
            me.place("3004", DARK_BLUISH_GRAY, kx, 25, 12, "R0")

    # 8. Mansard Roof Deck (py=15, h=1)
    for mz in [10, 14, 18, 22]:
        for kx in [8, 10, 12, 14, 16, 18, 20, 22]:
            me.place("3020", DARK_BLUISH_GRAY, kx, mz, 15, "R90")

    # Dormer pediments at py=16
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

    # Roof Finial Urns at py=16
    me.place("59900", PEARL_GOLD, 8, 10, 16, "R0")
    me.place("59900", PEARL_GOLD, 23, 10, 16, "R0")
    me.place("59900", PEARL_GOLD, 8, 25, 16, "R0")
    me.place("59900", PEARL_GOLD, 23, 25, 16, "R0")

    # Central Cupola Spire (py=16..21)
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

    # 9. Streetscape (py=2)
    # Cast-Iron Symmetrical Gate Piers & Gas Lanterns
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

    # Victorian Street Gas Lamps flanking the grand stoop
    for kx in [12, 19]:
        me.place("3024", BLACK, kx, 2, 2, "R0")
        me.place("3062b", BLACK, kx, 2, 3, "R0")
        me.place("3024", TRANS_LIGHT_BLUE, kx, 2, 6, "R0")
        me.place("59900", PEARL_GOLD, kx, 2, 7, "R0")

    # 10. Rear Courtyard Garden (py=2)
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

    # Formal Garden Benches & Planters
    me.place("3023", DARK_BLUISH_GRAY, 10, 34, 2, "R0")
    me.place("3069b", REDDISH_BROWN, 10, 34, 3, "R0")
    me.place("3023", DARK_BLUISH_GRAY, 10, 36, 2, "R0")
    me.place("3069b", REDDISH_BROWN, 10, 36, 3, "R0")
    me.place("3023", DARK_BLUISH_GRAY, 20, 34, 2, "R0")
    me.place("3069b", REDDISH_BROWN, 20, 34, 3, "R0")
    me.place("3023", DARK_BLUISH_GRAY, 20, 36, 2, "R0")
    me.place("3069b", REDDISH_BROWN, 20, 36, 3, "R0")

    me.place("3022", DARK_BLUISH_GRAY, 6, 30, 2, "R0")
    me.place("3942c", DARK_GREEN, 6, 30, 3, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 24, 30, 2, "R0")
    me.place("3942c", DARK_GREEN, 24, 30, 3, "R0")

    me.place("3022", DARK_BLUISH_GRAY, 6, 36, 2, "R0")
    me.place("3942c", DARK_GREEN, 6, 36, 3, "R0")
    me.place("3022", DARK_BLUISH_GRAY, 24, 36, 2, "R0")
    me.place("3942c", DARK_GREEN, 24, 36, 3, "R0")

    # Classical garden statues and courtyard topiaries
    me.place("3022", DARK_BLUISH_GRAY, 10, 30, 2, "R0")
    me.place("3062b", WHITE, 10, 30, 3, "R0")
    me.place("59900", PEARL_GOLD, 10, 30, 6, "R0")

    me.place("3022", DARK_BLUISH_GRAY, 20, 30, 2, "R0")
    me.place("3062b", WHITE, 20, 30, 3, "R0")
    me.place("59900", PEARL_GOLD, 20, 30, 6, "R0")

    # Dormer pediment pediment caps at py=17
    me.place("3023", WHITE, 11, 10, 17, "R0")
    me.place("3023", WHITE, 15, 10, 17, "R0")
    me.place("3023", WHITE, 19, 10, 17, "R0")
    me.place("3023", WHITE, 13, 25, 17, "R0")
    me.place("3023", WHITE, 19, 25, 17, "R0")

    # Additional Roof Cresting Grilles (py=16, h=1)
    for kx in [10, 14, 18, 22]:
        me.place("2412b", BLACK, kx, 11, 16, "R0")
        me.place("2412b", BLACK, kx, 24, 16, "R0")

    # Symmetrical Courtyard Parterre Flower Planters along rear wall
    for kx in [7, 8, 9, 21, 22, 23]:
        me.place("3024", REDDISH_BROWN, kx, 28, 2, "R0")
        me.place("3024", DARK_GREEN, kx, 28, 3, "R0")

    # Formal Boxwood Hedge Row along rear property line (mz=38, py=2..3)
    for kx in range(6, 26, 2):
        me.place("3023", DARK_GREEN, kx, 38, 2, "R0")
        me.place("3023", DARK_GREEN, kx, 38, 3, "R0")

    # Corner garden topiaries (py=2..8)
    for kx in [4, 27]:
        me.place("3022", DARK_BLUISH_GRAY, kx, 34, 2, "R0")
        me.place("3942c", DARK_GREEN, kx, 34, 3, "R0")

    # 11. Paving Tiles (py=2)
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

    return me

if __name__ == "__main__":
    me = build_grand_mansion()
    piece_count = me.count()
    print(f"\n{'━'*64}")
    print(f"  THE VANDERBILT - GRAND BEAUX-ARTS URBAN MANSION")
    print(f"  TOTAL PIECE COUNT: {piece_count}")
    print(f"{'━'*64}")

    p = Path("the_vanderbilt_mansion.ldr")
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
