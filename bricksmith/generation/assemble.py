"""Seeded guided assembly from a coarse module box.

Each step samples one attachment from the cached MLX model's next-token
distribution after ``illegal_mask`` has set illegal logit ids to -inf.
Poses come from parent-port mating and the graph is realized with
``BFSTreeCodec.decode``. 1x1 stems are not in the action vocabulary.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from bricksmith.core.connector import ConnectorType, Polarity
from bricksmith.generation.sampler import (
    AttachmentToken,
    PlacedPart,
    PortSpec,
    codec_attachment_ids,
    mask_attachment_candidates,
    place_token,
    realize_assembly,
    sample_codec_continuation,
)
from bricksmith.physics.validator import frame, world_properties
from bricksmith.training.codec import coarse_voxel_hex
from bricksmith.training.format_dataset import format_conditioning_prompt
from bricknet.data import load_catalog, load_connector_list

# Plates and bricks wider than 1 stud. 1x1 stems are intentionally absent.
PLATES = ("3031",)
BRICKS = ("3001", "3003", "3004", "3010")
YAWS = (0, 90, 180, 270)
GROUND_Y = 8.0


def _part_token(stem: str, color_id: int) -> tuple[AttachmentToken, int]:
    catalog = load_catalog()
    numeric = catalog.stem_to_id[stem]
    ports: list[PortSpec] = []
    for index, meta in enumerate(load_connector_list()[numeric]):
        kind, subtype = meta[0], meta[1]
        local = frame(numeric, index)
        if kind == "stud" and subtype == "stud":
            ports.append(
                PortSpec(
                    f"port_{index}",
                    ConnectorType.STUD,
                    Polarity.MALE,
                    local[:3, 3].copy(),
                    local[:3, :3].copy(),
                )
            )
        elif kind == "hole" and subtype == "hole":
            ports.append(
                PortSpec(
                    f"port_{index}",
                    ConnectorType.TUBE,
                    Polarity.FEMALE,
                    local[:3, 3].copy(),
                    local[:3, :3].copy(),
                )
            )
    _, _, lo, hi = world_properties(numeric, np.eye(4, dtype=np.float64))
    token = AttachmentToken(
        part_id=stem,
        color_id=color_id,
        parent_index=None,
        parent_port=None,
        self_port=None,
        rotation_offset=0,
        ports=ports,
        local_bounds_min=np.asarray(lo, dtype=np.float64),
        local_bounds_max=np.asarray(hi, dtype=np.float64),
    )
    return token, int(numeric)


def _ground_anchor(numeric_id: int, module_min: np.ndarray, module_max: np.ndarray) -> np.ndarray:
    """Place a part so its bottom sits on Y=8 and its footprint is centered in the box."""
    _, _, lo, hi = world_properties(numeric_id, np.eye(4, dtype=np.float64))
    transform = np.eye(4, dtype=np.float64)
    transform[1, 3] = GROUND_Y - float(hi[1])
    transform[0, 3] = 0.5 * (module_min[0] + module_max[0]) - 0.5 * (float(lo[0]) + float(hi[0]))
    transform[2, 3] = 0.5 * (module_min[2] + module_max[2]) - 0.5 * (float(lo[2]) + float(hi[2]))
    return transform


def module_box_from_studs(width: float, depth: float, height: float) -> tuple[np.ndarray, np.ndarray]:
    """Coarse stud box. Y points down; the ground plane is the box's maximum Y."""
    module_min = np.array([0.0, GROUND_Y - float(height) * 20.0, 0.0], dtype=np.float64)
    module_max = np.array([float(width) * 20.0, GROUND_Y, float(depth) * 20.0], dtype=np.float64)
    return module_min, module_max


@lru_cache(maxsize=1)
def _scope_payload() -> dict:
    import json

    path = Path(__file__).resolve().parents[2] / "configs" / "architecture_scope.json"
    return json.loads(path.read_text(encoding="utf-8"))


def scope_stems() -> tuple[str, ...]:
    """In-scope architecture catalog, including SNOT, jumpers, slopes, and tiles."""
    stems: list[str] = []
    for group in _scope_payload().get("part_categories", {}).values():
        stems.extend(str(stem) for stem in group)
    return tuple(dict.fromkeys(stems))


