with open("scripts/test_grand_cathedral_1000.py") as f:
    text = f.read()

old_cornice = """    # Crossing Pier Cornices & Lantern Gallery Window Sills (py=11)
    for kx in [13, 17]:
        for mz in [25, 29]:
            ce.place("3022", TAN, kx, mz, 11, "R0")
    # Window sill lintels bridging crossing piers (py=11, h=1: 1x4 plates 3710)
    ce.place("3710", TAN, 14, 25, 11, "R0")
    ce.place("3710", TAN, 14, 29, 11, "R0")
    ce.place("3710", TAN, 13, 26, 11, "R90")
    ce.place("3710", TAN, 17, 26, 11, "R90")"""

# A rigid crossing ring of plates bridging all 4 piers at py=11:
# West & East beams (spanning mz=25..29 across piers): 2x4 plates 3020 R90 at kx=13 and kx=17
# North & South beams (spanning kx=15..17 between the west and east beams): 1x2 plates 3023
new_cornice = """    # Crossing Rigid Ring (py=11, h=1: bridging all 4 crossing piers)
    ce.place("3020", TAN, 13, 25, 11, "R90") # West beam spanning kx=13..15, mz=25..29
    ce.place("3020", TAN, 17, 25, 11, "R90") # East beam spanning kx=17..19, mz=25..29
    ce.place("3022", TAN, 13, 29, 11, "R0")   # SW pier cap kx=13..15, mz=29..31
    ce.place("3022", TAN, 17, 29, 11, "R0")   # SE pier cap kx=17..19, mz=29..31
    # North & South arch lintels bridging the beams:
    ce.place("3023", TAN, 15, 25, 11, "R0")   # spans kx=15..17, mz=25..26
    ce.place("3023", TAN, 15, 29, 11, "R0")   # spans kx=15..17, mz=29..30"""

text = text.replace(old_cornice, new_cornice)
with open("scripts/test_grand_cathedral_1000.py", "w") as f:
    f.write(text)

