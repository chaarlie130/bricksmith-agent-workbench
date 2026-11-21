with open("scripts/test_grand_cathedral_1000.py") as f:
    text = f.read()

# Change bench base from 3024 (1x1 plate) to 3023 (1x2 plate):
text = text.replace('ce.place("3024", DARK_BLUISH_GRAY, kx, mz, 2, "R0") # bench base', 'ce.place("3023", DARK_BLUISH_GRAY, kx, mz, 2, "R0") # bench base')

with open("scripts/test_grand_cathedral_1000.py", "w") as f:
    f.write(text)

