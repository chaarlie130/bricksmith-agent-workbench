"""Connector-center diagnostics for local LDraw placement repairs."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np

from bricksmith.physics.validator import _resolve_part_num, frame, load_connector_list


def _key(point) -> tuple[float, float, float]:
    return tuple(round(float(value), 3) for value in point)


def analyze_alignment(path: Path, selected_lines: list[int]) -> dict:
    if not 1 <= len(selected_lines) <= 30 or len(set(selected_lines)) != len(selected_lines):
        raise ValueError("Select 1-30 distinct assembled placement lines")
    wanted = set(selected_lines)
    connectors = load_connector_list()
    stud_sources: dict[tuple, set[int]] = defaultdict(set)
    holes: dict[int, list[tuple]] = {}
    texts: dict[int, str] = {}
    for line_number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not text.startswith("1 "):
            continue
        fields = text.split()
        part_num = _resolve_part_num(fields[14])
        rotation = np.array([float(value) for value in fields[5:14]]).reshape(3, 3)
        origin = np.array([float(value) for value in fields[2:5]])
        local_holes = []
        for index, meta in enumerate(connectors[part_num]):
            family = str(meta[0])
            if family not in ("stud", "hole"):
                continue
            point = _key(rotation @ frame(part_num, index)[:3, 3] + origin)
            if family == "stud":
                stud_sources[point].add(line_number)
            elif line_number in wanted:
                local_holes.append(point)
        if line_number in wanted:
            holes[line_number] = local_holes
            texts[line_number] = text
    unknown = sorted(wanted - holes.keys())
    if unknown:
        raise ValueError(f"Not current placement lines: {unknown}")
    rows = []
    for line_number in selected_lines:
        local_holes = holes[line_number]
        if not local_holes:
            rows.append({"line": line_number, "text": texts[line_number],
                         "holes": 0, "note": "No underside hole connectors in local catalog"})
            continue
        candidates = []
        for dx in (-20, -10, 0, 10, 20):
            for dz in (-20, -10, 0, 10, 20):
                matched = sum(bool(stud_sources.get((x + dx, y, z + dz), set()) - {line_number})
                              for x, y, z in local_holes)
                candidates.append({"dx": dx, "dz": dz, "matching_holes": matched})
        candidates.sort(key=lambda item: (-item["matching_holes"],
                                          abs(item["dx"]) + abs(item["dz"]),
                                          item["dx"], item["dz"]))
        current = next(item["matching_holes"] for item in candidates
                       if item["dx"] == 0 and item["dz"] == 0)
        better = [item for item in candidates if item["matching_holes"] > current][:4]
        rows.append({"line": line_number, "text": texts[line_number],
                     "holes": len(local_holes), "current_matching_holes": current,
                     "candidate_xy_moves_ldu": better})
    return {"placements": rows,
            "note": "Connector matches are geometry hints only; test moves for collisions, support, and appearance. Candidate shifts move the selected part alone, not anything stacked on it."}
