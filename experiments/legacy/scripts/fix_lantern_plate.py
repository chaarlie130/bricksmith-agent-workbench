with open("scripts/test_grand_cathedral_1000.py") as f:
    text = f.read()

old_lp = """    # Lantern Cornice Tie Plates (py=15, h=1: 4x4 plates 3031)
    ce.place("3031", TAN, 13, 25, 15, "R0")
    ce.place("3031", TAN, 15, 27, 15, "R0")"""

new_lp = """    # Lantern Cornice Tie Plates (py=15, h=1: 4x4 plate 3031 centered)
    ce.place("3031", TAN, 14, 26, 15, "R0")"""

text = text.replace(old_lp, new_lp)
with open("scripts/test_grand_cathedral_1000.py", "w") as f:
    f.write(text)

