"""Forward logit masks and parent-port pose realization.

Before a token is sampled, candidates that would leave the module box,
mate incompatible ports, or overlap a brick already placed are masked.
Surviving tokens become an ``AssemblyGraph`` through ``BFSTreeCodec.decode``.
The child pose is the rigid alignment of the child port to the parent port
plus a discrete yaw, never a predicted absolute coordinate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np

from bricksmith.core.connector import ConnectorType, Polarity, Port
from bricksmith.core.tree import BFSTreeCodec, TreeNode

# Face contact is legal. A smaller gap than this counts as a solid overlap.
OVERLAP_EPS_LDU = 0.5
BOUNDS_EPS_LDU = 0.5


@dataclass
class PortSpec:
    port_id: str
    connector_type: ConnectorType
    polarity: Polarity
    local_position: np.ndarray
    local_orientation: np.ndarray

    def as_port(self) -> Port:
        return Port(
            port_id=self.port_id,
            connector_type=self.connector_type,
            polarity=self.polarity,
            local_position=np.asarray(self.local_position, dtype=np.float64),
            local_orientation=np.asarray(self.local_orientation, dtype=np.float64),
        )


@dataclass
class AttachmentToken:
    """One parent-relative attachment action.

    ``decoy_position`` is ignored. It exists so callers can prove the pose
    does not come from a supplied absolute coordinate.
    """

    part_id: str
    color_id: int
    parent_index: Optional[int]
    parent_port: Optional[str]
    self_port: Optional[str]
    rotation_offset: int
    ports: list[PortSpec] = field(default_factory=list)
    local_bounds_min: np.ndarray = field(default_factory=lambda: np.zeros(3))
    local_bounds_max: np.ndarray = field(default_factory=lambda: np.ones(3))
    anchor_transform: Optional[np.ndarray] = None
    decoy_position: Optional[np.ndarray] = None

    def port(self, port_id: Optional[str]) -> Optional[PortSpec]:
        for spec in self.ports:
            if spec.port_id == port_id:
                return spec
        return None


@dataclass
class PlacedPart:
    part_id: str
    color_id: int
    transform: np.ndarray
    bounds_min: np.ndarray
    bounds_max: np.ndarray
    ports: list[PortSpec]

    def port(self, port_id: Optional[str]) -> Optional[PortSpec]:
        for spec in self.ports:
            if spec.port_id == port_id:
                return spec
        return None


def _frame(position: np.ndarray, orientation: np.ndarray) -> np.ndarray:
    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = np.asarray(orientation, dtype=np.float64)
    transform[:3, 3] = np.asarray(position, dtype=np.float64)
    return transform


def yaw_matrix(degrees: int) -> np.ndarray:
    """Rotation about the local port Y axis, matching stud yaw."""
    radians = np.deg2rad(float(degrees))
    cosine, sine = float(np.cos(radians)), float(np.sin(radians))
    rotation = np.eye(4, dtype=np.float64)
    rotation[0, 0] = cosine
    rotation[0, 2] = sine
    rotation[2, 0] = -sine
    rotation[2, 2] = cosine
    return rotation


def attach_pose(
    parent_transform: np.ndarray,
    parent_port: PortSpec,
    child_port: PortSpec,
    rotation_offset: int,
) -> np.ndarray:
    """World pose of the child that mates ``child_port`` onto ``parent_port``."""
    parent_frame = _frame(parent_port.local_position, parent_port.local_orientation)
    child_frame = _frame(child_port.local_position, child_port.local_orientation)
    return parent_transform @ parent_frame @ yaw_matrix(rotation_offset) @ np.linalg.inv(child_frame)


def world_aabb(
    transform: np.ndarray,
    local_min: np.ndarray,
    local_max: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    lo = np.asarray(local_min, dtype=np.float64)
    hi = np.asarray(local_max, dtype=np.float64)
    corners = np.array(
        [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])],
        dtype=np.float64,
    )
    world = corners @ transform[:3, :3].T + transform[:3, 3]
    return world.min(axis=0), world.max(axis=0)


def _outside(bounds_min: np.ndarray, bounds_max: np.ndarray, module_min: np.ndarray, module_max: np.ndarray) -> bool:
    return bool(
        np.any(bounds_min < module_min - BOUNDS_EPS_LDU)
        or np.any(bounds_max > module_max + BOUNDS_EPS_LDU)
    )


def _overlaps(a_min: np.ndarray, a_max: np.ndarray, b_min: np.ndarray, b_max: np.ndarray) -> bool:
    return bool(
        np.all(a_min < b_max - OVERLAP_EPS_LDU) and np.all(a_max > b_min + OVERLAP_EPS_LDU)
    )


def _candidate_pose(token: AttachmentToken, placed: Sequence[PlacedPart]) -> Optional[np.ndarray]:
    if token.parent_index is None:
        return None
    if token.parent_index < 0 or token.parent_index >= len(placed):
        return None
    parent = placed[token.parent_index]
    parent_port = parent.port(token.parent_port)
    child_port = token.port(token.self_port)
    if parent_port is None or child_port is None:
        return None
    return attach_pose(parent.transform, parent_port, child_port, token.rotation_offset)


def illegal_mask(
    candidates: Sequence[AttachmentToken],
    placed: Sequence[PlacedPart],
    module_min: np.ndarray,
    module_max: np.ndarray,
) -> list[bool]:
    """True where the candidate must be masked before sampling.

    Masks (a) placement outside the module box, (b) incompatible port
    polarity such as stud-to-stud or tube-to-tube, and (c) an immediate
    bounding-box overlap with a brick already placed.
    """
    module_min = np.asarray(module_min, dtype=np.float64)
    module_max = np.asarray(module_max, dtype=np.float64)
    masked: list[bool] = []
    for token in candidates:
        parent_port_spec = None
        child_port_spec = token.port(token.self_port)
        parent = None
        if token.parent_index is not None and 0 <= token.parent_index < len(placed):
            parent = placed[token.parent_index]
            parent_port_spec = parent.port(token.parent_port)
        if parent is None or parent_port_spec is None or child_port_spec is None:
            masked.append(True)
            continue
        if not parent_port_spec.as_port().can_mate_with(child_port_spec.as_port()):
            masked.append(True)
            continue
        pose = attach_pose(parent.transform, parent_port_spec, child_port_spec, token.rotation_offset)
        lo, hi = world_aabb(pose, token.local_bounds_min, token.local_bounds_max)
        if _outside(lo, hi, module_min, module_max):
            masked.append(True)
            continue
        if any(_overlaps(lo, hi, part.bounds_min, part.bounds_max) for part in placed):
            masked.append(True)
            continue
        masked.append(False)
    return masked


def place_token(token: AttachmentToken, placed: list[PlacedPart]) -> PlacedPart:
    if token.parent_index is None:
        transform = (
            np.array(token.anchor_transform, dtype=np.float64)
            if token.anchor_transform is not None
            else np.eye(4, dtype=np.float64)
        )
    else:
        pose = _candidate_pose(token, placed)
        if pose is None:
            raise ValueError("cannot realize an attachment with no mated parent port")
        transform = pose
    lo, hi = world_aabb(transform, token.local_bounds_min, token.local_bounds_max)
    return PlacedPart(
        part_id=token.part_id,
        color_id=token.color_id,
        transform=transform,
        bounds_min=lo,
        bounds_max=hi,
        ports=list(token.ports),
    )


def apply_illegal_logit_mask(logits: np.ndarray, illegal_ids: Sequence[int]) -> np.ndarray:
    """Copy ``logits`` and set every illegal vocabulary id to negative infinity."""
    masked = np.array(logits, dtype=np.float32, copy=True)
    if len(illegal_ids):
        masked[np.asarray(list(illegal_ids), dtype=np.int64)] = -np.inf
    return masked


def mask_attachment_candidates(
    candidates: Sequence[AttachmentToken],
    placed_tokens: Sequence[AttachmentToken],
    placed_ids: Sequence[int],
    candidate_ids: Sequence[int],
    module_min: np.ndarray,
    module_max: np.ndarray,
) -> list[bool]:
    """Block only bounds violations, bad mating, AABB overlap, and mesh penetration."""
    placed_parts: list[PlacedPart] = []
    for token in placed_tokens:
        placed_parts.append(place_token(token, placed_parts))
    blocked = illegal_mask(candidates, placed_parts, module_min, module_max)
    for index, token in enumerate(candidates):
        if blocked[index]:
            continue
        child = place_token(token, placed_parts)
        if meshes_penetrate(
            list(placed_ids) + [int(candidate_ids[index])],
            [part.transform for part in placed_parts] + [child.transform],
        ):
            blocked[index] = True
    return blocked


def meshes_penetrate(part_ids: Sequence[int], transforms: Sequence[np.ndarray]) -> bool:
    """True when inset collision meshes interpenetrate, using the validator's kernel."""
    from bricknet.collision import colliding_pairs

    if len(part_ids) < 2:
        return False
    pairs = colliding_pairs(np.asarray(list(part_ids)), np.stack([np.asarray(t) for t in transforms]))
    return len(pairs) > 0


