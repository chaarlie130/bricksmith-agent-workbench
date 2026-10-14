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
    from scipy.sparse import coo_matrix, eye, hstack
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


@lru_cache(maxsize=512)
def _resolve_part_num(part_id: Union[str, int]) -> int:
    """Resolve a part stem (str) or catalog index (int) to a valid bricknet catalog integer ID."""
    if isinstance(part_id, (int, np.integer)):
        return int(part_id)
    import re
    from bricknet.data import load_catalog, load_aliases
    catalog = load_catalog()
    stem = str(part_id)
    if stem.endswith(".dat"):
        stem = stem[:-4]
    if stem in catalog.stem_to_id:
        return catalog.stem_to_id[stem]
    aliases = load_aliases()
    if stem in aliases:
        canonical = aliases[stem][0]
        if canonical in catalog.stem_to_id:
            return catalog.stem_to_id[canonical]

    # Pattern variant stripping (e.g. bl_54200pb103 -> 54200, 3068bp0i -> 3068b)
    s = stem[3:] if stem.startswith("bl_") else stem
    m = re.match(r"^([0-9]+[a-zA-Z]*?)(?:pb|p[0-9]|s[0-9]|d[0-9]).*$", s, re.IGNORECASE)
    candidates = [s]
    if m:
        candidates.append(m.group(1))

    for cand in candidates:
        if cand in catalog.stem_to_id:
            return catalog.stem_to_id[cand]
        if cand in aliases:
            canonical = aliases[cand][0]
            if canonical in catalog.stem_to_id:
                return catalog.stem_to_id[canonical]

    raise KeyError(f"Part '{part_id}' not found in catalog or aliases")


def frame(part_id: Union[str, int], flat_index: int):
    p_num = _resolve_part_num(part_id)
    conn_list = load_connector_list()
    if p_num >= len(conn_list) or flat_index >= len(conn_list[p_num]):
        raise IndexError(f"Connector index {flat_index} out of bounds for part {part_id}")
    _, subtype, polarity, subgroup_index, _ = conn_list[p_num][flat_index]
    return load_connectors()[p_num][subtype, polarity][subgroup_index]


@lru_cache(maxsize=128)
def properties(part_id: Union[str, int]):
    p_num = _resolve_part_num(part_id)
    mesh, lo, hi = _mesh(p_num)
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
    studs = [frame(p_num, i) for i, meta in enumerate(load_connector_list()[p_num]) if meta[0] == "stud"]
    top = min(f[1, 3] for f in studs) if studs else lo[1] - 0.25
    low = np.array([lo[0] - 0.25, top, lo[2] - 0.25])
    high = np.array([hi[0] + 0.25, bottom, hi[2] + 0.25])
    return abs(volume) / 10000, center, low, high


def world_properties(part_id: Union[str, int], transform: np.ndarray):
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
    details = {
        "solver_status": int(result.status),
        "max_equilibrium_residual": residual,
        "parts": n,
        "reaction_variables": len(variables),
    }
    if not passed:
        # Find the smallest force/moment balance violations, rather than
        # returning only HiGHS status=2. These are hints, not a proof that
        # each named part is the root cause of the unstable assembly.
        identity = eye(3 * n, format="csr")
        relaxed = hstack((matrix, identity, -identity), format="csr")
        cost = np.r_[np.zeros(len(variables)), np.ones(6 * n)]
        diagnosis = linprog(cost, A_eq=relaxed, b_eq=rhs,
                            bounds=(0, None), method="highs")
        if diagnosis.success:
            slack = diagnosis.x[len(variables):]
            by_part = (slack[:3 * n] + slack[3 * n:]).reshape(n, 3)
            scores = by_part.sum(axis=1)
            details["balance_slack_total"] = round(float(scores.sum()), 5)
            details["suspect_part_indices"] = [int(i) for i in np.argsort(-scores)[:12]
                                               if scores[i] > 1e-6]
    return passed, details


def validate_ldraw(
    content_or_path: Union[str, Path],
    *,
    ground_y: float = 8.0,
    check_sequence: bool = False,
    scope_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate an LDraw model for syntax, scope, collisions, connectivity, and static equilibrium.
    
    Note: Vertical insertion-clearance / assembly reachability sequence checking is reserved
    for Phase 4 (Production Pipeline / Assembly Instructions).
    """
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
    below_ground = []
    plate_bottoms = []
    catalog = load_catalog()
    for i, (_, _, lo, hi) in enumerate(props):
        if hi[1] > ground_y + EPS:
            below_ground.append(i)
        part_name = catalog.id_to_name[graph.part_ids[i]].lower()
        if "plate " in part_name:
            plate_bottoms.append(float(hi[1]))
        if abs(hi[1] - ground_y) <= EPS:
            if "plate " in part_name:
                ground_indices.append(i)
    report["checks"]["included_base"] = len(ground_indices) > 0
    if not ground_indices:
        ground_error = {"kind": "no_ground_baseplate"}
        if len(plate_bottoms) >= 2:
            candidate = max(plate_bottoms)
            if abs(candidate - ground_y) > EPS:
                ground_error["candidate_ground_y_ldu"] = round(candidate, 3)
                ground_error["note"] = (
                    "Plate undersides suggest another ground plane. Verify the model's "
                    "base and rerun with that ground-y value; this is not an automatic pass.")
        errors.append(ground_error)
    report["checks"]["no_parts_below_ground"] = not below_ground
    if below_ground:
        errors.append({"kind": "parts_below_ground", "part_indices": below_ground[:30],
                       "count": len(below_ground), "ground_y_ldu": ground_y,
                       "note": "LDraw +Y points down. A 32x32 baseplate normally has origin Y=0 and underside Y=8; the first plate above it has origin Y=-8."})

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
        errors.append({"kind": "disconnected_assembly", "component_sizes": [len(c) for c in comps],
                       "component_members": [c[:8] for c in comps]})

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
