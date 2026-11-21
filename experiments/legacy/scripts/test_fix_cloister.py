with open("scripts/test_full_cathedral.py") as f:
    text = f.read()

# Fix cloister columns
old_col = """# Cloister Colonnade Columns (White round bricks 3062b):
for mz in [13, 16, 19, 22]:
    ge.add_box("3062b", WHITE, 25, mz, 2, 1, 1, 3, rot=R0, comment="Cloister column")
for kx in [24, 26]:
    ge.add_box("3062b", WHITE, kx, 13, 2, 1, 1, 3, rot=R0, comment="Cloister N column")"""

new_col = """# Cloister Colonnade Columns (White round bricks 3062b):
for mz in [15, 18, 21]:
    ge.add_box("3062b", WHITE, 26, mz, 2, 1, 1, 3, rot=R0, comment="Cloister column")
for kx in [27, 28]:
    ge.add_box("3062b", WHITE, kx, 15, 2, 1, 1, 3, rot=R0, comment="Cloister N column")"""

text = text.replace(old_col, new_col)
with open("scripts/test_full_cathedral.py", "w") as f:
    f.write(text)