def _child_token(
    template: AttachmentToken,
    parent_port: str,
    self_port: str,
    yaw: int,
    color: int,
    parent_index: int = 0,
) -> AttachmentToken:
    return AttachmentToken(
        part_id=template.part_id,
        color_id=color,
        parent_index=parent_index,
        parent_port=parent_port,
        self_port=self_port,
        rotation_offset=yaw,
        ports=template.ports,
        local_bounds_min=template.local_bounds_min.copy(),
        local_bounds_max=template.local_bounds_max.copy(),
        decoy_position=np.array([999.0, 999.0, 999.0], dtype=np.float64),
    )


def _fits(part: PlacedPart, module_min: np.ndarray, module_max: np.ndarray) -> bool:
    return not (
        np.any(part.bounds_min < module_min - 0.5) or np.any(part.bounds_max > module_max + 0.5)
    )


def _point_in_hull_2d(point: np.ndarray, hull_points: np.ndarray, margin: float = 0.5) -> bool:
    """Return True if 2D point lies inside or within margin of the convex hull of hull_points."""
    if len(hull_points) == 0:
        return False
    min_pt = np.min(hull_points, axis=0) - margin
    max_pt = np.max(hull_points, axis=0) + margin
    if np.any(point < min_pt) or np.any(point > max_pt):
        return False

    unique_pts = np.unique(hull_points, axis=0)
    if len(unique_pts) < 3:
        return bool(np.all(point >= min_pt) and np.all(point <= max_pt))

    try:
        from scipy.spatial import Delaunay
        delaunay = Delaunay(unique_pts)
        return bool(delaunay.find_simplex(point) >= 0)
    except Exception:
        return bool(np.all(point >= min_pt) and np.all(point <= max_pt))


def _is_supported(
    child: PlacedPart,
    placed: Sequence[PlacedPart],
    parent_index: Optional[int] = None,
    contact_tol_y: float = 1.0,
    overlap_tol_xz: float = 0.5,
) -> bool:
    """True if child is physically supported by the ensemble of placed parts below it.

    Supports:
    1. Direct footprint containment on the designated parent (fast path).
    2. Multi-support ensemble check: gathers all contact regions from parts directly beneath
       the child (|y_bottom - y_top| <= contact_tol_y). Verifies that the child's (X, Z) center
       of mass lies inside the 2D convex hull of the aggregate supporting contact points.
       This enables running bonds (staggered bricks across multiple lower bricks) and lintels/arches
       across multiple columns without toppling under gravity.
    3. Valid non-vertical / side attachments (e.g. SNOT) where parent carries child via rigid interlocking.
    """
    if parent_index is not None and 0 <= parent_index < len(placed):
        parent = placed[parent_index]
        # Fast path: child footprint completely inside parent footprint
        if (
            child.bounds_min[0] >= parent.bounds_min[0] - 0.5
            and child.bounds_max[0] <= parent.bounds_max[0] + 0.5
            and child.bounds_min[2] >= parent.bounds_min[2] - 0.5
            and child.bounds_max[2] <= parent.bounds_max[2] + 0.5
        ):
            return True

    # In LDraw, +Y points down. Bottom of child is bounds_max[1].
    # Supporting parts below have their top surface at bounds_min[1].
    child_bottom_y = child.bounds_max[1]
    contact_corners: list[list[float]] = []

    for part in placed:
        part_top_y = part.bounds_min[1]
        if abs(child_bottom_y - part_top_y) <= contact_tol_y:
            ox_min = max(float(child.bounds_min[0]), float(part.bounds_min[0]))
            ox_max = min(float(child.bounds_max[0]), float(part.bounds_max[0]))
            oz_min = max(float(child.bounds_min[2]), float(part.bounds_min[2]))
            oz_max = min(float(child.bounds_max[2]), float(part.bounds_max[2]))

            if ox_max - ox_min > overlap_tol_xz and oz_max - oz_min > overlap_tol_xz:
                contact_corners.extend([
                    [ox_min, oz_min],
                    [ox_max, oz_min],
                    [ox_min, oz_max],
                    [ox_max, oz_max],
                ])

    if not contact_corners:
        if parent_index is not None and 0 <= parent_index < len(placed):
            parent = placed[parent_index]
            if np.all(child.bounds_min < parent.bounds_max + 1.0) and np.all(child.bounds_max > parent.bounds_min - 1.0):
                return True
        return False

    contact_pts = np.asarray(contact_corners, dtype=np.float64)
    child_com = 0.5 * np.array(
        [child.bounds_min[0] + child.bounds_max[0], child.bounds_min[2] + child.bounds_max[2]],
        dtype=np.float64,
    )
    return _point_in_hull_2d(child_com, contact_pts, margin=0.5)


