with open("scripts/test_catalog_builder.py") as f:
    text = f.read()

old_rw = """# Facade Rose Window
ce.place("3004", TAN, 13, 7, 5, "R0")
ce.place("3005", TRANS_LIGHT_BLUE, 15, 7, 5, "R0")
ce.place("3005", TRANS_LIGHT_BLUE, 16, 7, 5, "R0")
ce.place("3004", TAN, 17, 7, 5, "R0")"""

new_rw = """# Facade Portal Lintel (spans across open portal from kx=13 to 19):
ce.place("3009", TAN, 13, 7, 5, "R0")"""

text = text.replace(old_rw, new_rw)
with open("scripts/test_catalog_builder.py", "w") as f:
    f.write(text)

