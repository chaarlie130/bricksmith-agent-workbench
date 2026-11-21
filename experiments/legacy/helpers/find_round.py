import collections
from bricksmith.workbench.parts import inspect_part
with open("21030-1.mpd") as f:
    parts = collections.Counter(line.split()[14].replace('.dat', '') for line in f if line.startswith("1 "))
for p, count in parts.most_common(50):
    try:
        info = inspect_part(p)
        name = info['name'].lower()
        if 'round' in name or 'cone' in name or 'dome' in name or 'cylinder' in name:
            print(f"{count:4d} {p}: {name}")
    except:
        pass
