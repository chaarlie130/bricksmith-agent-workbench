with open("scripts/test_grand_cathedral_1000.py") as f:
    text = f.read()

# 1. Fix nameplate base in Stage 2:
# At mz=0, kx=13..19: change 6636 (tile) to 3710 (1x4 plate) + 3023 (1x2 plate)
text = text.replace('    for kx in [1, 7, 13, 19, 25]:\n        ce.place("6636", BLACK, kx, 0, 1, "R0")', """    for kx in [1, 7, 19, 25]:
        ce.place("6636", BLACK, kx, 0, 1, "R0")
    # At kx=13..19 (nameplate mount area): use plates with studs!
    ce.place("3710", BLACK, 13, 0, 1, "R0")
    ce.place("3023", BLACK, 17, 0, 1, "R0")""")

# 2. Fix Stage 6 cornices: change tiles 4162 and 6636 to plates 3710 and 3023
old_cornice = """    # Facade Wall Cornice
    ce.place("6636", TAN, 13, 7, 11, "R0")

    # Nave Clerestory Cornices (kx=13 and kx=17, mz=11..25)
    for kx in [13, 17]:
        ce.place("4162", TAN, kx, 11, 11, "R90") # mz=11..19
        ce.place("6636", TAN, kx, 19, 11, "R90") # mz=19..25

    # Transept Cornices
    ce.place("4162", TAN, 5, 25, 11, "R0")
    ce.place("4162", TAN, 5, 29, 11, "R0")
    ce.place("3023", TAN, 5, 27, 11, "R90")

    ce.place("4162", TAN, 19, 25, 11, "R0")
    ce.place("4162", TAN, 19, 29, 11, "R0")
    ce.place("3023", TAN, 25, 27, 11, "R90")"""

new_cornice = """    # Facade Wall Cornice (py=11, h=1: plates with studs for gallery balustrade)
    ce.place("3710", TAN, 13, 7, 11, "R0")
    ce.place("3023", TAN, 17, 7, 11, "R0")

    # Nave Clerestory Cornices (kx=13 and kx=17, mz=11..25: plates with studs for roof)
    for kx in [13, 17]:
        ce.place("3710", TAN, kx, 11, 11, "R90") # mz=11..15
        ce.place("3710", TAN, kx, 15, 11, "R90") # mz=15..19
        ce.place("3710", TAN, kx, 19, 11, "R90") # mz=19..23
        ce.place("3023", TAN, kx, 23, 11, "R90") # mz=23..25

    # Transept Cornices (plates with studs for transept roof)
    ce.place("3710", TAN, 5, 25, 11, "R0")
    ce.place("3710", TAN, 9, 25, 11, "R0")
    ce.place("3710", TAN, 5, 29, 11, "R0")
    ce.place("3710", TAN, 9, 29, 11, "R0")
    ce.place("3023", TAN, 5, 27, 11, "R90")

    ce.place("3710", TAN, 19, 25, 11, "R0")
    ce.place("3710", TAN, 23, 25, 11, "R0")
    ce.place("3710", TAN, 19, 29, 11, "R0")
    ce.place("3710", TAN, 23, 29, 11, "R0")
    ce.place("3023", TAN, 25, 27, 11, "R90")"""

text = text.replace(old_cornice, new_cornice)

# 3. Fix North Plaza benches: place directly on floor plate at py=2 and py=3
old_benches = """    # Town Plaza Benches
    for kx in [2, 4]:
        for mz in [13, 19]:
            ce.place("3024", DARK_BLUISH_GRAY, kx, mz, 3, "R0")
            ce.place("3069b", REDDISH_BROWN, kx, mz, 4, "R0")"""

new_benches = """    # Town Plaza Benches (resting directly on floor plates at py=2 and py=3)
    for kx in [2, 4]:
        for mz in [13, 19]:
            ce.place("3024", DARK_BLUISH_GRAY, kx, mz, 2, "R0")
            ce.place("3069b", REDDISH_BROWN, kx, mz, 3, "R0")"""

text = text.replace(old_benches, new_benches)

with open("scripts/test_grand_cathedral_1000.py", "w") as f:
    f.write(text)

