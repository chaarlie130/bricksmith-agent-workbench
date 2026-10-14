with open("scripts/test_grand_cathedral_1000.py") as f:
    text = f.read()

# Replace lantern window with supported beam
old_lw = """    # Glazed lantern gallery windows between piers
    ce.place("3004", TRANS_LIGHT_BLUE, 15, 29, 12, "R0")
    ce.place("3004", TRANS_LIGHT_BLUE, 13, 27, 12, "R90")
    ce.place("3004", TRANS_LIGHT_BLUE, 17, 27, 12, "R90")"""

# Omit floating lantern window bricks between piers (the arches are open arches!)
new_lw = """    # Lantern Gallery Arches (open crossing lantern arches between piers)"""

text = text.replace(old_lw, new_lw)
with open("scripts/test_grand_cathedral_1000.py", "w") as f:
    f.write(text)

