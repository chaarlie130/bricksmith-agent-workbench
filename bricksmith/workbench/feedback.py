"""Turn BrickSmith validation into line-addressable feedback for an agent."""
from __future__ import annotations

from pathlib import Path

from bricksmith.physics.validator import validate_ldraw


def check_model(path: Path, *, ground_y: float = 8.0) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    part_lines = [i for i, line in enumerate(lines, 1) if line.strip().startswith("1 ")]
    report = validate_ldraw(path, ground_y=ground_y)
    for error in report["errors"]:
        if error.get("kind") == "mesh_collision":
            error["line_pairs"] = [
                [part_lines[a], part_lines[b]]
                for a, b in error.get("pairs", [])
                if 0 <= a < len(part_lines) and 0 <= b < len(part_lines)
            ]
    report["file"] = str(path.resolve())
    report["ground_y_ldu"] = ground_y
    report["limitations"] = [
        "Approximate static equilibrium; a pass does not prove real-world strength.",
        "Assembly order and insertion clearance are not checked.",
    ]
    return report