def _supported(parent: PlacedPart, child: PlacedPart) -> bool:
    """Legacy alias: checks whether child is supported by parent."""
    return _is_supported(child, [parent], parent_index=0)


def _prompt(
    module_min: np.ndarray,
    module_max: np.ndarray,
    bag_name: str = "bag_1_foundation",
    aspect_ratio_str: Optional[str] = None,
    voxel_tokens: Optional[str] = None,
) -> str:
    """Canonical conditioning prompt with real bounds, aspect ratio, and coarse voxels."""
    size = np.maximum(module_max - module_min, 1.0)
    w_ldu = float(size[0])
    h_ldu = float(abs(size[1]))
    d_ldu = float(size[2])
    width = max(1, int(round(w_ldu / 20.0)))
    depth = max(1, int(round(d_ldu / 20.0)))
    height = max(1, int(round(h_ldu / 20.0)))

    if aspect_ratio_str is None:
        m = max(w_ldu, d_ldu, h_ldu)
        if m < 1e-6:
            aspect_ratio_str = "1.00:1.00:1.00"
        else:
            aspect_ratio_str = f"{round(w_ldu / m, 4):.2f}:{round(d_ldu / m, 4):.2f}:{round(h_ldu / m, 4):.2f}"

    if voxel_tokens is None:
        shape = np.maximum(np.ceil(np.array([w_ldu, h_ldu, d_ldu]) / 80.0).astype(int), 1)
        voxel_tokens = coarse_voxel_hex(np.ones(shape, dtype=bool))

    return format_conditioning_prompt(
        width=width,
        depth=depth,
        height=height,
        aspect_ratio_str=aspect_ratio_str,
        bag_name=bag_name,
        coarse_voxel_tokens=voxel_tokens,
    )


def _sample_action(
    model,
    tokenizer,
    prompt: str,
    context: Sequence[AttachmentToken],
    actions: Sequence[AttachmentToken],
    blocked: Sequence[bool],
    seed: int,
) -> AttachmentToken:
    """Sample one action by its training-codec token ids, with illegal ids at -inf."""
    legal: list[AttachmentToken] = []
    sequences: list[list[int]] = []
    for action, flag in zip(actions, blocked):
        if flag:
            continue
        sequences.append(codec_attachment_ids(tokenizer, list(context) + [action]))
        legal.append(action)
    if not legal:
        raise RuntimeError("logit mask rejected every attachment")
    chosen_ids = sample_codec_continuation(model, tokenizer, prompt, sequences, seed)
    print(f"sampled codec token ids: {' '.join(str(i) for i in chosen_ids)}")
    by_seq = {tuple(seq): action for seq, action in zip(sequences, legal)}
    key = tuple(chosen_ids)
    if key not in by_seq:
        raise RuntimeError("sampled codec token ids did not match a legal attachment")
    return by_seq[key]


def _plate_actions(module_min: np.ndarray, module_max: np.ndarray) -> list[tuple[AttachmentToken, int]]:
    actions = []
    for stem in PLATES:
        token, numeric = _part_token(stem, color_id=0)
        token.anchor_transform = _ground_anchor(numeric, module_min, module_max)
        token.decoy_position = np.array([1234.0, 5678.0, 9.0], dtype=np.float64)
        placed = place_token(token, [])
        if _fits(placed, module_min, module_max) and any(
            port.connector_type == ConnectorType.STUD for port in token.ports
        ):
            actions.append((token, numeric))
    return actions


