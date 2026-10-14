with open("scripts/test_grand_cathedral_1000.py") as f:
    text = f.read()

old_np = """    # I. Display Presentation Nameplate Plaque (mz=0, kx=14..18)
    ce.place("3020", BLACK, 14, 0, 2, "R0")
    ce.place("2412b", PEARL_GOLD, 14, 0, 3, "R0")
    ce.place("2412b", PEARL_GOLD, 16, 0, 3, "R0")"""

new_np = """    # I. Display Presentation Nameplate Plaque (mz=0, kx=14..18)
    ce.place("2431", BLACK, 14, 0, 2, "R0")
    ce.place("2412b", PEARL_GOLD, 14, 0, 3, "R0")
    ce.place("2412b", PEARL_GOLD, 16, 0, 3, "R0")"""

text = text.replace(old_np, new_np)
with open("scripts/test_grand_cathedral_1000.py", "w") as f:
    f.write(text)

