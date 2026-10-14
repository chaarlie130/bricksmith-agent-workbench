lines = open("scripts/build_reichstag.py").read().splitlines()
out = []
skip = False
for line in lines:
    if "Central mirrored funnel core" in line:
        skip = True
    if "Lantern Top" in line:
        skip = False
    if not skip:
        out.append(line)
open("scripts/build_reichstag.py", "w").write("\n".join(out))