def _child_actions(
    placed_tokens: Sequence[AttachmentToken],
    placed_ids: Sequence[int],
    module_min: np.ndarray,
    module_max: np.ndarray,
) -> tuple[list[AttachmentToken], list[bool]]:
    """In-scope attachments. Illegal mating, bounds, overlap, and mesh penetration are blocked."""
    placed_parts = []
    running: list[AttachmentToken] = []
    for token in placed_tokens:
        running.append(token)
        placed_parts.append(place_token(token, placed_parts))
    candidates: list[AttachmentToken] = []
    numeric_ids: list[int] = []
    for parent_index, parent in enumerate(placed_tokens):
        studs = [port.port_id for port in parent.ports if port.connector_type == ConnectorType.STUD]
        if not studs:
            continue
        for stem in scope_stems():
            try:
                template, numeric = _part_token(stem, color_id=15)
            except KeyError:
                continue
            holes = [port.port_id for port in template.ports if port.connector_type == ConnectorType.TUBE]
            if not holes:
                continue
            for stud in studs:
                for hole in holes[:2]:
                    for yaw in (0, 180):
                        candidates.append(
                            _child_token(template, stud, hole, yaw, 15, parent_index=parent_index)
                        )
                        numeric_ids.append(numeric)
    if not candidates:
        return [], []
    blocked = mask_attachment_candidates(
        candidates,
        placed_tokens,
        placed_ids,
        numeric_ids,
        module_min,
        module_max,
    )
    for index, token in enumerate(candidates):
        if blocked[index]:
            continue
        child = place_token(token, placed_parts)
        if not _is_supported(child, placed_parts, token.parent_index):
            blocked[index] = True
    return candidates, blocked


def generate_guided_assembly(
    module_min: np.ndarray,
    module_max: np.ndarray,
    seed: int = 0,
    adapter_path: Optional[str] = None,
    target_pieces: int = 8,
    bag_name: str = "bag_1_foundation",
    aspect_ratio_str: Optional[str] = None,
    voxel_tokens: Optional[str] = None,
):
    """Sample a grounded plate and further attachments from masked codec token ids."""
    from mlx_lm.utils import load

    from bricksmith.training.codec import cached_model_dir

    module_min = np.asarray(module_min, dtype=np.float64)
    module_max = np.asarray(module_max, dtype=np.float64)
    model_path = str(cached_model_dir())
    print(f"model path: {model_path}")
    if adapter_path:
        print(f"adapter path: {adapter_path}")
    model, tokenizer = load(model_path, adapter_path=adapter_path)
    if hasattr(model, "eval"):
        model.eval()

    plates = _plate_actions(module_min, module_max)
    if not plates:
        raise RuntimeError("no plate fits inside the module box")

    prompt = _prompt(
        module_min,
        module_max,
        bag_name=bag_name,
        aspect_ratio_str=aspect_ratio_str,
        voxel_tokens=voxel_tokens,
    )

    plate_tokens = [token for token, _numeric in plates]
    plate = _sample_action(
        model,
        tokenizer,
        prompt,
        [],
        plate_tokens,
        [False] * len(plate_tokens),
        seed,
    )
    plate_numeric = next(numeric for token, numeric in plates if token is plate)
    chosen: list[AttachmentToken] = [plate]
    chosen_ids: list[int] = [plate_numeric]
    for step in range(1, target_pieces):
        children, child_blocked = _child_actions(chosen, chosen_ids, module_min, module_max)
        if not children or not any(not flag for flag in child_blocked):
            raise RuntimeError(f"logit mask rejected every attachment at piece {step + 1}")
        child = _sample_action(
            model,
            tokenizer,
            prompt,
            chosen,
            children,
            child_blocked,
            seed + step,
        )
        catalog = load_catalog()
        chosen.append(child)
        chosen_ids.append(int(catalog.stem_to_id[child.part_id]))

    graph = realize_assembly(chosen, name="guided_assembly")
    print("BFSTreeCodec.decode")
    return graph
