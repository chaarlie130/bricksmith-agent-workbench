with open("scripts/test_full_cathedral.py") as f:
    text = f.read()

old_f = """# Cloister Center Fountain:
ge.add_box("3022", LIGHT_BLUISH_GRAY, 26, 17, 2, 2, 2, 1, rot=R0, comment="Fountain basin 2x2")
ge.add_box("3062b", TRANS_LIGHT_BLUE, 26, 17, 3, 1, 1, 3, rot=R0, comment="Fountain water jet")"""

new_f = """# Cloister Center Fountain:
ge.add_box("3022", LIGHT_BLUISH_GRAY, 25, 17, 2, 2, 2, 1, rot=R0, comment="Fountain basin 2x2")
ge.add_box("3062b", TRANS_LIGHT_BLUE, 25, 17, 3, 1, 1, 3, rot=R0, comment="Fountain water jet")"""

text = text.replace(old_f, new_f)
with open("scripts/test_full_cathedral.py", "w") as f:
    f.write(text)

