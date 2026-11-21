with open("scripts/test_grand_cathedral_1000.py") as f:
    text = f.read()

old_sill = """    # Window sills between piers:
    ce.place("3023", TAN, 15, 25, 11, "R0")
    ce.place("3023", TAN, 15, 29, 11, "R0")
    ce.place("3023", TAN, 13, 27, 11, "R90")
    ce.place("3023", TAN, 17, 27, 11, "R90")"""

# 1x4 plates bridging the piers (kx=14..18 and mz=26..30)
new_sill = """    # Window sill lintels bridging crossing piers (py=11, h=1: 1x4 plates 3710)
    ce.place("3710", TAN, 14, 25, 11, "R0")
    ce.place("3710", TAN, 14, 29, 11, "R0")
    ce.place("3710", TAN, 13, 26, 11, "R90")
    ce.place("3710", TAN, 17, 26, 11, "R90")"""

text = text.replace(old_sill, new_sill)
with open("scripts/test_grand_cathedral_1000.py", "w") as f:
    f.write(text)

