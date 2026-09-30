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
}


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
    docs = [Counter(tokens(f"{r.title} {r.title} {r.description} {r.description} {' '.join(r.part_counts)}")) for r in corpus]
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
        if score:
            ranked.append((score, ref))
    ranked.sort(key=lambda item: (-item[0], item[1].id))
    return [{"score": round(score, 4), **ref.summary()} for score, ref in ranked[:limit]]


def inspect_model(path: Path, start: int = 1, count: int = 60) -> dict:
    """Return a bounded, line-numbered excerpt with source provenance."""
    if start < 1 or not 1 <= count <= 200:
        raise ValueError("start must be >= 1 and count must be between 1 and 200")
    ref = read_reference(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    excerpt = [{"line": i + 1, "text": lines[i]} for i in range(start - 1, min(len(lines), start - 1 + count))]
    return {"reference": ref.summary(), "total_lines": len(lines), "excerpt": excerpt}
