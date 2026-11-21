#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bricksmith.workbench.feedback import check_model

from scripts.diagnose_stages import get_stage_builders, MansionEngine, LIGHT_BLUISH_GRAY

def test_s7_substages():
    stages = get_stage_builders()
    me = MansionEngine()
    
    # Run Stage 1..6
    for i in range(6):
        stages[i][1](me)
    
    test_ldr = Path("test_s7_sub.ldr")
    test_ldr.write_text("\n".join(me.lines) + "\n")
    print("Stage 1..6 base check:", check_model(test_ldr).get("checks", {}).get("approximate_gravity_equilibrium"))

    # Now let's add Stage 7 elements one by one
    items = []
    
    # 1. Partitions
    def add_partitions():
        from scripts.diagnose_stages import DARK_TAN
        for mz in [13, 17, 21]:
            me.place("3001", DARK_TAN, 9, mz, 12, "R0")
            me.place("3001", DARK_TAN, 13, mz, 12, "R0")
            me.place("3001", DARK_TAN, 17, mz, 12, "R0")
            me.place("3003", DARK_TAN, 21, mz, 12, "R0")
    items.append(("Partitions (mz=13, 17, 21)", add_partitions))

    # 2. West & East walls
    def add_side_walls():
        from scripts.diagnose_stages import DARK_BLUISH_GRAY
        for mz in [12, 16, 20]:
            me.place("3001", DARK_BLUISH_GRAY, 7, mz, 12, "R90")
            me.place("3001", DARK_BLUISH_GRAY, 23, mz, 12, "R90")
    items.append(("Side Walls (W & E)", add_side_walls))

    # 4. Front wall
    def add_front_wall():
        from scripts.diagnose_stages import DARK_BLUISH_GRAY, WHITE, TRANS_LIGHT_BLUE
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
    items.append(("Front Wall", add_front_wall))

    for name, fn in items:
        fn()
        test_ldr.write_text("\n".join(me.lines) + "\n")
        res = check_model(test_ldr)
        checks = res.get("checks", {})
        conn = checks.get("actual_connectivity")
        eq = checks.get("approximate_gravity_equilibrium")
        coll = checks.get("mesh_collision_free")
        print(f"  + {name:30s}: parts={me.count():4d} | Coll={coll} | Conn={conn} | Eq={eq}")
        if not eq:
            break

if __name__ == "__main__":
    test_s7_substages()
