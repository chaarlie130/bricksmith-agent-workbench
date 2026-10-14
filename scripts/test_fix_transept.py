import re

with open("scripts/test_full_cathedral.py") as f:
    text = f.read()

# Replace mz in [11, 15, 19, 23] for aisle walls with [11, 15, 19]
text = text.replace("for mz in [11, 15, 19, 23]:\n    ge.add_box(\"3001\", TAN, 9, mz, 2, 2, 4, 3, rot=R90", "for mz in [11, 15, 19, 21]:\n    ge.add_box(\"3001\", TAN, 9, mz, 2, 2, 4, 3, rot=R90")
text = text.replace("for mz in [11, 15, 19, 23]:\n    ge.add_box(\"3001\", TAN, 21, mz, 2, 2, 4, 3, rot=R90", "for mz in [11, 15, 19, 21]:\n    ge.add_box(\"3001\", TAN, 21, mz, 2, 2, 4, 3, rot=R90")
# Buttresses only at 11, 15, 19:
text = text.replace("for mz in [11, 15, 19, 21]:\n    ge.add_box(\"3001\", TAN, 9, mz, 2, 2, 4, 3, rot=R90, comment=\"North aisle wall 2x4\")\n    # Outer flying buttress pier projecting to kx=7:\n    ge.add_box(\"3003\", DARK_TAN, 7, mz + 1, 2, 2, 2, 3, rot=R0, comment=\"North buttress pier 2x2\")", """for mz in [11, 15, 19]:
    ge.add_box("3001", TAN, 9, mz, 2, 2, 4, 3, rot=R90, comment="North aisle wall 2x4")
    ge.add_box("3003", DARK_TAN, 7, mz + 1, 2, 2, 2, 3, rot=R0, comment="North buttress pier 2x2")
ge.add_box("3001", TAN, 9, 23, 2, 2, 2, 3, rot=R0, comment="North aisle corner 2x2")""")

text = text.replace("for mz in [11, 15, 19, 21]:\n    ge.add_box(\"3001\", TAN, 21, mz, 2, 2, 4, 3, rot=R90, comment=\"South aisle wall 2x4\")\n    # Outer flying buttress pier projecting to kx=23:\n    ge.add_box(\"3003\", DARK_TAN, 23, mz + 1, 2, 2, 2, 3, rot=R0, comment=\"South buttress pier 2x2\")", """for mz in [11, 15, 19]:
    ge.add_box("3001", TAN, 21, mz, 2, 2, 4, 3, rot=R90, comment="South aisle wall 2x4")
    ge.add_box("3003", DARK_TAN, 23, mz + 1, 2, 2, 2, 3, rot=R0, comment="South buttress pier 2x2")
ge.add_box("3001", TAN, 21, 23, 2, 2, 2, 3, rot=R0, comment="South aisle corner 2x2")""")

with open("scripts/test_full_cathedral.py", "w") as f:
    f.write(text)

