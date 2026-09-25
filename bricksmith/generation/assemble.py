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


def _supported(parent: PlacedPart, child: PlacedPart) -> bool:
    """Child footprint sits inside the parent's footprint, so the stud joint can carry it."""
    return bool(
        child.bounds_min[0] >= parent.bounds_min[0] - 0.5
        and child.bounds_max[0] <= parent.bounds_max[0] + 0.5
        and child.bounds_min[2] >= parent.bounds_min[2] - 0.5
        and child.bounds_max[2] <= parent.bounds_max[2] + 0.5
    )


def _prompt(module_min: np.ndarray, module_max: np.ndarray, chosen: str = "") -> str:
    size = np.maximum(module_max - module_min, 1.0)
    width = max(1, int(round(float(size[0] / 20.0))))
    depth = max(1, int(round(float(size[2] / 20.0))))
    height = max(1, int(round(float(size[1] / 20.0))))
    text = (
        f"[INPUT: Bounding Box {width}x{depth}x{height} + Aspect Ratio 1.00:1.00:1.00"
        " + Target Bag Name bag_1_foundation + Coarse Voxel Tokens 0]\n"
        "[TARGET: Discrete BFS Spanning Tree Path Tokens for that Bag]\n"
    )
    if chosen:
        text += chosen + "\n"
    return text


def _action_text(token: AttachmentToken) -> str:
    parent = -1 if token.parent_index is None else token.parent_index
    return (
        f"PART {token.part_id} COLOR {token.color_id} PARENT {parent} "
        f"PARENT_PORT {token.parent_port or 'ROOT'} SELF_PORT {token.self_port or 'ROOT'} "
        f"ROT {token.rotation_offset}"
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
        parent = placed_parts[token.parent_index]
        if not _supported(parent, child):
            blocked[index] = True
    return candidates, blocked


def generate_guided_assembly(
    module_min: np.ndarray,
    module_max: np.ndarray,
    seed: int = 0,
    adapter_path: Optional[str] = None,
    target_pieces: int = 8,
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

    plate_tokens = [token for token, _numeric in plates]
    plate = _sample_action(
        model,
        tokenizer,
        _prompt(module_min, module_max),
        [],
        plate_tokens,
        [False] * len(plate_tokens),
        seed,
    )
    plate_numeric = next(numeric for token, numeric in plates if token is plate)
    chosen: list[AttachmentToken] = [plate]
    chosen_ids: list[int] = [plate_numeric]
    history = _action_text(plate)
    for step in range(1, target_pieces):
        children, child_blocked = _child_actions(chosen, chosen_ids, module_min, module_max)
        if not children or not any(not flag for flag in child_blocked):
            raise RuntimeError(f"logit mask rejected every attachment at piece {step + 1}")
        child = _sample_action(
            model,
            tokenizer,
            _prompt(module_min, module_max, history),
            chosen,
            children,
            child_blocked,
            seed + step,
        )
        catalog = load_catalog()
        chosen.append(child)
        chosen_ids.append(int(catalog.stem_to_id[child.part_id]))
        history = history + "\n" + _action_text(child)

    graph = realize_assembly(chosen, name="guided_assembly")
    print("BFSTreeCodec.decode")
    return graph
