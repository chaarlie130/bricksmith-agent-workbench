lines = open("scripts/build_reichstag.py").read().splitlines()
out = []
for line in lines:
    if 'me.place("3024", GOLD, 20, 3, 5' in line:
        out.append(line.replace('"3024"', '"90398"'))
    elif 'me.place("3024", GOLD, 42, 3, 5' in line:
        out.append(line.replace('"3024"', '"90398"'))
    elif 'me.place("59900", DARK_BLUISH_GRAY, 24, 8, 33' in line:
        out.append(line.replace('"59900"', '"90398"'))
    elif 'me.place("59900", DARK_BLUISH_GRAY, 39, 8, 33' in line:
        out.append(line.replace('"59900"', '"90398"'))
    elif 'me.place("59900", DARK_BLUISH_GRAY, 31, 8, 39' in line:
        out.append(line.replace('"59900"', '"90398"'))
    else:
        out.append(line)
open("scripts/build_reichstag.py", "w").write("\n".join(out))
