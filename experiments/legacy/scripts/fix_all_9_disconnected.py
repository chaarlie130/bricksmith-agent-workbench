with open("scripts/test_grand_cathedral_1000.py") as f:
    text = f.read()

# 1. Nameplate mount plate at py=2: use 3710 (1x4 plate with studs) instead of 2431 tile
text = text.replace('ce.place("2431", BLACK, 14, 0, 2, "R0")', 'ce.place("3710", BLACK, 14, 0, 2, "R0")')

# 2. Omit the misaligned fountain coping tile:
text = text.replace('    # Fountain Coping Tiles\n    ce.place("3069b", LIGHT_BLUISH_GRAY, 25, 16, 3, "R0")\n    ce.place("3069b", LIGHT_BLUISH_GRAY, 25, 18, 3, "R0")', '    # Fountain Basin Plinth\n    ce.place("3024", LIGHT_BLUISH_GRAY, 26, 17, 2, "R0")')

# 3. Continuous solid nave roof at py=12:
old_nave_roof = """    # High Nave Roof: 2x4 and 2x2 bricks spanning clerestory walls kx=13..15 and 15..17
    for mz in [11, 15, 19]:
        ce.place("3001", DARK_BLUISH_GRAY, 13, mz, 12, "R0")
        ce.place("3004", DARK_BLUISH_GRAY, 17, mz, 12, "R90")
    ce.place("3003", DARK_BLUISH_GRAY, 13, 23, 12, "R0")
    ce.place("3004", DARK_BLUISH_GRAY, 17, 23, 12, "R90")"""

new_nave_roof = """    # High Nave Roof: continuous solid roof covering central nave kx=13..18, mz=11..25
    for mz in [11, 13, 15, 17, 19, 21, 23]:
        ce.place("3001", DARK_BLUISH_GRAY, 13, mz, 12, "R0")
        ce.place("3004", DARK_BLUISH_GRAY, 17, mz, 12, "R90")"""

text = text.replace(old_nave_roof, new_nave_roof)

# 4. Lantern gallery window sills at py=11:
old_crossing_cornice = """    # Crossing Pier Cornices
    for kx in [13, 17]:
        for mz in [25, 29]:
            ce.place("3022", TAN, kx, mz, 11, "R0")"""

new_crossing_cornice = """    # Crossing Pier Cornices & Lantern Gallery Window Sills (py=11)
    for kx in [13, 17]:
        for mz in [25, 29]:
            ce.place("3022", TAN, kx, mz, 11, "R0")
    # Window sills between piers:
    ce.place("3023", TAN, 15, 25, 11, "R0")
    ce.place("3023", TAN, 15, 29, 11, "R0")
    ce.place("3023", TAN, 13, 27, 11, "R90")
    ce.place("3023", TAN, 17, 27, 11, "R90")"""

text = text.replace(old_crossing_cornice, new_crossing_cornice)

with open("scripts/test_grand_cathedral_1000.py", "w") as f:
    f.write(text)