def attachment_nodes(actions: Sequence[AttachmentToken]) -> list[TreeNode]:
    """Parent-relative tree nodes whose poses come from port mating."""
    placed: list[PlacedPart] = []
    nodes: list[TreeNode] = []
    for step, token in enumerate(actions):
        part = place_token(token, placed)
        placed.append(part)
        nodes.append(
            TreeNode(
                step_index=step,
                brick_id=step + 1,
                part_id=token.part_id,
                color_id=int(token.color_id),
                parent_step_index=token.parent_index,
                parent_port=token.parent_port,
                self_port=token.self_port,
                conn_type=ConnectorType.STUD if token.parent_index is not None else None,
                transform=part.transform.copy(),
            )
        )
    return nodes


def codec_attachment_ids(tokenizer, actions: Sequence[AttachmentToken]) -> list[int]:
    """Tokenizer ids of the training codec's BFS attachment string for these actions."""
    from bricksmith.training.codec import load_codebook, serialize_tree

    text = serialize_tree(attachment_nodes(actions), load_codebook())
    encoded = tokenizer.encode(text, add_special_tokens=False)
    if not encoded:
        raise RuntimeError("training codec attachment encoded to zero tokens")
    return list(encoded)


def masked_logits_for_continuations(
    logits: np.ndarray,
    sequences: Sequence[Sequence[int]],
    blocked: Sequence[bool],
    offset: int,
) -> np.ndarray:
    """Set next-token ids to -inf unless they continue a candidate the mask left open."""
    legal = [seq for seq, flag in zip(sequences, blocked) if not flag]
    illegal = illegal_ids_for_continuations(int(np.asarray(logits).shape[0]), legal, offset)
    return apply_illegal_logit_mask(logits, illegal)


