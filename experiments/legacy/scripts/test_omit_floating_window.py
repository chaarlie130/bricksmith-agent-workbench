with open("scripts/test_grand_cathedral_1000.py") as f:
    text = f.read()

text = text.replace('    ce.place("3023", TAN, 15, 25, 11, "R0")   # spans kx=15..17, mz=25..26\n', '')
text = text.replace('    ce.place("3004", TRANS_LIGHT_BLUE, 15, 25, 12, "R0")\n', '')

with open("scripts/test_grand_cathedral_1000.py", "w") as f:
    f.write(text)

