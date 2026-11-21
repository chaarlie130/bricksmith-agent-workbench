lines = open("scripts/build_reichstag.py").read().splitlines()
in_ribs = False
for i, line in enumerate(lines):
    if "Structural ribs" in line:
        in_ribs = True
    elif in_ribs and "3024" in line and "LIGHT_BLUISH_GRAY" in line:
        lines[i] = line.replace("py+2", "py+3")
    elif in_ribs and "Central mirrored funnel" in line:
        in_ribs = False
open("scripts/build_reichstag.py", "w").write("\n".join(lines))
