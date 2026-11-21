import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bricksmith.workbench.feedback import check_model
import scripts.test_grand_cathedral_1000 as gc

ce = gc.generate_cathedral()
p = Path("test_eq_finder.ldr")

part_lines = [l for l in ce.lines if l.startswith("1 ")]
print(f"Total parts: {len(part_lines)}")

low = 300
high = len(part_lines)

while low < high:
    mid = (low + high) // 2
    p.write_text("\n".join(part_lines[:mid+1]) + "\n")
    res = check_model(p)
    ok = res.get("checks", {}).get("approximate_gravity_equilibrium", False)
    if ok:
        low = mid + 1
    else:
        high = mid

print(f"First failing part at index {low}:")
print("  Line:", part_lines[low])
if p.exists():
    p.unlink()
