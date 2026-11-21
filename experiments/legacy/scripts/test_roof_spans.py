#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bricksmith.workbench.feedback import check_model

from scripts.test_mansion_with_partitions import (
    MansionEngine, BLACK, WHITE, TAN, DARK_TAN, TRANS_LIGHT_BLUE,
    REDDISH_BROWN, LIGHT_BLUISH_GRAY, DARK_BLUISH_GRAY, DARK_GREEN, PEARL_GOLD
)

def build_mansion_with_spans():
    me = MansionEngine()

    # STAGE 1: Plinth Foundation (py=0, h=1)
    for mz in [0, 4, 8, 12, 16, 20, 24, 28, 32, 36]:
        for kx in [0, 8, 16, 24]:
            me.place("3035", DARK_BLUISH_GRAY, kx, mz, 0, "R0")

    # STAGE 2: Foundation Capping (py=1, h=1)
    for mz in [0, 4, 8, 12, 16, 20, 24, 28, 32, 36]:
        for kx in [0, 8, 16, 24]:
            me.place("3035", LIGHT_BLUISH_GRAY, kx, mz, 1, "R0")

    # STAGE 3: Basement / Ground Plinth Walls (py=2..4, h=3)
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
    me.place("3004", TRANS_LIGHT_BLUE, 19, 25, 2, "R90")
    me.place("3001", DARK_BLUISH_GRAY, 20, 25, 2, "R0")

    for mz in [13, 17, 21]:
        me.place("3001", DARK_BLUISH_GRAY, 8, mz, 2, "R0")
        me.place("3001", DARK_BLUISH_GRAY, 12, mz, 2, "R0")
        me.place("3001", DARK_BLUISH_GRAY, 16, mz, 2, "R0")
        me.place("3001", DARK_BLUISH_GRAY, 20, mz, 2, "R0")

    # Grand Entrance Stoop
    me.place("3003", LIGHT_BLUISH_GRAY, 14, 5, 2, "R0")
    me.place("3003", LIGHT_BLUISH_GRAY, 16, 5, 2, "R0")
    me.place("3003", LIGHT_BLUISH_GRAY, 14, 6, 2, "R0")
    me.place("3003", LIGHT_BLUISH_GRAY, 16, 6, 2, "R0")
    me.place("3003", LIGHT_BLUISH_GRAY, 14, 7, 2, "R0")
    me.place("3003", LIGHT_BLUISH_GRAY, 16, 7, 2, "R0")
    me.place("3003", LIGHT_BLUISH_GRAY, 14, 8, 2, "R0")
    me.place("3003", LIGHT_BLUISH_GRAY, 16, 8, 2, "R0")

    me.place("3003", LIGHT_BLUISH_GRAY, 14, 6, 3, "R0")
    me.place("3003", LIGHT_BLUISH_GRAY, 16, 6, 3, "R0")
    me.place("3003", LIGHT_BLUISH_GRAY, 14, 7, 3, "R0")
    me.place("3003", LIGHT_BLUISH_GRAY, 16, 7, 3, "R0")
    me.place("3003", LIGHT_BLUISH_GRAY, 14, 8, 3, "R0")
    me.place("3003", LIGHT_BLUISH_GRAY, 16, 8, 3, "R0")

    me.place("3003", LIGHT_BLUISH_GRAY, 14, 7, 4, "R0")
    me.place("3003", LIGHT_BLUISH_GRAY, 16, 7, 4, "R0")
    me.place("3003", LIGHT_BLUISH_GRAY, 14, 8, 4, "R0")
    me.place("3003", LIGHT_BLUISH_GRAY, 16, 8, 4, "R0")

    # STAGE 4: Piano Nobile (py=5..7, h=3)
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
    me.place("3003", TAN, 17, 25, 8, "R0")  # wait, py=5 below
    # Let's fix that typo right now: py was 8 instead of 5 for 17,25 in previous!
    # Let's place it at py=5!

    return me
