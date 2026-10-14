with open("scripts/test_grand_cathedral_1000.py") as f:
    text = f.read()

# Add 3666 and 3795 to PARTS_INFO
parts_add = """    "3030": {"h": 1, "R0": (10, 4), "R90": (4, 10), "R180": (10, 4), "R270": (4, 10)},
    "3666": {"h": 1, "R0": (6, 1), "R90": (1, 6), "R180": (6, 1), "R270": (1, 6)},
    "3795": {"h": 1, "R0": (6, 2), "R90": (2, 6), "R180": (6, 2), "R270": (2, 6)},"""

text = text.replace('    "3030": {"h": 1, "R0": (10, 4), "R90": (4, 10), "R180": (10, 4), "R270": (4, 10)},', parts_add)

# Update Crossing Rigid Ring:
old_ring = """    # Crossing Rigid Ring (py=11, h=1: bridging all 4 crossing piers)
    ce.place("3020", TAN, 13, 25, 11, "R90") # West beam spanning kx=13..15, mz=25..29
    ce.place("3020", TAN, 17, 25, 11, "R90") # East beam spanning kx=17..19, mz=25..29
    ce.place("3022", TAN, 13, 29, 11, "R0")   # SW pier cap kx=13..15, mz=29..31
    ce.place("3022", TAN, 17, 29, 11, "R0")   # SE pier cap kx=17..19, mz=29..31
    # North & South arch lintels bridging the beams:
    ce.place("3023", TAN, 15, 29, 11, "R0")   # spans kx=15..17, mz=29..30"""

new_ring = """    # Crossing Rigid Ring (py=11, h=1: 2x6 plates 3795 bridging all 4 crossing piers)
    ce.place("3795", TAN, 13, 25, 11, "R90") # West beam spanning kx=13..15, mz=25..31
    ce.place("3795", TAN, 17, 25, 11, "R90") # East beam spanning kx=17..19, mz=25..31"""

text = text.replace(old_ring, new_ring)
with open("scripts/test_grand_cathedral_1000.py", "w") as f:
    f.write(text)

