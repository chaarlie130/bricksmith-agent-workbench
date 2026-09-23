"""LDraw CAD (.ldr, .mpd) parser and emitter for BrickSmith."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union
import numpy as np

from bricksmith.core.graph import AssemblyGraph
from bricksmith.core.connector import ConnectorType

try:
    import bricknet
    from bricknet.data import load_catalog
    BRICKNET_AVAILABLE = True
except ImportError:
    BRICKNET_AVAILABLE = False


def parse_ldr(content_or_path: Union[str, Path], infer_connections: bool = True) -> AssemblyGraph:
    """Parse LDraw text content or file into an AssemblyGraph.
    When infer_connections is True and bricknet is available, physical port edges
    are accurately mapped using BrickNet's connector library.
    """
    if isinstance(content_or_path, Path) or (isinstance(content_or_path, str) and "\n" not in content_or_path and Path(content_or_path).exists()):
        text = Path(content_or_path).read_text(encoding="utf-8", errors="ignore")
    else:
        text = str(content_or_path)

    graph = AssemblyGraph()

    if infer_connections and BRICKNET_AVAILABLE:
        try:
            clean_lines = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("0 ")]
            bg = bricknet.parse_ldr("\n".join(clean_lines))
            catalog = load_catalog()

            id_map = {}
            for i, (pid, m, c) in enumerate(zip(bg.part_ids, bg.transforms, bg.colors)):
                part_stem = catalog.id_to_stem[pid] if pid < len(catalog.id_to_stem) else str(pid)
                brick_id = graph.add_part(part_id=part_stem, color_id=int(c), transform=m)
                id_map[i] = brick_id

            for edge in bg.edges:
                a_idx, b_idx = int(edge["a"]), int(edge["b"])
                conn_family = str(edge["family"])
                try:
                    conn_type = ConnectorType(conn_family)
                except ValueError:
                    conn_type = ConnectorType.STUD
                graph.connect(
                    source_id=id_map[a_idx],
                    source_port=f"port_{edge['a_conn']}",
                    target_id=id_map[b_idx],
                    target_port=f"port_{edge['b_conn']}",
                    conn_type=conn_type,
                )
            return graph
        except Exception:
            pass

    # Regex fallback parser
    pattern = re.compile(
        r"^\s*1\s+(-?\d+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+"
        r"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+"
        r"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+"
        r"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([a-zA-Z0-9_\-\.]+)",
        re.MULTILINE,
    )

    for match in pattern.finditer(text):
        color_id = int(match.group(1))
        x, y, z = float(match.group(2)), float(match.group(3)), float(match.group(4))
        a, b, c = float(match.group(5)), float(match.group(6)), float(match.group(7))
        d, e, f = float(match.group(8)), float(match.group(9)), float(match.group(10))
        g, h, i = float(match.group(11)), float(match.group(12)), float(match.group(13))
        raw_part = match.group(14).strip()
        part_stem = re.sub(r"\.dat$", "", raw_part, flags=re.IGNORECASE)

        transform = np.array([
            [a, b, c, x],
            [d, e, f, y],
            [g, h, i, z],
            [0.0, 0.0, 0.0, 1.0],
        ], dtype=np.float64)

        graph.add_part(part_id=part_stem, color_id=color_id, transform=transform)

    return graph


def save_ldr(graph: AssemblyGraph, output_path: Union[str, Path], title: Optional[str] = None) -> None:
    """Save an AssemblyGraph directly to an LDraw file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(graph.to_ldraw(title=title), encoding="utf-8")
