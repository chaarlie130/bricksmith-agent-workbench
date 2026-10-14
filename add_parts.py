lines = open("scripts/build_reichstag.py").read().splitlines()
out = []
for line in lines:
    out.append(line)
    if '"3957":' in line:
        out.append('    "90398": {"h": 5, "R0": (1, 1), "R90": (1, 1), "R180": (1, 1), "R270": (1, 1)},')
        out.append('    "15332": {"h": 6, "R0": (4, 1), "R90": (1, 4), "R180": (4, 1), "R270": (1, 4)},')
        out.append('    "50746": {"h": 2, "R0": (1, 1), "R90": (1, 1), "R180": (1, 1), "R270": (1, 1)},')
        out.append('    "15573": {"h": 1, "R0": (2, 1), "R90": (1, 2), "R180": (2, 1), "R270": (1, 2)},')
open("scripts/build_reichstag.py", "w").write("\n".join(out))
