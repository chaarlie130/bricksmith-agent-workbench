with open("scripts/test_catalog_builder.py") as f:
    text = f.read()

old_cl = """# High Nave Clerestory Walls (kx=13 and kx=17, mz=11..25)
for mz in [11, 15, 19]:
    ce.place("3001", TAN, 13, mz, 8, "R90")
    ce.place("3001", TAN, 17, mz, 8, "R90")
ce.place("3003", TAN, 13, 23, 8, "R0")
ce.place("3003", TAN, 17, 23, 8, "R0")"""

new_cl = """# High Nave Clerestory Walls (kx=13 and kx=17, mz=11..25)
# Supported continuously across piers
for kx in [13, 17]:
    ce.place("3009", TAN, kx, 11, 8, "R90") # mz=11..17
    ce.place("3009", TAN, kx, 17, 8, "R90") # mz=17..23
    ce.place("3004", TAN, kx, 23, 8, "R90") # mz=23..25"""

text = text.replace(old_cl, new_cl)
with open("scripts/test_catalog_builder.py", "w") as f:
    f.write(text)

