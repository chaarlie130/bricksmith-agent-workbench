with open("scripts/test_catalog_builder.py") as f:
    text = f.read()

old_vault = """# Side Aisle Vaulting / Roofs (py=8, h=1: 2x4 plates bridging piers to outer walls)
for mz in [11, 13, 15, 17, 19, 21, 23]:
    ce.place("3020", DARK_BLUISH_GRAY, 10, mz, 8, "R0")
    ce.place("3020", DARK_BLUISH_GRAY, 18, mz, 8, "R0")"""

# 2x4 plates (3020 R0: w=4, d=2)
# North aisle: kx=9..13 (w=4 studs, mz in [11, 13, 15, 17, 19, 21])
# South aisle: kx=19..23 (w=4 studs, mz in [11, 13, 15, 17, 19, 21])
new_vault = """# Side Aisle Vaulting / Roofs (py=8, h=1: 2x4 plates resting on outer aisle walls)
for mz in [11, 13, 15, 17, 19, 21]:
    ce.place("3020", DARK_BLUISH_GRAY, 9, mz, 8, "R0")
    ce.place("3020", DARK_BLUISH_GRAY, 19, mz, 8, "R0")
ce.place("3022", DARK_BLUISH_GRAY, 9, 23, 8, "R0")
ce.place("3022", DARK_BLUISH_GRAY, 19, 23, 8, "R0")"""

text = text.replace(old_vault, new_vault)
with open("scripts/test_catalog_builder.py", "w") as f:
    f.write(text)

