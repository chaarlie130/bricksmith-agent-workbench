with open("scripts/test_catalog_builder.py") as f:
    text = f.read()

text = text.replace('ce.place("3001", TAN, 14, 35, 8, "R0")', 'ce.place("3010", TAN, 14, 35, 8, "R0")')

with open("scripts/test_catalog_builder.py", "w") as f:
    f.write(text)

