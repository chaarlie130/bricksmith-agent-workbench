with open("scripts/test_build_1000.py") as f:
    text = f.read()

old_fb = """# Cloister Garden Flowerbeds & Pathway Tiles (py=2, h=1: 1x1 plates 3024)
for mz in [12, 14, 16, 18, 20, 22]:
    for kx in [24, 27]:
        ce.place("3024", DARK_GREEN, kx, mz, 2, "R0")"""

new_fb = """# Cloister Garden Flowerbeds & Pathway Tiles (py=2, h=1: 1x1 plates 3024)
for mz in [15, 19, 21]:
    ce.place("3024", DARK_GREEN, 27, mz, 2, "R0")"""

text = text.replace(old_fb, new_fb)
with open("scripts/test_build_1000.py", "w") as f:
    f.write(text)

