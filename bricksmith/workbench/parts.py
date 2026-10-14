"""Read-only, geometry-backed part lookup for design agents."""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path
import re

from bricksmith.physics.validator import BRICKNET_AVAILABLE, _resolve_part_num, frame, load_catalog, properties
from bricksmith.workbench.references import DEFAULT_CORPUS, load_references, tokens


@lru_cache(maxsize=1)
def _usage() -> Counter[str]:
    counts: Counter[str] = Counter()
    for reference in load_references(DEFAULT_CORPUS):
        counts.update(reference.part_counts)
    return counts


def search_parts(query: str, limit: int = 12) -> list[dict]:
    """Search actual BrickNet/LDraw names; prefer parts used in local examples."""
    if not BRICKNET_AVAILABLE:
        raise RuntimeError("BrickNet part catalog is unavailable")
    # Models often say "plate 1 x 10" while catalog names use "plate 1x10".
    normalized = re.sub(r"\b(\d+)\s*(?:x|by)\s*(\d+)\b", r"\1x\2", query, flags=re.I)
    dimensions = re.findall(r"(?<!\d)\d+x\d+(?:x\d+)?", normalized.lower())
    family = next((term for term in tokens(normalized)
                   if term in {"brick", "plate", "tile", "slope", "fence", "arch", "window", "door", "hinge"}), None)
    terms = set(tokens(normalized))
    if not terms or not 1 <= limit <= 30:
        raise ValueError("Use a nonempty part query and a limit of 1-30")
    catalog = load_catalog()
    usage = _usage()
    ranked = []
    for stem, part_id in catalog.stem_to_id.items():
        if not stem or not stem[0].isdigit():
            continue
        name = str(catalog.id_to_name[part_id])
        if family and family not in set(tokens(name)):
            continue
        if any(not re.search(rf"(?<!\d){re.escape(dimension)}(?!\d)", name.lower())
               for dimension in dimensions):
            continue
        name_terms = set(tokens(name))
        matches = len(terms & name_terms)
        if not matches:
            continue
        common = usage[stem.lower()]
        ranked.append((matches, common, stem, name))
    # Prefer exact term coverage, but descriptive intent words such as "porch"
    # must not make a real column or roof part disappear from search.
    if len(terms) > 1:
        exact_used = [row for row in ranked if row[0] == len(terms) and row[1] > 0]
        if exact_used:
            ranked = exact_used
        else:
            used = [row for row in ranked if row[1] > 0 and row[0] >= 2]
            if used:
                ranked = used
            else:
                threshold = max(2, len(terms) // 2)
                narrowed = [row for row in ranked if row[0] >= threshold]
                # Descriptive two-word requests often combine synonyms rather
                # than catalog terms ("flower foliage" versus "plant flower").
                # Keep real single-term hits instead of reporting no parts.
                ranked = narrowed if narrowed else ranked
    ranked.sort(key=lambda row: (-row[0], -row[1], row[2]))
    return [{"part_id": stem, "name": name, "reference_uses": common}
            for _, common, stem, name in ranked[:limit]]


def inspect_part(stem: str) -> dict:
    """Report true mesh extents relative to LDraw origin; not inferred studs."""
    if not BRICKNET_AVAILABLE:
        raise RuntimeError("BrickNet part catalog is unavailable")
    if not stem or not all(c.isalnum() or c in "_-" for c in stem):
        raise ValueError("Use a simple LDraw part ID without a path or extension")
    part_num = _resolve_part_num(stem)
    catalog = load_catalog()
    from bricknet.data import load_connector_list
    _, _, low, high = properties(part_num)
    connectors: dict[str, list[list[float]]] = {"stud": [], "hole": []}
    for index, meta in enumerate(load_connector_list()[part_num]):
        family = str(meta[0])
        if family in connectors:
            pos = frame(part_num, index)[:3, 3]
            connectors[family].append([round(float(v), 3) for v in pos])
    connector_summary = {}
    for family, positions in connectors.items():
        connector_summary[family] = {
            "count": len(positions), "sample_centers_ldu": positions[:8],
            "x_phase_mod_20_ldu": sorted({round(p[0] % 20, 3) for p in positions}),
            "z_phase_mod_20_ldu": sorted({round(p[2] % 20, 3) for p in positions}),
            "heights_ldu": sorted({p[1] for p in positions}),
        }
    library_file = Path(__file__).resolve().parents[2] / "data/ldraw/parts" / f"{stem}.dat"
    license_line = None
    if library_file.is_file():
        for line in library_file.read_text(encoding="utf-8", errors="replace").splitlines()[:20]:
            if line.startswith("0 !LICENSE "):
                license_line = line.removeprefix("0 !LICENSE ")
                break
    return {
        "part_id": stem, "name": str(catalog.id_to_name[part_num]),
        "origin_to_mesh_bounds_ldu": {"min": [round(float(x), 3) for x in low],
                                       "max": [round(float(x), 3) for x in high]},
        "body_span_studs_xz": [round(float((high[0] - low[0]) / 20), 3),
                               round(float((high[2] - low[2]) / 20), 3)],
        "body_height_plates": round(float((high[1] - low[1]) / 8), 3),
        "connectors": connector_summary,
        "reference_uses": _usage()[stem.lower()],
        "library_license": license_line,
        "note": "Bounds are approximate mesh/body extents and connector centers are local to the part in LDraw axes (+Y down). Align stud and hole centers after each part's transform; matching centers alone do not prove no collision or real-world strength.",
    }
