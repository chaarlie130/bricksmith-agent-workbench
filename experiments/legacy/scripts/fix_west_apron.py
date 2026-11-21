with open("scripts/test_grand_cathedral_1000.py") as f:
    text = f.read()

old_ap = """    # West Side Apron (kx=1..4, mz=7..36)
    for mz in range(7, 37, 2):
        for kx in [1, 3]:
            ce.place("3069b", LIGHT_BLUISH_GRAY, kx, mz, 2, "R0")"""

new_ap = """    # West Side Apron (kx=1..4, mz=7..10 and mz=25..36)
    for mz in [7, 9]:
        for kx in [1, 3]:
            ce.place("3069b", LIGHT_BLUISH_GRAY, kx, mz, 2, "R0")
    for mz in range(25, 37, 2):
        for kx in [1, 3]:
            ce.place("3069b", LIGHT_BLUISH_GRAY, kx, mz, 2, "R0")"""

text = text.replace(old_ap, new_ap)
with open("scripts/test_grand_cathedral_1000.py", "w") as f:
    f.write(text)

