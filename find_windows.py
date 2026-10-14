import collections
from bricksmith.workbench.parts import inspect_part
with open("21030-1.mpd") as f:
    parts = collections.Counter(line.split()[14].replace('.dat', '') for line in f if line.startswith("1 "))
for p, count in parts.most_common(100):
    try:
        info = inspect_part(p)
        name = info['name'].lower()
        if 'window' in name or 'glass' in name or 'grille' in name or 'fence' in name or 'brick 1x1' in name or 'brick 1x2' in name:
            print(f"{count:4d} {p}: {name}")
    except:
        pass
