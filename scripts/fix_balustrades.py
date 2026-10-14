with open("scripts/test_grand_cathedral_1000.py") as f:
    text = f.read()

old_b = """    # E. High Clerestory Balustrade Crenellations (py=12, h=1: 1x1 plates 3024 along nave gutter)
    for mz in range(11, 25):
        ce.place("3024", TAN, 12, mz, 12, "R0")
        ce.place("3024", TAN, 18, mz, 12, "R0")

    # F. Transept Balustrade Crenellations (py=12, h=1: 1x1 plates 3024)
    for kx in range(5, 13):
        ce.place("3024", TAN, kx, 24, 12, "R0")
        ce.place("3024", TAN, kx, 30, 12, "R0")
    for kx in range(19, 27):
        ce.place("3024", TAN, kx, 24, 12, "R0")
        ce.place("3024", TAN, kx, 30, 12, "R0")

    # G. West Facade Gallery Balustrade (py=12, h=1: 1x1 plates 3024 across front)
    for kx in range(13, 19):
        ce.place("3024", TAN, kx, 8, 12, "R0")"""

new_b = """    # E. West Facade Gallery Balustrade (py=12, h=1: 1x1 plates 3024 across front gallery at mz=7)
    for kx in [13, 14, 17, 18]:
        ce.place("3024", TAN, kx, 7, 12, "R0")"""

text = text.replace(old_b, new_b)
with open("scripts/test_grand_cathedral_1000.py", "w") as f:
    f.write(text)

