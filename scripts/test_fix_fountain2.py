with open("scripts/test_full_cathedral.py") as f:
    text = f.read()

old_col = """# Cloister Colonnade Columns (White round bricks 3062b):
for mz in [14, 18, 22]:
    ge.add_box("3062b", WHITE, 25, mz, 2, 1, 1, 3, rot=R0, comment="Cloister column")
ge.add_box("3062b", WHITE, 26, 14, 2, 1, 1, 3, rot=R0, comment="Cloister N column")"""

new_col = """# Cloister Colonnade Columns (White round bricks 3062b):
for mz in [14, 22]:
    ge.add_box("3062b", WHITE, 25, mz, 2, 1, 1, 3, rot=R0, comment="Cloister column")
ge.add_box("3062b", WHITE, 26, 14, 2, 1, 1, 3, rot=R0, comment="Cloister N column")"""

text = text.replace(old_col, new_col)
with open("scripts/test_full_cathedral.py", "w") as f:
    f.write(text)

