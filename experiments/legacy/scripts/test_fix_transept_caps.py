with open("scripts/test_catalog_builder.py") as f:
    text = f.read()

text = text.replace('ce.place("3003", TAN, 5, 27, 8, "R0")', 'ce.place("3004", TAN, 5, 27, 8, "R90")')
text = text.replace('ce.place("3003", TAN, 25, 27, 8, "R0")', 'ce.place("3004", TAN, 25, 27, 8, "R90")')

with open("scripts/test_catalog_builder.py", "w") as f:
    f.write(text)

