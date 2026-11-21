with open("scripts/test_grand_cathedral_1000.py") as f:
    text = f.read()

text = text.replace('    # Fountain Basin Plinth\n    ce.place("3024", LIGHT_BLUISH_GRAY, 26, 17, 2, "R0")', '')

with open("scripts/test_grand_cathedral_1000.py", "w") as f:
    f.write(text)

