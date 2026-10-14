lines = open("scripts/build_reichstag.py").read().splitlines()
for i, line in enumerate(lines):
    if "3023" in line and "py+3" in line:
        lines[i] = line.replace("py+3", "py+2")
    if "fill_rect(py+3" in line:
        lines[i] = line.replace("py+3", "py+2")
open("scripts/build_reichstag.py", "w").write("\n".join(lines))
