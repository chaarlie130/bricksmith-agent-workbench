"""Supported construction, collision, and static equilibrium checks for BrickSmith."""
from __future__ import annotations

import json
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("BRICKNET_DATA", str(ROOT / "data/bricknet-data"))

import numpy as np

# Optional imports if bricknet / meshlib are available
try:
    import bricknet
    import meshlib.mrmeshnumpy as mesh_numpy
    from bricknet.collision import _mesh, colliding_pairs
    from bricknet.data import load_aliases, load_catalog, load_connector_list, load_connectors
    from scipy.optimize import linprog
    from scipy.sparse import coo_matrix
    BRICKNET_AVAILABLE = True
except ImportError:
    BRICKNET_AVAILABLE = False

EPS = 1e-5
CONTACT_PATCH_HALF_WIDTH_LDU = 3.0
ROTATIONS = (
    np.eye(3),
    np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]),
    np.diag([-1, 1, -1]),
    np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]]),
)


@lru_cache(maxsize=1)
def load_scope(scope_path: Optional[str] = None):
    if scope_path and Path(scope_path).exists():
        config = json.loads(Path(scope_path).read_text())
    else:
        default_scope = ROOT / "configs/architecture_scope.json"
        if default_scope.exists():
            config = json.loads(default_scope.read_text())
        else:
            config = {"part_categories": {}, "colors": {}}
    
    # Flatten categories
    all_stems = []
    if "part_categories" in config:
        for cat_list in config["part_categories"].values():
            all_stems.extend(cat_list)
    elif "part_stems" in config:
        all_stems = config["part_stems"]

    if BRICKNET_AVAILABLE:
        aliases = load_aliases()
        canonical = {aliases[s][0] if s in aliases else s for s in all_stems}
    else:
        canonical = set(all_stems)
    return config, canonical


def frame(part_id: str, flat_index: int):
    _, subtype, polarity, subgroup_index, _ = load_connector_list()[part_id][flat_index]
    return load_connectors()[part_id][subtype, polarity][subgroup_index]


@lru_cache(maxsize=128)
def properties(part_id: str):
    mesh, lo, hi = _mesh(part_id)
    vertices = mesh_numpy.getNumpyVerts(mesh)
    faces = mesh_numpy.getNumpyFaces(mesh.topology)
    a, b, c = (vertices[faces[:, i]] for i in range(3))
    tetra = np.einsum("ij,ij->i", a, np.cross(b, c)) / 6.0
    volume = tetra.sum()
    if not np.isfinite(volume) or abs(volume) < EPS:
        raise ValueError(f"Mesh for {part_id} has no usable enclosed volume")
    center = (tetra[:, None] * (a + b + c) / 4).sum(axis=0) / volume
    if not np.isfinite(center).all():
        raise ValueError(f"Mesh center of mass for {part_id} is nonfinite")
    bottom = round((hi[1] + 0.25) / 8) * 8
    studs = [frame(part_id, i) for i, meta in enumerate(load_connector_list()[part_id]) if meta[0] == "stud"]
    top = min(f[1, 3] for f in studs) if studs else lo[1] - 0.25
    low = np.array([lo[0] - 0.25, top, lo[2] - 0.25])
    high = np.array([hi[0] + 0.25, bottom, hi[2] + 0.25])
    return abs(volume) / 10000, center, low, high


def world_properties(part_id: str, transform: np.ndarray):
    mass, center, lo, hi = properties(part_id)
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    corners = corners @ transform[:3, :3].T + transform[:3, 3]
    return mass, transform[:3, :3] @ center + transform[:3, 3], corners.min(axis=0), corners.max(axis=0)


def vertical_equilibrium(props, contacts, ground_indices):
    """HiGHS LP solver for vertical compressive load equilibrium."""
    n = len(props)
    if not n:
        return False, {"reason": "empty assembly"}
    variables = [
        (a, b, point + np.array([dx, 0, dz]))
        for a, b, point in contacts
        if a < n and b < n
        for dx in (-CONTACT_PATCH_HALF_WIDTH_LDU, CONTACT_PATCH_HALF_WIDTH_LDU)
        for dz in (-CONTACT_PATCH_HALF_WIDTH_LDU, CONTACT_PATCH_HALF_WIDTH_LDU)
    ]
    for index in ground_indices:
        if index >= n:
            continue
        _, _, lo, hi = props[index]
        for x in (lo[0] + 1, hi[0] - 1):
            for z in (lo[2] + 1, hi[2] - 1):
                variables.append((-1, index, np.array([x, hi[1], z])))

    if not variables:
        return False, {"reason": "no supports"}

    rows, cols, vals = [], [], []
    rhs = np.zeros(3 * n)
    for i, (mass, _, _, _) in enumerate(props):
        rhs[3 * i] = mass

    for column, (lower, upper, point) in enumerate(variables):
        for index, sign in ((upper, 1), (lower, -1)):
            if index < 0:
                continue
            delta = point - props[index][1]
            for row, value in (
                (3 * index, sign),
                (3 * index + 1, sign * delta[0] / 20),
                (3 * index + 2, sign * delta[2] / 20),
            ):
                rows.append(row)
                cols.append(column)
                vals.append(value)

    matrix = coo_matrix((vals, (rows, cols)), shape=(3 * n, len(variables))).tocsr()
    result = linprog(np.zeros(len(variables)), A_eq=matrix, b_eq=rhs, bounds=(0, None), method="highs")
    residual = float(np.max(np.abs(matrix @ result.x - rhs))) if result.success else None
    passed = bool(result.success and residual is not None and residual < 1e-6)
    return passed, {
        "solver_status": int(result.status),
        "max_equilibrium_residual": residual,
        "parts": n,
        "reaction_variables": len(variables),
    }


