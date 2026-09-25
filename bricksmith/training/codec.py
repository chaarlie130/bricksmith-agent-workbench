"""Compact parent-relative attachment codec and the trainer's tokenizer.

Targets are digit strings. Each piece is a discrete graph action
(part, color, parent index, parent port, self port, rotation offset),
never a continuous (x, y, z) pose. A global codebook maps digit indices
back to part ids, colors, and port names so ``BFSTreeCodec.decode`` can
restore the bag.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import numpy as np

from bricksmith.core.connector import ConnectorType
from bricksmith.core.tree import TreeNode

ROOT = Path(__file__).resolve().parents[2]
CODEBOOK_PATH = Path(__file__).resolve().parent / "codebook.json"
MODEL_REPO = "mlx-community/Llama-3.2-3B-Instruct-4bit"
TOKEN_LIMIT = 1500
DATASET_TOKEN_CAP = 1400

# Tail digit: 0-3 is a stud mating with that many quarter-turns of yaw.
# 4, 5, 6 record axle, hinge, and ball matings (yaw stored as 0).
_TAIL_CONN = {
    4: ConnectorType.AXLE,
    5: ConnectorType.HINGE,
    6: ConnectorType.BALL,
}
_CONN_TAIL = {
    ConnectorType.AXLE: 4,
    ConnectorType.HINGE: 5,
    ConnectorType.BALL: 6,
}


class TokenizationError(Exception):
    """A bag could not be encoded inside the training token budget."""


@dataclass(frozen=True)
class Codebook:
    part_ids: tuple[str, ...]
    color_ids: tuple[int, ...]

    @property
    def part_index(self) -> dict[str, int]:
        return {part_id: i for i, part_id in enumerate(self.part_ids)}

    @property
    def color_index(self) -> dict[int, int]:
        return {color_id: i for i, color_id in enumerate(self.color_ids)}

    def to_json(self) -> dict:
        return {"part_ids": list(self.part_ids), "color_ids": list(self.color_ids)}


_ACTIVE: Optional[Codebook] = None


def set_active_codebook(codebook: Optional[Codebook]) -> None:
    global _ACTIVE
    _ACTIVE = codebook


def load_codebook(path: Optional[Path] = None) -> Codebook:
    if _ACTIVE is not None and path is None:
        return _ACTIVE
    source = path or CODEBOOK_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    return Codebook(
        part_ids=tuple(payload["part_ids"]),
        color_ids=tuple(int(c) for c in payload["color_ids"]),
    )


def save_codebook(codebook: Codebook, path: Optional[Path] = None) -> None:
    target = path or CODEBOOK_PATH
    target.write_text(json.dumps(codebook.to_json()), encoding="utf-8")
    set_active_codebook(codebook)


def cached_model_dir() -> Path:
    """Local snapshot of the 4-bit instruct model the trainer fine-tunes."""
    hub = Path.home() / ".cache/huggingface/hub" / ("models--" + MODEL_REPO.replace("/", "--"))
    snapshots = hub / "snapshots"
    if not snapshots.exists():
        raise FileNotFoundError(f"Cached model not found at {snapshots}")
    snaps = sorted(p for p in snapshots.iterdir() if p.is_dir())
    if not snaps:
        raise FileNotFoundError(f"No snapshot under {snapshots}")
    return snaps[-1]


@lru_cache(maxsize=1)
def training_tokenizer():
    """Hugging Face tokenizer shared with ``mlx_lm`` (same tokenizer.json)."""
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(cached_model_dir())


def count_tokens(text: str) -> int:
    """Token count the MLX trainer uses: encode plus a trailing eos if needed."""
    tokenizer = training_tokenizer()
    ids = tokenizer.encode(text)
    eos = tokenizer.eos_token_id
    if eos is not None and (not ids or ids[-1] != eos):
        ids = list(ids) + [eos]
    return len(ids)


def port_code_v1(name: Optional[str]) -> int:
    """Legacy v1 3-digit port code (physical ports 0..996)."""
    if name is None or name == "ROOT":
        return 0
    if name == "stud_0":
        return 1
    if name == "tube_0":
        return 2
    if name.startswith("port_") and name[5:].isdigit():
        code = 3 + int(name[5:])
        if code >= 1000:
            raise TokenizationError(f"port index does not fit in 3-digit v1 code range: {name}")
        return code
    raise TokenizationError(f"unsupported v1 port name: {name}")


def port_name_v1(code: int) -> Optional[str]:
    """Legacy v1 3-digit port name."""
    if code == 0:
        return None
    if code == 1:
        return "stud_0"
    if code == 2:
        return "tube_0"
    if 3 <= code < 1000:
        return f"port_{code - 3}"
    raise TokenizationError(f"bad v1 port code {code}")


# Aliases for backward compatibility
port_code = port_code_v1
port_name = port_name_v1


def port_to_v2_entry(name: Optional[str]) -> tuple[int, int]:
    """Return (kind, index) for v2 5-digit port encoding: kind (1 digit) + index (4 digits)."""
    if name is None or name == "ROOT":
        return (0, 0)
    if name == "stud_0":
        return (1, 0)
    if name == "tube_0":
        return (2, 0)
    if name.startswith("port_") and name[5:].isdigit():
        idx = int(name[5:])
        if idx > 9999:
            raise TokenizationError(f"port index exceeds 4 digits: {name}")
        return (3, idx)
    if name.startswith("iface_") and name[6:].isdigit():
        idx = int(name[6:])
        if idx > 9999:
            raise TokenizationError(f"interface port index exceeds 4 digits: {name}")
        return (4, idx)
    raise TokenizationError(f"unsupported port name: {name}")


def port_from_v2_entry(kind: int, index: int) -> Optional[str]:
    """Inverse of port_to_v2_entry."""
    if kind == 0:
        return None
    if kind == 1:
        return "stud_0"
    if kind == 2:
        return "tube_0"
    if kind == 3:
        return f"port_{index}"
    if kind == 4:
        return f"iface_{index}"
    raise TokenizationError(f"bad v2 port kind {kind}")


def _pack_tail(conn: Optional[ConnectorType], rotation_quarters: int) -> int:
    if conn is None or conn == ConnectorType.STUD:
        return int(rotation_quarters) % 4
    if conn not in _CONN_TAIL:
        raise TokenizationError(f"unsupported connection type: {conn}")
    return _CONN_TAIL[conn]


def _unpack_tail(digit: int) -> tuple[Optional[ConnectorType], int]:
    if 0 <= digit <= 3:
        return ConnectorType.STUD, digit
    if digit in _TAIL_CONN:
        return _TAIL_CONN[digit], 0
    raise TokenizationError(f"bad tail digit {digit}")


def _rotation_quarters(parent_transform: np.ndarray, child_transform: np.ndarray) -> int:
    relative = parent_transform[:3, :3].T @ child_transform[:3, :3]
    yaw = float(np.arctan2(relative[0, 2], relative[0, 0]))
    return int(round(np.degrees(yaw) / 90.0)) % 4


class _Digits:
    def __init__(self, text: str):
        self.text = text
        self.i = 0

    def take(self, n: int) -> int:
        chunk = self.text[self.i : self.i + n]
        if len(chunk) != n or not chunk.isdigit():
            raise TokenizationError(f"expected {n} digits at offset {self.i}")
        self.i += n
        return int(chunk)

    def remaining(self) -> int:
        return len(self.text) - self.i


def serialize_tree(tree: Sequence, codebook: Codebook, version: int = 2) -> str:
    """Encode one bag's BFS tree as a pure digit string.

    Version 1: Legacy 3-digit port codes (physical ports 0..996).
    Version 2: Starts with '00002', 5-digit port table entries: kind (1) + index (4).
               Separate physical (kind=3, port_0..port_9999) and interface (kind=4, iface_0..iface_9999).
               Preserves rotation_quarters on all root/interface nodes.
    """
    if not tree:
        raise TokenizationError("empty tree")
    if version not in (1, 2):
        raise ValueError(f"unsupported codec version: {version}")

    part_locals: list[int] = []
    part_of: dict[str, int] = {}
    port_locals: list = []
    port_of: dict[str, int] = {}

    def local_port(name: Optional[str]) -> int:
        key = name or "ROOT"
        if key not in port_of:
            port_of[key] = len(port_locals)
            if version == 2:
                port_locals.append(port_to_v2_entry(None if key == "ROOT" else key))
            else:
                port_locals.append(port_code_v1(None if key == "ROOT" else key))
        return port_of[key]

    records: list = []
    for node in tree:
        if node.part_id not in part_of:
            try:
                global_part = codebook.part_index[node.part_id]
            except KeyError as exc:
                raise TokenizationError(f"part {node.part_id} missing from codebook") from exc
            part_of[node.part_id] = len(part_locals)
            part_locals.append(global_part)
        try:
            color_i = codebook.color_index[int(node.color_id)]
        except KeyError as exc:
            raise TokenizationError(f"color {node.color_id} missing from codebook") from exc
        if color_i > 99:
            raise TokenizationError(f"color index {color_i} exceeds 2 digits")
        if node.parent_step_index is None:
            parent = 0
        else:
            parent = int(node.step_index) - int(node.parent_step_index)
            if not 1 <= parent <= 99:
                raise TokenizationError(f"parent delta {parent} does not fit in 2 digits")

        if node.parent_step_index is None or node.conn_type in (None, ConnectorType.STUD):
            if node.parent_step_index is None:
                quarters = int(getattr(node, "rotation_quarters", 0)) % 4
            else:
                rot = getattr(node, "rotation_quarters", None)
                if rot is not None and rot != 0:
                    quarters = int(rot) % 4
                else:
                    parent_node = tree[node.parent_step_index]
                    quarters = _rotation_quarters(parent_node.transform, node.transform)
            tail = _pack_tail(ConnectorType.STUD, quarters)
        else:
            tail = _pack_tail(node.conn_type, 0)

        pp = local_port(node.parent_port)
        sp = local_port(node.self_port)
        if pp > 999 or sp > 999:
            raise TokenizationError("more than 999 distinct ports in one bag")
        records.append((part_of[node.part_id], color_i, parent, pp, sp, tail))

    width = 3 if len(part_locals) > 99 else 2
    if len(port_locals) <= 10:
        port_width = 1
    elif len(port_locals) <= 100:
        port_width = 2
    else:
        port_width = 3
    if len(part_locals) > 999:
        raise TokenizationError("more than 999 distinct parts in one bag")
    if len(port_locals) > 999:
        raise TokenizationError("more than 999 distinct ports in one bag")
    if port_width == 1 and any(pp > 9 or sp > 9 for _, _, _, pp, sp, _ in records):
        port_width = 2
    if port_width == 2 and any(pp > 99 or sp > 99 for _, _, _, pp, sp, _ in records):
        port_width = 3

    out = []
    if version == 2:
        out.append("00002")
    out.append(f"{len(part_locals):03d}")
    out.extend(f"{idx:04d}" for idx in part_locals)
    out.append(f"{len(port_locals):03d}")
    if version == 2:
        out.extend(f"{kind:01d}{idx:04d}" for kind, idx in port_locals)
    else:
        out.extend(f"{code:03d}" for code in port_locals)
    out.append(str(width))
    out.append(str(port_width))
    out.append(f"{len(records):03d}")
    for part_i, color_i, parent, pp, sp, tail in records:
        out.append(
            f"{part_i:0{width}d}{color_i:02d}{parent:02d}{pp:0{port_width}d}{sp:0{port_width}d}{tail:01d}"
        )
    return "".join(out)


def parse_attachment_digits(digits: str, codebook: Codebook) -> List[TreeNode]:
    """Inverse of ``serialize_tree`` supporting both v1 legacy and v2 versioned formats."""
    reader = _Digits(digits)
    version = 1
    if digits.startswith("00002"):
        reader.take(5)
        version = 2

    n_parts = reader.take(3)
    part_locals = [reader.take(4) for _ in range(n_parts)]
    n_ports = reader.take(3)
    if version == 2:
        port_locals = []
        for _ in range(n_ports):
            kind = reader.take(1)
            idx = reader.take(4)
            port_locals.append(port_from_v2_entry(kind, idx))
    else:
        raw_codes = [reader.take(3) for _ in range(n_ports)]
        port_locals = [port_name_v1(code) for code in raw_codes]

    width = reader.take(1)
    port_width = reader.take(1)
    if width not in (2, 3):
        raise TokenizationError(f"bad part-index width {width}")
    if port_width not in (1, 2, 3):
        raise TokenizationError(f"bad port-index width {port_width}")
    n_steps = reader.take(3)
    nodes: List[TreeNode] = []
    for step in range(n_steps):
        part_i = reader.take(width)
        color_i = reader.take(2)
        parent_code = reader.take(2)
        pp_i = reader.take(port_width)
        sp_i = reader.take(port_width)
        tail = reader.take(1)
        if part_i >= len(part_locals) or pp_i >= len(port_locals) or sp_i >= len(port_locals):
            raise TokenizationError("local index out of range")
        if color_i >= len(codebook.color_ids):
            raise TokenizationError("color index out of range")
        global_part = part_locals[part_i]
        if global_part >= len(codebook.part_ids):
            raise TokenizationError("part index out of range")
        conn, quarters = _unpack_tail(tail)
        p_name = port_locals[pp_i]
        s_name = port_locals[sp_i]
        if parent_code == 0:
            parent_step = None
            parent_port = p_name
            self_port = s_name
            conn_out = conn if (p_name is not None or s_name is not None) else None
        else:
            parent_step = step - parent_code
            if parent_step < 0:
                raise TokenizationError(f"parent delta {parent_code} runs before step {step}")
            parent_port = p_name
            self_port = s_name
            conn_out = conn
        nodes.append(
            TreeNode(
                step_index=step,
                brick_id=step + 1,
                part_id=codebook.part_ids[global_part],
                color_id=int(codebook.color_ids[color_i]),
                parent_step_index=parent_step,
                parent_port=parent_port,
                self_port=self_port,
                conn_type=conn_out,
                transform=None,
                rotation_quarters=quarters,
            )
        )
    if reader.remaining() != 0:
        raise TokenizationError(f"{reader.remaining()} trailing digits")
    if not nodes:
        raise TokenizationError("payload contained no steps")
    return nodes


def extract_payload_digits(text: str) -> str:
    marker = "[TARGET:"
    if marker in text:
        rest = text.split(marker, 1)[1]
        _, _, payload = rest.partition("\n")
    else:
        payload = text
    return "".join(ch for ch in payload if ch.isdigit())


def tree_nodes_from_target_text(text: str, codebook: Optional[Codebook] = None) -> List[TreeNode]:
    book = codebook if codebook is not None else load_codebook()
    return parse_attachment_digits(extract_payload_digits(text), book)


def coarse_voxel_hex(grid: np.ndarray, nx: int = 8, ny: int = 4, nz: int = 8) -> str:
    """OR-pool an occupancy grid into a fixed-width hex massing signature."""
    arr = np.asarray(grid, dtype=bool)
    if arr.ndim != 3 or arr.size == 0 or not arr.any():
        return "0"
    sx, sy, sz = arr.shape

    def edges(n: int, bins: int) -> list[int]:
        return [int(round(i * n / bins)) for i in range(bins + 1)]

    xs, ys, zs = edges(sx, nx), edges(sy, ny), edges(sz, nz)
    bits: list[int] = []
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                block = arr[xs[i] : xs[i + 1], ys[j] : ys[j + 1], zs[k] : zs[k + 1]]
                bits.append(1 if block.size and bool(block.any()) else 0)
    value = 0
    for bit in bits:
        value = (value << 1) | bit
    width = max(1, (len(bits) + 3) // 4)
    return f"{value:0{width}x}"


def build_codebook(part_ids: Iterable[str], color_ids: Iterable[int]) -> Codebook:
    parts = tuple(sorted(set(part_ids)))
    colors = tuple(sorted(set(int(c) for c in color_ids)))
    if len(parts) > 10000:
        raise TokenizationError("part codebook exceeds 4 digits")
    if len(colors) > 100:
        raise TokenizationError("color codebook exceeds 2 digits")
    return Codebook(part_ids=parts, color_ids=colors)
