#!/usr/bin/env python
"""Flatten a multi-part LDraw MPD file into one absolute-coordinate .ldr file.

Official LEGO Architecture sets (like 21030) are authored as MPD files with
many named submodels, where a type-1 line can reference another submodel
(e.g. "21030 - 1.ldr") instead of a primitive .dat part. BrickSmith's parser
expects a flat stream of primitive placements, so these submodel references
are mis-read as unknown parts. This script recursively resolves submodel
references into absolute-transform primitive placements.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

LINE1_RE = re.compile(
    r"^\s*1\s+(-?\d+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+"
    r"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+"
    r"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+"
    r"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+(.+?)\s*$"
)


def parse_submodels(text: str) -> dict[str, list[str]]:
    """Split an MPD file's text into {submodel_name: [raw type-1/comment lines]}."""
    submodels: dict[str, list[str]] = {}
    current = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        m = re.match(r"^\s*0\s+FILE\s+(.+?)\s*$", line, re.IGNORECASE)
        if m:
            current = m.group(1)
            submodels[current] = []
            continue
        if current is not None:
            submodels[current].append(line)
    return submodels


def mat_from_fields(fields) -> np.ndarray:
    x, y, z, a, b, c, d, e, f, g, h, i = fields
    return np.array(
        [
            [a, b, c, x],
            [d, e, f, y],
            [g, h, i, z],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def mat_to_fields(m: np.ndarray) -> tuple:
    x, y, z = m[0, 3], m[1, 3], m[2, 3]
    a, b, c = m[0, 0], m[0, 1], m[0, 2]
    d, e, f = m[1, 0], m[1, 1], m[1, 2]
    g, h, i = m[2, 0], m[2, 1], m[2, 2]
    return x, y, z, a, b, c, d, e, f, g, h, i


def fmt(v: float) -> str:
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return f"{v:.6g}"


def flatten(
    submodels: dict[str, list[str]],
    name: str,
    parent_transform: np.ndarray,
    parent_color: int,
    out: list,
    depth: int = 0,
) -> None:
    if depth > 20:
        raise RecursionError(f"submodel nesting too deep at {name!r}")
    lines = submodels.get(name)
    if lines is None:
        raise KeyError(f"submodel not found: {name!r}")

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("0 "):
            continue
        m = LINE1_RE.match(line)
        if not m:
            continue
        color = int(m.group(1))
        fields = tuple(float(m.group(i)) for i in range(2, 14))
        part_ref = m.group(14).strip()
        local_mat = mat_from_fields(fields)
        combined = parent_transform @ local_mat
        resolved_color = color if color != 16 else parent_color

        if part_ref in submodels:
            flatten(submodels, part_ref, combined, resolved_color, out, depth + 1)
        else:
            out.append((resolved_color, combined, part_ref))


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: flatten_mpd.py <input.mpd> <output.ldr>", file=sys.stderr)
        return 2

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    text = in_path.read_text(encoding="utf-8", errors="ignore")
    submodels = parse_submodels(text)
    if not submodels:
        print("no '0 FILE' submodels found; is this an MPD file?", file=sys.stderr)
        return 1

    root_name = next(iter(submodels))
    identity = np.eye(4, dtype=np.float64)

    placements: list = []
    flatten(submodels, root_name, identity, 16, placements)

    out_lines = [f"0 {root_name} (flattened)", "0 Name: " + out_path.name, ""]
    for color, mat, part in placements:
        x, y, z, a, b, c, d, e, f, g, h, i = mat_to_fields(mat)
        out_lines.append(
            "1 {color} {x} {y} {z} {a} {b} {c} {d} {e} {f} {g} {h} {i} {part}".format(
                color=color,
                x=fmt(x), y=fmt(y), z=fmt(z),
                a=fmt(a), b=fmt(b), c=fmt(c),
                d=fmt(d), e=fmt(e), f=fmt(f),
                g=fmt(g), h=fmt(h), i=fmt(i),
                part=part,
            )
        )

    out_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"wrote {len(placements)} primitive placements to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