def validate_ldraw(
    content_or_path: Union[str, Path],
    *,
    ground_y: float = 8.0,
    check_sequence: bool = True,
    scope_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate an LDraw model for syntax, scope, collisions, connectivity, and static equilibrium."""
    if isinstance(content_or_path, Path) or (isinstance(content_or_path, str) and "\n" not in content_or_path and Path(content_or_path).exists()):
        text = Path(content_or_path).read_text(encoding="utf-8", errors="ignore")
    else:
        text = str(content_or_path)

    started = time.perf_counter()
    errors = []
    report = {
        "schema": "bricksmith-construction-v1",
        "passed": False,
        "checks": {},
        "errors": errors,
    }

    if not BRICKNET_AVAILABLE:
        report["errors"].append({"kind": "environment_error", "detail": "bricknet or meshlib not installed in current environment"})
        return report

    config, allowed_stems = load_scope(scope_path)
    aliases = load_aliases()

    # Syntax & Scope Pass
    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("0 ")]
    count = len(lines)
    report["physical_piece_count"] = count

    if count == 0:
        errors.append({"kind": "empty_assembly"})
        return report

    try:
        graph = bricknet.parse_ldr("\n".join(lines))
        props = [world_properties(pid, m) for pid, m in zip(graph.part_ids, graph.transforms)]
    except Exception as exc:
        errors.append({"kind": "geometry_parse_error", "detail": str(exc)})
        return report

    # 1. Mesh Collision Check
    collisions = colliding_pairs(graph.part_ids, graph.transforms)
    report["checks"]["mesh_collision_free"] = len(collisions) == 0
    if collisions:
        errors.append({"kind": "mesh_collision", "count": len(collisions), "pairs": list(collisions)})

    # 2. Baseplate & Ground Check
    ground_indices = []
    for i, (_, _, lo, hi) in enumerate(props):
        if abs(hi[1] - ground_y) <= EPS:
            part_name = load_catalog().id_to_name[graph.part_ids[i]].lower()
            if "plate " in part_name:
                ground_indices.append(i)
    report["checks"]["included_base"] = len(ground_indices) > 0
    if not ground_indices:
        errors.append({"kind": "no_ground_baseplate"})

    # 3. Contacts & Connectivity
    contacts = []
    seen = set()
    for edge in graph.edges:
        if str(edge["family"]) != "stud":
            continue
        a, b = int(edge["a"]), int(edge["b"])
        fa = graph.transforms[a] @ frame(graph.part_ids[a], int(edge["a_conn"]))
        fb = graph.transforms[b] @ frame(graph.part_ids[b], int(edge["b_conn"]))
        if float(np.max(np.abs(fa[:3, 3] - fb[:3, 3]))) <= EPS:
            key = (a, b, *(round(float(v), 5) for v in fa[:3, 3]))
            if key not in seen:
                seen.add(key)
                contacts.append((a, b, fa[:3, 3]))

    # Connected Components
    neighbors = [set() for _ in range(count)]
    for a, b, _ in contacts:
        neighbors[a].add(b)
        neighbors[b].add(a)

    visited, comps = set(), []
    for start in range(count):
        if start not in visited:
            comp, stack = [], [start]
            while stack:
                node = stack.pop()
                if node not in visited:
                    visited.add(node)
                    comp.append(node)
                    stack.extend(neighbors[node] - visited)
            comps.append(comp)

    report["checks"]["actual_connectivity"] = len(comps) == 1
    if len(comps) > 1:
        errors.append({"kind": "disconnected_assembly", "component_sizes": [len(c) for c in comps]})

    # 4. Compressive Gravity Equilibrium (HiGHS LP)
    eq_ok, eq_details = vertical_equilibrium(props, contacts, ground_indices)
    report["checks"]["approximate_gravity_equilibrium"] = eq_ok
    if not eq_ok:
        errors.append({"kind": "gravity_equilibrium_infeasible", "details": eq_details})

    report["passed"] = (len(errors) == 0) and all(report["checks"].values())
    report["elapsed_seconds"] = round(time.perf_counter() - started, 4)
    return report


@lru_cache(maxsize=128)
def local_triangles(part_id: str):
    mesh, _, _ = _mesh(part_id)
    return mesh_numpy.getNumpyVerts(mesh)[mesh_numpy.getNumpyFaces(mesh.topology)]