def illegal_ids_for_continuations(
    vocab_size: int,
    sequences: Sequence[Sequence[int]],
    offset: int,
) -> list[int]:
    """Mask every vocab id that is not the next training-codec token of a legal sequence."""
    legal = {int(seq[offset]) for seq in sequences if offset < len(seq)}
    if not legal:
        return list(range(vocab_size))
    return [index for index in range(vocab_size) if index not in legal]


def _model_next_logits(model, token_ids: Sequence[int]) -> np.ndarray:
    import mlx.core as mx

    logits = model(mx.array(list(token_ids))[None])
    if isinstance(logits, (tuple, list)):
        logits = logits[0]
    vector = np.array(logits[0, -1].astype(mx.float32))
    del logits
    mx.clear_cache()
    return vector


def sample_codec_continuation(
    model,
    tokenizer,
    prompt: str,
    sequences: Sequence[Sequence[int]],
    seed: int,
) -> list[int]:
    """Sample a codec id sequence, masking every illegal next-token id to -inf."""
    if not sequences:
        raise RuntimeError("no legal codec sequences")
    prompt_ids = list(tokenizer.encode(prompt))
    alive = [list(seq) for seq in sequences]
    offset = 0
    chosen: list[int] = []
    for _ in range(4096):
        pending = [seq for seq in alive if offset < len(seq)]
        if not pending:
            break
        legal_next = {int(seq[offset]) for seq in pending}
        if len(legal_next) == 1:
            pick = next(iter(legal_next))
            vocab = int(getattr(tokenizer, "vocab_size", 0))
            illegal_count = vocab - 1 if vocab else 0
            print(f"mask-forced token: illegal_logit_ids={illegal_count} sampled_token_id={pick}")
        else:
            logits = _model_next_logits(model, prompt_ids + chosen)
            illegal = illegal_ids_for_continuations(int(logits.shape[0]), pending, offset)
            masked = apply_illegal_logit_mask(logits, illegal)
            pick = sample_masked_token_id(masked, seed + offset)
            print(
                f"next-token forward: vocab={logits.shape[0]} "
                f"illegal_logit_ids={len(illegal)} sampled_token_id={pick}"
            )
        if pick not in legal_next:
            raise RuntimeError(f"sampled token {pick} is outside the codec mask")
        chosen.append(pick)
        alive = [seq for seq in pending if seq[offset] == pick]
        offset += 1
        if len(alive) == 1 and offset >= len(alive[0]):
            break
    else:
        raise RuntimeError("codec continuation exceeded the step limit")
    if not alive:
        raise RuntimeError("sampled codec token ids matched no attachment")
    return list(alive[0])


