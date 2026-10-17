"""Stable, offline design documents and explicit v1 session migration.

This module deliberately does not use the permissive LDraw graph parser: its
fallback behavior can omit unsupported records and converts decimal tokens to
binary floats. M1 accepts only flat type-0 comments and physical type-1 parts.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import math
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

DESIGN_SCHEMA = "bricksmith-design-v1"
DESIGN_SCHEMA_V2 = "bricksmith-design-v2"
INTENT_LEDGER_SCHEMA = "bricksmith-intent-ledger-v1"
REPAIR_ATTEMPT_SCHEMA = "bricksmith-repair-attempt-v2"
SESSION_SCHEMA = "bricksmith-agent-session-v2"
MANIFEST_SCHEMA = "bricksmith-agent-session-manifest-v2"
REVISION_SCHEMA = "bricksmith-design-revision-v1"
EXPORT_SCHEMA = "bricksmith-design-export-v1"
LINE_MAP_SCHEMA = "bricksmith-line-map-v1"
MIGRATION_SCHEMA = "bricksmith-v1-session-migration-v1"
MIGRATION_VERSION = 1
MIGRATION_NAMESPACE = uuid.UUID("7e3f7118-2fc2-5e5b-8dde-b294b101e52b")
MATRIX_TOLERANCE = Decimal("0.000001")
LINE_SEPARATORS = frozenset("\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029")
NUMBER_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
MODULE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class DesignError(ValueError):
    """Invalid design, unsupported source syntax, or unsafe migration input."""


@dataclass(frozen=True)
class CatalogIndex:
    part_stems: Mapping[str, str]
    aliases: Mapping[str, Any]
    color_ids: frozenset[int]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(data: bytes) -> dict[str, str]:
    """Versioned exact-byte hash record."""
    return {"schema": "bricksmith-file-hash-v1", "algorithm": "sha256",
            "value": sha256_bytes(data)}


def _decimal_text(value: Decimal | int | float) -> str:
    if isinstance(value, bool):
        raise DesignError("Boolean is not a numeric design value")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DesignError("Design numbers must be finite")
        value = Decimal(str(value))
    elif isinstance(value, int):
        value = Decimal(value)
    if not isinstance(value, Decimal) or not value.is_finite():
        raise DesignError("Design numbers must be finite decimals")
    if value.is_zero():
        return "0"
    sign, digit_tuple, exponent = value.as_tuple()
    digits = "".join(str(digit) for digit in digit_tuple)
    while len(digits) > 1 and digits.endswith("0"):
        digits = digits[:-1]
        exponent += 1
    adjusted = len(digits) + exponent - 1
    prefix = "-" if sign else ""
    if -6 <= adjusted < 21:
        point = len(digits) + exponent
        if point <= 0:
            return prefix + "0." + "0" * (-point) + digits
        if point >= len(digits):
            return prefix + digits + "0" * (point - len(digits))
        return prefix + digits[:point] + "." + digits[point:]
    mantissa = digits[0] + ("." + digits[1:] if len(digits) > 1 else "")
    return f"{prefix}{mantissa}e{adjusted}"


def _json_text(value: Any, *, indent: int | None = 2, sort_keys: bool = True) -> str:
    """JSON encoder that emits Decimal tokens without a binary-float roundtrip."""
    step = indent if isinstance(indent, int) and indent >= 0 else None

    def encode(item: Any, depth: int) -> str:
        pad = " " * (step * depth) if step is not None else ""
        child_pad = " " * (step * (depth + 1)) if step is not None else ""
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if isinstance(item, (Decimal, int, float)) and not isinstance(item, bool):
            return _decimal_text(item)
        if isinstance(item, str):
            return json.dumps(item, ensure_ascii=False)
        if isinstance(item, list):
            if not item:
                return "[]"
            values = [encode(child, depth + 1) for child in item]
            if step is None:
                return "[" + ",".join(values) + "]"
            return "[\n" + ",\n".join(child_pad + child for child in values) + "\n" + pad + "]"
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise DesignError("JSON object keys must be strings")
            if not item:
                return "{}"
            keys = sorted(item) if sort_keys else list(item)
            pairs = [(json.dumps(key, ensure_ascii=False), encode(item[key], depth + 1)) for key in keys]
            if step is None:
                return "{" + ",".join(key + ":" + child for key, child in pairs) + "}"
            return "{\n" + ",\n".join(child_pad + key + ": " + child for key, child in pairs) + "\n" + pad + "}"
        raise DesignError(f"Unsupported JSON value type: {type(item).__name__}")

    return encode(value, 0)


def canonical_json(value: Any) -> str:
    return _json_text(value, indent=None, sort_keys=True)


def read_json(path: Path) -> Any:
    try:
        raw = path.read_bytes().decode("utf-8")
        return json.loads(raw, parse_float=Decimal,
                          parse_constant=lambda token: (_ for _ in ()).throw(
                              DesignError(f"Nonfinite JSON number {token!r} is not allowed")))
    except (OSError, UnicodeError, json.JSONDecodeError, InvalidOperation) as exc:
        raise DesignError(f"Unable to read valid UTF-8 JSON from {path}: {exc}") from exc


def _write_json(path: Path, value: Any) -> bytes:
    payload = (_json_text(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(payload)
    return payload


def _uuid(value: Any, field: str) -> str:
    if not isinstance(value, str) or not UUID_RE.fullmatch(value):
        raise DesignError(f"{field} must be a canonical UUID string")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise DesignError(f"{field} must be a valid UUID") from exc
    if str(parsed) != value:
        raise DesignError(f"{field} must use lowercase canonical UUID form")
    return value


def _new_id() -> str:
    return str(uuid.uuid4())


def _as_decimal(value: Any, field: str, *, nullable: bool = False) -> Decimal | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, float)):
        raise DesignError(f"{field} must be a finite JSON number" + (" or null" if nullable else ""))
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DesignError(f"{field} must be a finite JSON number") from exc
    if not result.is_finite():
        raise DesignError(f"{field} must be finite")
    return result


def _decimal_add_exact(left: Decimal, right: Decimal) -> Decimal:
    """Add finite Decimals as integer coefficients, independent of Decimal context."""
    if not left.is_finite() or not right.is_finite():
        raise DesignError("Design numbers must be finite")
    left_sign, left_digits, left_exponent = left.as_tuple()
    right_sign, right_digits, right_exponent = right.as_tuple()
    exponent = min(left_exponent, right_exponent)
    left_coefficient = int("".join(map(str, left_digits)) or "0")
    right_coefficient = int("".join(map(str, right_digits)) or "0")
    if left_sign:
        left_coefficient = -left_coefficient
    if right_sign:
        right_coefficient = -right_coefficient
    total = (left_coefficient * 10 ** (left_exponent - exponent)
             + right_coefficient * 10 ** (right_exponent - exponent))
    sign = int(total < 0)
    digits = tuple(int(char) for char in str(abs(total))) if total else (0,)
    return Decimal((sign, digits, exponent))


def _catalog_index(catalog: Any = None, *, aliases: Mapping[str, Any] | None = None,
                   color_ids: set[int] | frozenset[int] | None = None) -> CatalogIndex:
    if catalog is None:
        try:
            from bricknet.data import load_aliases, load_catalog
            catalog = load_catalog()
            aliases = load_aliases()
        except Exception as exc:
            raise DesignError(f"BrickNet part catalog is unavailable: {type(exc).__name__}: {exc}") from exc
    stems = getattr(catalog, "stem_to_id", None)
    if not isinstance(stems, Mapping) or not stems:
        raise DesignError("BrickNet catalog is unavailable or contains no part identifiers")
    id_to_stem = getattr(catalog, "id_to_stem", None)
    canonical: dict[str, str] = {}
    for stem, numeric_id in stems.items():
        if not isinstance(stem, str):
            continue
        if isinstance(id_to_stem, Mapping):
            resolved = id_to_stem.get(numeric_id, stem)
        elif isinstance(id_to_stem, (list, tuple)) and type(numeric_id) is int and 0 <= numeric_id < len(id_to_stem):
            resolved = id_to_stem[numeric_id]
        else:
            resolved = stem
        if isinstance(resolved, str):
            canonical[stem.casefold()] = resolved
    if color_ids is None:
        codes = getattr(catalog, "code_to_color", None)
        if not isinstance(codes, Mapping) or not codes:
            raise DesignError("BrickNet catalog has no color identifiers")
        color_ids = frozenset(code for code in codes if type(code) is int)
    if not color_ids or any(type(code) is not int for code in color_ids):
        raise DesignError("Color catalog must contain integer LDraw identifiers")
    return CatalogIndex(canonical, aliases or {}, frozenset(color_ids))


def _part_id(token: str, catalog: CatalogIndex, source: str, line: int) -> tuple[str, str]:
    if "\\" in token or any(segment == ".." for segment in token.split("/")):
        raise DesignError(f"{source}:{line}: unsafe part reference {token!r}")
    if token.startswith("/") or not token.lower().endswith(".dat"):
        raise DesignError(f"{source}:{line}: physical placement must reference a catalog .dat part")
    parts = PurePosixPath(token).parts
    if len(parts) > 2 or (len(parts) == 2 and parts[0].casefold() not in {"parts", "p"}):
        raise DesignError(f"{source}:{line}: unsupported part path {token!r}")
    stem = parts[-1][:-4]
    folded = stem.casefold()
    if folded in catalog.part_stems:
        return catalog.part_stems[folded], token
    alias_value = catalog.aliases.get(stem)
    if alias_value is None:
        alias_value = catalog.aliases.get(folded)
    candidates = alias_value if isinstance(alias_value, (list, tuple)) else [alias_value]
    for candidate in candidates:
        if isinstance(candidate, str):
            candidate_stem = candidate.removesuffix(".dat").casefold()
            if candidate_stem in catalog.part_stems:
                return catalog.part_stems[candidate_stem], token
    raise DesignError(f"{source}:{line}: unresolved LDraw part identifier {token!r}")


def _validate_comment_line(text: Any, field: str) -> None:
    if not isinstance(text, str) or not text or any(char in LINE_SEPARATORS for char in text):
        raise DesignError(f"{field} must be exactly one physical type-0 line without line separators")
    fields = text.split()
    if not fields or fields[0] != "0":
        raise DesignError(f"{field} must begin with the exact LDraw record token 0")
    directive = fields[1].casefold() if len(fields) > 1 else ""
    if directive in {"file", "nofile", "!data"} or directive.startswith("!:"):
        raise DesignError(f"{field} contains an unsupported MPD/submodel directive")


def _decimal_token(token: str, source: str, line: int, field: str) -> Decimal:
    if not NUMBER_RE.fullmatch(token):
        raise DesignError(f"{source}:{line}: {field} is not a valid decimal number: {token!r}")
    try:
        value = Decimal(token)
    except InvalidOperation as exc:
        raise DesignError(f"{source}:{line}: invalid decimal {field}: {token!r}") from exc
    if not value.is_finite():
        raise DesignError(f"{source}:{line}: {field} must be finite")
    return value


def _determinant(matrix: list[list[Decimal]]) -> Decimal:
    a, b, c = matrix
    return (a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0]))


def _validate_rotation(matrix: Any, field: str) -> list[list[Decimal]]:
    if not isinstance(matrix, list) or len(matrix) != 3:
        raise DesignError(f"{field} must be a 3x3 matrix")
    values: list[list[Decimal]] = []
    for row_index, row in enumerate(matrix):
        if not isinstance(row, list) or len(row) != 3:
            raise DesignError(f"{field}[{row_index}] must contain exactly three values")
        values.append([_as_decimal(item, f"{field}[{row_index}][{col}]") for col, item in enumerate(row)])
    for row in range(3):
        for col in range(3):
            dot = sum((values[k][row] * values[k][col] for k in range(3)), Decimal(0))
            target = Decimal(1) if row == col else Decimal(0)
            if abs(dot - target) > MATRIX_TOLERANCE:
                raise DesignError(f"{field} is not orthonormal within 1e-6 at R^T R[{row}][{col}]")
    determinant = _determinant(values)
    if abs(abs(determinant) - Decimal(1)) > MATRIX_TOLERANCE:
        raise DesignError(f"{field} determinant must have absolute value 1 within 1e-6")
    return values


def _parse_flat_ldr(content: str | bytes, *, source: str, catalog: Any = None,
                    aliases: Mapping[str, Any] | None = None,
                    color_ids: set[int] | frozenset[int] | None = None) -> dict[str, Any]:
    index = _catalog_index(catalog, aliases=aliases, color_ids=color_ids)
    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DesignError(f"{source}: source is not valid UTF-8") from exc
    else:
        text = content
    placements: list[dict[str, Any]] = []
    comments: list[dict[str, Any]] = []
    for line_number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        fields = raw.split()
        record_type = fields[0]
        if record_type == "0":
            _validate_comment_line(raw, f"{source}:{line_number}")
            comments.append({"text": raw, "source_line": line_number})
            continue
        if record_type in {"2", "3", "4", "5"}:
            raise DesignError(f"{source}:{line_number}: type-{record_type} geometry is unsupported")
        if record_type != "1":
            raise DesignError(f"{source}:{line_number}: unsupported LDraw record type {record_type!r}")
        if len(fields) != 15:
            raise DesignError(f"{source}:{line_number}: type-1 placement requires exactly 15 fields")
        if not re.fullmatch(r"\d+", fields[1]):
            raise DesignError(f"{source}:{line_number}: color identifier must be a nonnegative integer")
        color = int(fields[1])
        if color not in index.color_ids:
            raise DesignError(f"{source}:{line_number}: unresolved LDraw color identifier {color}")
        part_id, part_reference = _part_id(fields[14], index, source, line_number)
        numbers = [_decimal_token(token, source, line_number, f"placement field {position}")
                   for position, token in enumerate(fields[2:14], 1)]
        translation = numbers[:3]
        rotation = [numbers[3:6], numbers[6:9], numbers[9:12]]
        try:
            rotation = _validate_rotation(rotation, f"{source}:{line_number} rotation")
        except DesignError as exc:
            raise DesignError(str(exc)) from exc
        placements.append({"part_id": part_id, "color_id": color,
            "translation_ldu": translation, "rotation": rotation,
            "source_line": line_number, "source_part_reference": part_reference,
            "placement_ordinal": len(placements)})
    return {"placements": placements, "comments": comments, "source": source,
            "content_sha256": sha256_bytes(text.encode("utf-8"))}


def _part_semantics(parts: list[dict[str, Any]], *, appearance: bool) -> list[list[Any]]:
    rows = []
    for part in parts:
        row: list[Any] = [part["part_id"]]
        if appearance:
            row.append(part["color_id"])
        row.extend(_as_decimal(value, "part translation") for value in part["translation_ldu"])
        row.extend(_as_decimal(value, "part rotation") for matrix_row in part["rotation"] for value in matrix_row)
        rows.append(row)
    return sorted(rows, key=canonical_json)


def _physical_hash(parts: list[dict[str, Any]], *, appearance: bool) -> dict[str, str]:
    schema = "bricksmith-appearance-v1" if appearance else "bricksmith-structure-v1"
    return {"schema": schema, "algorithm": "sha256",
            "value": sha256_bytes(canonical_json(_part_semantics(parts, appearance=appearance)).encode("utf-8"))}


def refresh_hashes(design: dict[str, Any]) -> dict[str, Any]:
    """Update versioned semantic hashes in-place and return the document."""
    design["hashes"] = {
        "appearance": _physical_hash(design["parts"], appearance=True),
        "structure": _physical_hash(design["parts"], appearance=False),
        "design": {"schema": "bricksmith-design-content-v1", "algorithm": "sha256",
                   "value": sha256_bytes(canonical_json({key: value for key, value in design.items()
                       if key != "hashes"}).encode("utf-8"))},
    }
    return design


def _hash_shape(record: Any, schema: str, field: str) -> None:
    if not isinstance(record, dict) or record.get("schema") != schema or record.get("algorithm") != "sha256":
        raise DesignError(f"{field} must use {schema} with sha256")
    digest = record.get("value")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise DesignError(f"{field}.value must be a SHA-256 digest")


def _enum(value: Any, allowed: set[str], field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise DesignError(f"{field} must be one of {', '.join(sorted(allowed))}")
    return value


def _relative_artifact(value: Any, field: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or not value:
        raise DesignError(f"{field} must be a relative artifact path" + (" or null" if nullable else ""))
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise DesignError(f"{field} must stay within its artifact root")


def _json_safe(value: Any, field: str) -> None:
    try:
        canonical_json(value)
    except (DesignError, TypeError, ValueError) as exc:
        raise DesignError(f"{field} must contain valid JSON values: {exc}") from exc


def _validate_uuid_array(value: Any, field: str, known: set[str] | None = None) -> None:
    if not isinstance(value, list):
        raise DesignError(f"{field} must be an array")
    for index, item in enumerate(value):
        ref = _uuid(item, f"{field}[{index}]")
        if known is not None and ref not in known:
            raise DesignError(f"{field}[{index}] references unknown ID {ref}")


def validate_design(design: Any, *, verify_hashes: bool = True, catalog: Any = None,
                    aliases: Mapping[str, Any] | None = None,
                    color_ids: set[int] | frozenset[int] | None = None) -> None:
    """Validate a complete v1 design value, raising field-specific DesignError."""
    if not isinstance(design, dict):
        raise DesignError("design must be a JSON object")
    schema = design.get("schema")
    if schema not in {DESIGN_SCHEMA, DESIGN_SCHEMA_V2}:
        raise DesignError(f"design.schema must be {DESIGN_SCHEMA!r} or {DESIGN_SCHEMA_V2!r}")
    is_v2 = schema == DESIGN_SCHEMA_V2
    names = ("assemblies", "parts", "requirements", "decisions", "issues", "source_references", "source_comments", "historical_notes")
    _uuid(design.get("revision_id"), "revision_id")
    parent_revision = design.get("parent_revision_id")
    if parent_revision is not None:
        _uuid(parent_revision, "parent_revision_id")
    required_fields = {"brief", "brief_source", "ground_y", "piece_range", *names, "revision_id",
                       "parent_revision_id", "schema", "hashes"}
    if is_v2: required_fields.add("intent_ledger")
    missing_fields = sorted(required_fields - set(design))
    if missing_fields:
        raise DesignError(f"design is missing required fields: {', '.join(missing_fields)}")
    if "brief" not in design or (design["brief"] is not None and not isinstance(design["brief"], str)):
        raise DesignError("brief must be a string or null")
    _enum(design.get("brief_source"), {"user", "agent", "unknown", "operator"} if is_v2 else
          {"user", "agent", "unknown"}, "brief_source")
    if is_v2 and design["brief"] is not None and len(design["brief"].encode("utf-8")) > 64 * 1024:
        raise DesignError("brief exceeds 64 KiB UTF-8 bytes")
    if is_v2 and "brief_instruction_id" in design and design["brief_instruction_id"] is not None:
        _uuid(design["brief_instruction_id"], "brief_instruction_id")
    _as_decimal(design.get("ground_y"), "ground_y", nullable=True)
    piece_range = design.get("piece_range")
    if not isinstance(piece_range, dict) or set(piece_range) != {"minimum", "maximum"}:
        raise DesignError("piece_range must contain minimum and maximum")
    minimum = _as_decimal(piece_range["minimum"], "piece_range.minimum", nullable=True)
    maximum = _as_decimal(piece_range["maximum"], "piece_range.maximum", nullable=True)
    for field, bound in (("minimum", minimum), ("maximum", maximum)):
        if bound is not None and bound < 0:
            raise DesignError(f"piece_range.{field} cannot be negative")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise DesignError("piece_range.minimum cannot exceed maximum")

    for name in names:
        if not isinstance(design.get(name), list):
            raise DesignError(f"{name} must be an array")
    all_ids: set[str] = set()
    def add_id(record: dict[str, Any], field: str) -> str:
        identifier = _uuid(record.get("id"), f"{field}.id")
        if identifier in all_ids:
            raise DesignError(f"Duplicate design ID {identifier} at {field}.id")
        all_ids.add(identifier)
        return identifier

    assembly_ids: set[str] = set()
    for i, assembly in enumerate(design["assemblies"]):
        field = f"assemblies[{i}]"
        if not isinstance(assembly, dict):
            raise DesignError(f"{field} must be an object")
        assembly_id = add_id(assembly, field)
        assembly_ids.add(assembly_id)
        if not isinstance(assembly.get("name"), str) or not assembly["name"].strip():
            raise DesignError(f"{field}.name must be a nonempty string")
        if assembly.get("role") is not None and not isinstance(assembly["role"], str):
            raise DesignError(f"{field}.role must be a string or null")
        parent = assembly.get("parent_assembly_id")
        if parent is not None:
            _uuid(parent, f"{field}.parent_assembly_id")
        if not isinstance(assembly.get("design_properties"), dict):
            raise DesignError(f"{field}.design_properties must be an object")
        _json_safe(assembly["design_properties"], f"{field}.design_properties")
        if not isinstance(assembly.get("relationships"), list):
            raise DesignError(f"{field}.relationships must be an array")
        if not isinstance(assembly.get("field_locks"), list):
            raise DesignError(f"{field}.field_locks must be an array")
        for j, relationship in enumerate(assembly["relationships"]):
            rel_field = f"{field}.relationships[{j}]"
            if not isinstance(relationship, dict):
                raise DesignError(f"{rel_field} must be an object")
            add_id(relationship, rel_field)
            if not isinstance(relationship.get("kind"), str) or not relationship["kind"]:
                raise DesignError(f"{rel_field}.kind must be a nonempty string")
            _uuid(relationship.get("target_assembly_id"), f"{rel_field}.target_assembly_id")
            _enum(relationship.get("source"), {"user", "agent", "imported", "unknown"}, f"{rel_field}.source")
            _json_safe(relationship, rel_field)
        for j, lock in enumerate(assembly["field_locks"]):
            lock_field = f"{field}.field_locks[{j}]"
            if not isinstance(lock, dict):
                raise DesignError(f"{lock_field} must be an object")
            add_id(lock, lock_field)
            _enum(lock.get("owner"), {"user", "agent", "unknown"}, f"{lock_field}.owner")
            _uuid(lock.get("target_id"), f"{lock_field}.target_id")
            fields = lock.get("fields")
            if not isinstance(fields, list) or not fields or any(not isinstance(item, str) or not item for item in fields):
                raise DesignError(f"{lock_field}.fields must be a nonempty string array")
            _json_safe(lock, lock_field)
    for assembly in design["assemblies"]:
        parent = assembly.get("parent_assembly_id")
        if parent is not None and parent not in assembly_ids:
            raise DesignError(f"Assembly {assembly['id']} references unknown parent {parent}")
        for relationship in assembly["relationships"]:
            if relationship["target_assembly_id"] not in assembly_ids:
                raise DesignError(f"Relationship references unknown assembly {relationship['target_assembly_id']}")
            if "related_assembly_ids" in relationship:
                _validate_uuid_array(relationship["related_assembly_ids"],
                    f"assemblies.{assembly['id']}.relationships.related_assembly_ids", assembly_ids)
        for lock in assembly["field_locks"]:
            target = lock["target_id"]
            # Part IDs are checked after all parts have been read.
            if target not in assembly_ids and not isinstance(target, str):
                raise DesignError(f"Field lock target {target!r} is invalid")
    parents = {assembly["id"]: assembly.get("parent_assembly_id") for assembly in design["assemblies"]}
    for assembly_id in assembly_ids:
        seen: set[str] = set()
        current: str | None = assembly_id
        while current is not None:
            if current in seen:
                raise DesignError(f"Assembly parent cycle includes {current}")
            seen.add(current)
            current = parents[current]

    part_ids: set[str] = set()
    for i, part in enumerate(design["parts"]):
        field = f"parts[{i}]"
        if not isinstance(part, dict):
            raise DesignError(f"{field} must be an object")
        part_id = add_id(part, field)
        part_ids.add(part_id)
        _uuid(part.get("assembly_id"), f"{field}.assembly_id")
        if part["assembly_id"] not in assembly_ids:
            raise DesignError(f"{field}.assembly_id references unknown assembly {part['assembly_id']}")
        if not isinstance(part.get("part_id"), str) or not part["part_id"].strip():
            raise DesignError(f"{field}.part_id must be a catalog identifier")
        if type(part.get("color_id")) is not int or part["color_id"] < 0:
            raise DesignError(f"{field}.color_id must be a nonnegative integer")
        translation = part.get("translation_ldu")
        if not isinstance(translation, list) or len(translation) != 3:
            raise DesignError(f"{field}.translation_ldu must contain three LDU coordinates")
        for axis, value in zip("xyz", translation):
            _as_decimal(value, f"{field}.translation_ldu.{axis}")
        _validate_rotation(part.get("rotation"), f"{field}.rotation")
        reference = part.get("ldraw_part_reference")
        if not isinstance(reference, str) or not reference.lower().endswith(".dat") or ".." in PurePosixPath(reference).parts:
            raise DesignError(f"{field}.ldraw_part_reference must be a safe .dat reference")
        if not isinstance(part.get("provenance"), dict):
            raise DesignError(f"{field}.provenance must be an object")
        _json_safe(part["provenance"], f"{field}.provenance")
    catalog_index = _catalog_index(catalog, aliases=aliases, color_ids=color_ids)
    for i, part in enumerate(design["parts"]):
        resolved, _ = _part_id(part["ldraw_part_reference"], catalog_index, "design", i + 1)
        if resolved != part["part_id"]:
            raise DesignError(f"parts[{i}].part_id does not match its resolved LDraw catalog reference")
        if part["color_id"] not in catalog_index.color_ids:
            raise DesignError(f"parts[{i}].color_id {part['color_id']} is unresolved in the LDraw color catalog")
    issue_ids: set[str] = {item.get("id") for item in design.get("issues", []) if isinstance(item, dict)}
    for assembly in design["assemblies"]:
        for lock in assembly["field_locks"]:
            if lock["target_id"] not in assembly_ids and lock["target_id"] not in part_ids:
                raise DesignError(f"Field lock references unknown target {lock['target_id']}")

    source_reference_ids: set[str] = set()
    for i, reference in enumerate(design["source_references"]):
        field = f"source_references[{i}]"
        if not isinstance(reference, dict):
            raise DesignError(f"{field} must be an object")
        ref_id = add_id(reference, field)
        source_reference_ids.add(ref_id)
        if not isinstance(reference.get("original_source_identity"), str) or not reference["original_source_identity"]:
            raise DesignError(f"{field}.original_source_identity must be a nonempty string")
        _uuid(reference["id"], f"{field}.id")
        _hash_shape(reference.get("content_hash"), "bricksmith-file-hash-v1", f"{field}.content_hash")
        if not isinstance(reference.get("role"), str) or not reference["role"]:
            raise DesignError(f"{field}.role must be a nonempty string")
        for key in ("local_artifact_reference", "license_rights_status", "missing_data_notes"):
            if key not in reference or (reference[key] is not None and not isinstance(reference[key], str)):
                raise DesignError(f"{field}.{key} must be a string or null")
        _relative_artifact(reference["local_artifact_reference"], f"{field}.local_artifact_reference", nullable=True)
    for i, part in enumerate(design["parts"]):
        source_ref = part["provenance"].get("source_reference_id")
        if source_ref is not None and source_ref not in source_reference_ids:
            raise DesignError(f"parts[{i}].provenance.source_reference_id is unknown")
        source_file = part["provenance"].get("source_file")
        if source_file is not None:
            _relative_artifact(source_file, f"parts[{i}].provenance.source_file")
        if "source_line" in part["provenance"] and (type(part["provenance"]["source_line"]) is not int or part["provenance"]["source_line"] < 1):
            raise DesignError(f"parts[{i}].provenance.source_line must be a positive integer")
    for assembly in design["assemblies"]:
        for j, relationship in enumerate(assembly["relationships"]):
            if "evidence_reference_ids" in relationship:
                _validate_uuid_array(relationship["evidence_reference_ids"],
                    f"assemblies[{assembly['id']}].relationships[{j}].evidence_reference_ids", source_reference_ids)

    requirement_ids: set[str] = set()
    for i, requirement in enumerate(design["requirements"]):
        field = f"requirements[{i}]"
        if not isinstance(requirement, dict):
            raise DesignError(f"{field} must be an object")
        requirement_ids.add(add_id(requirement, field))
        if not isinstance(requirement.get("description"), str) or not requirement["description"]:
            raise DesignError(f"{field}.description must be a nonempty string")
        _enum(requirement.get("source"), {"user", "agent", "unknown", "operator"} if is_v2 else
              {"user", "agent", "unknown"}, f"{field}.source")
        _enum(requirement.get("priority"), {"mandatory", "preferred", "unknown"}, f"{field}.priority")
        _enum(requirement.get("status"), {"pending", "satisfied", "failed", "unverified"}, f"{field}.status")
        _validate_uuid_array(requirement.get("affected_assembly_ids"), f"{field}.affected_assembly_ids", assembly_ids)
        _validate_uuid_array(requirement.get("evidence_reference_ids"), f"{field}.evidence_reference_ids", source_reference_ids)
        if "measurable_predicate" not in requirement:
            raise DesignError(f"{field}.measurable_predicate is required (use null when unknown)")
        if is_v2:
            legacy_fields = {"id", "description", "source", "priority", "affected_assembly_ids",
                "measurable_predicate", "evidence_reference_ids", "status"}
            extended_fields = legacy_fields | {"instruction_id", "supersedes_id", "originating_operation_id"}
            if not legacy_fields <= set(requirement):
                raise DesignError(f"{field} is missing design-v1 requirement fields")
            if requirement.get("originating_operation_id") is not None:
                if set(requirement) != extended_fields:
                    raise DesignError(f"{field} has unknown or incomplete design-v2 fields")
                if len(requirement["description"].encode("utf-8")) > 16 * 1024:
                    raise DesignError(f"{field}.description exceeds 16 KiB UTF-8 bytes")
                for key in ("instruction_id", "supersedes_id"):
                    if requirement[key] is not None: _uuid(requirement[key], f"{field}.{key}")
                _uuid(requirement["originating_operation_id"], f"{field}.originating_operation_id")
        _json_safe(requirement, field)
    decision_ids: set[str] = set()
    for i, decision in enumerate(design["decisions"]):
        field = f"decisions[{i}]"
        if not isinstance(decision, dict):
            raise DesignError(f"{field} must be an object")
        decision_ids.add(add_id(decision, field))
        if not isinstance(decision.get("statement"), str) or not decision["statement"]:
            raise DesignError(f"{field}.statement must be a nonempty string")
        if not isinstance(decision.get("rationale"), str):
            raise DesignError(f"{field}.rationale must be a string")
        _enum(decision.get("source"), {"user", "agent", "unknown", "operator"} if is_v2 else
              {"user", "agent", "unknown"}, f"{field}.source")
        _enum(decision.get("status"), {"active", "superseded", "unverified"}, f"{field}.status")
        _validate_uuid_array(decision.get("related_assembly_ids"), f"{field}.related_assembly_ids", assembly_ids)
        _validate_uuid_array(decision.get("related_requirement_ids"), f"{field}.related_requirement_ids", requirement_ids)
        _validate_uuid_array(decision.get("evidence_reference_ids"), f"{field}.evidence_reference_ids", source_reference_ids)
        supersedes = decision.get("supersedes_id")
        if supersedes is not None:
            _uuid(supersedes, f"{field}.supersedes_id")
        if is_v2:
            legacy_fields = {"id", "statement", "rationale", "source", "status", "related_assembly_ids",
                "related_requirement_ids", "evidence_reference_ids", "supersedes_id"}
            extended_fields = legacy_fields | {"instruction_id", "originating_operation_id"}
            if not legacy_fields <= set(decision):
                raise DesignError(f"{field} is missing design-v1 decision fields")
            if decision.get("originating_operation_id") is not None:
                if set(decision) != extended_fields:
                    raise DesignError(f"{field} has unknown or incomplete design-v2 fields")
                if (len(decision["statement"].encode("utf-8")) > 16 * 1024
                        or len(decision["rationale"].encode("utf-8")) > 16 * 1024):
                    raise DesignError(f"{field} text exceeds 16 KiB UTF-8 bytes")
                for key in ("instruction_id", "originating_operation_id"):
                    _uuid(decision[key], f"{field}.{key}")
        _json_safe(decision, field)
    for i, decision in enumerate(design["decisions"]):
        supersedes = decision.get("supersedes_id")
        if supersedes is not None and supersedes not in decision_ids:
            raise DesignError(f"decisions[{i}].supersedes_id references unknown decision")
    if is_v2:
        def validate_supersession(records: list[dict[str, Any]], field: str) -> None:
            seen_children: set[str] = set()
            positions = {record["id"]: index for index, record in enumerate(records)}
            for index, record in enumerate(records):
                # Older C1 decisions may contain historical supersession links
                # whose ordering predates the v2 append-only rule. New records
                # carry originating_operation_id and are strictly ordered.
                if field in {"requirements", "decisions"} and "originating_operation_id" not in record:
                    continue
                target = record.get("supersedes_id")
                if target is None: continue
                if target == record["id"]: raise DesignError(f"{field}[{index}] cannot supersede itself")
                if target not in positions or positions[target] >= index:
                    raise DesignError(f"{field}[{index}].supersedes_id must reference an earlier record of the same kind")
                if target in seen_children:
                    raise DesignError(f"{field} has competing active replacements for {target}")
                seen_children.add(target)
        validate_supersession(design["requirements"], "requirements")
        validate_supersession(design["decisions"], "decisions")

        ledger = design.get("intent_ledger")
        if not isinstance(ledger, dict) or set(ledger) != {"schema", "instructions", "repair_attempts", "next_actions"}:
            raise DesignError("intent_ledger must contain exactly schema, instructions, repair_attempts, and next_actions")
        if ledger.get("schema") != INTENT_LEDGER_SCHEMA:
            raise DesignError(f"intent_ledger.schema must be {INTENT_LEDGER_SCHEMA!r}")
        for key in ("instructions", "repair_attempts", "next_actions"):
            if not isinstance(ledger.get(key), list): raise DesignError(f"intent_ledger.{key} must be an array")

        def text_field(record: dict[str, Any], key: str, field: str, *, maximum: int = 16 * 1024,
                       nonempty: bool = True) -> None:
            value = record.get(key)
            if not isinstance(value, str) or (nonempty and not value):
                raise DesignError(f"{field}.{key} must be {'nonempty ' if nonempty else ''}text")
            if len(value.encode("utf-8")) > maximum: raise DesignError(f"{field}.{key} exceeds {maximum} UTF-8 bytes")

        def timestamp(value: Any, field: str) -> None:
            if not isinstance(value, str) or not value.endswith("Z"):
                raise DesignError(f"{field} must be a UTC ISO 8601 timestamp ending in Z")
            try: parsed = datetime.datetime.fromisoformat(value[:-1] + "+00:00")
            except ValueError as exc: raise DesignError(f"{field} must be a valid UTC ISO 8601 timestamp") from exc
            if parsed.utcoffset() != datetime.timedelta(0): raise DesignError(f"{field} must be UTC")

        def evidence_refs(value: Any, field: str) -> None:
            if not isinstance(value, list): raise DesignError(f"{field} must be an array")
            for index, item in enumerate(value):
                target = f"{field}[{index}]"
                if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
                    raise DesignError(f"{target} must contain exactly path and sha256")
                _relative_artifact(item.get("path"), f"{target}.path")
                if not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
                    raise DesignError(f"{target}.sha256 must be a SHA-256 digest")

        instruction_ids: set[str] = set()
        for index, record in enumerate(ledger["instructions"]):
            field = f"intent_ledger.instructions[{index}]"
            if not isinstance(record, dict) or set(record) != {"id", "text", "source", "originating_operation_id", "created_at"}:
                raise DesignError(f"{field} has an invalid strict record shape")
            instruction_ids.add(add_id(record, field))
            text_field(record, "text", field, maximum=64 * 1024)
            _enum(record.get("source"), {"user", "operator"}, f"{field}.source")
            _uuid(record.get("originating_operation_id"), f"{field}.originating_operation_id")
            timestamp(record.get("created_at"), f"{field}.created_at")

        for index, record in enumerate(ledger["repair_attempts"]):
            field = f"intent_ledger.repair_attempts[{index}]"
            if not isinstance(record, dict) or set(record) != {"schema", "id", "issue_ids", "attempted_operation_id",
                "observed_revision_id", "recorded_revision_id", "outcome_at_recording",
                "evidence_references", "note", "originating_operation_id"}:
                raise DesignError(f"{field} has an invalid strict record shape")
            if record.get("schema") != REPAIR_ATTEMPT_SCHEMA:
                raise DesignError(f"{field}.schema must be {REPAIR_ATTEMPT_SCHEMA!r}")
            add_id(record, field)
            _validate_uuid_array(record.get("issue_ids"), f"{field}.issue_ids", issue_ids)
            _uuid(record.get("attempted_operation_id"), f"{field}.attempted_operation_id")
            _uuid(record.get("observed_revision_id"), f"{field}.observed_revision_id")
            _uuid(record.get("recorded_revision_id"), f"{field}.recorded_revision_id")
            _uuid(record.get("originating_operation_id"), f"{field}.originating_operation_id")
            outcome = record.get("outcome_at_recording")
            outcome_fields = {"schema", "disposition", "attempted_base_revision_id", "candidate_id",
                "revision_id", "report_sha256", "policy_status", "construction_status", "receipt_sha256"}
            if not isinstance(outcome, dict) or set(outcome) != outcome_fields or outcome.get("schema") != "bricksmith-repair-outcome-v1":
                raise DesignError(f"{field}.outcome_at_recording has an invalid strict outcome shape")
            _enum(outcome.get("disposition"), {"committed", "candidate", "failed", "aborted", "discarded"},
                  f"{field}.outcome_at_recording.disposition")
            _uuid(outcome.get("attempted_base_revision_id"), f"{field}.outcome_at_recording.attempted_base_revision_id")
            for key in ("candidate_id", "revision_id"):
                if outcome.get(key) is not None: _uuid(outcome[key], f"{field}.outcome_at_recording.{key}")
            for key in ("report_sha256", "receipt_sha256"):
                if outcome.get(key) is not None and (not isinstance(outcome[key], str)
                        or not re.fullmatch(r"[0-9a-f]{64}", outcome[key])):
                    raise DesignError(f"{field}.outcome_at_recording.{key} must be a SHA-256 digest or null")
            for key in ("policy_status", "construction_status"):
                if outcome.get(key) is not None and not isinstance(outcome[key], str):
                    raise DesignError(f"{field}.outcome_at_recording.{key} must be text or null")
            evidence_refs(record.get("evidence_references"), f"{field}.evidence_references")
            if record.get("note") is not None: text_field(record, "note", field, nonempty=False)

        action_ids: set[str] = set()
        for index, record in enumerate(ledger["next_actions"]):
            field = f"intent_ledger.next_actions[{index}]"
            if not isinstance(record, dict) or set(record) != {"id", "description", "kind", "related_requirement_ids",
                "related_issue_ids", "source", "evidence_references", "status", "supersedes_id", "originating_operation_id"}:
                raise DesignError(f"{field} has an invalid strict record shape")
            action_ids.add(add_id(record, field))
            text_field(record, "description", field)
            _enum(record.get("kind"), {"inspect", "research", "edit", "check", "render", "review", "finalize"}, f"{field}.kind")
            _validate_uuid_array(record.get("related_requirement_ids"), f"{field}.related_requirement_ids", requirement_ids)
            _validate_uuid_array(record.get("related_issue_ids"), f"{field}.related_issue_ids", issue_ids)
            _enum(record.get("source"), {"agent", "operator"}, f"{field}.source")
            evidence_refs(record.get("evidence_references"), f"{field}.evidence_references")
            _enum(record.get("status"), {"pending", "done", "cancelled"}, f"{field}.status")
            if record.get("supersedes_id") is not None: _uuid(record["supersedes_id"], f"{field}.supersedes_id")
            _uuid(record.get("originating_operation_id"), f"{field}.originating_operation_id")
        validate_supersession(ledger["next_actions"], "intent_ledger.next_actions")

        for category in ("requirements", "decisions"):
            for index, record in enumerate(design[category]):
                if "instruction_id" in record and record["instruction_id"] is not None and record["instruction_id"] not in instruction_ids:
                    raise DesignError(f"{category}[{index}].instruction_id references unknown instruction")
        brief_instruction_id = design.get("brief_instruction_id")
        if brief_instruction_id is not None and brief_instruction_id not in instruction_ids:
            raise DesignError("brief_instruction_id references unknown instruction")

        counted = (design["requirements"] + design["decisions"] + design["issues"] +
                   design["source_references"] + ledger["instructions"] + ledger["repair_attempts"] +
                   ledger["next_actions"])
        if len(counted) > 2000: raise DesignError("design-v2 ledger record count exceeds 2,000")
        size = len(canonical_json({"requirements": design["requirements"], "decisions": design["decisions"],
            "issues": design["issues"], "source_references": design["source_references"],
            "intent_ledger": ledger}).encode("utf-8"))
        if size > 2 * 1024 * 1024: raise DesignError("design-v2 ledger data exceeds 2 MiB canonical JSON")
    known_reference_ids = assembly_ids | part_ids | requirement_ids | decision_ids | source_reference_ids
    for i, issue in enumerate(design["issues"]):
        field = f"issues[{i}]"
        if not isinstance(issue, dict):
            raise DesignError(f"{field} must be an object")
        issue_ids.add(add_id(issue, field))
        if not isinstance(issue.get("kind"), str) or not issue["kind"]:
            raise DesignError(f"{field}.kind must be a nonempty string")
        if is_v2 and "originating_operation_id" in issue:
            _uuid(issue["originating_operation_id"], f"{field}.originating_operation_id")
            _uuid(issue.get("originating_revision_id"), f"{field}.originating_revision_id")
            for key in ("kind", "next_proposed_action"):
                if not isinstance(issue.get(key), str): raise DesignError(f"{field}.{key} must be text")
                if len(issue[key].encode("utf-8")) > 16 * 1024:
                    raise DesignError(f"{field}.{key} exceeds 16 KiB UTF-8 bytes")
        _enum(issue.get("status"), {"open", "resolved", "unverified"}, f"{field}.status")
        _validate_uuid_array(issue.get("affected_ids"), f"{field}.affected_ids", known_reference_ids)
        _validate_uuid_array(issue.get("evidence_reference_ids"), f"{field}.evidence_reference_ids", source_reference_ids)
        for key in ("first_observation_revision_id", "last_observation_revision_id"):
            if issue.get(key) is not None:
                _uuid(issue[key], f"{field}.{key}")
        _validate_uuid_array(issue.get("attempted_operation_ids"), f"{field}.attempted_operation_ids")
        _json_safe(issue, field)

    for i, comment in enumerate(design["source_comments"]):
        field = f"source_comments[{i}]"
        if not isinstance(comment, dict):
            raise DesignError(f"{field} must be an object")
        _validate_comment_line(comment.get("text"), f"{field}.text")
        assembly_id = comment.get("assembly_id")
        if assembly_id is not None and assembly_id not in assembly_ids:
            raise DesignError(f"{field}.assembly_id references unknown assembly")
        source_ref = comment.get("source_reference_id")
        if source_ref is not None and source_ref not in source_reference_ids:
            raise DesignError(f"{field}.source_reference_id references unknown source")
        if type(comment.get("source_line")) is not int or comment["source_line"] < 1:
            raise DesignError(f"{field}.source_line must be a positive integer")
        if comment.get("source_file") is not None:
            _relative_artifact(comment["source_file"], f"{field}.source_file")
    for i, note in enumerate(design["historical_notes"]):
        field = f"historical_notes[{i}]"
        if not isinstance(note, dict) or not isinstance(note.get("text"), str):
            raise DesignError(f"{field} must contain historical text")
        _enum(note.get("source"), {"user", "agent", "unknown"}, f"{field}.source")
        if note.get("status") != "historical_unverified":
            raise DesignError(f"{field} must retain source and historical_unverified status")
    if verify_hashes:
        hashes = design.get("hashes")
        if not isinstance(hashes, dict):
            raise DesignError("hashes must be an object")
        for key, schema in (("appearance", "bricksmith-appearance-v1"),
                            ("structure", "bricksmith-structure-v1"),
                            ("design", "bricksmith-design-content-v1")):
            _hash_shape(hashes.get(key), schema, f"hashes.{key}")
        expected = copy.deepcopy(design)
        refresh_hashes(expected)
        for key in ("appearance", "structure", "design"):
            if expected["hashes"][key] != hashes[key]:
                raise DesignError(f"hashes.{key} does not match design contents")


def _fresh_revision(parent: str | None = None) -> str:
    return _new_id()


def _assembly(identifier: str, name: str, *, parent: str | None = None, role: str | None = None) -> dict[str, Any]:
    return {"id": identifier, "name": name, "role": role, "parent_assembly_id": parent,
            "design_properties": {}, "relationships": [], "field_locks": []}


def _blank_design(*, revision_id: str, parent_revision_id: str | None, brief: str | None,
                  brief_source: str, ground_y: Any, piece_range: dict[str, Any],
                  assemblies: list[dict[str, Any]], parts: list[dict[str, Any]],
                  source_references: list[dict[str, Any]], source_comments: list[dict[str, Any]],
                  historical_notes: list[dict[str, Any]] | None = None,
                  catalog: Any = None, aliases: Mapping[str, Any] | None = None,
                  color_ids: set[int] | frozenset[int] | None = None) -> dict[str, Any]:
    design = {"schema": DESIGN_SCHEMA, "revision_id": revision_id,
        "parent_revision_id": parent_revision_id, "brief": brief, "brief_source": brief_source,
        "ground_y": ground_y, "piece_range": piece_range, "assemblies": assemblies,
        "parts": parts, "requirements": [], "decisions": [], "issues": [],
        "source_references": source_references, "source_comments": source_comments,
        "historical_notes": historical_notes or []}
    refresh_hashes(design)
    validate_design(design, catalog=catalog, aliases=aliases, color_ids=color_ids)
    return design


def import_ldr(content_or_path: str | bytes | Path, *, catalog: Any = None,
               aliases: Mapping[str, Any] | None = None,
               color_ids: set[int] | frozenset[int] | None = None,
               ground_y: Any = None, minimum_pieces: Any = None,
               maximum_pieces: Any = None, brief: str | None = None,
               source_name: str | None = None) -> dict[str, Any]:
    """Import strict flat LDraw and allocate stable random identities once."""
    if isinstance(content_or_path, Path):
        path = content_or_path
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise DesignError(f"Unable to read LDraw source {path}: {exc}") from exc
        source = source_name or path.name
    elif isinstance(content_or_path, bytes):
        content = content_or_path
        source = source_name or "<bytes>"
    else:
        content = content_or_path.encode("utf-8")
        source = source_name or "<memory>"
    parsed = _parse_flat_ldr(content, source=source, catalog=catalog,
                             aliases=aliases, color_ids=color_ids)
    index = _catalog_index(catalog, aliases=aliases, color_ids=color_ids)
    revision_id, assembly_id, source_id = _new_id(), _new_id(), _new_id()
    source_hash = file_hash(content)
    reference = {"id": source_id, "original_source_identity": parsed["content_sha256"],
        "content_hash": source_hash, "role": "design_source", "local_artifact_reference": None,
        "license_rights_status": "unknown", "missing_data_notes": None}
    parts = []
    for item in parsed["placements"]:
        parts.append({"id": _new_id(), "assembly_id": assembly_id,
            "part_id": item["part_id"], "color_id": item["color_id"],
            "translation_ldu": item["translation_ldu"], "rotation": item["rotation"],
            "ldraw_part_reference": item["source_part_reference"],
            "provenance": {"source_reference_id": source_id, "source_file": source,
                "source_line": item["source_line"], "placement_ordinal": item["placement_ordinal"]}})
    comments = [{**item, "assembly_id": assembly_id, "source_reference_id": source_id}
                for item in parsed["comments"]]
    range_value = {"minimum": minimum_pieces, "maximum": maximum_pieces}
    index  # Resolve catalog once at the boundary; values are canonical in each part.
    return _blank_design(revision_id=revision_id, parent_revision_id=None, brief=brief,
        brief_source="user" if brief is not None else "unknown", ground_y=ground_y,
        piece_range=range_value, assemblies=[_assembly(assembly_id, "Imported design")],
        parts=parts, source_references=[reference], source_comments=comments,
        catalog=catalog, aliases=aliases, color_ids=color_ids)


def _catalog_part_id(part_id: str, catalog: CatalogIndex) -> str:
    if part_id.casefold() in catalog.part_stems:
        return catalog.part_stems[part_id.casefold()]
    raise DesignError(f"unresolved catalog part identifier {part_id!r}")


def _ids_or_default(design: dict[str, Any], part_ids: list[str] | None,
                    assembly_ids: list[str] | None) -> list[dict[str, Any]]:
    if part_ids is not None and not isinstance(part_ids, list):
        raise DesignError("part_ids selector must be an array")
    if assembly_ids is not None and not isinstance(assembly_ids, list):
        raise DesignError("assembly_ids selector must be an array")
    known_parts = {part["id"]: part for part in design["parts"]}
    known_assemblies = {assembly["id"]: assembly for assembly in design["assemblies"]}
    selected_parts: set[str] = set()
    if part_ids is None and assembly_ids is None:
        return list(design["parts"])
    for part_id in part_ids or []:
        _uuid(part_id, "part selector")
        if part_id not in known_parts:
            raise DesignError(f"Unknown part selector {part_id}")
        selected_parts.add(part_id)
    children: dict[str, set[str]] = {assembly_id: set() for assembly_id in known_assemblies}
    for assembly in design["assemblies"]:
        parent = assembly.get("parent_assembly_id")
        if parent is not None:
            children[parent].add(assembly["id"])
    for assembly_id in assembly_ids or []:
        _uuid(assembly_id, "assembly selector")
        if assembly_id not in known_assemblies:
            raise DesignError(f"Unknown assembly selector {assembly_id}")
        descendants = {assembly_id}
        stack = [assembly_id]
        while stack:
            current = stack.pop()
            for child in children[current]:
                if child not in descendants:
                    descendants.add(child)
                    stack.append(child)
        selected_parts.update(part["id"] for part in design["parts"] if part["assembly_id"] in descendants)
    return [known_parts[part_id] for part_id in sorted(selected_parts)]


def _validate_line_map_shape(line_map: Any) -> None:
    if not isinstance(line_map, dict) or set(line_map) != {"schema", "revision_id", "exports"}:
        raise DesignError("line_map must contain exactly schema, revision_id, and exports")
    if line_map.get("schema") != LINE_MAP_SCHEMA:
        raise DesignError(f"line_map.schema must be {LINE_MAP_SCHEMA!r}")
    _uuid(line_map.get("revision_id"), "line_map.revision_id")
    exports = line_map.get("exports")
    if not isinstance(exports, dict):
        raise DesignError("line_map.exports must be an object")
    for path, record in exports.items():
        field = f"line_map.exports[{path!r}]"
        if not isinstance(path, str) or not isinstance(record, dict):
            raise DesignError(f"{field} must be an object")
        if set(record) != {"revision_id", "file_sha256", "placements"}:
            raise DesignError(f"{field} must contain exactly revision_id, file_sha256, and placements")
        _uuid(record.get("revision_id"), f"{field}.revision_id")
        if record["revision_id"] != line_map["revision_id"]:
            raise DesignError(f"{field}.revision_id differs from line_map.revision_id")
        if not isinstance(record.get("file_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", record["file_sha256"]):
            raise DesignError(f"{field}.file_sha256 must be a SHA-256 digest")
        placements = record.get("placements")
        if not isinstance(placements, list):
            raise DesignError(f"{field}.placements must be an array")
        seen_lines: set[int] = set()
        seen_parts: set[str] = set()
        for index, placement in enumerate(placements):
            placement_field = f"{field}.placements[{index}]"
            if not isinstance(placement, dict) or set(placement) != {"line", "part_id", "assembly_id"}:
                raise DesignError(f"{placement_field} must contain exactly line, part_id, and assembly_id")
            line = placement.get("line")
            if type(line) is not int or line < 1:
                raise DesignError(f"{placement_field}.line must be a positive integer")
            part_id = _uuid(placement.get("part_id"), f"{placement_field}.part_id")
            _uuid(placement.get("assembly_id"), f"{placement_field}.assembly_id")
            if line in seen_lines:
                raise DesignError(f"{field} contains duplicate placement line {line}")
            if part_id in seen_parts:
                raise DesignError(f"{field} contains duplicate part ID {part_id}")
            seen_lines.add(line)
            seen_parts.add(part_id)


def _expected_line_map(design: dict[str, Any], *, catalog: Any = None,
                       aliases: Mapping[str, Any] | None = None,
                       color_ids: set[int] | frozenset[int] | None = None) -> tuple[dict[str, Any], dict[str, bytes]]:
    exports: dict[str, Any] = {}
    payloads: dict[str, bytes] = {}
    generated: list[tuple[str, str | None]] = [("build.ldr", None)]
    generated.extend((f"modules/{assembly['id']}.ldr", assembly["id"])
                     for assembly in sorted(design["assemblies"], key=lambda item: item["id"]))
    for path, assembly_id in generated:
        payload, placements = _export_text(design, assembly_id)
        _verify_export_payload(design, assembly_id, payload, placements,
            catalog=catalog, aliases=aliases, color_ids=color_ids, artifact=path)
        payloads[path] = payload
        exports[path] = {"revision_id": design["revision_id"],
            "file_sha256": sha256_bytes(payload), "placements": placements}
    return {"schema": LINE_MAP_SCHEMA, "revision_id": design["revision_id"],
            "exports": exports}, payloads


def _validate_line_map_for_design(line_map: Any, design: dict[str, Any], *,
                                  catalog: Any = None,
                                  aliases: Mapping[str, Any] | None = None,
                                  color_ids: set[int] | frozenset[int] | None = None) -> dict[str, Any]:
    _validate_line_map_shape(line_map)
    if line_map["revision_id"] != design["revision_id"]:
        raise DesignError("line_map.revision_id does not match the design revision")
    expected, _ = _expected_line_map(design, catalog=catalog, aliases=aliases, color_ids=color_ids)
    known_parts = {part["id"]: part for part in design["parts"]}
    known_assemblies = {assembly["id"] for assembly in design["assemblies"]}
    if set(line_map["exports"]) != set(expected["exports"]):
        raise DesignError("line_map.exports does not contain exactly the design's build and module exports")
    for path, record in line_map["exports"].items():
        if path not in expected["exports"]:
            raise DesignError(f"line_map.exports contains unsupported export path {path!r}")
        for index, placement in enumerate(record["placements"]):
            field = f"line_map.exports[{path!r}].placements[{index}]"
            if placement["part_id"] not in known_parts:
                raise DesignError(f"{field}.part_id references an unknown design part")
            if placement["assembly_id"] not in known_assemblies:
                raise DesignError(f"{field}.assembly_id references an unknown design assembly")
            if known_parts[placement["part_id"]]["assembly_id"] != placement["assembly_id"]:
                raise DesignError(f"{field}.assembly_id does not own its mapped part")
        expected_record = expected["exports"][path]
        if record["file_sha256"] != expected_record["file_sha256"]:
            raise DesignError(f"line_map.exports[{path!r}].file_sha256 does not match deterministic export")
        if record["placements"] != expected_record["placements"]:
            raise DesignError(f"line_map.exports[{path!r}].placements do not match deterministic export lines and ownership")
    return expected["exports"]


def inspect_design(design: dict[str, Any], *, part_ids: list[str] | None = None,
                   assembly_ids: list[str] | None = None,
                   export_path: str | None = None, export_sha256: str | None = None,
                   line_map: dict[str, Any] | None = None, catalog: Any = None,
                   aliases: Mapping[str, Any] | None = None,
                   color_ids: set[int] | frozenset[int] | None = None) -> dict[str, Any]:
    validate_design(design, catalog=catalog, aliases=aliases, color_ids=color_ids)
    selected = _ids_or_default(design, part_ids, assembly_ids)
    coordinates = [[_as_decimal(value, "translation") for value in part["translation_ldu"]]
                   for part in selected]
    bounds = None
    if coordinates:
        bounds = {"min_ldu": [min(row[axis] for row in coordinates) for axis in range(3)],
                  "max_ldu": [max(row[axis] for row in coordinates) for axis in range(3)],
                  "basis": "placement origins"}
    result: dict[str, Any] = {"revision_id": design["revision_id"],
        "selected_part_ids": sorted(part["id"] for part in selected),
        "selected_assembly_ids": sorted({part["assembly_id"] for part in selected}),
        "piece_count": len(selected), "bounds": bounds}
    if export_path is not None or line_map is not None:
        if not isinstance(export_path, str) or not isinstance(line_map, dict):
            raise DesignError("An export path and its line map are both required for line-number inspection")
        expected_exports = _validate_line_map_for_design(line_map, design, catalog=catalog,
            aliases=aliases, color_ids=color_ids)
        entry = line_map["exports"].get(export_path)
        if not isinstance(entry, dict):
            raise DesignError("Line map has no export entry for this design revision")
        expected_entry = expected_exports.get(export_path)
        if expected_entry is None:
            raise DesignError(f"Unknown export path {export_path!r} for this design")
        if not isinstance(export_sha256, str) or export_sha256 != entry.get("file_sha256") or export_sha256 != expected_entry["file_sha256"]:
            raise DesignError("Line map file hash does not match the supplied export identity")
        selected_ids = {part["id"] for part in selected}
        result["export_identity"] = {"path": export_path, "file_sha256": expected_entry["file_sha256"]}
        result["export_lines"] = [item for item in expected_entry["placements"] if item["part_id"] in selected_ids]
    return result


def move_parts(design: dict[str, Any], part_ids: list[str], *, dx: Any = 0,
               dy: Any = 0, dz: Any = 0, catalog: Any = None,
               aliases: Mapping[str, Any] | None = None,
               color_ids: set[int] | frozenset[int] | None = None) -> dict[str, Any]:
    """Return an in-memory child revision moving selected stable part IDs."""
    validate_design(design, catalog=catalog, aliases=aliases, color_ids=color_ids)
    selected = {part["id"] for part in _ids_or_default(design, part_ids, [])}
    delta = [_as_decimal(dx, "dx"), _as_decimal(dy, "dy"), _as_decimal(dz, "dz")]
    result = copy.deepcopy(design)
    result["parent_revision_id"] = result["revision_id"]
    result["revision_id"] = _new_id()
    for part in result["parts"]:
        if part["id"] in selected:
            part["translation_ldu"] = [_decimal_add_exact(_as_decimal(v, "translation"), change)
                                        for v, change in zip(part["translation_ldu"], delta)]
    refresh_hashes(result)
    validate_design(result, catalog=catalog, aliases=aliases, color_ids=color_ids)
    return result


def recolor_parts(design: dict[str, Any], part_ids: list[str], color_id: int, *,
                  catalog: Any = None, aliases: Mapping[str, Any] | None = None,
                  color_ids: set[int] | frozenset[int] | None = None) -> dict[str, Any]:
    """Return an in-memory child revision recoloring selected stable IDs."""
    validate_design(design, catalog=catalog, aliases=aliases, color_ids=color_ids)
    index = _catalog_index(catalog, aliases=aliases, color_ids=color_ids)
    if type(color_id) is not int or color_id not in index.color_ids:
        raise DesignError(f"Unresolved LDraw color identifier {color_id!r}")
    selected = {part["id"] for part in _ids_or_default(design, part_ids, [])}
    result = copy.deepcopy(design)
    result["parent_revision_id"] = result["revision_id"]
    result["revision_id"] = _new_id()
    for part in result["parts"]:
        if part["id"] in selected:
            part["color_id"] = color_id
    refresh_hashes(result)
    validate_design(result, catalog=catalog, aliases=aliases, color_ids=color_ids)
    return result


def _format_number(value: Any) -> str:
    return _decimal_text(_as_decimal(value, "export number"))


def _export_text(design: dict[str, Any], assembly_id: str | None = None) -> tuple[bytes, list[dict[str, Any]]]:
    parts = [part for part in design["parts"] if assembly_id is None or part["assembly_id"] == assembly_id]
    parts.sort(key=lambda part: (part["assembly_id"], part["id"]))
    comments = [comment for comment in design["source_comments"]
                if assembly_id is None or comment["assembly_id"] in {None, assembly_id}]
    comments.sort(key=lambda item: (item.get("source_file", ""), item["source_line"], item["text"]))
    lines = ["0 BrickSmith deterministic design export"]
    lines.extend(comment["text"] for comment in comments)
    placement_map = []
    for part in parts:
        matrix = [_as_decimal(value, "rotation") for row in part["rotation"] for value in row]
        translation = [_as_decimal(value, "translation") for value in part["translation_ldu"]]
        reference = part.get("ldraw_part_reference") or f"{part['part_id']}.dat"
        line = "1 " + str(part["color_id"]) + " " + " ".join(
            _format_number(value) for value in translation + matrix) + " " + reference
        lines.append(line)
        placement_map.append({"line": len(lines), "part_id": part["id"], "assembly_id": part["assembly_id"]})
    return ("\n".join(lines) + "\n").encode("utf-8"), placement_map


def _verify_export_payload(design: dict[str, Any], assembly_id: str | None,
                           payload: bytes, placement_map: Any, *, catalog: Any = None,
                           aliases: Mapping[str, Any] | None = None,
                           color_ids: set[int] | frozenset[int] | None = None,
                           artifact: str) -> None:
    """Check the exact serialized placements and their stable-ID line mapping."""
    if assembly_id is not None and assembly_id not in {a["id"] for a in design["assemblies"]}:
        raise DesignError(f"{artifact} refers to an unknown assembly")
    expected_parts = [part for part in design["parts"]
                      if assembly_id is None or part["assembly_id"] == assembly_id]
    expected_parts.sort(key=lambda part: (part["assembly_id"], part["id"]))
    parsed = _parse_flat_ldr(payload, source=artifact, catalog=catalog,
                             aliases=aliases, color_ids=color_ids)["placements"]
    if _physical_hash(parsed, appearance=True) != _physical_hash(expected_parts, appearance=True):
        raise DesignError(f"{artifact} physical placement multiset differs from the design")
    if not isinstance(placement_map, list) or len(placement_map) != len(expected_parts):
        raise DesignError(f"{artifact} line map does not cover every physical placement")
    if len(parsed) != len(expected_parts):
        raise DesignError(f"{artifact} contains a different number of physical placements")
    for index, (part, parsed_part, entry) in enumerate(zip(expected_parts, parsed, placement_map)):
        expected_entry = {"line": parsed_part["source_line"], "part_id": part["id"],
                          "assembly_id": part["assembly_id"]}
        if entry != expected_entry:
            raise DesignError(f"{artifact} line-map placement {index} does not match design ownership/line")
        if _part_semantics([parsed_part], appearance=True) != _part_semantics([part], appearance=True):
            raise DesignError(f"{artifact} line {expected_entry['line']} does not match mapped part {part['id']}")


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _new_file(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def write_design(path: Path, design: dict[str, Any], *, catalog: Any = None,
                 aliases: Mapping[str, Any] | None = None,
                 color_ids: set[int] | frozenset[int] | None = None) -> dict[str, Any]:
    validate_design(design, catalog=catalog, aliases=aliases, color_ids=color_ids)
    payload = (_json_text(design, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _new_file(path, payload)
    return {"path": str(path.resolve()), "file_sha256": sha256_bytes(payload),
            "revision_id": design["revision_id"], "design_hash": design["hashes"]["design"]["value"]}


def load_design(path: Path, *, catalog: Any = None, aliases: Mapping[str, Any] | None = None,
                color_ids: set[int] | frozenset[int] | None = None) -> dict[str, Any]:
    value = read_json(path)
    validate_design(value, catalog=catalog, aliases=aliases, color_ids=color_ids)
    return value


def export_design(design: dict[str, Any], destination: Path, *, catalog: Any = None,
                  aliases: Mapping[str, Any] | None = None,
                  color_ids: set[int] | frozenset[int] | None = None) -> dict[str, Any]:
    """Publish a deterministic export bundle to a new destination directory."""
    validate_design(design, catalog=catalog, aliases=aliases, color_ids=color_ids)
    destination = destination.expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Destination already exists: {destination}")
    parent = destination.parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=parent))
    try:
        all_exports: dict[str, Any] = {}
        build_bytes, build_placements = _export_text(design)
        _verify_export_payload(design, None, build_bytes, build_placements,
            catalog=catalog, aliases=aliases, color_ids=color_ids, artifact="build.ldr")
        (temporary / "build.ldr").write_bytes(build_bytes)
        all_exports["build.ldr"] = {"revision_id": design["revision_id"],
            "file_sha256": sha256_bytes(build_bytes), "placements": build_placements}
        for assembly in sorted(design["assemblies"], key=lambda item: item["id"]):
            rel = f"modules/{assembly['id']}.ldr"
            module_path = temporary / rel
            if not _within(module_path, temporary):
                raise DesignError("Generated module path escaped export destination")
            module_path.parent.mkdir(parents=True, exist_ok=True)
            payload, placements = _export_text(design, assembly["id"])
            _verify_export_payload(design, assembly["id"], payload, placements,
                catalog=catalog, aliases=aliases, color_ids=color_ids, artifact=rel)
            module_path.write_bytes(payload)
            all_exports[rel] = {"revision_id": design["revision_id"],
                "file_sha256": sha256_bytes(payload), "placements": placements}
        # Keep the export bundle shape stable for designs with no assemblies;
        # revision sealing copies this directory even when the module set is empty.
        (temporary / "modules").mkdir(exist_ok=True)
        (temporary / "design.json").write_bytes((_json_text(design, indent=2, sort_keys=True) + "\n").encode())
        line_map = {"schema": LINE_MAP_SCHEMA, "revision_id": design["revision_id"], "exports": all_exports}
        (temporary / "line_map.json").write_bytes((_json_text(line_map, indent=2, sort_keys=True) + "\n").encode())
        revision = {"schema": REVISION_SCHEMA, "revision_id": design["revision_id"],
            "parent_revision_id": design["parent_revision_id"], "hashes": design["hashes"],
            "exports": {path: record["file_sha256"] for path, record in all_exports.items()}}
        (temporary / "revision.json").write_bytes((_json_text(revision, indent=2, sort_keys=True) + "\n").encode())
        manifest = {"schema": EXPORT_SCHEMA, "revision_id": design["revision_id"],
            "design_hash": design["hashes"]["design"]["value"],
            "files": {str(file.relative_to(temporary)): sha256_bytes(file.read_bytes())
                      for file in sorted(temporary.rglob("*")) if file.is_file()}}
        (temporary / "manifest.json").write_bytes((_json_text(manifest, indent=2, sort_keys=True) + "\n").encode())
        # Validate all artifacts and exact line-map bindings before publication.
        validate_design(read_json(temporary / "design.json"), catalog=catalog,
                        aliases=aliases, color_ids=color_ids)
        for rel, entry in all_exports.items():
            output = temporary / rel
            if sha256_bytes(output.read_bytes()) != entry["file_sha256"]:
                raise DesignError(f"Export hash changed before publication: {rel}")
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"Destination already exists: {destination}")
        os.rename(temporary, destination)
        return {"destination": str(destination), "revision_id": design["revision_id"],
            "design_hash": design["hashes"]["design"]["value"],
            "build_sha256": all_exports["build.ldr"]["file_sha256"],
            "line_map": str(destination / "line_map.json"), "files": sorted(manifest["files"])}
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _relative_file(root: Path, relative: str, *, required: bool = True) -> Path | None:
    rel = PurePosixPath(relative)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise DesignError(f"Unsafe source artifact path {relative!r}")
    path = root.joinpath(*rel.parts)
    if path.is_symlink():
        resolved = path.resolve(strict=False)
        if not _within(resolved, root):
            raise DesignError(f"Source artifact escapes the session directory: {relative}")
        raise DesignError(f"Symlinked source artifacts are not accepted: {relative}")
    if not _within(path, root):
        raise DesignError(f"Source artifact escapes the session directory: {relative}")
    if not path.is_file():
        if required:
            raise DesignError(f"Missing source artifact: {relative}")
        return None
    return path


def _input_identity(file_bytes: Mapping[str, bytes]) -> tuple[str, list[dict[str, Any]]]:
    records = [{"path": path, "sha256": sha256_bytes(data)}
               for path, data in sorted(file_bytes.items())]
    return sha256_bytes(canonical_json(records).encode("utf-8")), records


def _target_piece_range(value: Any) -> dict[str, Any]:
    if value is None:
        return {"minimum": None, "maximum": None}
    if isinstance(value, bool):
        return {"minimum": None, "maximum": None}
    if isinstance(value, (int, Decimal)):
        amount = _as_decimal(value, "target_pieces")
        return {"minimum": amount, "maximum": amount}
    if not isinstance(value, str):
        return {"minimum": None, "maximum": None}
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(\d+(?:\.\d+)?)\s*", value, re.IGNORECASE)
    if match:
        return {"minimum": Decimal(match.group(1)), "maximum": Decimal(match.group(2))}
    single = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*", value)
    if single:
        amount = Decimal(single.group(1))
        return {"minimum": amount, "maximum": amount}
    return {"minimum": None, "maximum": None}


def _deterministic_uuid(name: str) -> str:
    return str(uuid.uuid5(MIGRATION_NAMESPACE, name))


def _legacy_usage(state: dict[str, Any]) -> dict[str, int | None]:
    events = state.get("events", [])
    result: dict[str, int | None] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        observed: list[int] = []
        complete = True
        for event in events if isinstance(events, list) else []:
            usage = event.get("usage") if isinstance(event, dict) else None
            amount = usage.get(key) if isinstance(usage, dict) else None
            if type(amount) is not int or amount < 0:
                complete = False
            else:
                observed.append(amount)
        result[key] = sum(observed) if complete else None
    return result


def _migration_field_dispositions(state: dict[str, Any]) -> dict[str, str]:
    dispositions = {}
    for key in sorted(state):
        if key == "brief":
            outcome = "retained_as_user_brief"
        elif key in {"ground_y", "target_pieces", "model", "reference_image"}:
            outcome = "retained_as_explicit_configuration"
        elif key == "plan":
            outcome = "retained_as_historical_unverified_prose"
        elif key in {"schema", "module_order"}:
            outcome = "used_as_migration_input"
        else:
            outcome = "unmigrated_historical_field"
        dispositions[key] = outcome
    return dispositions


def _all_v1_session_inputs(root: Path, state: dict[str, Any], module_paths: dict[str, Path],
                           build_path: Path | None) -> dict[str, bytes]:
    paths: dict[str, Path] = {"state.json": root / "state.json"}
    paths.update({f"modules/{name}.ldr": path for name, path in module_paths.items()})
    if build_path is not None:
        paths["build.ldr"] = build_path
    return {relative: path.read_bytes() for relative, path in sorted(paths.items())}


def _parse_session_build(content: bytes, source: str, *, catalog: Any,
                         aliases: Mapping[str, Any] | None,
                         color_ids: set[int] | frozenset[int] | None) -> list[dict[str, Any]]:
    return _parse_flat_ldr(content, source=source, catalog=catalog,
                           aliases=aliases, color_ids=color_ids)["placements"]


def _placement_hash(placements: list[dict[str, Any]]) -> str:
    return _physical_hash(placements, appearance=True)["value"]


def _write_migrated_revision(root: Path, design: dict[str, Any], *, catalog: Any = None,
                             aliases: Mapping[str, Any] | None = None,
                             color_ids: set[int] | frozenset[int] | None = None) -> dict[str, Any]:
    revision_id = design["revision_id"]
    revision_root = root / "revisions" / revision_id
    modules_root = revision_root / "modules"
    modules_root.mkdir(parents=True)
    build_bytes, build_placements = _export_text(design)
    _verify_export_payload(design, None, build_bytes, build_placements,
        catalog=catalog, aliases=aliases, color_ids=color_ids, artifact="build.ldr")
    (revision_root / "design.json").write_bytes((_json_text(design, indent=2, sort_keys=True) + "\n").encode())
    (revision_root / "build.ldr").write_bytes(build_bytes)
    exports = {"build.ldr": {"revision_id": revision_id, "file_sha256": sha256_bytes(build_bytes),
                              "placements": build_placements}}
    module_paths = {}
    for assembly in sorted(design["assemblies"], key=lambda item: item["id"]):
        relative = f"modules/{assembly['id']}.ldr"
        payload, placements = _export_text(design, assembly["id"])
        _verify_export_payload(design, assembly["id"], payload, placements,
            catalog=catalog, aliases=aliases, color_ids=color_ids, artifact=relative)
        target = modules_root / f"{assembly['id']}.ldr"
        target.write_bytes(payload)
        module_paths[relative] = target
        exports[relative] = {"revision_id": revision_id, "file_sha256": sha256_bytes(payload),
                             "placements": placements}
    line_map = {"schema": LINE_MAP_SCHEMA, "revision_id": revision_id, "exports": exports}
    line_map_bytes = (_json_text(line_map, indent=2, sort_keys=True) + "\n").encode()
    (revision_root / "line_map.json").write_bytes(line_map_bytes)
    record = {"schema": REVISION_SCHEMA, "revision_id": revision_id,
        "parent_revision_id": design["parent_revision_id"], "hashes": design["hashes"],
        "exports": {path: item["file_sha256"] for path, item in exports.items()}}
    revision_bytes = (_json_text(record, indent=2, sort_keys=True) + "\n").encode()
    (revision_root / "revision.json").write_bytes(revision_bytes)
    artifact_hashes = {str(path.relative_to(root)): sha256_bytes(path.read_bytes())
        for path in sorted(revision_root.rglob("*")) if path.is_file()}
    return {"line_map": line_map, "artifact_hashes": artifact_hashes,
            "revision_record": record}


def migrate_v1_session(source: Path, destination: Path, *, catalog: Any = None,
                       aliases: Mapping[str, Any] | None = None,
                       color_ids: set[int] | frozenset[int] | None = None) -> dict[str, Any]:
    """Migrate a v1 session into a new inert v2 snapshot, leaving the source untouched."""
    source = source.expanduser().resolve(strict=True)
    if not source.is_dir():
        raise DesignError(f"v1 session source is not a directory: {source}")
    destination = destination.expanduser().absolute()
    resolved_destination = destination.resolve(strict=False)
    if _within(resolved_destination, source):
        raise DesignError("Migration destination cannot be inside the source session")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Destination already exists: {destination}")

    state_path = _relative_file(source, "state.json")
    assert state_path is not None
    state_bytes = state_path.read_bytes()
    try:
        state = json.loads(state_bytes.decode("utf-8"), parse_float=Decimal,
                           parse_constant=lambda token: (_ for _ in ()).throw(
                               DesignError(f"Legacy state has nonfinite JSON value {token}")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DesignError(f"Unable to read legacy state.json: {exc}") from exc
    if not isinstance(state, dict) or state.get("schema") != "bricksmith-agent-session-v1":
        raise DesignError("Migration requires bricksmith-agent-session-v1 state.json")
    module_order = state.get("module_order")
    if not isinstance(module_order, list) or any(not isinstance(name, str) for name in module_order):
        raise DesignError("state.json module_order must be an array of module names")
    duplicates = sorted({name for name in module_order if module_order.count(name) > 1})
    if duplicates:
        raise DesignError(f"Duplicate entries in module_order: {', '.join(duplicates)}")
    for name in module_order:
        if not MODULE_NAME_RE.fullmatch(name) or name in {".", ".."}:
            raise DesignError(f"Unsafe module name in module_order: {name!r}")
    modules_directory = source / "modules"
    if modules_directory.is_symlink() and not _within(modules_directory.resolve(strict=False), source):
        raise DesignError("modules directory escapes the source session")
    if modules_directory.exists() and not modules_directory.is_dir():
        raise DesignError("modules path is not a directory")
    module_paths: dict[str, Path] = {}
    for name in module_order:
        relative = f"modules/{name}.ldr"
        module_paths[name] = _relative_file(source, relative)  # type: ignore[assignment]
    declared = {f"{name}.ldr" for name in module_order}
    if modules_directory.is_dir():
        extras = sorted(path.name for path in modules_directory.glob("*.ldr") if path.name not in declared)
        if extras:
            raise DesignError(f"Unlisted module files are not migrated: {', '.join(extras)}")
    build_path = _relative_file(source, "build.ldr", required=False)
    file_bytes = _all_v1_session_inputs(source, state, module_paths, build_path)
    source_identity, source_records = _input_identity(file_bytes)

    # Explicitly fail if the catalog cannot be loaded, even for an empty session.
    index = _catalog_index(catalog, aliases=aliases, color_ids=color_ids)
    parsed_modules: dict[str, dict[str, Any]] = {}
    for name, path in module_paths.items():
        parsed_modules[name] = _parse_flat_ldr(file_bytes[f"modules/{name}.ldr"],
            source=f"modules/{name}.ldr", catalog=catalog, aliases=aliases, color_ids=color_ids)
    module_placements = [placement for parsed in parsed_modules.values() for placement in parsed["placements"]]
    diagnostics: list[str] = []
    if build_path is not None:
        build_placements = _parse_session_build(file_bytes["build.ldr"], "build.ldr",
            catalog=catalog, aliases=aliases, color_ids=color_ids)
        if _placement_hash(build_placements) != _placement_hash(module_placements):
            raise DesignError("Saved build.ldr disagrees with module geometry; migration refused")
    else:
        diagnostics.append("No saved build.ldr was present; build was derived from module_order and module files.")

    session_id = _deterministic_uuid(f"{source_identity}|session")
    revision_id = _deterministic_uuid(f"{source_identity}|revision|initial")
    assemblies: list[dict[str, Any]] = []
    parts: list[dict[str, Any]] = []
    source_references: list[dict[str, Any]] = []
    source_comments: list[dict[str, Any]] = []
    for module_name in module_order:
        assembly_id = _deterministic_uuid(f"{source_identity}|assembly|{module_name}")
        source_path = f"modules/{module_name}.ldr"
        module_bytes = file_bytes[source_path]
        module_hash = sha256_bytes(module_bytes)
        reference_id = _deterministic_uuid(f"{source_identity}|source|{module_name}")
        source_references.append({"id": reference_id, "original_source_identity": module_hash,
            "content_hash": file_hash(module_bytes), "role": "migrated_v1_module",
            "local_artifact_reference": None, "license_rights_status": "unknown",
            "missing_data_notes": "Original module remains in the source v1 session."})
        assemblies.append(_assembly(assembly_id, module_name))
        parsed = parsed_modules[module_name]
        for placement in parsed["placements"]:
            ordinal = placement["placement_ordinal"]
            part_id = _deterministic_uuid(f"{source_identity}|part|{module_name}|{ordinal}")
            canonical_part = _catalog_part_id(placement["part_id"], index)
            parts.append({"id": part_id, "assembly_id": assembly_id,
                "part_id": canonical_part, "color_id": placement["color_id"],
                "translation_ldu": placement["translation_ldu"], "rotation": placement["rotation"],
                "ldraw_part_reference": placement["source_part_reference"],
                "provenance": {"source_reference_id": reference_id, "source_file": source_path,
                    "source_line": placement["source_line"], "placement_ordinal": ordinal,
                    "source_identity": source_identity}})
        for comment in parsed["comments"]:
            source_comments.append({**comment, "source_file": source_path,
                "assembly_id": assembly_id, "source_reference_id": reference_id})

    ground_y = state.get("ground_y")
    if ground_y is not None:
        ground_y = _as_decimal(ground_y, "state.json ground_y")
    brief = state.get("brief")
    if brief is not None and not isinstance(brief, str):
        raise DesignError("state.json brief must be a string or null")
    plan = state.get("plan")
    historical_notes = ([{"source": "agent", "text": plan,
        "status": "historical_unverified"}] if isinstance(plan, str) and plan else [])
    design = _blank_design(revision_id=revision_id, parent_revision_id=None,
        brief=brief, brief_source="user" if brief is not None else "unknown",
        ground_y=ground_y, piece_range=_target_piece_range(state.get("target_pieces")),
        assemblies=assemblies, parts=parts, source_references=source_references,
        source_comments=source_comments, historical_notes=historical_notes,
        catalog=catalog, aliases=aliases, color_ids=color_ids)
    if len(parts) != len(module_placements):
        raise DesignError("Internal migration placement count differs from parsed modules")

    target_parent = destination.parent.resolve(strict=False)
    target_parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=target_parent))
    try:
        revision_data = _write_migrated_revision(temporary, design,
            catalog=catalog, aliases=aliases, color_ids=color_ids)
        usage = _legacy_usage(state)
        new_state = {"schema": SESSION_SCHEMA, "session_id": session_id,
            "current_revision_id": revision_id, "operation_receipts": {},
            "run_state": "paused", "stop_reason": None,
            "request_references": [], "event_references": [], "pending_image_ids": [],
            "cumulative_usage": usage, "read_only": True, "execution_enabled": False}
        state_bytes_out = (_json_text(new_state, indent=2, sort_keys=True) + "\n").encode()
        (temporary / "state.json").write_bytes(state_bytes_out)
        dispositions = _migration_field_dispositions(state)
        unmigrated = [key for key, disposition in dispositions.items()
                      if disposition == "unmigrated_historical_field"]
        manifest = {"schema": MANIFEST_SCHEMA, "session_id": session_id,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "migration": {"schema": MIGRATION_SCHEMA, "version": MIGRATION_VERSION,
                "source_schema": state["schema"], "source_content_identity": source_identity,
                "source_file_hashes": [{"path": path, **file_hash(data)} for path, data in sorted(file_bytes.items())],
                "field_dispositions": dispositions, "unmigrated_fields": unmigrated,
                "explicit_configuration": {key: state.get(key) for key in
                    ("model", "target_pieces", "ground_y", "reference_image") if key in state},
                "diagnostics": diagnostics,
                "historical_evidence_policy": "Legacy checks, reviews, views, events, and submissions are not fresh M1 acceptance evidence."},
            "current_revision_id": revision_id,
            "artifact_hashes": {**revision_data["artifact_hashes"], "state.json": sha256_bytes(state_bytes_out)}}
        manifest_bytes = (_json_text(manifest, indent=2, sort_keys=True) + "\n").encode()
        (temporary / "manifest.json").write_bytes(manifest_bytes)
        # Re-read all newly written semantic records before exposing the destination.
        validate_design(read_json(temporary / "revisions" / revision_id / "design.json"),
                        catalog=catalog, aliases=aliases, color_ids=color_ids)
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"Destination already exists: {destination}")
        os.rename(temporary, destination)
        return {"destination": str(destination), "session_id": session_id,
            "revision_id": revision_id, "source_content_identity": source_identity,
            "design_hash": design["hashes"]["design"]["value"],
            "appearance_hash": design["hashes"]["appearance"]["value"],
            "structure_hash": design["hashes"]["structure"]["value"],
            "piece_count": len(parts), "diagnostics": diagnostics,
            "unmigrated_fields": unmigrated}
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def load_line_map(path: Path) -> dict[str, Any]:
    value = read_json(path)
    _validate_line_map_shape(value)
    return value


def load_session_v2_design(session: Path, *, catalog: Any = None,
                           aliases: Mapping[str, Any] | None = None,
                           color_ids: set[int] | frozenset[int] | None = None) -> dict[str, Any]:
    """Read the pointed immutable design snapshot for offline session inspection."""
    state = read_json(session / "state.json")
    if not isinstance(state, dict) or state.get("schema") != SESSION_SCHEMA:
        raise DesignError(f"Expected {SESSION_SCHEMA} session state")
    revision_id = _uuid(state.get("current_revision_id"), "state.current_revision_id")
    design_path = session / "revisions" / revision_id / "design.json"
    if not _within(design_path, session):
        raise DesignError("Current design revision escapes the session root")
    design = load_design(design_path, catalog=catalog, aliases=aliases, color_ids=color_ids)
    if design["revision_id"] != revision_id:
        raise DesignError("state.current_revision_id does not match design revision")
    return design
