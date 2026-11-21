with open("scripts/test_catalog_builder.py") as f:
    text = f.read()

old_vault = """# Side Aisle Vaulting / Roofs (py=8, h=1: plates 3020)
for mz in [11, 15, 19]:
    ce.place("3020", DARK_BLUISH_GRAY, 9, mz, 8, "R90")
    ce.place("3020", DARK_BLUISH_GRAY, 19, mz, 8, "R90")
ce.place("3022", DARK_BLUISH_GRAY, 9, 23, 8, "R0")
ce.place("3022", DARK_BLUISH_GRAY, 19, 23, 8, "R0")"""

# North aisle: kx=10..14 (w=4 studs, spans pier at 13..15 and wall at 9..11!)
# South aisle: kx=18..22 (w=4 studs, spans pier at 17..19 and wall at 21..23!)
new_vault = """# Side Aisle Vaulting / Roofs (py=8, h=1: 2x4 plates bridging piers to outer walls)
for mz in [11, 13, 15, 17, 19, 21, 23]:
    ce.place("3020", DARK_BLUISH_GRAY, 10, mz, 8, "R0")
    ce.place("3020", DARK_BLUISH_GRAY, 18, mz, 8, "R0")"""

text = text.replace(old_vault, new_vault)
with open("scripts/test_catalog_builder.py", "w") as f:
    f.write(text)