def illegal_ids_for_actions(
    vocab_size: int,
    token_ids: Sequence[int],
    blocked: Sequence[bool],
) -> list[int]:
    """Vocabulary ids that must be masked: blocked actions, plus every non-action id."""
    legal = {int(token_id) for token_id, flag in zip(token_ids, blocked) if not flag}
    if not legal:
        return list(range(vocab_size))
    return [index for index in range(vocab_size) if index not in legal]


def sample_masked_token_id(masked_logits: np.ndarray, seed: int) -> int:
    """Draw one id from a logit vector whose illegal entries are already -inf."""
    import mlx.core as mx

    if not np.isfinite(masked_logits).any():
        raise RuntimeError("logit mask removed every token")
    usable = np.array(masked_logits, dtype=np.float32, copy=True)
    usable[~np.isfinite(usable)] = np.float32(-1e30)
    mx.random.seed(seed)
    drawn = mx.random.categorical(mx.array(usable))
    return int(np.array(drawn).reshape(-1)[0])


def select_attachment(
    candidates: Sequence[AttachmentToken],
    placed: Sequence[PlacedPart],
    module_min: np.ndarray,
    module_max: np.ndarray,
    rng,
    predicate=None,
) -> Optional[AttachmentToken]:
    """Sample uniformly from candidates the mask (and optional predicate) allow."""
    mask = illegal_mask(candidates, placed, module_min, module_max)
    legal = [token for token, blocked in zip(candidates, mask) if not blocked]
    if predicate is not None:
        legal = [token for token in legal if predicate(token, placed)]
    if not legal:
        return None
    return legal[rng.randrange(len(legal))]


def realize_assembly(tokens: Sequence[AttachmentToken], name: str = "guided_assembly"):
    """Realize attachment tokens. Child poses come only from parent-port mating."""
    placed: list[PlacedPart] = []
    nodes: list[TreeNode] = []
    for step, token in enumerate(tokens):
        part = place_token(token, placed)
        placed.append(part)
        conn = None
        if token.parent_index is not None:
            parent_port = placed[token.parent_index].port(token.parent_port)
            child_port = token.port(token.self_port)
            conn = parent_port.connector_type if parent_port is not None else ConnectorType.STUD
            if child_port is not None and parent_port is not None:
                # Record the mating family from the male side when present.
                if child_port.connector_type == ConnectorType.STUD:
                    conn = ConnectorType.STUD
                else:
                    conn = parent_port.connector_type
        nodes.append(
            TreeNode(
                step_index=step,
                brick_id=step + 1,
                part_id=token.part_id,
                color_id=int(token.color_id),
                parent_step_index=token.parent_index,
                parent_port=token.parent_port,
                self_port=token.self_port,
                conn_type=conn,
                transform=part.transform.copy(),
            )
        )
    return BFSTreeCodec.decode(nodes, name=name)
