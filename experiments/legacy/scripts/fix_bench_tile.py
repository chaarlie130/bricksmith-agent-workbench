with open("scripts/test_grand_cathedral_1000.py") as f:
    text = f.read()

# Change plaza cobblestones to kx in [1, 5] (leaving kx=3 for benches)
text = text.replace('        for kx in [1, 3, 5]:', '        for kx in [1, 5]:')
# And benches at kx = 3:
text = text.replace('    for kx in [2, 4]:', '    for kx in [3]:')

with open("scripts/test_grand_cathedral_1000.py", "w") as f:
    f.write(text)

