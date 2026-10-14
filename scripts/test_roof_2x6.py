with open("scripts/test_grand_cathedral_1000.py") as f:
    text = f.read()

old_roof = """    # High Nave Roof: continuous solid roof covering central nave kx=13..18, mz=11..25
    for mz in [11, 13, 15, 17, 19, 21, 23]:
        ce.place("3001", DARK_BLUISH_GRAY, 13, mz, 12, "R0")
        ce.place("3004", DARK_BLUISH_GRAY, 17, mz, 12, "R90")

    # High Nave Ridge Cresting (py=15, h=1: 1x2 grille tiles 2412b)
    for mz in range(11, 25, 2):
        ce.place("2412b", DARK_BLUISH_GRAY, 15, mz, 15, "R90")

    # Transept Gabled Roofs (py=12, h=3)
    # North Transept Roof (kx=5..13, mz=25..27 and 27..29)
    ce.place("3001", DARK_BLUISH_GRAY, 5, 25, 12, "R0")
    ce.place("3001", DARK_BLUISH_GRAY, 9, 25, 12, "R0")
    ce.place("3001", DARK_BLUISH_GRAY, 5, 29, 12, "R0")
    ce.place("3001", DARK_BLUISH_GRAY, 9, 29, 12, "R0")

    # South Transept Roof (kx=19..27, mz=25..27 and 27..29)
    ce.place("3001", DARK_BLUISH_GRAY, 19, 25, 12, "R0")
    ce.place("3001", DARK_BLUISH_GRAY, 23, 25, 12, "R0")
    ce.place("3001", DARK_BLUISH_GRAY, 19, 29, 12, "R0")
    ce.place("3001", DARK_BLUISH_GRAY, 23, 29, 12, "R0")

    # Choir & Apse Hipped Roof (py=12, h=3)
    ce.place("3001", DARK_BLUISH_GRAY, 13, 31, 12, "R90")
    ce.place("3001", DARK_BLUISH_GRAY, 17, 31, 12, "R90")
    ce.place("3010", DARK_BLUISH_GRAY, 14, 35, 12, "R0")"""

# 2x6 plates (3795) bridging both clerestory walls seamlessly:
new_roof = """    # High Nave Roof: 2x6 plates (3795 R0: w=6, d=2) bridging North and South clerestory walls
    for mz in [11, 13, 15, 17, 19, 21, 23]:
        ce.place("3795", DARK_BLUISH_GRAY, 13, mz, 12, "R0")

    # High Nave Ridge Cresting (py=13, h=1: 1x2 grille tiles 2412b)
    for mz in range(11, 25, 2):
        ce.place("2412b", DARK_BLUISH_GRAY, 15, mz, 13, "R90")

    # Transept Roofs (2x6 plates 3795 R90: w=2, d=6 bridging North and South transept walls)
    # North Transept
    for kx in [5, 7, 9, 11]:
        ce.place("3795", DARK_BLUISH_GRAY, kx, 25, 12, "R90")

    # South Transept
    for kx in [19, 21, 23, 25]:
        ce.place("3795", DARK_BLUISH_GRAY, kx, 25, 12, "R90")

    # Choir Roof (py=12, h=1)
    ce.place("3795", DARK_BLUISH_GRAY, 13, 31, 12, "R0")
    ce.place("3795", DARK_BLUISH_GRAY, 13, 33, 12, "R0")
    ce.place("3010", DARK_BLUISH_GRAY, 14, 35, 12, "R0")"""

text = text.replace(old_roof, new_roof)
with open("scripts/test_grand_cathedral_1000.py", "w") as f:
    f.write(text)

