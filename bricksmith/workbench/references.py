"""Small, auditable lexical index over local LDraw reference models.

This is a first retrieval layer, not an embedding model or a claim that a
retrieved assembly is physically valid. Model files remain the source of truth.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from bricksmith.physics.validator import BRICKNET_AVAILABLE

try:
    from bricknet.data import load_catalog
except ImportError:
    load_catalog = None

DEFAULT_CORPUS = Path(__file__).resolve().parents[2] / "data/reference_sets/ldr"
TOKEN = re.compile(r"[a-z]+|\d+[a-z]*", re.IGNORECASE)
STOPWORDS = {"a", "an", "and", "for", "in", "of", "on", "the", "to", "with", "lego", "set", "model"}

# Human-readable descriptions for a small seed set. Other models remain
# searchable by title, part IDs, and metadata. Expand with reviewed labels.
DESCRIPTIONS = {
    "omr_21000-1_Sears_Tower": "Black skyscraper with bundled stepped shafts and roof antennas",
    "omr_21002-1_Empire_State_Building": "Art Deco skyscraper with repeated setbacks and a narrow spire",
    "omr_21004-1_Solomon_R_Guggenheim_Museum": "Modern museum with curved rotunda and rectangular annex",
    "omr_21006-1_The_White_House": "Neoclassical residence with columns portico and symmetrical wings",
    "omr_21009-1_Farnsworth_House": "Modern glass house raised on columns with terrace and flat roof",
    "omr_21011-1_Brandenburg_Gate": "Monumental gate with repeated columns and upper attic",
    "omr_21012-1_Sydney_Opera_House": "Shell roof forms over a stepped podium",
    "omr_21015-1_The_Leaning_Tower_of_Pisa": "Leaning round tower with stacked arcades",
    "omr_21023-1_Flatiron_Building": "Triangular wedge skyscraper on a street corner",
    "omr_21036-1_Arc_de_Triomphe": "Stone triumphal arch with central opening and plaza",
    "omr_21041-1_Great_Wall_of_China": "Fortified wall and watchtowers crossing hilly terrain",
    "omr_1854-1_House_with_Roof-Windows_Velux": "Traditional house example with pitched roof and roof windows",
    "omr_31009-1_Small_Cottage": "Small traditional cottage house with pitched roof",
    "omr_5766-1_Log_Cabin": "Traditional log cabin house and pitched roof construction",
    "omr_4996-1_Beach_House": "Residential house example with roof and exterior detail",
    "omr_560-1_Town_House_with_Garden": "Traditional town house and garden",
    "omr_6372-1_Town_House": "Traditional town house example",
    "omr_1484-1_Weetabix_Town_House": "Traditional town house example",
    "bricksafe_350_SpanishVilla_1971": "Traditional villa house architecture and roof example",
    "bricksafe_226-2-c192_House_p32": "Traditional small house example with slope roof parts",
    "bricksafe_226-2-c191_House_p32": "Traditional small house example with slope roof parts",
}

PART_FAMILIES = {"window", "door", "hinge", "arch", "slope", "fence",
                 "stair", "column", "wedge", "panel", "tile", "plate"}


def part_family_tags(reference: Reference, catalog=None) -> set[str]:
    """Literal catalog-name families only, not inferred architectural uses."""
    if catalog is None:
        if not BRICKNET_AVAILABLE or load_catalog is None:
            return set()
        catalog = load_catalog()
    tags: set[str] = set()
    for stem in reference.part_counts:
        part_num = catalog.stem_to_id.get(stem)
        if part_num is None:
            continue
        name_words = set(tokens(str(catalog.id_to_name[part_num])))
        tags.update(name_words & PART_FAMILIES)
    return tags


def tokens(value: str) -> list[str]:
    return [word for word in TOKEN.findall(value.lower().replace("_", " ")) if word not in STOPWORDS]


@dataclass(frozen=True)
class Reference:
    id: str
    path: str
    title: str
    description: str
    source: str
    license: str | None
    sha256: str
    piece_count: int
    part_counts: dict[str, int]

    def summary(self) -> dict:
        result = asdict(self)
        result["top_parts"] = dict(Counter(self.part_counts).most_common(8))
        del result["part_counts"]
        return result


def read_reference(path: Path) -> Reference:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    counts: Counter[str] = Counter()
    title = path.stem.split("_", 1)[-1].replace("_", " ")
    license_line = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("0 !LICENSE ") and license_line is None:
            license_line = stripped.removeprefix("0 !LICENSE ")
        elif stripped.startswith("0 Name:"):
            continue
        elif stripped.startswith("0 ") and title == path.stem.split("_", 1)[-1].replace("_", " "):
            candidate = stripped[2:].strip()
            if candidate and not candidate.startswith("!") and not candidate.startswith("//"):
                title = candidate
        elif stripped.startswith("1 "):
            fields = stripped.split()
            if len(fields) == 15:
                counts[Path(fields[-1]).stem.lower()] += 1
    source = path.stem.split("_", 1)[0].lower()
    return Reference(
        id=path.stem,
        path=str(path.resolve()),
        title=title,
        description=DESCRIPTIONS.get(path.stem, ""),
        source=source,
        license=license_line,
        sha256=hashlib.sha256(raw).hexdigest(),
        piece_count=sum(counts.values()),
        part_counts=dict(counts),
    )


def load_references(corpus: Path = DEFAULT_CORPUS) -> list[Reference]:
    if not corpus.is_dir():
        raise FileNotFoundError(f"reference directory does not exist: {corpus}")
    references = [read_reference(path) for path in sorted(corpus.glob("*.ldr"))]
    if not references:
        raise ValueError(f"no .ldr models found in {corpus}")
    return references


def search(references: Iterable[Reference], query: str, limit: int = 5) -> list[dict]:
    """Rank models with field-weighted BM25-style lexical matching."""
    if limit < 1:
        raise ValueError("limit must be positive")
    query_terms = set(tokens(query))
    if not query_terms:
        raise ValueError("query needs at least one searchable word")
    corpus = list(references)
    catalog = load_catalog() if BRICKNET_AVAILABLE and load_catalog else None
    families = [part_family_tags(ref, catalog) for ref in corpus]
    docs = [Counter(tokens(f"{r.title} {r.title} {r.description} {r.description} "
                           f"{' '.join(r.part_counts)} {' '.join(sorted(tags))}"))
            for r, tags in zip(corpus, families)]
    frequency = Counter(term for doc in docs for term in doc)
    average_length = sum(map(lambda doc: sum(doc.values()), docs)) / max(len(docs), 1)
    ranked = []
    for ref, doc in zip(corpus, docs):
        length = sum(doc.values())
        score = 0.0
        for term in query_terms:
            tf = doc[term]
            if not tf:
                continue
            idf = math.log(1 + (len(corpus) - frequency[term] + 0.5) / (frequency[term] + 0.5))
            score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / max(average_length, 1)))
        if "traditional" in query_terms and "modern" in doc:
            score *= 0.35
        if "modern" in query_terms and "traditional" in doc:
            score *= 0.35
        if score:
            ranked.append((score, ref))
    ranked.sort(key=lambda item: (-item[0], item[1].id))
    by_id = {ref.id: doc for ref, doc in zip(corpus, docs)}
    families_by_id = {ref.id: tags for ref, tags in zip(corpus, families)}
    results = []
    for score, ref in ranked[:limit]:
        matched = sorted(term for term in query_terms if by_id[ref.id][term])
        results.append({"score": round(score, 4), "matched_query_terms": matched,
                        "unmatched_query_terms": sorted(query_terms - set(matched)),
                        "query_coverage": round(len(matched) / len(query_terms), 3),
                        "matched_part_families": sorted(query_terms & families_by_id[ref.id]),
                        **ref.summary()})
    return results


def inspect_model(path: Path, start: int = 1, count: int = 60) -> dict:
    """Return a bounded, line-numbered excerpt with source provenance."""
    if start < 1 or not 1 <= count <= 200:
        raise ValueError("start must be >= 1 and count must be between 1 and 200")
    ref = read_reference(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    excerpt = [{"line": i + 1, "text": lines[i]} for i in range(start - 1, min(len(lines), start - 1 + count))]
    return {"reference": ref.summary(), "total_lines": len(lines), "excerpt": excerpt}


def inspect_reference_region(path: Path, x_min: float, x_max: float,
                             z_min: float, z_max: float,
                             h_min: float, h_max: float,
                             offset: int = 0, count: int = 40) -> dict:
    """Inspect exact placements by origin region, not arbitrary source order.

    X/Z use studs and height uses plates above the LDraw origin, matching
    ``study_reference``. This deliberately does not claim the entire part body
    lies within the region or infer a buildable subassembly.
    """
    bounds = (x_min, x_max, z_min, z_max, h_min, h_max)
    if any(type(value) not in (int, float) or not math.isfinite(value)
           or abs(value) > 500 for value in bounds):
        raise ValueError("Region bounds must be finite stud/plate coordinates within ±500")
    if x_min > x_max or z_min > z_max or h_min > h_max:
        raise ValueError("Region minimum must not exceed maximum")
    if type(offset) is not int or offset < 0 or type(count) is not int or not 1 <= count <= 60:
        raise ValueError("Region offset must be nonnegative and count must be 1-60")
    ref = read_reference(path)
    matches = []
    for line_num, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        fields = line.split()
        if len(fields) != 15 or fields[0] != "1":
            continue
        try:
            x, y, z = (float(value) for value in fields[2:5])
        except ValueError:
            continue
        x_studs, z_studs, h_plates = x / 20, z / 20, -y / 8
        if x_min <= x_studs <= x_max and z_min <= z_studs <= z_max and h_min <= h_plates <= h_max:
            matches.append({"line": line_num, "text": line,
                            "x_studs": round(x_studs, 3),
                            "z_studs": round(z_studs, 3),
                            "h_plates": round(h_plates, 3)})
    excerpt = matches[offset:offset + count]
    next_offset = offset + len(excerpt) if offset + len(excerpt) < len(matches) else None
    return {"reference_id": ref.id, "title": ref.title, "sha256": ref.sha256,
            "license": ref.license, "region": {"x_studs": [x_min, x_max],
             "z_studs": [z_min, z_max], "h_plates": [h_min, h_max]},
            "total_matches": len(matches), "offset": offset,
            "next_offset": next_offset, "placements": excerpt,
            "note": "Filters part origins only; large or rotated part bodies may cross the region boundary. These source placements are construction evidence, not a checked or reusable assembly."}


def study_reference(path: Path, focus: str = "overview") -> dict:
    """Give the agent a compact, height-sorted view of real LDraw placements.

    Coordinates use studs horizontally and plates vertically, like the
    successful human-readable context pack; the source line number and matrix
    preserve a route back to exact LDraw evidence.
    """
    if focus not in ("overview", "lower", "upper", "slopes"):
        raise ValueError("focus must be overview, lower, upper, or slopes")
    ref = read_reference(path)
    catalog = load_catalog() if BRICKNET_AVAILABLE else None
    placements = []
    for line_num, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        fields = line.split()
        if len(fields) != 15 or fields[0] != "1":
            continue
        try:
            x, y, z = (float(v) for v in fields[2:5])
            matrix = [float(v) for v in fields[5:14]]
        except ValueError:
            continue
        stem = Path(fields[14]).stem.lower()
        part_num = catalog.stem_to_id.get(stem) if catalog else None
        name = str(catalog.id_to_name[part_num]) if part_num is not None else stem
        placements.append({"line": line_num, "h_plates": round(-y / 8, 3),
                           "x_studs": round(x / 20, 3), "z_studs": round(z / 20, 3),
                           "part_id": stem, "part_name": name, "color": fields[1],
                           "matrix": [round(v, 3) for v in matrix]})
    placements.sort(key=lambda row: (row["h_plates"], row["line"]))
    if not placements:
        return {"reference_id": ref.id, "sha256": ref.sha256, "focus": focus,
                "piece_count": 0, "placements": []}
    heights = Counter(row["h_plates"] for row in placements)
    if focus == "lower":
        selected = placements[:60]
    elif focus == "upper":
        selected = placements[-60:]
    elif focus == "slopes":
        candidates = [row for row in placements if "slope" in row["part_name"].lower()]
        selected = candidates[-60:]
    else:
        stride = max(1, math.ceil(len(placements) / 30))
        selected = placements[::stride][:30]
    return {"reference_id": ref.id, "sha256": ref.sha256, "license": ref.license,
            "focus": focus, "piece_count": len(placements),
            "origin_extent_studs": {
                "x": [min(r["x_studs"] for r in placements), max(r["x_studs"] for r in placements)],
                "z": [min(r["z_studs"] for r in placements), max(r["z_studs"] for r in placements)],
                "h_plates": [min(heights), max(heights)]},
            "height_layers": [{"h_plates": h, "parts": n} for h, n in sorted(heights.items())],
            "selected_count": len(selected), "placements": selected,
            "note": "Origin extents omit part body sizes. h=-LDraw_y/8; origin heights are not necessarily top-face heights for special parts. Matrices use LDraw axes (+Y down)."}
