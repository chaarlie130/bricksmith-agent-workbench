with open("scripts/test_catalog_builder.py") as f:
    text = f.read()

old_v = """# Side Aisle Vaulting / Roofs (py=8, h=1: 2x4 plates resting on outer aisle walls)
for mz in [11, 13, 15, 17, 19, 21]:
    ce.place("3020", DARK_BLUISH_GRAY, 9, mz, 8, "R0")
    ce.place("3020", DARK_BLUISH_GRAY, 19, mz, 8, "R0")
ce.place("3022", DARK_BLUISH_GRAY, 9, 23, 8, "R0")
ce.place("3022", DARK_BLUISH_GRAY, 21, 23, 8, "R0")"""

# Aisle wall cap plates sitting squarely on the outer walls (kx=9..10 and 21..22):
# 1x4 and 1x2 plates (3710 R90: w=1, d=4) along mz=11..23
new_v = """# Side Aisle Wall Caps (py=8, h=1: 1x4 plates sitting squarely on outer walls)
for mz in [11, 15, 19]:
    ce.place("3710", DARK_BLUISH_GRAY, 9, mz, 8, "R90")
    ce.place("3710", DARK_BLUISH_GRAY, 21, mz, 8, "R90")
ce.place("3023", DARK_BLUISH_GRAY, 9, 23, 8, "R90")
ce.place("3023", DARK_BLUISH_GRAY, 21, 23, 8, "R90")"""

text = text.replace(old_v, new_v)
with open("scripts/test_catalog_builder.py", "w") as f:
    f.write(text)

