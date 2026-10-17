"""Offline stable-ID transaction engine with immutable candidates and recovery."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from . import design, revisions

OPERATION_SCHEMA = "bricksmith-operation-v1"
OPERATION_SCHEMA_V2 = "bricksmith-operation-v2"
OPERATION_SCHEMA_V3 = "bricksmith-operation-v3"
ADAPTER_INVOCATION_SCHEMA = "bricksmith-tool-invocation-v1"
TRUSTED_INGRESS_SCHEMA = "bricksmith-trusted-intake-v1"
_TRUSTED_INGRESS_CAPABILITY = object()
MAX_OPERATIONS = 64
MAX_REQUEST_BYTES = 1 << 20
MAX_PARTS = 1500
CHECKS = ("mesh_collision_free", "included_base", "no_parts_below_ground",
          "actual_connectivity", "approximate_gravity_equilibrium")
HARD = ("mesh_collision_free", "included_base", "no_parts_below_ground")


class TransactionError(ValueError):
    """Invalid operation, policy failure, stale base, or durable-state conflict."""

    def __init__(self, message: str, *, candidate: dict[str, Any] | None = None):
        super().__init__(message)
        self.candidate = candidate


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(design.canonical_json(value).encode()).hexdigest()


def _event_path(root: Path, reference: str) -> Path:
    if not isinstance(reference, str) or not __import__("re").fullmatch(r"events/[0-9]{8}\.json", reference):
        raise TransactionError("unsafe event artifact reference")
    events_root = root / "events"
    path = root / reference
    if events_root.is_symlink() or path.is_symlink() or path.resolve(strict=False).parent != events_root.resolve():
        raise TransactionError("event artifact escaped workspace")
    return path


def _json_normalize(value: Any) -> Any:
    """Materialize Python tuple-like report collections as their JSON arrays."""
    if isinstance(value, dict): return {key: _json_normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)): return [_json_normalize(item) for item in value]
    return value


def _exact_mul_add(a: Decimal, b: Decimal, c: Decimal) -> Decimal:
    # Decimal arithmetic observes ambient context. Convert finite values into
    # integer coefficients and align exponents for a context-independent sum.
    if not all(v.is_finite() for v in (a, b, c)):
        raise TransactionError("Transform numbers must be finite")
    sign_a, da, ea = a.as_tuple(); sign_b, db, eb = b.as_tuple()
    ca = int("".join(map(str, da)) or "0") * (-1 if sign_a else 1)
    cb = int("".join(map(str, db)) or "0") * (-1 if sign_b else 1)
    product = ca * cb
    ep = ea + eb
    sign_c, dc, ec = c.as_tuple()
    cc = int("".join(map(str, dc)) or "0") * (-1 if sign_c else 1)
    exponent = min(ep, ec)
    total = product * 10 ** (ep - exponent) + cc * 10 ** (ec - exponent)
    return Decimal((int(total < 0), tuple(int(x) for x in str(abs(total))) if total else (0,), exponent))


def _exact_dot(row: list[Decimal], vector: list[Decimal]) -> Decimal:
    products = []
    for a, b in zip(row, vector):
        sa, da, ea = a.as_tuple(); sb, db, eb = b.as_tuple()
        coefficient = int("".join(map(str, da)) or "0") * int("".join(map(str, db)) or "0")
        coefficient *= (-1 if sa else 1) * (-1 if sb else 1)
        products.append((coefficient, ea + eb))
    exponent = min(e for _, e in products)
    total = sum(c * 10 ** (e - exponent) for c, e in products)
    return Decimal((int(total < 0), tuple(int(x) for x in str(abs(total))) if total else (0,), exponent))


def _matrix(value: Any, field: str) -> list[list[Decimal]]:
    if not isinstance(value, list) or len(value) != 3 or any(not isinstance(row, list) or len(row) != 3 for row in value):
        raise TransactionError(f"{field} must be a 3x3 matrix")
    matrix = [[design._as_decimal(v, f"{field}[{i}][{j}]") for j, v in enumerate(row)] for i, row in enumerate(value)]
    tol = design.MATRIX_TOLERANCE
    # Check R^T R == I using exact arithmetic then tolerance only for admission.
    for i in range(3):
        for j in range(3):
            dot = _exact_dot([matrix[k][i] for k in range(3)], [matrix[k][j] for k in range(3)])
            target = Decimal(1) if i == j else Decimal(0)
            difference = design._decimal_add_exact(dot, target.copy_negate())
            if difference.copy_abs() > tol:
                raise TransactionError("rotation must be orthonormal within 1e-6; scaling/shear is unsupported")
    # Orthogonality constrains determinant magnitude; reflections are permitted.
    return matrix


def _exact_vec(value: Any, field: str) -> list[Decimal]:
    if not isinstance(value, list) or len(value) != 3:
        raise TransactionError(f"{field} must contain three finite LDU numbers")
    return [design._as_decimal(v, f"{field}[{i}]") for i, v in enumerate(value)]


def _id(value: Any, field: str) -> str:
    try:
        return design._uuid(value, field)
    except design.DesignError as exc:
        raise TransactionError(str(exc)) from exc


def _only(record: dict[str, Any], allowed: set[str], field: str) -> None:
    if not isinstance(record, dict):
        raise TransactionError(f"{field} must be an object")
    extra = set(record) - allowed
    if extra:
        raise TransactionError(f"{field} has unknown field(s): {', '.join(sorted(extra))}")


def normalize_request(request: Any) -> tuple[dict[str, Any], bytes, str]:
    if not isinstance(request, dict):
        raise TransactionError("operation request must be an object")
    try:
        raw = design.canonical_json(request).encode("utf-8")
    except (design.DesignError, TypeError, ValueError) as exc:
        raise TransactionError(f"request contains invalid or nonfinite JSON values: {exc}") from exc
    if len(raw) > MAX_REQUEST_BYTES:
        raise TransactionError("serialized operation request exceeds 1 MiB")
    schema = request.get("schema")
    allowed = {"schema", "operation_id", "base_revision_id", "intent", "operations",
               "requirement_ids", "issue_ids"}
    if schema in {OPERATION_SCHEMA_V2, OPERATION_SCHEMA_V3}: allowed.update({"adapter_invocation", "adapter_evidence"})
    _only(request, allowed, "request")
    if schema not in {OPERATION_SCHEMA, OPERATION_SCHEMA_V2, OPERATION_SCHEMA_V3}:
        raise TransactionError(f"request.schema must be {OPERATION_SCHEMA!r}, {OPERATION_SCHEMA_V2!r}, or {OPERATION_SCHEMA_V3!r}")
    _id(request.get("operation_id"), "operation_id")
    _id(request.get("base_revision_id"), "base_revision_id")
    if schema in {OPERATION_SCHEMA_V2, OPERATION_SCHEMA_V3}:
        invocation = request.get("adapter_invocation")
        if invocation is not None:
            if not isinstance(invocation, dict): raise TransactionError("adapter_invocation must be an object when present")
            _only(invocation, {"schema", "tool_name", "arguments", "operation_id",
                               "expected_base_revision_id", "expected_export_sha256"}, "adapter_invocation")
            if invocation.get("schema") != ADAPTER_INVOCATION_SCHEMA: raise TransactionError("adapter_invocation.schema is unsupported")
            if not isinstance(invocation.get("tool_name"), str) or not invocation["tool_name"]: raise TransactionError("adapter_invocation.tool_name is required")
            if not isinstance(invocation.get("arguments"), dict): raise TransactionError("adapter_invocation.arguments must be an object")
            _id(invocation.get("operation_id"), "adapter_invocation.operation_id")
            _id(invocation.get("expected_base_revision_id"), "adapter_invocation.expected_base_revision_id")
            if invocation["operation_id"] != request["operation_id"] or invocation["expected_base_revision_id"] != request["base_revision_id"]:
                raise TransactionError("adapter_invocation identity does not match operation request")
            if not isinstance(invocation.get("expected_export_sha256"), str) or not __import__("re").fullmatch(r"[0-9a-f]{64}", invocation["expected_export_sha256"]):
                raise TransactionError("adapter_invocation.expected_export_sha256 must be a SHA-256 digest")
        evidence = request.get("adapter_evidence")
        if evidence is not None:
            _only(evidence, {"schema", "generated_content", "result_metadata"}, "adapter_evidence")
            if evidence.get("schema") != "bricksmith-tool-operation-evidence-v1":
                raise TransactionError("adapter_evidence schema is unsupported")
            if "generated_content" in evidence and not isinstance(evidence["generated_content"], str):
                raise TransactionError("adapter_evidence.generated_content must be a string")
            if "result_metadata" in evidence and not isinstance(evidence["result_metadata"], dict):
                raise TransactionError("adapter_evidence.result_metadata must be an object")
    if not isinstance(request.get("intent"), str) or not request["intent"].strip():
        raise TransactionError("intent must be a nonempty string")
    ops = request.get("operations")
    if not isinstance(ops, list) or not 1 <= len(ops) <= MAX_OPERATIONS:
        raise TransactionError("operations must contain 1–64 ordered operations")
    for i, op in enumerate(ops):
        if not isinstance(op, dict) or not isinstance(op.get("type"), str):
            raise TransactionError(f"operations[{i}] must be an object with an explicit type")
        _validate_operation(op, i, allow_v2=schema in {OPERATION_SCHEMA_V2, OPERATION_SCHEMA_V3},
                            allow_v3=schema == OPERATION_SCHEMA_V3)
    for key in ("requirement_ids", "issue_ids"):
        values = request.get(key, [])
        if not isinstance(values, list):
            raise TransactionError(f"{key} must be an array")
        for i, value in enumerate(values):
            _id(value, f"{key}[{i}]")
    normalized = copy.deepcopy(request)
    normalized.setdefault("requirement_ids", [])
    normalized.setdefault("issue_ids", [])
    return normalized, raw, hashlib.sha256(raw).hexdigest()


def _validate_selector(selector: Any, field: str = "selector") -> None:
    if not isinstance(selector, dict):
        raise TransactionError(f"{field} must be an object")
    _only(selector, {"part_ids", "assembly_ids"}, field)
    parts = selector.get("part_ids", [])
    assemblies = selector.get("assembly_ids", [])
    if not isinstance(parts, list) or not isinstance(assemblies, list) or not (parts or assemblies):
        raise TransactionError(f"{field} requires part_ids and/or assembly_ids")
    for i, value in enumerate(parts): _id(value, f"{field}.part_ids[{i}]")
    for i, value in enumerate(assemblies): _id(value, f"{field}.assembly_ids[{i}]")


def _validate_operation(op: dict[str, Any], i: int, *, allow_v2: bool = False,
                        allow_v3: bool = False) -> None:
    kind = op["type"]; where = f"operations[{i}]"
    common = {"type"}
    shapes: dict[str, set[str]] = {
        "add_part": common | {"part"},
        "replace_part": common | {"part_id", "replacement", "retain_id"},
        "delete": common | {"selector"},
        "delete_assembly": common | {"assembly_id", "delete_descendants"},
        "transform": common | {"selector", "rotation", "translation_ldu", "pivot_ldu"},
        "recolor": common | {"selector", "color_id"},
        "clone_assemblies": common | {"assembly_ids", "assembly_id_map", "part_id_map", "translation_ldu"},
        "create_assembly": common | {"assembly"},
        "update_assembly": common | {"assembly_id", "fields"},
        "set_membership": common | {"part_ids", "assembly_id"},
        "upsert_issue": common | {"issue_id", "kind", "status", "affected_ids", "next_proposed_action"},
    }
    if allow_v2:
        shapes["replace_assembly_contents"] = common | {"assembly_id", "parts", "source_comments", "source_reference"}
    if allow_v3:
        shapes.update({"upgrade_design_v2": common,
            "ledger_add_instruction": common | {"record"},
            "ledger_add_requirement": common | {"record"},
            "ledger_add_decision": common | {"record"},
            "ledger_update_issue": common | {"issue_id", "kind", "status", "affected_ids",
                "evidence_reference_ids", "next_proposed_action"},
            "ledger_add_repair_attempt": common | {"record"},
            "ledger_add_next_action": common | {"record"},
            "ledger_set_initial_brief": common | {"instruction_id"}})
    if kind not in shapes:
        raise TransactionError(f"{where}.type is unsupported: {kind!r}")
    _only(op, shapes[kind], where)
    if kind in {"delete", "transform", "recolor"}: _validate_selector(op.get("selector"), f"{where}.selector")
    if kind == "add_part":
        _required(op, {"part"}, where); _validate_part_record(op["part"], f"{where}.part")
    elif kind == "replace_part":
        _required(op, {"part_id", "replacement", "retain_id"}, where)
        _id(op["part_id"], f"{where}.part_id")
        if type(op["retain_id"]) is not bool: raise TransactionError(f"{where}.retain_id must be boolean")
        _validate_part_record(op["replacement"], f"{where}.replacement")
    elif kind == "transform":
        _required(op, {"rotation", "translation_ldu", "pivot_ldu"}, where)
        _matrix(op.get("rotation"), f"{where}.rotation")
        _exact_vec(op.get("translation_ldu"), f"{where}.translation_ldu")
        _exact_vec(op.get("pivot_ldu"), f"{where}.pivot_ldu")
    elif kind == "recolor":
        _required(op, {"color_id"}, where)
        if type(op["color_id"]) is not int or op["color_id"] < 0: raise TransactionError(f"{where}.color_id must be a nonnegative integer")
    elif kind == "clone_assemblies":
        _required(op, {"assembly_ids", "assembly_id_map", "part_id_map", "translation_ldu"}, where)
        ids = op.get("assembly_ids")
        if not isinstance(ids, list) or not ids: raise TransactionError(f"{where}.assembly_ids must be nonempty")
        for value in ids: _id(value, f"{where}.assembly_ids[]")
        for key in ("assembly_id_map", "part_id_map"):
            mapping = op.get(key)
            if not isinstance(mapping, dict): raise TransactionError(f"{where}.{key} must explicitly map source IDs to new UUIDs")
            for source, target in mapping.items(): _id(source, f"{where}.{key}.source"); _id(target, f"{where}.{key}.target")
        _exact_vec(op.get("translation_ldu"), f"{where}.translation_ldu")
    elif kind == "create_assembly":
        _required(op, {"assembly"}, where)
        assembly = op["assembly"]
        if not isinstance(assembly, dict): raise TransactionError(f"{where}.assembly must be an object")
        _only(assembly, {"id", "name", "role", "parent_assembly_id", "design_properties", "relationships", "field_locks"}, f"{where}.assembly")
        _required(assembly, {"id", "name", "role", "parent_assembly_id", "design_properties", "relationships", "field_locks"}, f"{where}.assembly")
        _id(assembly["id"], f"{where}.assembly.id")
        if not isinstance(assembly["name"], str) or not assembly["name"].strip(): raise TransactionError(f"{where}.assembly.name must be nonempty")
        if assembly["role"] is not None and not isinstance(assembly["role"], str): raise TransactionError(f"{where}.assembly.role must be a string or null")
        if assembly["parent_assembly_id"] is not None: _id(assembly["parent_assembly_id"], f"{where}.assembly.parent_assembly_id")
        if not isinstance(assembly["design_properties"], dict): raise TransactionError(f"{where}.assembly.design_properties must be an object")
        try: design.canonical_json(assembly["design_properties"])
        except (design.DesignError, TypeError, ValueError) as exc: raise TransactionError(f"{where}.assembly.design_properties must be finite JSON") from exc
        for key in ("relationships", "field_locks"):
            records = assembly[key]
            if not isinstance(records, list): raise TransactionError(f"{where}.assembly.{key} must be an array")
            allowed = ({"id", "kind", "target_assembly_id", "source", "related_assembly_ids", "evidence_reference_ids"}
                       if key == "relationships" else {"id", "owner", "target_id", "fields"})
            for j, record in enumerate(records):
                field = f"{where}.assembly.{key}[{j}]"
                _only(record, allowed, field)
                if key == "relationships":
                    _required(record, {"id", "kind", "target_assembly_id", "source"}, field)
                    _id(record["id"], f"{field}.id"); _id(record["target_assembly_id"], f"{field}.target_assembly_id")
                    if not isinstance(record["kind"], str) or not record["kind"]: raise TransactionError(f"{field}.kind must be nonempty")
                    if not isinstance(record["source"], str) or record["source"] not in {"user", "agent", "imported", "unknown"}: raise TransactionError(f"{field}.source enum is invalid")
                    for id_field in ("related_assembly_ids", "evidence_reference_ids"):
                        if id_field in record:
                            if not isinstance(record[id_field], list): raise TransactionError(f"{field}.{id_field} must be an array")
                            for j2, value in enumerate(record[id_field]): _id(value, f"{field}.{id_field}[{j2}]")
                else:
                    _required(record, {"id", "owner", "target_id", "fields"}, field)
                    _id(record["id"], f"{field}.id"); _id(record["target_id"], f"{field}.target_id")
                    if not isinstance(record["owner"], str) or record["owner"] not in {"user", "agent", "unknown"}: raise TransactionError(f"{field}.owner enum is invalid")
                    if not isinstance(record["fields"], list) or not record["fields"] or any(not isinstance(x, str) or not x for x in record["fields"]):
                        raise TransactionError(f"{field}.fields must be a nonempty string array")
    elif kind == "update_assembly":
        _required(op, {"assembly_id", "fields"}, where)
        _id(op.get("assembly_id"), f"{where}.assembly_id")
        fields = op.get("fields")
        if not isinstance(fields, dict) or not fields or set(fields) - {"name", "role", "parent_assembly_id", "design_properties", "relationships"}:
            raise TransactionError(f"{where}.fields contains unsupported or empty assembly metadata")
        if "name" in fields and (not isinstance(fields["name"], str) or not fields["name"].strip()): raise TransactionError(f"{where}.fields.name must be nonempty")
        if "role" in fields and fields["role"] is not None and not isinstance(fields["role"], str): raise TransactionError(f"{where}.fields.role must be a string or null")
        if "parent_assembly_id" in fields and fields["parent_assembly_id"] is not None: _id(fields["parent_assembly_id"], f"{where}.fields.parent_assembly_id")
        if "design_properties" in fields:
            if not isinstance(fields["design_properties"], dict): raise TransactionError(f"{where}.fields.design_properties must be an object")
            try: design.canonical_json(fields["design_properties"])
            except (design.DesignError, TypeError, ValueError) as exc: raise TransactionError(f"{where}.fields.design_properties must be finite JSON") from exc
        if "relationships" in fields:
            if not isinstance(fields["relationships"], list): raise TransactionError(f"{where}.fields.relationships must be an array")
            for j, record in enumerate(fields["relationships"]):
                field = f"{where}.fields.relationships[{j}]"
                allowed = {"id", "kind", "target_assembly_id", "source", "related_assembly_ids", "evidence_reference_ids"}
                _only(record, allowed, field); _required(record, {"id", "kind", "target_assembly_id", "source"}, field)
                _id(record["id"], f"{field}.id"); _id(record["target_assembly_id"], f"{field}.target_assembly_id")
                if not isinstance(record["kind"], str) or not record["kind"]: raise TransactionError(f"{field}.kind must be nonempty")
                if not isinstance(record["source"], str) or record["source"] not in {"user", "agent", "imported", "unknown"}: raise TransactionError(f"{field}.source enum is invalid")
                for id_field in ("related_assembly_ids", "evidence_reference_ids"):
                    if id_field in record:
                        if not isinstance(record[id_field], list): raise TransactionError(f"{field}.{id_field} must be an array")
                        for k, value in enumerate(record[id_field]): _id(value, f"{field}.{id_field}[{k}]")
                try: design.canonical_json(record)
                except (design.DesignError, TypeError, ValueError) as exc: raise TransactionError(f"{field} must contain finite JSON values") from exc
    elif kind == "set_membership":
        _required(op, {"part_ids", "assembly_id"}, where)
        parts = op.get("part_ids")
        if not isinstance(parts, list) or not parts: raise TransactionError(f"{where}.part_ids must be nonempty")
        for value in parts: _id(value, f"{where}.part_ids[]")
        _id(op.get("assembly_id"), f"{where}.assembly_id")
    elif kind == "delete_assembly":
        _required(op, {"assembly_id", "delete_descendants"}, where)
        _id(op.get("assembly_id"), f"{where}.assembly_id")
        if type(op.get("delete_descendants")) is not bool: raise TransactionError(f"{where}.delete_descendants must be boolean")
    elif kind == "upsert_issue":
        _required(op, {"issue_id", "kind", "status", "affected_ids", "next_proposed_action"}, where)
        _id(op.get("issue_id"), f"{where}.issue_id")
        if not isinstance(op.get("kind"), str) or not op["kind"].strip(): raise TransactionError(f"{where}.kind must be a nonempty string")
        if not isinstance(op["status"], str) or op["status"] not in {"open", "resolved", "unverified"}: raise TransactionError(f"{where}.status enum is invalid")
        if not isinstance(op.get("affected_ids"), list): raise TransactionError(f"{where}.affected_ids must be an array")
        for value in op["affected_ids"]: _id(value, f"{where}.affected_ids[]")
        if not isinstance(op.get("next_proposed_action"), str): raise TransactionError(f"{where}.next_proposed_action must be a string")
    elif kind == "replace_assembly_contents":
        _required(op, {"assembly_id", "parts", "source_comments", "source_reference"}, where)
        _id(op["assembly_id"], f"{where}.assembly_id")
        if not isinstance(op["parts"], list) or len(op["parts"]) > MAX_PARTS:
            raise TransactionError(f"{where}.parts must be an array of at most {MAX_PARTS} records")
        seen = set()
        for j, part in enumerate(op["parts"]):
            _validate_part_record(part, f"{where}.parts[{j}]")
            if part["id"] in seen: raise TransactionError(f"{where}.parts contains duplicate ID {part['id']}")
            seen.add(part["id"])
        if not isinstance(op["source_comments"], list): raise TransactionError(f"{where}.source_comments must be an array")
        for j, comment in enumerate(op["source_comments"]):
            field = f"{where}.source_comments[{j}]"
            _only(comment, {"text", "source_line"}, field)
            _required(comment, {"text", "source_line"}, field)
            try: design._validate_comment_line(comment["text"], f"{field}.text")
            except design.DesignError as exc: raise TransactionError(str(exc)) from exc
            if type(comment["source_line"]) is not int or comment["source_line"] < 1:
                raise TransactionError(f"{field}.source_line must be a positive integer")
        reference = op["source_reference"]
        if not isinstance(reference, dict): raise TransactionError(f"{where}.source_reference must be an object")
        _only(reference, {"id", "original_source_identity", "content_hash", "role",
                          "local_artifact_reference", "license_rights_status", "missing_data_notes"}, f"{where}.source_reference")
        _required(reference, {"id", "original_source_identity", "content_hash", "role",
                              "local_artifact_reference", "license_rights_status", "missing_data_notes"}, f"{where}.source_reference")
        _id(reference["id"], f"{where}.source_reference.id")
        if not isinstance(reference["original_source_identity"], str) or not reference["original_source_identity"]:
            raise TransactionError(f"{where}.source_reference.original_source_identity must be nonempty")
        try:
            if reference["content_hash"].get("schema") != "bricksmith-file-hash-v1" or reference["content_hash"].get("algorithm") != "sha256" or not __import__("re").fullmatch(r"[0-9a-f]{64}", reference["content_hash"].get("value", "")):
                raise ValueError
        except (AttributeError, TypeError, ValueError):
            raise TransactionError(f"{where}.source_reference.content_hash is invalid")
        if not isinstance(reference["role"], str) or not reference["role"]:
            raise TransactionError(f"{where}.source_reference.role must be nonempty")
        for key in ("local_artifact_reference", "license_rights_status", "missing_data_notes"):
            if reference[key] is not None and not isinstance(reference[key], str):
                raise TransactionError(f"{where}.source_reference.{key} must be a string or null")
        if reference["local_artifact_reference"] is not None:
            try: design._relative_artifact(reference["local_artifact_reference"], f"{where}.source_reference.local_artifact_reference")
            except design.DesignError as exc: raise TransactionError(str(exc)) from exc
    elif kind in {"ledger_add_instruction", "ledger_add_requirement", "ledger_add_decision",
                  "ledger_add_repair_attempt", "ledger_add_next_action"}:
        _required(op, {"record"}, where)
        record = op["record"]
        shapes_by_kind = {
            "ledger_add_instruction": {"id", "text", "source", "originating_operation_id", "created_at"},
            "ledger_add_requirement": {"id", "description", "source", "priority", "affected_assembly_ids",
                "measurable_predicate", "evidence_reference_ids", "status", "instruction_id", "supersedes_id", "originating_operation_id"},
            "ledger_add_decision": {"id", "statement", "rationale", "source", "status", "related_assembly_ids",
                "related_requirement_ids", "evidence_reference_ids", "supersedes_id", "instruction_id", "originating_operation_id"},
            "ledger_add_repair_attempt": {"id", "issue_ids", "attempted_operation_id", "observed_revision_id",
                "schema", "evidence_references", "note", "originating_operation_id"},
            "ledger_add_next_action": {"id", "description", "kind", "related_requirement_ids", "related_issue_ids",
                "source", "evidence_references", "status", "supersedes_id", "originating_operation_id"}}
        if not isinstance(record, dict): raise TransactionError(f"{where}.record must be an object")
        _only(record, shapes_by_kind[kind], f"{where}.record")
        _required(record, shapes_by_kind[kind], f"{where}.record")
        for key in ("id", "originating_operation_id"):
            if key in record: _id(record[key], f"{where}.record.{key}")
        enum_fields = {
            "ledger_add_instruction": {"source": {"user", "operator"}},
            "ledger_add_requirement": {"source": {"user", "agent", "unknown", "operator"},
                "priority": {"mandatory", "preferred", "unknown"}, "status": {"pending", "satisfied", "failed", "unverified"}},
            "ledger_add_decision": {"source": {"user", "agent", "unknown", "operator"},
                "status": {"active", "superseded", "unverified"}},
            "ledger_add_next_action": {"source": {"agent", "operator"},
                "kind": {"inspect", "research", "edit", "check", "render", "review", "finalize"},
                "status": {"pending", "done", "cancelled"}},
        }.get(kind, {})
        for key, allowed_values in enum_fields.items():
            if not isinstance(record.get(key), str) or record[key] not in allowed_values:
                raise TransactionError(f"{where}.record.{key} enum is invalid")
        if kind == "ledger_add_repair_attempt":
            if record.get("schema") != design.REPAIR_ATTEMPT_SCHEMA:
                raise TransactionError(f"{where}.record.schema must be {design.REPAIR_ATTEMPT_SCHEMA!r}")
            for key in ("attempted_operation_id", "observed_revision_id"):
                _id(record[key], f"{where}.record.{key}")
            if not isinstance(record.get("issue_ids"), list):
                raise TransactionError(f"{where}.record.issue_ids must be an array")
            for j, value in enumerate(record["issue_ids"]): _id(value, f"{where}.record.issue_ids[{j}]")
            if not isinstance(record.get("evidence_references"), list):
                raise TransactionError(f"{where}.record.evidence_references must be an array")
            if record.get("note") is not None and not isinstance(record["note"], str):
                raise TransactionError(f"{where}.record.note must be text or null")
        try: design.canonical_json(record)
        except (design.DesignError, TypeError, ValueError) as exc:
            raise TransactionError(f"{where}.record must contain finite JSON values: {exc}") from exc
    elif kind == "ledger_update_issue":
        _required(op, {"issue_id", "kind", "status", "affected_ids", "evidence_reference_ids", "next_proposed_action"}, where)
        _id(op["issue_id"], f"{where}.issue_id")
        if not isinstance(op["kind"], str) or not op["kind"]: raise TransactionError(f"{where}.kind must be nonempty text")
        if len(op["kind"].encode("utf-8")) > 16 * 1024: raise TransactionError(f"{where}.kind exceeds 16 KiB UTF-8 bytes")
        if not isinstance(op["status"], str) or op["status"] not in {"open", "resolved", "unverified"}:
            raise TransactionError(f"{where}.status enum is invalid")
        for key in ("affected_ids", "evidence_reference_ids"):
            if not isinstance(op[key], list): raise TransactionError(f"{where}.{key} must be an array")
            for j, value in enumerate(op[key]): _id(value, f"{where}.{key}[{j}]")
        if not isinstance(op["next_proposed_action"], str): raise TransactionError(f"{where}.next_proposed_action must be text")
        if len(op["next_proposed_action"].encode("utf-8")) > 16 * 1024:
            raise TransactionError(f"{where}.next_proposed_action exceeds 16 KiB UTF-8 bytes")
    elif kind == "ledger_set_initial_brief":
        _required(op, {"instruction_id"}, where); _id(op["instruction_id"], f"{where}.instruction_id")


def _validate_part_record(part: Any, field: str) -> None:
    if not isinstance(part, dict):
        raise TransactionError(f"{field} must be an object")
    _only(part, {"id", "assembly_id", "part_id", "color_id", "translation_ldu", "rotation",
                 "ldraw_part_reference", "provenance"}, field)
    required = {"id", "assembly_id", "part_id", "color_id", "translation_ldu", "rotation",
                "ldraw_part_reference", "provenance"}
    missing = sorted(required - set(part))
    if missing: raise TransactionError(f"{field} is missing required field(s): {', '.join(missing)}")
    _id(part["id"], f"{field}.id"); _id(part["assembly_id"], f"{field}.assembly_id")
    if not isinstance(part["part_id"], str) or not part["part_id"].strip():
        raise TransactionError(f"{field}.part_id must be a nonempty catalog identifier")
    if type(part["color_id"]) is not int or part["color_id"] < 0:
        raise TransactionError(f"{field}.color_id must be a nonnegative integer")
    _exact_vec(part["translation_ldu"], f"{field}.translation_ldu")
    _matrix(part["rotation"], f"{field}.rotation")
    reference = part["ldraw_part_reference"]
    if not isinstance(reference, str) or not reference.lower().endswith(".dat") or ".." in Path(reference).parts or "\\" in reference:
        raise TransactionError(f"{field}.ldraw_part_reference must be a safe .dat reference")
    provenance = part.get("provenance")
    if not isinstance(provenance, dict): raise TransactionError(f"{field}.provenance must be an object")
    _only(provenance, {"source_reference_id", "source_file", "source_line", "placement_ordinal",
                       "derived_from", "operation_id", "source"}, f"{field}.provenance")
    if provenance.get("source_reference_id") is not None: _id(provenance["source_reference_id"], f"{field}.provenance.source_reference_id")
    if provenance.get("derived_from") is not None: _id(provenance["derived_from"], f"{field}.provenance.derived_from")
    if provenance.get("operation_id") is not None: _id(provenance["operation_id"], f"{field}.provenance.operation_id")
    for key in ("source_file", "source"):
        if key in provenance and provenance[key] is not None and not isinstance(provenance[key], str):
            raise TransactionError(f"{field}.provenance.{key} must be a string or null")
    if "source_file" in provenance and provenance["source_file"] is not None:
        source_file = provenance["source_file"]
        if Path(source_file).is_absolute() or ".." in Path(source_file).parts or "\\" in source_file:
            raise TransactionError(f"{field}.provenance.source_file must be a safe relative path")
    if "source_line" in provenance and (type(provenance["source_line"]) is not int or provenance["source_line"] < 1):
        raise TransactionError(f"{field}.provenance.source_line must be a positive integer")
    try: design.canonical_json(provenance)
    except (design.DesignError, TypeError, ValueError) as exc:
        raise TransactionError(f"{field}.provenance must contain finite JSON values") from exc


def _required(record: dict[str, Any], fields: set[str], where: str) -> None:
    missing = sorted(fields - set(record))
    if missing: raise TransactionError(f"{where} is missing required field(s): {', '.join(missing)}")


def _descendants(design_value: dict[str, Any], assembly_id: str) -> set[str]:
    children: dict[str, set[str]] = {}
    for assembly in design_value["assemblies"]:
        parent = assembly.get("parent_assembly_id")
        if parent is not None: children.setdefault(parent, set()).add(assembly["id"])
    result = {assembly_id}; stack = [assembly_id]
    while stack:
        current = stack.pop()
        for child in children.get(current, set()):
            if child not in result: result.add(child); stack.append(child)
    return result


def _resolve_selector(base: dict[str, Any], selector: dict[str, Any]) -> list[str]:
    parts = {part["id"]: part for part in base["parts"]}
    assemblies = {assembly["id"]: assembly for assembly in base["assemblies"]}
    selected = set(selector.get("part_ids", []))
    for part_id in selected:
        if part_id not in parts: raise TransactionError(f"Selector references unknown base part {part_id}")
    for assembly_id in selector.get("assembly_ids", []):
        if assembly_id not in assemblies: raise TransactionError(f"Selector references unknown base assembly {assembly_id}")
        owners = _descendants(base, assembly_id)
        selected.update(part["id"] for part in base["parts"] if part["assembly_id"] in owners)
    return sorted(selected)


def _freeze_intent(base: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    frozen = copy.deepcopy(request)
    known_requirements = {r["id"] for r in base["requirements"]}
    known_issues = {i["id"] for i in base["issues"]}
    if not set(frozen.get("requirement_ids", [])) <= known_requirements:
        raise TransactionError("request.requirement_ids contains an ID absent from the declared base")
    if not set(frozen.get("issue_ids", [])) <= known_issues:
        raise TransactionError("request.issue_ids contains an ID absent from the declared base")
    frozen_ops = []
    created_parts: set[str] = set()
    for index, op in enumerate(frozen["operations"]):
        item = copy.deepcopy(op)
        if "selector" in item:
            explicit = set(item["selector"].get("part_ids", []))
            base_ids = {p["id"] for p in base["parts"]}
            new_explicit = explicit - base_ids
            if not new_explicit <= created_parts:
                raise TransactionError(f"operations[{index}] selector references IDs not present in the base or created by an earlier operation")
            resolved = set(_resolve_selector(base, {"part_ids": sorted(explicit & base_ids),
                "assembly_ids": item["selector"].get("assembly_ids", [])}))
            item["resolved_part_ids"] = sorted(resolved | new_explicit)
        elif item["type"] == "clone_assemblies":
            assembly_ids = set(item["assembly_ids"])
            for assembly_id in assembly_ids:
                if assembly_id not in {a["id"] for a in base["assemblies"]}:
                    raise TransactionError(f"clone_assemblies references unknown base assembly {assembly_id}")
            descendants = set().union(*(_descendants(base, aid) for aid in assembly_ids))
            item["resolved_assembly_ids"] = sorted(descendants)
            item["resolved_part_ids"] = sorted(p["id"] for p in base["parts"] if p["assembly_id"] in descendants)
            if set(item["assembly_id_map"]) != descendants:
                raise TransactionError("clone assembly_id_map must map every selected descendant assembly exactly once")
            if set(item["part_id_map"]) != set(item["resolved_part_ids"]):
                raise TransactionError("clone part_id_map must map every selected descendant part exactly once")
        elif item["type"] in {"delete", "transform", "recolor"}:
            pass
        elif item["type"] == "set_membership":
            explicit = set(item["part_ids"])
            allowed_ids = {p["id"] for p in base["parts"]} | created_parts
            if not explicit <= allowed_ids:
                raise TransactionError(f"operations[{index}] set_membership references an unknown part")
            item["resolved_part_ids"] = sorted(explicit)
        if item["type"] == "add_part": created_parts.add(item["part"].get("id"))
        elif item["type"] == "replace_part" and not item["retain_id"]: created_parts.add(item["replacement"].get("id"))
        elif item["type"] == "clone_assemblies": created_parts.update(item["part_id_map"].values())
        elif item["type"] == "replace_assembly_contents": created_parts.update(part["id"] for part in item["parts"])
        frozen_ops.append(item)
    frozen["operations"] = frozen_ops
    return frozen


def _trusted_ingress_record(request: dict[str, Any], context: Any,
                            argument_hash: str) -> dict[str, Any] | None:
    if context is None: return None
    if not isinstance(context, dict) or context.get("capability") is not _TRUSTED_INGRESS_CAPABILITY:
        raise TransactionError("trusted intake must enter through the operator-only application entry point")
    source, instruction_id, text = context.get("source"), context.get("instruction_id"), context.get("text")
    if source not in {"user", "operator"} or not isinstance(text, str):
        raise TransactionError("trusted intake source or exact instruction text is invalid")
    instruction_ops = [op for op in request["operations"] if op["type"] == "ledger_add_instruction"]
    if len(instruction_ops) != 1:
        raise TransactionError("trusted intake must contain exactly one appended instruction")
    record = instruction_ops[0]["record"]
    if (record.get("id") != instruction_id or record.get("text") != text
            or record.get("source") != source or record.get("originating_operation_id") != request["operation_id"]):
        raise TransactionError("trusted instruction does not match operator intake provenance")
    material = {"schema": TRUSTED_INGRESS_SCHEMA, "source": source,
        "instruction_id": instruction_id, "instruction_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "operation_id": request["operation_id"], "base_revision_id": request["base_revision_id"],
        "argument_hash": argument_hash}
    return {**material, "binding_sha256": _canonical_hash(material)}


def _verify_trusted_ingress(frozen: dict[str, Any], argument_hash: str,
                            candidate: dict[str, Any] | None = None) -> dict[str, Any] | None:
    trust = frozen.get("trusted_ingress")
    trusted_ops = [op for op in frozen.get("operations", []) if op.get("type") == "ledger_add_instruction"]
    privileged_ops = any(op.get("type") == "ledger_set_initial_brief" for op in frozen.get("operations", []))
    privileged_ops |= any(op.get("type") in {"ledger_add_requirement", "ledger_add_decision"}
        and op.get("record", {}).get("source") in {"user", "operator"} for op in frozen.get("operations", []))
    privileged_ops |= any(op.get("type") == "ledger_add_next_action"
        and op.get("record", {}).get("source") == "operator" for op in frozen.get("operations", []))
    if not trust:
        if trusted_ops or privileged_ops: raise TransactionError("user/operator ledger authority requires verified trusted intake")
        return None
    allowed = {"schema", "source", "instruction_id", "instruction_text_sha256", "operation_id",
               "base_revision_id", "argument_hash", "binding_sha256"}
    if not isinstance(trust, dict) or set(trust) != allowed or trust.get("schema") != TRUSTED_INGRESS_SCHEMA:
        raise TransactionError("trusted intake provenance is malformed")
    material = {key: value for key, value in trust.items() if key != "binding_sha256"}
    if (trust.get("operation_id") != frozen.get("operation_id")
            or trust.get("base_revision_id") != frozen.get("base_revision_id")
            or trust.get("argument_hash") != argument_hash
            or trust.get("binding_sha256") != _canonical_hash(material)
            or not trusted_ops or len(trusted_ops) != 1):
        raise TransactionError("trusted intake provenance does not bind to the durable operation intent")
    instruction = trusted_ops[0]["record"]
    if (instruction.get("id") != trust["instruction_id"] or instruction.get("source") != trust["source"]
            or hashlib.sha256(instruction.get("text", "").encode("utf-8")).hexdigest() != trust["instruction_text_sha256"]):
        raise TransactionError("trusted intake instruction does not match its durable provenance")
    if candidate is not None:
        candidate_instruction = next((item for item in candidate.get("intent_ledger", {}).get("instructions", [])
            if item.get("id") == trust["instruction_id"]), None)
        if candidate_instruction != instruction:
            raise TransactionError("candidate instruction does not match trusted intake evidence")
    return trust


def _validate_ledger_authority(base: dict[str, Any], request: dict[str, Any], trusted: dict[str, Any] | None) -> None:
    operations = request["operations"]
    has_upgrade = any(op["type"] == "upgrade_design_v2" for op in operations)
    if has_upgrade:
        if len(operations) != 1 or base["schema"] != design.DESIGN_SCHEMA:
            raise TransactionError("explicit design-v2 upgrade must be the only operation on a design-v1 base")
        if trusted is not None: raise TransactionError("schema upgrade cannot include trusted intake")
    elif base["schema"] == design.DESIGN_SCHEMA:
        if any(op["type"].startswith("ledger_") for op in operations):
            raise TransactionError("ledger operations require explicit transaction-upgrade-v2 first")
        if request["schema"] == OPERATION_SCHEMA_V3:
            raise TransactionError("operation-v3 geometry calls require an explicitly upgraded design-v2 base")
    if request["schema"] != OPERATION_SCHEMA_V3 and any(op["type"].startswith("ledger_") for op in operations):
        raise TransactionError("ledger operations require bricksmith-operation-v3")
    if base["schema"] == design.DESIGN_SCHEMA_V2 and any(op["type"] == "upsert_issue" for op in operations):
        raise TransactionError("design-v2 issue changes must use ledger_update_issue under operation-v3")
    trusted_id = trusted.get("instruction_id") if trusted else None
    req_by_id = {record["id"]: record for record in base.get("requirements", [])}
    decision_by_id = {record["id"]: record for record in base.get("decisions", [])}
    for op in operations:
        kind = op["type"]
        if kind == "ledger_add_instruction" and trusted is None:
            raise TransactionError("instruction records can only be created by trusted intake")
        if kind == "ledger_add_requirement":
            record = op["record"]
            if record.get("source") in {"user", "operator"}:
                if trusted is None or record.get("instruction_id") != trusted_id:
                    raise TransactionError("user/operator requirements require a linked trusted correction instruction")
            target = record.get("supersedes_id")
            old = req_by_id.get(target)
            if old and old.get("source") in {"user", "operator"}:
                if trusted is None or record.get("instruction_id") != trusted_id:
                    raise TransactionError("agent requirement cannot supersede user/operator constraints")
        if kind == "ledger_add_decision":
            record = op["record"]
            if record.get("source") in {"user", "operator"}:
                if trusted is None or record.get("instruction_id") != trusted_id:
                    raise TransactionError("user/operator decisions require a linked trusted instruction")
            old = decision_by_id.get(record.get("supersedes_id"))
            if old and old.get("source") in {"user", "operator"}:
                if trusted is None or record.get("instruction_id") != trusted_id:
                    raise TransactionError("agent decision cannot supersede user/operator decisions")
        if kind == "ledger_add_next_action" and op["record"].get("source") == "operator":
            if trusted is None: raise TransactionError("operator next actions require trusted intake")
        if kind == "ledger_set_initial_brief" and trusted is None:
            raise TransactionError("initial brief may only be filled through trusted intake")


def _part_by_id(value: dict[str, Any], part_id: str) -> dict[str, Any]:
    for part in value["parts"]:
        if part["id"] == part_id: return part
    raise TransactionError(f"Operation references missing/deleted part {part_id}")


def _historical_entity_ids(root: Path, current_revision_id: str) -> set[str]:
    """Derive lifetime ID use from revisions and state-authenticated allocation evidence."""
    used: set[str] = set(); seen: set[str] = set(); revision_id: str | None = current_revision_id
    while revision_id is not None:
        if revision_id in seen: raise TransactionError("revision ancestry contains a cycle")
        seen.add(revision_id)
        value = revisions.load_revision(root, revision_id)
        used.update(_design_entity_ids(value))
        revision_id = value.get("parent_revision_id")
    state = revisions.read_state(root)
    for opid, receipt in state.get("receipts", {}).items():
        folder = _op_dir(root, opid)
        report_path = folder / "report.json"
        if report_path.is_symlink() or not report_path.is_file() or hashlib.sha256(report_path.read_bytes()).hexdigest() != receipt.get("report_sha256"):
            raise TransactionError(f"committed identity evidence is missing or corrupt: {opid}")
        report = design.read_json(report_path)
        allocated = report.get("allocated_entity_ids")
        if (receipt.get("disposition") != "committed" or report.get("operation_id") != opid
                or report.get("candidate_id") != receipt.get("candidate_id")
                or not isinstance(allocated, list) or any(not isinstance(item, str) for item in allocated)
                or len(set(allocated)) != len(allocated)):
            raise TransactionError(f"committed identity allocation evidence is missing or invalid: {opid}")
        try:
            for identity in allocated: _id(identity, "committed allocated identity")
        except TransactionError as exc:
            raise TransactionError(f"committed identity allocation evidence is invalid: {opid}") from exc
        used.update(allocated)
    return used


def _design_entity_ids(value: dict[str, Any]) -> set[str]:
    ids = set()
    for category in ("assemblies", "parts", "requirements", "decisions", "issues", "source_references"):
        for record in value.get(category, []):
            ids.add(record["id"])
            if category == "assemblies":
                ids.update(item["id"] for item in record.get("relationships", []))
                ids.update(item["id"] for item in record.get("field_locks", []))
    ledger = value.get("intent_ledger", {})
    for category in ("instructions", "repair_attempts", "next_actions"):
        ids.update(record["id"] for record in ledger.get(category, []))
    return ids


def _check_lock_change(base: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    conflicts = []
    base_parts = {p["id"]: p for p in base["parts"]}; cand_parts = {p["id"]: p for p in candidate["parts"]}
    base_assemblies = {a["id"]: a for a in base["assemblies"]}; cand_assemblies = {a["id"]: a for a in candidate["assemblies"]}
    def user_locks(value: dict[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
        return {lock["id"]: (assembly["id"], lock)
            for assembly in value["assemblies"] for lock in assembly["field_locks"]
            if lock.get("owner") == "user"}
    base_user_locks, candidate_user_locks = user_locks(base), user_locks(candidate)
    def lock_semantics(holder_id: str, lock: dict[str, Any]) -> tuple[str, str]:
        normalized = copy.deepcopy(lock)
        if isinstance(normalized.get("fields"), list): normalized["fields"] = sorted(normalized["fields"])
        return holder_id, design.canonical_json(normalized)
    for lock_id, (holder_id, lock) in base_user_locks.items():
        current = candidate_user_locks.get(lock_id)
        before_semantics = lock_semantics(holder_id, lock)
        after_semantics = None if current is None else lock_semantics(*current)
        if after_semantics != before_semantics:
            conflicts.append({"lock_id": lock_id, "target_id": lock.get("target_id"),
                              "reason": "user lock identity or protective semantics changed"})
    for assembly in base["assemblies"]:
        for lock in assembly["field_locks"]:
            if lock.get("owner") != "user": continue
            target_id = lock["target_id"]
            before = base_parts.get(target_id, base_assemblies.get(target_id))
            after = cand_parts.get(target_id, cand_assemblies.get(target_id))
            if before is None or after is None:
                conflicts.append({"lock_id": lock["id"], "target_id": target_id, "reason": "protected target was removed"}); continue
            for field in lock["fields"]:
                before_value = _locked_value(field, target_id, before, base)
                after_value = _locked_value(field, target_id, after, candidate)
                if before_value != after_value:
                    conflicts.append({"lock_id": lock["id"], "target_id": target_id,
                                      "field": field, "reason": "user-locked field changed"})
    # User requirements are immutable through this model-authored interface.
    req_before = {r["id"]: r for r in base["requirements"] if r["source"] == "user"}
    req_after = {r["id"]: r for r in candidate["requirements"]}
    for rid, requirement in req_before.items():
        if req_after.get(rid) != requirement:
            conflicts.append({"requirement_id": rid, "reason": "user requirement removed or changed"})
    return conflicts


def _locked_value(field: str, target_id: str, record: dict[str, Any], document: dict[str, Any]) -> Any:
    if "name" in record and field in {"parts", "members", "membership", "member_part_ids"}:
        return sorted(part["id"] for part in document["parts"] if part["assembly_id"] == target_id)
    if "name" in record and field in {"descendant_part_ids", "subtree_membership"}:
        owners = _descendants(document, target_id)
        return sorted(part["id"] for part in document["parts"] if part["assembly_id"] in owners)
    return record.get(field)


def _validate_evidence_references(root: Path, references: list[dict[str, Any]]) -> None:
    canonical = root.resolve(strict=True)
    for item in references:
        try: design._relative_artifact(item["path"], "ledger evidence path")
        except design.DesignError as exc: raise TransactionError(str(exc)) from exc
        relative = Path(item["path"])
        path = canonical.joinpath(*relative.parts)
        cursor = canonical
        for component in relative.parts:
            cursor = cursor / component
            if cursor.is_symlink(): raise TransactionError("ledger evidence path contains a symlink")
        try: path.resolve(strict=True).relative_to(canonical)
        except (OSError, ValueError) as exc: raise TransactionError("ledger evidence path is missing or escapes workspace") from exc
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise TransactionError("ledger evidence path is missing or its hash does not match")


def resolve_repair_attempt(root: Path, attempt: dict[str, Any], *,
                           recording_operation_id: str | None = None,
                           recording_base_revision_id: str | None = None,
                           recorded_outcome: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolve repair evidence once, using state receipts as the only commit authority."""
    root = root.expanduser().absolute()
    attempted = attempt["attempted_operation_id"]
    if attempted == recording_operation_id:
        raise TransactionError("repair attempt cannot refer to its own recording operation")
    folder = _op_dir(root, attempted)
    if folder.is_symlink() or not folder.is_dir():
        raise TransactionError("repair attempt operation is missing or foreign to this workspace")
    state = revisions.read_state(root)
    authoritative = state.get("receipts", {}).get(attempted)
    local_path = folder / "receipt.json"
    if local_path.is_symlink(): raise TransactionError("repair attempt receipt is a symlink")
    local = design.read_json(local_path) if local_path.is_file() else None
    if authoritative is None and isinstance(local, dict) and local.get("disposition") == "committed":
        raise TransactionError("operation-local receipt claims commit without an authoritative state receipt")
    receipt = authoritative if authoritative is not None else local
    if not isinstance(receipt, dict) or receipt.get("operation_id") != attempted:
        raise TransactionError("repair attempt has no verified durable outcome receipt")
    disposition = receipt.get("disposition")
    if disposition not in {"committed", "candidate", "failed", "aborted", "discarded"}:
        raise TransactionError("repair attempt receipt has an unsupported disposition")
    intent_path = folder / "intent.json"
    if intent_path.is_symlink() or not intent_path.is_file():
        raise TransactionError("repair attempt durable intent is missing or unsafe")
    intent = design.read_json(intent_path)
    if (intent.get("operation_id") != attempted
            or receipt.get("argument_hash") != intent.get("argument_hash")
            or receipt.get("base_revision_id") != intent.get("base_revision_id")):
        raise TransactionError("repair attempt receipt does not match its frozen operation intent")
    base_revision_id = intent.get("base_revision_id")
    if not isinstance(base_revision_id, str): raise TransactionError("repair attempt base revision is invalid")

    report = None; report_sha = None; policy_status = None
    report_path = folder / "report.json"
    candidate_path = folder / "candidate" / "design.json"
    candidate = None
    candidate_id = receipt.get("candidate_id")
    if disposition in {"committed", "candidate", "discarded"}:
        if (report_path.is_symlink() or not report_path.is_file()
                or candidate_path.is_symlink() or not candidate_path.is_file()):
            raise TransactionError("repair attempt candidate/report evidence is missing or unsafe")
        report_bytes = report_path.read_bytes(); candidate_bytes = candidate_path.read_bytes()
        report_sha = hashlib.sha256(report_bytes).hexdigest()
        if (receipt.get("report_sha256") != report_sha
                or receipt.get("candidate_sha256") != hashlib.sha256(candidate_bytes).hexdigest()):
            raise TransactionError("repair attempt report or candidate evidence hash is corrupt")
        report = design.read_json(report_path); candidate = design.read_json(candidate_path)
        if (report.get("operation_id") != attempted
                or report.get("candidate_id") != candidate_id
                or report.get("candidate_sha256") != hashlib.sha256(candidate_bytes).hexdigest()
                or candidate.get("revision_id") != candidate_id):
            raise TransactionError("repair attempt report/candidate identity does not match its receipt")
        policy_status = report.get("status")
        if disposition == "committed":
            if (authoritative is None or authoritative.get("disposition") != "committed"
                    or receipt.get("revision_id") != candidate_id):
                raise TransactionError("committed repair outcome lacks an authoritative state receipt")
            if local is not None:
                for key in ("operation_id", "argument_hash", "base_revision_id", "candidate_id",
                            "candidate_sha256", "report_sha256"):
                    if local.get(key) != authoritative.get(key):
                        raise TransactionError("local and authoritative committed receipts disagree")
        elif disposition == "candidate" and authoritative is not None:
            raise TransactionError("state has a committed receipt but the repair outcome is marked candidate")
    else:
        if authoritative is not None: raise TransactionError("terminal local failure conflicts with a state receipt")
        failure_path = folder / "failure.json"
        if failure_path.is_symlink() or not failure_path.is_file():
            raise TransactionError("repair attempt terminal failure evidence is missing or unsafe")
        failure = design.read_json(failure_path)
        status = "failure" if disposition == "failed" else "aborted"
        validated = _validate_failure_record(failure, operation_id=attempted,
            base_revision_id=base_revision_id, status=status, operation_dir=folder)
        if local.get("failure") != validated:
            raise TransactionError("repair attempt receipt does not match terminal failure evidence")
        if disposition == "failed" and receipt.get("candidate_id") is not None:
            raise TransactionError("failed repair receipt must not publish a candidate identity")

    revision_id = receipt.get("revision_id") if disposition == "committed" else None
    if recorded_outcome is not None:
        immutable = ("attempted_base_revision_id", "candidate_id", "report_sha256")
        current = {"attempted_base_revision_id": base_revision_id, "candidate_id": candidate_id,
                   "report_sha256": report_sha}
        if any(recorded_outcome.get(key) != current[key] for key in immutable):
            raise TransactionError("repair attempt's recorded outcome does not bind to its source evidence")
        recorded_disposition = recorded_outcome.get("disposition")
        allowed_changes = {"candidate": {"candidate", "committed", "discarded"},
                           "committed": {"committed"}, "failed": {"failed"},
                           "aborted": {"aborted"}, "discarded": {"discarded"}}
        if disposition not in allowed_changes.get(recorded_disposition, set()):
            raise TransactionError("repair attempt outcome changed through an invalid disposition transition")
        recorded_receipt_sha = recorded_outcome.get("receipt_sha256")
        current_receipt_sha = _canonical_hash(receipt)
        if recorded_disposition == "candidate":
            if disposition == "candidate" and current_receipt_sha != recorded_receipt_sha:
                raise TransactionError("staged repair receipt changed after its outcome was recorded")
            if disposition in {"committed", "discarded"}:
                proposal_receipt_path = folder / "candidate-receipt.json"
                if proposal_receipt_path.is_symlink() or not proposal_receipt_path.is_file():
                    raise TransactionError("immutable staged repair receipt evidence is missing or corrupt")
                proposal_receipt = design.read_json(proposal_receipt_path)
                if (_canonical_hash(proposal_receipt) != recorded_receipt_sha
                        or proposal_receipt.get("disposition") != "candidate"
                        or proposal_receipt.get("operation_id") != attempted
                        or proposal_receipt.get("candidate_id") != candidate_id
                        or proposal_receipt.get("report_sha256") != report_sha):
                    raise TransactionError("immutable staged repair receipt does not match source evidence")
        elif disposition in {"failed", "aborted", "discarded"} and current_receipt_sha != recorded_receipt_sha:
            raise TransactionError("terminal repair receipt changed after its outcome was recorded")
        expected_recorded_observation = (recorded_outcome.get("revision_id")
            if recorded_disposition == "committed" else base_revision_id)
        if attempt.get("observed_revision_id") != expected_recorded_observation:
            raise TransactionError("repair attempt observation does not match its immutable recorded outcome")
    else:
        expected_observed = revision_id if disposition == "committed" else base_revision_id
        if attempt.get("observed_revision_id") != expected_observed:
            raise TransactionError("repair attempt observed_revision_id must identify the attempt result or its base")

    if recording_operation_id is not None:
        if attempt.get("originating_operation_id") != recording_operation_id:
            raise TransactionError("repair attempt origin operation does not match its recording operation")
    if recording_base_revision_id is None and recording_operation_id is not None:
        recording_intent_path = _op_dir(root, recording_operation_id) / "intent.json"
        if recording_intent_path.is_symlink() or not recording_intent_path.is_file():
            raise TransactionError("repair attempt recording intent is missing or unsafe")
        recording_intent = design.read_json(recording_intent_path)
        recording_base_revision_id = recording_intent.get("base_revision_id")
    if recording_base_revision_id is not None and attempt.get("recorded_revision_id") != recording_base_revision_id:
        raise TransactionError("repair attempt recorded_revision_id does not match its operation base")
    if recorded_outcome is not None:
        if recording_operation_id is None:
            raise TransactionError("repair attempt snapshot is missing its recording operation identity")
        recording_receipt = state.get("receipts", {}).get(recording_operation_id)
        if not isinstance(recording_receipt, dict) or recording_receipt.get("disposition") != "committed":
            raise TransactionError("repair attempt recording operation lacks an authoritative committed receipt")
        recording_folder = _op_dir(root, recording_operation_id)
        recording_report = recording_folder / "report.json"
        recording_candidate = recording_folder / "candidate" / "design.json"
        if any(path.is_symlink() or not path.is_file() for path in (recording_report, recording_candidate)):
            raise TransactionError("repair attempt recording evidence is missing or unsafe")
        report_bytes = recording_report.read_bytes(); candidate_bytes = recording_candidate.read_bytes()
        if (hashlib.sha256(report_bytes).hexdigest() != recording_receipt.get("report_sha256")
                or hashlib.sha256(candidate_bytes).hexdigest() != recording_receipt.get("candidate_sha256")):
            raise TransactionError("repair attempt recording evidence hashes are invalid")
        report_value = design.read_json(recording_report)
        candidate_value = design.read_json(recording_candidate)
        if (report_value.get("operation_id") != recording_operation_id
                or report_value.get("candidate_id") != recording_receipt.get("revision_id")
                or candidate_value.get("revision_id") != recording_receipt.get("revision_id")
                or not any(item == attempt for item in candidate_value.get("intent_ledger", {}).get("repair_attempts", []))):
            raise TransactionError("repair attempt does not match its committed recording candidate")
    observed = revisions.load_revision(root, attempt["observed_revision_id"])
    recorded = revisions.load_revision(root, attempt["recorded_revision_id"])
    if not set(attempt["issue_ids"]) <= {item["id"] for item in observed.get("issues", [])}:
        raise TransactionError("repair attempt issue references do not exist in the observed revision")
    if not set(attempt["issue_ids"]) <= {item["id"] for item in recorded.get("issues", [])}:
        raise TransactionError("repair attempt issue references do not exist in the recording revision")
    _validate_evidence_references(root, attempt["evidence_references"])
    result = {"schema": "bricksmith-repair-outcome-v1", "disposition": disposition,
        "attempted_base_revision_id": base_revision_id, "candidate_id": candidate_id,
        "revision_id": revision_id, "report_sha256": report_sha,
        "policy_status": policy_status, "construction_status": receipt.get("construction_status"),
        "receipt_sha256": _canonical_hash(receipt)}
    return result


def _apply(base: dict[str, Any], frozen: dict[str, Any], historical_ids: set[str] | None = None,
           root: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    result = copy.deepcopy(base); result["parent_revision_id"] = base["revision_id"]; result["revision_id"] = str(uuid.uuid4())
    before_parts = {p["id"]: p for p in base["parts"]}
    historical_ids = set(historical_ids or ())
    affected: set[str] = set(); created: set[str] = set(); deleted: set[str] = set(); provenance_map = {}
    for n, op in enumerate(frozen["operations"]):
        kind = op["type"]
        try:
            if kind == "upgrade_design_v2":
                if result["schema"] != design.DESIGN_SCHEMA: raise TransactionError("only design-v1 can be explicitly upgraded")
                result["schema"] = design.DESIGN_SCHEMA_V2
                result["intent_ledger"] = {"schema": design.INTENT_LEDGER_SCHEMA,
                    "instructions": [], "repair_attempts": [], "next_actions": []}
            elif kind == "ledger_add_instruction":
                record = copy.deepcopy(op["record"])
                if result["schema"] != design.DESIGN_SCHEMA_V2: raise TransactionError("ledger operations require design-v2")
                if record["originating_operation_id"] != frozen["operation_id"]: raise TransactionError("instruction originating operation does not match")
                if record["id"] in historical_ids or record["id"] in created: raise TransactionError("instruction ID has already been used")
                result["intent_ledger"]["instructions"].append(record); created.add(record["id"]); affected.add(record["id"])
            elif kind == "ledger_add_requirement":
                record = copy.deepcopy(op["record"])
                if result["schema"] != design.DESIGN_SCHEMA_V2: raise TransactionError("ledger operations require design-v2")
                if record["originating_operation_id"] != frozen["operation_id"]: raise TransactionError("requirement originating operation does not match")
                if record["id"] in historical_ids or record["id"] in created: raise TransactionError("requirement ID has already been used")
                result["requirements"].append(record); created.add(record["id"]); affected.add(record["id"])
            elif kind == "ledger_add_decision":
                record = copy.deepcopy(op["record"])
                if result["schema"] != design.DESIGN_SCHEMA_V2: raise TransactionError("ledger operations require design-v2")
                if record["originating_operation_id"] != frozen["operation_id"]: raise TransactionError("decision originating operation does not match")
                if record["id"] in historical_ids or record["id"] in created: raise TransactionError("decision ID has already been used")
                result["decisions"].append(record); created.add(record["id"]); affected.add(record["id"])
            elif kind == "ledger_update_issue":
                if result["schema"] != design.DESIGN_SCHEMA_V2: raise TransactionError("ledger operations require design-v2")
                issue = next((item for item in result["issues"] if item["id"] == op["issue_id"]), None)
                if issue is None:
                    if op["status"] == "resolved": raise TransactionError("a new issue cannot begin as resolved")
                    if op["issue_id"] in historical_ids or op["issue_id"] in created: raise TransactionError("issue ID has already been used")
                    issue = {"id": op["issue_id"], "kind": op["kind"], "status": op["status"],
                        "affected_ids": list(op["affected_ids"]), "evidence_reference_ids": list(op["evidence_reference_ids"]),
                        "first_observation_revision_id": None,
                        "last_observation_revision_id": None,
                        "attempted_operation_ids": [frozen["operation_id"]], "next_proposed_action": op["next_proposed_action"],
                        "originating_operation_id": frozen["operation_id"],
                        "originating_revision_id": result["revision_id"]}
                    result["issues"].append(issue); created.add(op["issue_id"])
                else:
                    issue.update({"kind": op["kind"], "status": op["status"],
                        "affected_ids": list(op["affected_ids"]),
                        "evidence_reference_ids": list(op["evidence_reference_ids"]),
                        "next_proposed_action": op["next_proposed_action"]})
                    if frozen["operation_id"] not in issue["attempted_operation_ids"]:
                        issue["attempted_operation_ids"].append(frozen["operation_id"])
                affected.add(op["issue_id"])
            elif kind == "ledger_add_repair_attempt":
                record = copy.deepcopy(op["record"])
                if result["schema"] != design.DESIGN_SCHEMA_V2: raise TransactionError("ledger operations require design-v2")
                if record["originating_operation_id"] != frozen["operation_id"]: raise TransactionError("repair attempt originating operation does not match")
                if record["id"] in historical_ids or record["id"] in created: raise TransactionError("repair attempt ID has already been used")
                if root is None: raise TransactionError("repair attempt verification requires its workspace")
                record["recorded_revision_id"] = frozen["base_revision_id"]
                outcome = resolve_repair_attempt(root, record,
                    recording_operation_id=frozen["operation_id"],
                    recording_base_revision_id=frozen["base_revision_id"])
                record["outcome_at_recording"] = outcome
                for issue_id in record["issue_ids"]:
                    issue = next(item for item in result["issues"] if item["id"] == issue_id)
                    if record["attempted_operation_id"] not in issue["attempted_operation_ids"]:
                        issue["attempted_operation_ids"].append(record["attempted_operation_id"])
                result["intent_ledger"]["repair_attempts"].append(record); created.add(record["id"]); affected.add(record["id"])
            elif kind == "ledger_add_next_action":
                record = copy.deepcopy(op["record"])
                if result["schema"] != design.DESIGN_SCHEMA_V2: raise TransactionError("ledger operations require design-v2")
                if record["originating_operation_id"] != frozen["operation_id"]: raise TransactionError("next action originating operation does not match")
                if record["id"] in historical_ids or record["id"] in created: raise TransactionError("next action ID has already been used")
                if root is None: raise TransactionError("next action evidence verification requires its workspace")
                _validate_evidence_references(root, record["evidence_references"])
                result["intent_ledger"]["next_actions"].append(record); created.add(record["id"]); affected.add(record["id"])
            elif kind == "ledger_set_initial_brief":
                if result["schema"] != design.DESIGN_SCHEMA_V2: raise TransactionError("brief corrections require design-v2")
                if result.get("brief") not in (None, "") or result.get("brief_source") != "unknown":
                    raise TransactionError("a nonempty original brief/source is immutable")
                instruction = next((item for item in result["intent_ledger"]["instructions"] if item["id"] == op["instruction_id"]), None)
                if instruction is None or frozen.get("trusted_ingress", {}).get("instruction_id") != op["instruction_id"]:
                    raise TransactionError("initial brief must bind to this operation's trusted instruction")
                result["brief"] = instruction["text"]; result["brief_source"] = instruction["source"]
                result["brief_instruction_id"] = instruction["id"]
            elif kind == "add_part":
                part = copy.deepcopy(op["part"]); _id(part.get("id"), f"operations[{n}].part.id")
                if part["id"] in historical_ids or part["id"] in created: raise TransactionError("add_part ID has already been used in workspace history")
                result["parts"].append(part); created.add(part["id"]); affected.add(part["id"])
            elif kind == "replace_part":
                old = _part_by_id(result, op["part_id"]); replacement = copy.deepcopy(op["replacement"])
                old_id = old["id"]
                if op["retain_id"]:
                    replacement["id"] = old_id
                else:
                    _id(replacement.get("id"), f"operations[{n}].replacement.id")
                    if replacement["id"] in historical_ids or replacement["id"] in created: raise TransactionError("replacement ID has already been used in workspace history")
                    deleted.add(old_id); created.add(replacement["id"]); affected.add(replacement["id"])
                result["parts"].remove(old); result["parts"].append(replacement); affected.add(old_id)
            elif kind == "delete":
                ids = set(op["resolved_part_ids"])
                for part_id in ids: result["parts"].remove(_part_by_id(result, part_id)); deleted.add(part_id); affected.add(part_id)
            elif kind == "transform":
                rotation = _matrix(op["rotation"], f"operations[{n}].rotation")
                translation = _exact_vec(op["translation_ldu"], "translation_ldu"); pivot = _exact_vec(op["pivot_ldu"], "pivot_ldu")
                for part_id in op["resolved_part_ids"]:
                    part = _part_by_id(result, part_id)
                    pos = [design._as_decimal(v, "position") for v in part["translation_ldu"]]
                    offset = [design._decimal_add_exact(v, p.copy_negate()) for v, p in zip(pos, pivot)]
                    rotated = [_exact_dot(row, offset) for row in rotation]
                    part["translation_ldu"] = [design._decimal_add_exact(design._decimal_add_exact(pivot[i], rotated[i]), translation[i]) for i in range(3)]
                    current = [[design._as_decimal(v, "part.rotation") for v in row] for row in part["rotation"]]
                    part["rotation"] = [[_exact_dot(rotation[i], [current[k][j] for k in range(3)]) for j in range(3)] for i in range(3)]
                    affected.add(part_id)
            elif kind == "recolor":
                for part_id in op["resolved_part_ids"]: _part_by_id(result, part_id)["color_id"] = op["color_id"]; affected.add(part_id)
            elif kind == "clone_assemblies":
                amap, pmap = op["assembly_id_map"], op["part_id_map"]
                targets = list(amap.values()) + list(pmap.values())
                if len(set(targets)) != len(targets) or any(t in historical_ids or t in created for t in targets): raise TransactionError("clone IDs must be globally fresh across workspace history")
                src_asms = {a["id"]: a for a in result["assemblies"]}
                src_parts = {p["id"]: p for p in result["parts"]}
                for old_id in op["resolved_assembly_ids"]:
                    if old_id not in src_asms: raise TransactionError(f"clone source assembly was deleted by an earlier operation: {old_id}")
                    new_asm = copy.deepcopy(src_asms[old_id]); new_asm["id"] = amap[old_id]
                    parent = new_asm.get("parent_assembly_id")
                    new_asm["parent_assembly_id"] = amap.get(parent, parent)
                    for rel in new_asm["relationships"]:
                        rel["id"] = str(uuid.uuid4())
                        if rel["id"] in historical_ids or rel["id"] in created:
                            raise TransactionError("clone relationship ID has already been used in workspace history")
                        created.add(rel["id"])
                        rel["target_assembly_id"] = amap.get(rel["target_assembly_id"], rel["target_assembly_id"])
                    new_asm["field_locks"] = []
                    new_asm["name"] = f"{new_asm['name']} copy"
                    result["assemblies"].append(new_asm); affected.add(new_asm["id"]); created.add(new_asm["id"])
                for old_id in op["resolved_part_ids"]:
                    if old_id not in src_parts: raise TransactionError(f"clone source part was deleted by an earlier operation: {old_id}")
                    part = copy.deepcopy(src_parts[old_id]); new_id = pmap[old_id]
                    if part["assembly_id"] not in amap:
                        raise TransactionError(f"clone source part {old_id} now belongs to assembly {part['assembly_id']}, outside the frozen clone selection")
                    part["id"] = new_id; part["assembly_id"] = amap[part["assembly_id"]]
                    part["provenance"] = {**part["provenance"], "derived_from": old_id}
                    delta = _exact_vec(op["translation_ldu"], "translation_ldu")
                    part["translation_ldu"] = [design._decimal_add_exact(design._as_decimal(v, "position"), d) for v, d in zip(part["translation_ldu"], delta)]
                    result["parts"].append(part); affected.add(new_id); created.add(new_id)
                provenance_map = {**provenance_map, **{new: old for old, new in pmap.items()}, **{new: old for old, new in amap.items()}}
            elif kind == "create_assembly":
                record = copy.deepcopy(op["assembly"]); aid = _id(record.get("id"), f"operations[{n}].assembly.id")
                if aid in historical_ids or aid in created: raise TransactionError("assembly ID has already been used in workspace history")
                if any(lock.get("owner") == "user" for lock in record.get("field_locks", [])):
                    raise TransactionError("model-authored operations cannot create user-owned locks")
                if any(rel.get("source") == "user" for rel in record.get("relationships", [])):
                    raise TransactionError("model-authored operations cannot claim user-authored relationships")
                result["assemblies"].append(record); affected.add(aid); created.add(aid)
                for nested in record.get("relationships", []) + record.get("field_locks", []):
                    nested_id = _id(nested.get("id"), f"operations[{n}].assembly nested identity")
                    if nested_id in historical_ids or nested_id in created: raise TransactionError("nested assembly identity has already been used in workspace history")
                    created.add(nested_id)
            elif kind == "update_assembly":
                aid = op["assembly_id"]; assembly = next((a for a in result["assemblies"] if a["id"] == aid), None)
                if assembly is None: raise TransactionError(f"unknown assembly {aid}")
                if "relationships" in op["fields"] and any(rel.get("source") == "user" for rel in op["fields"]["relationships"]):
                    raise TransactionError("model-authored operations cannot claim user-authored relationships")
                if "relationships" in op["fields"]:
                    old_ids = {item["id"] for item in assembly["relationships"]}
                    for rel in op["fields"]["relationships"]:
                        rid = rel["id"]
                        if rid not in old_ids:
                            if rid in historical_ids or rid in created: raise TransactionError("relationship identity has already been used in workspace history")
                            created.add(rid)
                if "field_locks" in op["fields"]:
                    old_lock_ids = {item["id"] for item in assembly["field_locks"]}
                    for lock in op["fields"]["field_locks"]:
                        lock_id = lock["id"]
                        if lock_id not in old_lock_ids:
                            if lock_id in historical_ids or lock_id in created: raise TransactionError("field-lock identity has already been used in workspace history")
                            created.add(lock_id)
                assembly.update(copy.deepcopy(op["fields"])); affected.add(aid)
            elif kind == "set_membership":
                aid = op["assembly_id"]
                if aid not in {a["id"] for a in result["assemblies"]}: raise TransactionError(f"unknown assembly {aid}")
                for part_id in op["resolved_part_ids"]: _part_by_id(result, part_id)["assembly_id"] = aid; affected.add(part_id)
            elif kind == "delete_assembly":
                aid = op["assembly_id"]
                if aid not in {a["id"] for a in result["assemblies"]}: raise TransactionError(f"unknown assembly {aid}")
                delete_ids = _descendants(base, aid) if op["delete_descendants"] else {aid}
                if not op["delete_descendants"] and any(a.get("parent_assembly_id") == aid for a in result["assemblies"]):
                    raise TransactionError("assembly has children; reparent them or explicitly delete descendants")
                for doomed in delete_ids:
                    if any(a.get("parent_assembly_id") == doomed and a["id"] not in delete_ids for a in result["assemblies"]):
                        raise TransactionError("assembly deletion would orphan a child")
                    result["assemblies"] = [a for a in result["assemblies"] if a["id"] != doomed]
                    affected.add(doomed); deleted.add(doomed)
                if frozen.get("schema") in {OPERATION_SCHEMA_V2, OPERATION_SCHEMA_V3}:
                    for comment in result["source_comments"]:
                        if comment.get("assembly_id") in delete_ids:
                            # Keep historical source comments in the design-level
                            # view when their owning leaf assembly is discarded.
                            comment["assembly_id"] = None
                if op["delete_descendants"]:
                    for part in list(result["parts"]):
                        if part["assembly_id"] in delete_ids:
                            result["parts"].remove(part); affected.add(part["id"]); deleted.add(part["id"])
            elif kind == "upsert_issue":
                issue_id = op["issue_id"]
                existing = next((issue for issue in result["issues"] if issue["id"] == issue_id), None)
                if existing is None:
                    if issue_id in historical_ids or issue_id in created: raise TransactionError("issue ID has already been used in workspace history")
                    created.add(issue_id)
                    result["issues"].append({"id": issue_id, "kind": op["kind"], "status": op["status"],
                        "affected_ids": list(op["affected_ids"]), "evidence_reference_ids": [],
                        "first_observation_revision_id": result["revision_id"],
                        "last_observation_revision_id": result["revision_id"],
                        "attempted_operation_ids": [frozen["operation_id"]],
                        "next_proposed_action": op["next_proposed_action"]})
                else:
                    existing.update({"kind": op["kind"], "status": op["status"],
                        "affected_ids": list(op["affected_ids"]),
                        "last_observation_revision_id": result["revision_id"],
                        "next_proposed_action": op["next_proposed_action"]})
                    if frozen["operation_id"] not in existing["attempted_operation_ids"]:
                        existing["attempted_operation_ids"].append(frozen["operation_id"])
                affected.add(issue_id)
            elif kind == "replace_assembly_contents":
                aid = op["assembly_id"]
                if aid not in {assembly["id"] for assembly in result["assemblies"]}:
                    raise TransactionError(f"unknown assembly {aid}")
                assembly = next(assembly for assembly in result["assemblies"] if assembly["id"] == aid)
                source_ref = copy.deepcopy(op["source_reference"])
                source_id = source_ref["id"]
                if source_id in historical_ids or source_id in created:
                    raise TransactionError("source-reference ID has already been used in workspace history")
                result["source_references"].append(source_ref); created.add(source_id); affected.add(source_id)
                prior = {part["id"]: part for part in result["parts"] if part["assembly_id"] == aid}
                supplied = copy.deepcopy(op["parts"])
                supplied_ids = set()
                for part in supplied:
                    if part["assembly_id"] != aid:
                        raise TransactionError("bulk replacement part must belong directly to the named assembly")
                    part_id = part["id"]
                    if part_id in supplied_ids: raise TransactionError(f"bulk replacement repeats part ID {part_id}")
                    supplied_ids.add(part_id)
                    if part_id not in prior:
                        if part_id in historical_ids or part_id in created:
                            raise TransactionError("bulk replacement part ID has already been used in workspace history")
                        created.add(part_id)
                    affected.add(part_id)
                for part_id in set(prior) - supplied_ids:
                    deleted.add(part_id); affected.add(part_id)
                result["parts"] = [part for part in result["parts"] if part["assembly_id"] != aid] + supplied
                result["source_comments"] = [comment for comment in result["source_comments"]
                    if comment.get("assembly_id") != aid]
                for comment in op["source_comments"]:
                    result["source_comments"].append({**copy.deepcopy(comment),
                        "assembly_id": aid, "source_reference_id": source_id,
                        "source_file": f"modules/{assembly['name']}.ldr"})
        except (design.DesignError, KeyError, ValueError) as exc:
            raise TransactionError(f"operations[{n}] ({kind}) failed: {exc}", candidate=copy.deepcopy(result)) from exc
    # A live issue may not keep references to entities removed in this edit.
    # Require an explicit issue update to replace those references; reports keep
    # the historical IDs and operation evidence without weakening M1 validation.
    upserted_issue_ids = {op["issue_id"] for op in frozen["operations"] if op["type"] == "upsert_issue"}
    live_entity_ids = {record["id"] for key in ("assemblies", "parts", "requirements", "decisions", "source_references") for record in result[key]}
    for issue in result["issues"]:
        dangling = sorted(set(issue.get("affected_ids", [])) - live_entity_ids)
        if dangling and issue["id"] not in upserted_issue_ids:
            raise TransactionError(f"issue {issue['id']} references deleted entities {dangling}; upsert the issue in this request", candidate=copy.deepcopy(result))
    conflicts = _check_lock_change(base, result)
    removed_target = next((item for item in conflicts if item.get("reason") == "protected target was removed"), None)
    if removed_target:
        raise TransactionError(f"user lock {removed_target['lock_id']} protects a target removed by this operation", candidate=copy.deepcopy(result))
    # Retain the immutable design ledger and add explicit policy/validation issues later.
    design.refresh_hashes(result)
    try: design.validate_design(result)
    except design.DesignError as exc: raise TransactionError(f"final candidate violates design invariants: {exc}", candidate=copy.deepcopy(result)) from exc
    if len(result["parts"]) > MAX_PARTS: raise TransactionError("candidate exceeds 1,500 physical placements")
    summary = {"affected_ids": sorted(affected), "affected_count": len(affected),
               "created_ids": sorted(created), "deleted_ids": sorted(deleted),
               "allocated_entity_ids": sorted(created),
               "clone_derived_from": provenance_map,
               "piece_delta": len(result["parts"]) - len(base["parts"]),
               "origin_bounds_before": _bounds(base["parts"]), "origin_bounds_after": _bounds(result["parts"]),
               "hashes_changed": {key: base["hashes"][key]["value"] != result["hashes"][key]["value"]
                                  for key in ("appearance", "structure", "design")},
               "policy_conflicts": conflicts}
    return result, summary


def _bounds(parts: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not parts: return None
    coords = [[design._as_decimal(x, "translation") for x in p["translation_ldu"]] for p in parts]
    return {"basis": "placement origins", "min_ldu": [min(row[i] for row in coords) for i in range(3)],
            "max_ldu": [max(row[i] for row in coords) for i in range(3)]}


def _run_validation(value: dict[str, Any], workdir: Path, label: str,
                    validator: Callable[[Path, float], dict[str, Any]] | None = None) -> dict[str, Any]:
    design.validate_design(value)
    if value.get("ground_y") is None: raise TransactionError("ground_y is unknown; construction policy cannot evaluate")
    build, placements = design._export_text(value)
    design._verify_export_payload(value, None, build, placements, artifact=f"{label}.ldr")
    ldr_path = workdir / f"{label}.ldr"; ldr_path.write_bytes(build)
    if validator is None:
        from .feedback import check_model
        validator = lambda path, ground: check_model(path, ground_y=float(ground))
    try:
        raw = validator(ldr_path, float(value["ground_y"]))
    except Exception as exc:
        return {"schema": "bricksmith-transaction-validation-v1", "raw_report": None,
                "evaluation": {"available": False, "exception": type(exc).__name__, "detail": str(exc), "checks": None,
                               "reason": f"checker exception: {type(exc).__name__}: {exc}"}}
    raw = _json_normalize(raw)
    interpretation = _interpret_report(raw, placements)
    return {"schema": "bricksmith-transaction-validation-v1", "raw_report": raw,
            "evaluation": interpretation, "export_sha256": hashlib.sha256(build).hexdigest(),
            "design_hash": value["hashes"]["design"]["value"]}


def _interpret_report(raw: Any, placements: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(raw, dict) or not isinstance(raw.get("checks"), dict):
        return {"available": False, "reason": "missing checks object", "checks": None, "evidence_complete": False}
    errors = raw.get("errors", [])
    diagnostics = raw.get("diagnostics", {})
    if not isinstance(errors, list) or any(not isinstance(error, dict) for error in errors):
        return {"available": False, "reason": "malformed checker errors", "checks": None, "evidence_complete": False}
    if not isinstance(diagnostics, dict): diagnostics = {}
    checks = raw["checks"]
    if any(type(checks.get(k)) is not bool for k in CHECKS):
        return {"available": False, "reason": "all five checks must be explicit booleans", "checks": copy.deepcopy(checks), "evidence_complete": False}
    below_complete = diagnostics.get("below_ground_indices_complete_flag") is True
    below_indices = diagnostics.get("below_ground_indices_complete") if below_complete else None
    if below_complete and not isinstance(below_indices, list): below_complete = False; below_indices = None
    if not below_complete and checks["no_parts_below_ground"] and not any(error.get("kind") == "parts_below_ground" for error in errors):
        # A true complete check establishes the empty offender set without relying
        # on a truncated diagnostic sample.
        below_complete = True; below_indices = []
    check_passed = raw.get("passed")
    if type(check_passed) is not bool or (check_passed != all(checks[key] for key in CHECKS)):
        return {"available": False, "reason": "checker summary conflicts with the five explicit checks",
                "checks": {key: checks[key] for key in CHECKS}, "evidence_complete": False}
    collisions: set[tuple[str, str]] = set(); below: set[str] = set(); missing_base = not checks["included_base"]
    index_to_id = {i: p["part_id"] for i, p in enumerate(placements)}
    mapping_complete = len(index_to_id) == len(placements)
    collision_error_seen = False
    below_error_seen = False
    for error in raw.get("errors", []):
        if error.get("kind") == "mesh_collision":
            collision_error_seen = True
            pairs = error.get("pairs")
            if not isinstance(pairs, list) or type(error.get("count")) is not int or error["count"] != len(pairs):
                mapping_complete = False; pairs = []
            for pair in pairs:
                if not isinstance(pair, (list, tuple)) or len(pair) != 2 or any(type(x) is not int or x not in index_to_id for x in pair):
                    mapping_complete = False; continue
                a, b = index_to_id[pair[0]], index_to_id[pair[1]]
                collisions.add(tuple(sorted((a, b))))
    if below_indices is not None:
        below_error = next((error for error in raw.get("errors", []) if error.get("kind") == "parts_below_ground"), None)
        below_error_seen = below_error is not None
        if below_error is not None and (type(below_error.get("count")) is not int or below_error["count"] != len(below_indices)):
            mapping_complete = False
        for index in below_indices:
            if type(index) is not int or index not in index_to_id: mapping_complete = False
            else: below.add(index_to_id[index])
    else:
        # A false check paired with the legacy 30-item sample has no complete
        # identity set; that evidence cannot support repair policy.
        if not checks["no_parts_below_ground"]: mapping_complete = False
    if not checks["mesh_collision_free"] and not collision_error_seen: mapping_complete = False
    if checks["mesh_collision_free"] and collision_error_seen: mapping_complete = False
    if not checks["no_parts_below_ground"] and (not below_error_seen or not below_complete): mapping_complete = False
    if checks["no_parts_below_ground"] and below_indices and len(below_indices): mapping_complete = False
    if raw.get("physical_piece_count") is not None and raw.get("physical_piece_count") != len(placements): mapping_complete = False
    return {"available": True, "checks": {key: checks[key] for key in CHECKS},
            "collision_pairs": [list(pair) for pair in sorted(collisions)],
            "below_ground_part_ids": sorted(below), "below_ground_complete": below_complete,
            "missing_base": missing_base, "identity_mapping_complete": mapping_complete,
            "evidence_complete": mapping_complete and below_complete,
            "raw_passed": raw.get("passed") is True}


def _policy(base_eval: dict[str, Any], candidate_eval: dict[str, Any], conflicts: list[dict[str, Any]]) -> dict[str, Any]:
    reasons = []
    if conflicts: reasons.append({"code": "policy_conflict", "details": conflicts})
    for label, evaluation in (("base", base_eval), ("candidate", candidate_eval)):
        if not evaluation.get("available"):
            reasons.append({"code": f"{label}_validation_unavailable", "details": evaluation.get("reason", evaluation.get("detail"))})
        elif not evaluation.get("evidence_complete"): reasons.append({"code": f"{label}_evidence_incomplete", "details": "stable offender mapping is incomplete"})
    if reasons: return {"commit_eligible": False, "status": "blocked", "reasons": reasons}
    b, c = base_eval, candidate_eval
    bchecks, cchecks = b["checks"], c["checks"]
    base_hard_bad = any(not bchecks[k] for k in HARD)
    cand_hard_bad = any(not cchecks[k] for k in HARD)
    hard_removed = False
    if not base_hard_bad:
        if cand_hard_bad:
            reasons.append({"code": "hard_check_regression", "details": [k for k in HARD if bchecks[k] and not cchecks[k]]})
    else:
        bc = {tuple(x) for x in b["collision_pairs"]}; cc = {tuple(x) for x in c["collision_pairs"]}
        bb = set(b["below_ground_part_ids"]); cb = set(c["below_ground_part_ids"])
        if not cc <= bc: reasons.append({"code": "new_collision_offenders", "details": [list(pair) for pair in sorted(cc - bc)]})
        if not cb <= bb: reasons.append({"code": "new_below_ground_offenders", "details": sorted(cb - bb)})
        if not bchecks["included_base"] and not cchecks["included_base"]:
            # Retained missing base is permitted only if another hard violation is removed.
            pass
        if bchecks["included_base"] and not cchecks["included_base"]: reasons.append({"code": "missing_base_regression"})
        hard_removed = bool(bc - cc or bb - cb or (not bchecks["included_base"] and cchecks["included_base"]))
        if not hard_removed: reasons.append({"code": "no_hard_violation_removed"})
    if reasons: return {"commit_eligible": False, "status": "blocked", "reasons": reasons}
    if cand_hard_bad: status = "repair_incomplete"
    elif not cchecks["actual_connectivity"] or not cchecks["approximate_gravity_equilibrium"]: status = "provisional"
    else: status = "construction_passed"
    if status in {"repair_incomplete", "provisional"}:
        reasons.append({"code": status, "details": "candidate commit is not final design acceptance"})
    return {"commit_eligible": True, "status": status, "reasons": reasons}


def _evaluation_fingerprint(base_validation: dict[str, Any], candidate_validation: dict[str, Any],
                            ground_y: Any, environment_identity: dict[str, Any] | None) -> str:
    """Hash semantically relevant evidence, excluding timing/path diagnostics."""
    def stable(value: dict[str, Any]) -> dict[str, Any]:
        return {"schema": value.get("schema"), "export_sha256": value.get("export_sha256"),
                "design_hash": value.get("design_hash"), "evaluation": value.get("evaluation")}
    return _canonical_hash({"base": stable(base_validation), "candidate": stable(candidate_validation),
                            "ground_y": ground_y, "evaluation_environment_identity": environment_identity,
                            "validator_contract": "bricksmith-five-check-transaction-v1"})


def _write_json_durable(path: Path, value: Any, *, failpoint=None) -> bytes:
    payload = (design._json_text(value, indent=2, sort_keys=True) + "\n").encode()
    if failpoint:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = __import__("tempfile").mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temp = Path(name)
        with os.fdopen(fd, "wb") as stream:
            split = max(1, len(payload) // 2)
            stream.write(payload[:split]); stream.flush(); os.fsync(stream.fileno())
            failpoint("during_candidate_writes")
            stream.write(payload[split:]); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, path); revisions._flush_dir(path.parent)
        return payload
    revisions._atomic_bytes(path, payload)
    return payload


def _op_dir(root: Path, operation_id: str) -> Path:
    _id(operation_id, "operation_id")
    operations_root = root / "operations"
    if operations_root.is_symlink() or not operations_root.is_dir() or operations_root.resolve().parent != root.resolve():
        raise TransactionError("operations root must be a real directory inside the workspace")
    path = root / "operations" / operation_id
    if path.is_symlink() or path.resolve(strict=False).parent != (root / "operations").resolve(strict=False):
        raise TransactionError("operation path escaped transaction workspace")
    return path


def propose_edit(root: Path, request: Any, *, validator: Callable[[Path, float], dict[str, Any]] | None = None,
                 failpoint: Callable[[str], None] | None = None,
                 _created_candidate: list[bool] | None = None,
                 _trusted_ingress: dict[str, Any] | None = None) -> dict[str, Any]:
    if _created_candidate is not None:
        _created_candidate[:] = [False]
    normalized, raw_bytes, argument_hash = normalize_request(request)
    opid = normalized["operation_id"]; root = root.expanduser().absolute()
    with revisions.writer_lock(root):
        state, base = revisions.current_revision(root)
        declared_base = revisions.load_revision(root, normalized["base_revision_id"])
        trust = _trusted_ingress_record(normalized, _trusted_ingress, argument_hash)
        _validate_ledger_authority(declared_base, normalized, trust)
        opdir = _op_dir(root, opid)
        committed = state["receipts"].get(opid)
        if committed is not None:
            if committed.get("argument_hash") != argument_hash:
                raise TransactionError("operation_id was already committed with different arguments")
            return committed
        if opdir.exists():
            intent_path = opdir / "intent.json"
            if not intent_path.is_file(): raise TransactionError("operation has incomplete intent staging; run recover")
            existing = design.read_json(intent_path)
            if existing.get("argument_hash") != argument_hash:
                raise TransactionError("operation_id was already used with different arguments")
            stored_receipt = opdir / "receipt.json"
            if stored_receipt.exists():
                prior = design.read_json(stored_receipt)
                if prior.get("disposition") == "committed":
                    raise TransactionError("operation-local receipt claims commit without an authoritative state receipt")
                if prior.get("disposition") in {"discarded", "aborted", "failed"}: return prior
            return inspect_candidate(root, opid)
        if normalized["base_revision_id"] != state["current_revision_id"]:
            raise TransactionError("stale base_revision_id; reload current revision and revalidate")
        frozen = _freeze_intent(base, normalized)
        if trust is not None: frozen["trusted_ingress"] = trust
        _verify_trusted_ingress(frozen, argument_hash)
        historical_ids = _historical_entity_ids(root, state["current_revision_id"])
        opdir.mkdir(mode=0o700)
        revisions._flush_dir(root / "operations")
        if failpoint: failpoint("before_intent_flush")
        frozen_bytes = _write_json_durable(opdir / "intent.json", {"schema": "bricksmith-normalized-intent-v1",
            "operation_id": opid, "argument_hash": argument_hash, "request_sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "base_revision_id": base["revision_id"], "intent": frozen})
        if failpoint: failpoint("after_intent_flush")
        try:
            candidate, summary = _apply(base, frozen, historical_ids, root)
            (opdir / "candidate").mkdir()
            candidate_payload = (design._json_text(candidate, indent=2, sort_keys=True) + "\n").encode()
            _write_json_durable(opdir / "candidate" / "design.json", candidate, failpoint=failpoint)
            environment_before = _evaluation_environment_identity()
            base_validation = _run_validation(base, opdir, "base", validator)
            candidate_validation = _run_validation(candidate, opdir, "candidate", validator)
            environment_after = _evaluation_environment_identity()
            if candidate_validation.get("evaluation", {}).get("available"):
                updated_issue_ids = {op["issue_id"] for op in frozen["operations"] if op["type"] == "ledger_update_issue"}
                for issue in candidate["issues"]:
                    if issue["id"] in updated_issue_ids:
                        if issue.get("first_observation_revision_id") is None:
                            issue["first_observation_revision_id"] = candidate["revision_id"]
                        issue["last_observation_revision_id"] = candidate["revision_id"]
            _write_json_durable(opdir / "checks" if False else opdir / "base-validation.json", base_validation)
            _write_json_durable(opdir / "candidate-validation.json", candidate_validation)
            policy = _policy(base_validation["evaluation"], candidate_validation["evaluation"], summary["policy_conflicts"])
            if policy["status"] in {"provisional", "repair_incomplete"}:
                live_ids = {record["id"] for key in ("assemblies", "parts", "requirements", "decisions", "source_references") for record in candidate[key]}
                issue = {"id": str(uuid.uuid4()), "kind": policy["status"], "status": "open",
                         "affected_ids": [identity for identity in summary["affected_ids"] if identity in live_ids], "evidence_reference_ids": [],
                         "first_observation_revision_id": candidate["revision_id"],
                         "last_observation_revision_id": candidate["revision_id"],
                         "attempted_operation_ids": [opid], "next_proposed_action": "repair and revalidate",
                         "originating_operation_id": opid,
                         "originating_revision_id": candidate["revision_id"]}
                candidate["issues"].append(issue)
                summary["created_ids"].append(issue["id"])
                summary["allocated_entity_ids"].append(issue["id"])
                summary["affected_ids"].append(issue["id"])
                summary["affected_count"] += 1
                summary["created_ids"].sort(); summary["allocated_entity_ids"].sort(); summary["affected_ids"].sort()
            design.refresh_hashes(candidate); design.validate_design(candidate)
            # Auto-created policy issues are design metadata. Bind the saved
            # validation envelope to final candidate bytes while retaining the
            # exact raw physical checker report and export identity.
            candidate_validation["design_hash"] = candidate["hashes"]["design"]["value"]
            _write_json_durable(opdir / "candidate-validation.json", candidate_validation)
            candidate_payload = (design._json_text(candidate, indent=2, sort_keys=True) + "\n").encode()
            _write_json_durable(opdir / "candidate" / "design.json", candidate)
            data_identity = _data_identity()
            evaluation_fingerprint = _evaluation_fingerprint(base_validation, candidate_validation,
                base["ground_y"], environment_after)
            if environment_after is None:
                policy["commit_eligible"] = False; policy["status"] = "blocked"
                policy.setdefault("reasons", []).append({"code": "checker_data_identity_unavailable",
                    "details": "one or more checker environment inputs could not be fingerprinted"})
            elif environment_before != environment_after:
                policy["commit_eligible"] = False; policy["status"] = "blocked"
                policy.setdefault("reasons", []).append({"code": "checker_environment_changed_during_proposal",
                    "details": "checker inputs changed while proposal validation was running"})
            summary.update({"schema": "bricksmith-candidate-report-v1", "operation_id": opid, "candidate_id": candidate["revision_id"],
                "base_revision_id": base["revision_id"], "candidate_sha256": hashlib.sha256(candidate_payload).hexdigest(),
                "candidate_design_hash": candidate["hashes"]["design"]["value"],
                "base_design_hash": base["hashes"]["design"]["value"],
                "validation": {"base": "base-validation.json", "candidate": "candidate-validation.json"},
                "evaluation_fingerprint": evaluation_fingerprint, "policy": policy,
                "data_identity": data_identity,
                "evaluation_environment_identity": environment_after,
                "commit_eligible": policy["commit_eligible"], "status": policy["status"],
                "requirements_retained": [r["id"] for r in base["requirements"]],
                "issues_retained": [i["id"] for i in base["issues"]],
                "requirements_addressed": list(frozen.get("requirement_ids", [])),
                "issues_addressed": list(frozen.get("issue_ids", []))})
            trust = _verify_trusted_ingress(frozen, argument_hash, candidate)
            if trust is not None: summary["trusted_intake_binding_sha256"] = trust["binding_sha256"]
            if frozen.get("adapter_invocation"):
                summary["adapter_invocation_sha256"] = _canonical_hash(frozen["adapter_invocation"])
            if frozen.get("adapter_evidence"):
                if "generated_content" in frozen["adapter_evidence"]:
                    summary["generated_content_sha256"] = hashlib.sha256(
                        frozen["adapter_evidence"]["generated_content"].encode("utf-8")).hexdigest()
                if "result_metadata" in frozen["adapter_evidence"]:
                    summary["adapter_result"] = copy.deepcopy(frozen["adapter_evidence"]["result_metadata"])
            if failpoint: failpoint("before_report_flush")
            report_payload = _write_json_durable(opdir / "report.json", summary)
            if failpoint: failpoint("after_report_flush")
            receipt = {"schema": "bricksmith-operation-receipt-v1", "operation_id": opid,
                       "argument_hash": argument_hash, "base_revision_id": base["revision_id"],
                       "candidate_id": candidate["revision_id"], "candidate_sha256": hashlib.sha256(candidate_payload).hexdigest(),
                       "report_sha256": hashlib.sha256(report_payload).hexdigest(), "disposition": "candidate",
                       "commit_eligible": policy["commit_eligible"], "created_revision_id": None}
            if trust is not None: receipt["trusted_intake_binding_sha256"] = trust["binding_sha256"]
            if failpoint: failpoint("before_candidate_receipt_flush")
            _write_json_durable(opdir / "candidate-receipt.json", receipt)
            _write_json_durable(opdir / "receipt.json", receipt)
            if failpoint: failpoint("after_candidate_receipt_flush")
            if failpoint: failpoint("after_candidate_seal_before_pointer")
            if _created_candidate is not None: _created_candidate[:] = [True]
            return summary
        except BaseException as exc:
            invalid_candidate = getattr(exc, "candidate", None)
            if isinstance(invalid_candidate, dict):
                (opdir / "candidate").mkdir(exist_ok=True)
                _write_json_durable(opdir / "candidate" / "invalid-design.json", invalid_candidate)
            failure = {"schema": "bricksmith-candidate-failure-v1", "operation_id": opid,
                       "base_revision_id": base["revision_id"], "status": "failure",
                       "error_type": type(exc).__name__, "error": str(exc)}
            if isinstance(invalid_candidate, dict): failure["candidate_artifact"] = "candidate/invalid-design.json"
            _write_json_durable(opdir / "failure.json", failure)
            if failpoint: failpoint("after_failure_flush")
            terminal = {"schema": "bricksmith-operation-receipt-v1", "operation_id": opid,
                        "argument_hash": argument_hash, "base_revision_id": base["revision_id"],
                        "candidate_id": None, "candidate_sha256": None, "report_sha256": None,
                        "disposition": "failed", "status": "failure", "failure": failure}
            _write_json_durable(opdir / "receipt.json", terminal)
            if isinstance(exc, TransactionError): return failure
            raise


def _data_identity() -> str | None:
    value = os.environ.get("BRICKNET_DATA")
    if not value: return None
    path = Path(value)
    if not path.exists(): return None
    from .provenance import hash_tree
    return hash_tree(path)


def _evaluation_environment_identity() -> dict[str, Any] | None:
    """Return a complete, location-independent identity of checker inputs."""
    from . import provenance
    root = Path(__file__).resolve().parents[2]
    source_files = ("bricksmith/workbench/transactions.py", "bricksmith/workbench/design.py",
                    "bricksmith/workbench/feedback.py",
                    "bricksmith/physics/validator.py", "configs/architecture_scope.json")
    local_code = {}
    for relative in source_files:
        path = root / relative
        if not path.is_file(): return None
        local_code[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    bricknet = provenance._bricknet_identity()
    catalog = (bricknet.get("catalog_data") or {}) if isinstance(bricknet, dict) else {}
    mesh_identity = _data_identity()
    package_names = ("bricknet", "meshlib", "numpy", "scipy")
    packages = {name: provenance._package_version(name) for name in package_names}
    if (bricknet.get("available") is not True or not bricknet.get("source_content_sha256") or
            catalog.get("available") is not True or not catalog.get("content_sha256") or
            mesh_identity is None or any(not packages[name] for name in package_names)):
        return None
    return {"schema": "bricksmith-checker-environment-v1", "local_code": local_code,
            "bricknet": {"version": bricknet.get("version"),
                         "source_content_sha256": bricknet.get("source_content_sha256"),
                         "package_data_sha256": catalog.get("content_sha256")},
            "mesh_data_sha256": mesh_identity,
            "dependencies": packages,
            "python": {"implementation": sys.implementation.name,
                       "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"}}


def inspect_candidate(root: Path, operation_id: str) -> dict[str, Any]:
    root = root.expanduser().absolute(); opdir = _op_dir(root, operation_id)
    if not opdir.is_dir() or opdir.is_symlink(): raise TransactionError("candidate operation does not exist")
    state = revisions.read_state(root)
    authoritative = state["receipts"].get(operation_id)
    if authoritative is not None: return authoritative
    receipt_path = opdir / "receipt.json"
    if receipt_path.is_symlink(): raise TransactionError("operation receipt cannot be a symlink")
    if receipt_path.exists():
        stored = design.read_json(receipt_path)
        if stored.get("disposition") == "committed":
            raise TransactionError("operation-local receipt claims commit without an authoritative state receipt")
        if stored.get("disposition") in {"aborted", "failed", "discarded"}: return stored
    report_path = opdir / "report.json"
    if report_path.exists():
        if report_path.is_symlink(): raise TransactionError("candidate report cannot be a symlink")
        result = design.read_json(report_path)
        if receipt_path.exists():
            stored_receipt = design.read_json(receipt_path)
            if stored_receipt.get("report_sha256") and hashlib.sha256(report_path.read_bytes()).hexdigest() != stored_receipt["report_sha256"]:
                raise TransactionError("candidate report bytes changed; eligibility is invalid")
        candidate_path = opdir / "candidate" / "design.json"
        if candidate_path.is_symlink(): raise TransactionError("candidate design cannot be a symlink")
        payload = candidate_path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != result.get("candidate_sha256"):
            raise TransactionError("candidate bytes changed; eligibility is invalid")
        if state["current_revision_id"] != result.get("base_revision_id"):
            result["commit_eligible"] = False
            result["policy"] = {"commit_eligible": False, "status": "blocked", "reasons": [{"code": "stale_base", "details": "revalidation required"}]}
        return result
    failure = opdir / "failure.json"
    if failure.is_symlink(): raise TransactionError("candidate failure record cannot be a symlink")
    if failure.exists(): return design.read_json(failure)
    intent = opdir / "intent.json"
    if intent.exists(): return {"operation_id": operation_id, "status": "staging", "candidate_available": (opdir / "candidate/design.json").exists()}
    raise TransactionError("operation has no durable intent")


def commit_candidate(root: Path, operation_id: str, candidate_id: str, *,
                     failpoint: Callable[[str], None] | None = None,
                     validator: Callable[[Path, float], dict[str, Any]] | None = None) -> dict[str, Any]:
    _id(operation_id, "operation_id"); _id(candidate_id, "candidate_id"); root = root.expanduser().absolute()
    with revisions.writer_lock(root):
        state = revisions.read_state(root); opdir = _op_dir(root, operation_id)
        published = state["receipts"].get(operation_id)
        if published is not None:
            if published.get("candidate_id") != candidate_id: raise TransactionError("operation already committed with another candidate")
            intent_path = opdir / "intent.json"; report_path = opdir / "report.json"
            candidate_path = opdir / "candidate" / "design.json"
            if any(path.is_symlink() or not path.is_file() for path in (intent_path, report_path, candidate_path)):
                raise TransactionError("committed trusted-intake evidence is missing or unsafe")
            intent_record = design.read_json(intent_path); report = design.read_json(report_path)
            candidate_bytes = candidate_path.read_bytes(); report_bytes = report_path.read_bytes()
            candidate = design.read_json(candidate_path)
            if (hashlib.sha256(candidate_bytes).hexdigest() != published.get("candidate_sha256")
                    or hashlib.sha256(report_bytes).hexdigest() != published.get("report_sha256")
                    or report.get("candidate_id") != candidate_id
                    or candidate.get("revision_id") != candidate_id):
                raise TransactionError("committed candidate or report changed; durable evidence is corrupt")
            trust = _verify_trusted_ingress(intent_record.get("intent"), intent_record.get("argument_hash"), candidate)
            binding = trust.get("binding_sha256") if trust else None
            if (binding != published.get("trusted_intake_binding_sha256")
                    or report.get("trusted_intake_binding_sha256") != binding):
                raise TransactionError("committed trusted-intake binding does not match its durable evidence")
            _write_json_durable(opdir / "receipt.json", published)
            return published
        for relative in ("intent.json", "receipt.json", "report.json", "base-validation.json", "candidate-validation.json", "candidate/design.json"):
            path = opdir / relative
            if path.is_symlink(): raise TransactionError(f"transaction artifact cannot be a symlink: {relative}")
        intent = design.read_json(opdir / "intent.json"); receipt = design.read_json(opdir / "receipt.json") if (opdir / "receipt.json").exists() else None
        trust = _verify_trusted_ingress(intent.get("intent"), intent.get("argument_hash"))
        binding = trust.get("binding_sha256") if trust else None
        if receipt is None and binding is not None:
            raise TransactionError("candidate receipt is missing trusted-intake provenance")
        if receipt is not None and binding != receipt.get("trusted_intake_binding_sha256"):
            raise TransactionError("candidate receipt does not match trusted-intake provenance")
        if receipt and receipt.get("disposition") == "committed":
            raise TransactionError("operation-local receipt claims commit without an authoritative state receipt")
        if receipt and receipt.get("disposition") == "discarded": raise TransactionError("discarded candidate cannot be committed")
        if receipt and receipt.get("disposition") in {"aborted", "failed"}:
            raise TransactionError(f"{receipt['disposition']} operation cannot be committed; start a new operation against the current base")
        if not receipt or receipt.get("disposition") != "candidate":
            raise TransactionError("operation has no verified candidate receipt")
        report = design.read_json(opdir / "report.json")
        if report.get("candidate_id") != candidate_id: raise TransactionError("candidate ID does not match operation")
        if receipt and receipt.get("report_sha256") != hashlib.sha256((opdir / "report.json").read_bytes()).hexdigest():
            raise TransactionError("candidate report changed; revalidation required")
        if not report.get("commit_eligible"): raise TransactionError("candidate is not commit eligible")
        saved_base_v = design.read_json(opdir / "base-validation.json")
        saved_candidate_v = design.read_json(opdir / "candidate-validation.json")
        environment_identity = _evaluation_environment_identity()
        if environment_identity is None: raise TransactionError("checker environment identity is unavailable; revalidation cannot authorize commit")
        if environment_identity != report.get("evaluation_environment_identity"):
            raise TransactionError("checker environment changed; candidate revalidation required")
        saved_fingerprint = _evaluation_fingerprint(saved_base_v, saved_candidate_v,
            revisions.load_revision(root, state["current_revision_id"])["ground_y"], environment_identity)
        if saved_fingerprint != report.get("evaluation_fingerprint"):
            raise TransactionError("saved evaluation evidence changed; candidate revalidation required")
        if state["current_revision_id"] != intent.get("base_revision_id"):
            raise TransactionError("stale base; candidate must be re-proposed and revalidated")
        candidate_path = opdir / "candidate" / "design.json"; candidate_bytes = candidate_path.read_bytes()
        if hashlib.sha256(candidate_bytes).hexdigest() != report.get("candidate_sha256"):
            raise TransactionError("candidate bytes changed; revalidation required")
        candidate = design.read_json(candidate_path); design.validate_design(candidate)
        verified_trust = _verify_trusted_ingress(intent.get("intent"), intent.get("argument_hash"), candidate)
        verified_binding = verified_trust.get("binding_sha256") if verified_trust else None
        if (verified_binding != receipt.get("trusted_intake_binding_sha256")
                or report.get("trusted_intake_binding_sha256") != verified_binding):
            raise TransactionError("candidate trusted-intake evidence changed; revalidation required")
        if candidate["hashes"]["design"]["value"] != report.get("candidate_design_hash"):
            raise TransactionError("candidate design hash changed; revalidation required")
        # Recheck both base and candidate under the lock and bind to current data.
        with tempfile.TemporaryDirectory(prefix="bricksmith-commit-") as tmp:
            base = revisions.load_revision(root, state["current_revision_id"])
            base_v = _run_validation(base, Path(tmp), "base", validator)
            cand_v = _run_validation(candidate, Path(tmp), "candidate", validator)
            policy = _policy(base_v["evaluation"], cand_v["evaluation"], report.get("policy_conflicts", []))
        environment_after = _evaluation_environment_identity()
        if environment_after is None or environment_after != environment_identity:
            raise TransactionError("checker environment changed during commit revalidation; propose again")
        if not policy["commit_eligible"]: raise TransactionError("commit revalidation blocked: " + json.dumps(policy["reasons"]))
        fingerprint = _evaluation_fingerprint(base_v, cand_v, base["ground_y"], environment_after)
        if fingerprint != report.get("evaluation_fingerprint"):
            raise TransactionError("evaluation fingerprint changed; candidate revalidation required")
        if hashlib.sha256(candidate_path.read_bytes()).hexdigest() != report.get("candidate_sha256"):
            raise TransactionError("candidate bytes changed during commit revalidation")
        if hashlib.sha256((opdir / "report.json").read_bytes()).hexdigest() != receipt.get("report_sha256"):
            raise TransactionError("candidate report changed during commit revalidation")
        metadata = revisions._seal_revision(root, candidate, parent=state["current_revision_id"], operation_id=operation_id,
                                            validation_ref=f"operations/{operation_id}/candidate-validation.json")
        if failpoint: failpoint("after_seal_before_pointer")
        receipt = {"schema": "bricksmith-operation-receipt-v1", "operation_id": operation_id,
                   "argument_hash": intent["argument_hash"], "base_revision_id": state["current_revision_id"],
                   "candidate_id": candidate_id, "revision_id": candidate_id,
                   "candidate_sha256": hashlib.sha256(candidate_bytes).hexdigest(),
                   "report_sha256": hashlib.sha256((opdir / "report.json").read_bytes()).hexdigest(),
                   "disposition": "committed", "commit_eligible": True,
                   "construction_status": policy["status"], "revision_metadata": metadata}
        if verified_binding is not None: receipt["trusted_intake_binding_sha256"] = verified_binding
        state["current_revision_id"] = candidate_id
        state["receipts"][operation_id] = receipt
        revisions.write_state(root, state)  # atomic commit point: pointer + receipt
        if failpoint: failpoint("after_pointer_commit")
        event = revisions.append_event(root, {"kind": "operation_committed", "operation_id": operation_id,
                                              "revision_id": candidate_id, "status": policy["status"]})
        if failpoint: failpoint("during_event_finalization")
        receipt["event_reference"] = event
        state = revisions.read_state(root); state["receipts"][operation_id] = receipt; revisions.write_state(root, state)
        revisions.finalize_compatibility_export(root, candidate_id, failpoint=failpoint)
        _write_json_durable(opdir / "receipt.json", receipt)
        return receipt


def discard_candidate(root: Path, operation_id: str) -> dict[str, Any]:
    _id(operation_id, "operation_id"); root = root.expanduser().absolute()
    with revisions.writer_lock(root):
        state = revisions.read_state(root); opdir = _op_dir(root, operation_id)
        committed = state.get("receipts", {}).get(operation_id)
        if committed is not None: return committed
        receipt_path = opdir / "receipt.json"
        if receipt_path.is_symlink(): raise TransactionError("operation receipt cannot be a symlink")
        if not receipt_path.exists(): raise TransactionError("operation has no candidate receipt")
        receipt = design.read_json(receipt_path)
        if receipt.get("disposition") == "committed":
            raise TransactionError("operation-local receipt claims commit without an authoritative state receipt")
        if receipt.get("disposition") in {"aborted", "failed"}: return receipt
        if receipt.get("disposition") == "discarded": return receipt
        receipt["disposition"] = "discarded"; receipt["discarded_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        _write_json_durable(receipt_path, receipt)
        return receipt


def _validate_failure_record(failure: Any, *, operation_id: str, base_revision_id: Any,
                             status: str, operation_dir: Path | None = None) -> dict[str, Any]:
    if (not isinstance(failure, dict)
            or failure.get("schema") != "bricksmith-candidate-failure-v1"
            or failure.get("operation_id") != operation_id
            or failure.get("status") != status
            or failure.get("base_revision_id") != base_revision_id):
        raise TransactionError(f"{status} terminal failure evidence identity or schema is invalid: {operation_id}")
    if status == "failure":
        if not isinstance(failure.get("error_type"), str) or not failure["error_type"]:
            raise TransactionError(f"failed proposal evidence lacks an error category: {operation_id}")
        if not isinstance(failure.get("error"), str) or not failure["error"]:
            raise TransactionError(f"failed proposal evidence lacks an error message: {operation_id}")
        artifact = failure.get("candidate_artifact")
        if artifact is not None:
            artifact_path = Path(artifact)
            if (artifact != "candidate/invalid-design.json" or artifact_path.is_absolute()
                    or ".." in artifact_path.parts):
                raise TransactionError(f"failed proposal evidence has an unsafe candidate reference: {operation_id}")
            referenced = operation_dir / artifact_path if operation_dir is not None else None
            if referenced is not None and (referenced.is_symlink() or not referenced.is_file()):
                raise TransactionError(f"failed proposal candidate evidence is missing or unsafe: {operation_id}")
    else:
        if (not isinstance(failure.get("reason"), str)
                or not isinstance(failure.get("retained_artifacts"), list)
                or any(not isinstance(item, str) for item in failure["retained_artifacts"])):
            raise TransactionError(f"aborted failure evidence is invalid: {operation_id}")
    return failure


def recover(root: Path, *, failpoint: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Transaction-level recovery repairs committed receipts and post-commit exports."""
    root = root.expanduser().absolute()
    with revisions.writer_lock(root):
        state = revisions.read_state(root)
        current = revisions.load_revision(root, state["current_revision_id"])
        repaired = []
        aborted = []
        for opid, receipt in state["receipts"].items():
            opdir = _op_dir(root, opid)
            candidate_path = opdir / "candidate" / "design.json"
            report_path = opdir / "report.json"
            intent_path = opdir / "intent.json"
            if intent_path.is_symlink() or not intent_path.is_file():
                raise TransactionError(f"committed operation intent is missing or unsafe: {opid}")
            if candidate_path.is_symlink() or not candidate_path.is_file() or hashlib.sha256(candidate_path.read_bytes()).hexdigest() != receipt.get("candidate_sha256"):
                raise TransactionError(f"committed candidate artifact is missing or corrupt: {opid}")
            if report_path.is_symlink() or not report_path.is_file() or hashlib.sha256(report_path.read_bytes()).hexdigest() != receipt.get("report_sha256"):
                raise TransactionError(f"committed candidate report is missing or corrupt: {opid}")
            if receipt.get("disposition") != "committed": raise TransactionError("state references a non-committed operation receipt")
            intent_record = design.read_json(intent_path)
            report = design.read_json(report_path); candidate = design.read_json(candidate_path)
            trust = _verify_trusted_ingress(intent_record.get("intent"), intent_record.get("argument_hash"), candidate)
            binding = trust.get("binding_sha256") if trust else None
            if (binding != receipt.get("trusted_intake_binding_sha256")
                    or report.get("trusted_intake_binding_sha256") != binding):
                raise TransactionError(f"committed trusted-intake provenance is inconsistent: {opid}")
            if not (opdir / "receipt.json").exists() or design.read_json(opdir / "receipt.json").get("disposition") != "committed":
                _write_json_durable(opdir / "receipt.json", receipt); repaired.append(f"receipt:{opid}")
            if not receipt.get("event_reference") or not _event_path(root, receipt["event_reference"]).is_file():
                ref = revisions.append_event(root, {"kind": "operation_committed", "operation_id": opid,
                    "revision_id": receipt["revision_id"], "status": receipt.get("construction_status")})
                receipt["event_reference"] = ref; repaired.append(f"event:{opid}")
                if ref not in state.setdefault("events", []): state["events"].append(ref)
        if state.get("receipts") and state["current_revision_id"] not in {r["revision_id"] for r in state["receipts"].values()}:
            # Later initialization or an unrelated revision is valid; receipt index
            # may reference historical revisions, so only ensure current exists.
            pass
        state["receipts"] = {k: v for k, v in state["receipts"].items()}
        revisions.write_state(root, state)
        expected = (revisions.revision_dir(root, current["revision_id"]) / "build.ldr").read_bytes()
        compatibility = root / "build.ldr"
        if not compatibility.is_file() or compatibility.read_bytes() != expected:
            revisions.finalize_compatibility_export(root, current["revision_id"]); repaired.append("compatibility_export")
        for temp_export in root.glob(".build.ldr.*"):
            if temp_export.is_file() and not temp_export.is_symlink():
                temp_export.unlink(); repaired.append("removed_interrupted_compatibility_temp")
        # Staged/uncommitted sealed candidates are intentionally retained and
        # reported, never published by recovery.
        uncommitted = []
        failed = []
        discarded = []
        for folder in sorted((root / "operations").iterdir()):
            if not folder.is_dir() or folder.is_symlink(): continue
            opid = folder.name
            if opid in state["receipts"]: continue
            op_receipt = folder / "receipt.json"
            if op_receipt.is_symlink(): raise TransactionError(f"operation receipt is a symlink: {opid}")
            local = design.read_json(op_receipt) if op_receipt.is_file() else None
            if local and local.get("disposition") == "committed":
                raise TransactionError(f"operation-local receipt claims commit without authoritative state receipt: {opid}")
            if local and local.get("disposition") == "discarded":
                discarded.append(opid); continue
            if local and local.get("disposition") in {"aborted", "failed"}:
                if local.get("disposition") == "aborted":
                    preserved = folder / "interrupted-candidate-receipt.json"
                    failure_path = folder / "failure.json"
                    if preserved.exists() or preserved.is_symlink():
                        if preserved.is_symlink() or not preserved.is_file(): raise TransactionError(f"preserved candidate receipt is unsafe: {opid}")
                        digest = hashlib.sha256(preserved.read_bytes()).hexdigest()
                        if local.get("preserved_receipt_sha256") != digest:
                            raise TransactionError(f"preserved candidate receipt does not match terminal receipt: {opid}")
                    if failure_path.exists() or failure_path.is_symlink():
                        if failure_path.is_symlink() or not failure_path.is_file() or design.read_json(failure_path) != local.get("failure"):
                            raise TransactionError(f"aborted failure evidence does not match terminal receipt: {opid}")
                    aborted.append(opid)
                else:
                    intent_path = folder / "intent.json"
                    failure_path = folder / "failure.json"
                    if (intent_path.is_symlink() or not intent_path.is_file()
                            or failure_path.is_symlink() or not failure_path.is_file()):
                        raise TransactionError(f"failed operation evidence is missing or unsafe: {opid}")
                    intent = design.read_json(intent_path)
                    if (intent.get("operation_id") != opid
                            or not isinstance(intent.get("argument_hash"), str)
                            or not isinstance(intent.get("base_revision_id"), str)
                            or local.get("argument_hash") != intent.get("argument_hash")
                            or local.get("base_revision_id") != intent.get("base_revision_id")):
                        raise TransactionError(f"failed operation receipt does not match durable intent: {opid}")
                    failure = _validate_failure_record(design.read_json(failure_path), operation_id=opid,
                        base_revision_id=intent.get("base_revision_id"), status="failure", operation_dir=folder)
                    if local.get("failure") != failure:
                        raise TransactionError(f"failed operation receipt does not match failure evidence: {opid}")
                    failed.append(opid)
                continue
            intent_path = folder / "intent.json"
            if not intent_path.exists() and not any(folder.iterdir()):
                folder.rmdir(); repaired.append(f"removed_empty_staging:{opid}"); continue
            reason = None
            intent = None
            if intent_path.is_symlink(): reason = "intent artifact is a symlink"
            elif not intent_path.is_file(): reason = "durable intent is missing"
            else:
                try:
                    loaded_intent = design.read_json(intent_path)
                    if not isinstance(loaded_intent, dict):
                        reason = "durable intent is not a JSON object"
                    elif loaded_intent.get("operation_id") != opid or not isinstance(loaded_intent.get("argument_hash"), str):
                        reason = "durable intent identity is malformed"
                    else:
                        intent = loaded_intent
                except Exception as exc:
                    reason = f"durable intent is unreadable: {type(exc).__name__}"
            if reason is None and local and local.get("disposition") == "candidate":
                try:
                    candidate_path = folder / "candidate" / "design.json"
                    report_path = folder / "report.json"
                    if candidate_path.is_symlink() or not candidate_path.is_file(): raise ValueError("candidate design is missing or unsafe")
                    if report_path.is_symlink() or not report_path.is_file(): raise ValueError("candidate report is missing or unsafe")
                    candidate_bytes = candidate_path.read_bytes(); report_bytes = report_path.read_bytes()
                    report = design.read_json(report_path); candidate = design.read_json(candidate_path)
                    design.validate_design(candidate)
                    if hashlib.sha256(candidate_bytes).hexdigest() != local.get("candidate_sha256") or local.get("candidate_sha256") != report.get("candidate_sha256"):
                        raise ValueError("candidate bytes do not match the sealed receipt and report")
                    if hashlib.sha256(report_bytes).hexdigest() != local.get("report_sha256"):
                        raise ValueError("report bytes do not match the sealed receipt")
                    if candidate.get("revision_id") != local.get("candidate_id") or report.get("candidate_id") != local.get("candidate_id"):
                        raise ValueError("candidate identity does not match its sealed receipt")
                    if intent.get("argument_hash") != local.get("argument_hash") or intent.get("base_revision_id") != local.get("base_revision_id"):
                        raise ValueError("candidate receipt does not match its durable intent")
                    uncommitted.append(opid)
                    continue
                except Exception as exc:
                    reason = f"candidate receipt is incomplete or unverifiable: {exc}"
            elif reason is None and local is not None:
                reason = f"unsupported operation-local disposition: {local.get('disposition')}"
            elif reason is None and intent is not None:
                reason = "proposal interrupted before a complete candidate receipt was sealed"
            failure_path = folder / "failure.json"
            if (reason in {None, "proposal interrupted before a complete candidate receipt was sealed"}
                    and intent is not None and failure_path.exists()):
                if failure_path.is_symlink() or not failure_path.is_file():
                    raise TransactionError(f"failed proposal evidence is unsafe: {opid}")
                saved_failure = design.read_json(failure_path)
                if isinstance(saved_failure, dict) and saved_failure.get("status") == "failure":
                    failure = _validate_failure_record(saved_failure, operation_id=opid,
                        base_revision_id=intent.get("base_revision_id"), status="failure", operation_dir=folder)
                    terminal = {"schema": "bricksmith-operation-receipt-v1", "operation_id": opid,
                        "argument_hash": intent["argument_hash"], "base_revision_id": intent["base_revision_id"],
                        "candidate_id": None, "candidate_sha256": None, "report_sha256": None,
                        "disposition": "failed", "status": "failure", "failure": failure}
                    if failpoint: failpoint("before_failed_receipt_flush")
                    _write_json_durable(op_receipt, terminal)
                    if failpoint: failpoint("after_failed_receipt_flush")
                    failed.append(opid); repaired.append(f"reconciled_failed_proposal:{opid}")
                    continue
            failure = {"schema": "bricksmith-candidate-failure-v1", "operation_id": opid,
                       "base_revision_id": intent.get("base_revision_id") if intent else None,
                       "status": "aborted", "reason": reason,
                       "retained_artifacts": sorted(path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file()
                           and path.name not in {"failure.json", "receipt.json", "interrupted-candidate-receipt.json"})}
            prior_receipt = folder / "interrupted-candidate-receipt.json"
            preserved_hash = None
            if local and local.get("disposition") == "candidate":
                original = (design._json_text(local, indent=2, sort_keys=True) + "\n").encode()
                if prior_receipt.is_symlink(): raise TransactionError(f"interrupted candidate receipt evidence is unsafe: {opid}")
                if prior_receipt.exists():
                    if not prior_receipt.is_file() or prior_receipt.read_bytes() != original:
                        raise TransactionError(f"interrupted candidate receipt evidence does not match original: {opid}")
                else:
                    _write_json_durable(prior_receipt, local)
                    if failpoint: failpoint("after_interrupted_receipt_preserved")
                preserved_hash = hashlib.sha256(original).hexdigest()
            failure_path = folder / "failure.json"
            if failure_path.is_symlink(): raise TransactionError(f"aborted failure evidence is unsafe: {opid}")
            if failure_path.exists():
                if not failure_path.is_file(): raise TransactionError(f"aborted failure evidence is unsafe: {opid}")
                failure = _validate_failure_record(design.read_json(failure_path), operation_id=opid,
                    base_revision_id=intent.get("base_revision_id") if intent else None, status="aborted")
            else:
                _write_json_durable(failure_path, failure)
            if failpoint: failpoint("after_interrupted_failure_record")
            terminal = {"schema": "bricksmith-operation-receipt-v1", "operation_id": opid,
                        "argument_hash": intent.get("argument_hash") if intent else None,
                        "base_revision_id": intent.get("base_revision_id") if intent else None,
                        "candidate_id": None, "candidate_sha256": None, "report_sha256": None,
                        "disposition": "aborted", "status": "aborted", "failure": failure}
            if preserved_hash is not None: terminal["preserved_receipt_sha256"] = preserved_hash
            _write_json_durable(op_receipt, terminal)
            aborted.append(opid); repaired.append(f"aborted_incomplete_proposal:{opid}")
        referenced = {state["current_revision_id"]} | {receipt.get("revision_id") for receipt in state["receipts"].values()}
        orphan_revisions = sorted(p.name for p in (root / "revisions").iterdir()
            if p.is_dir() and p.name not in referenced and not p.name.startswith("."))
        staging_revisions = sorted(p.name for p in (root / "revisions").iterdir()
            if p.is_dir() and p.name.startswith("."))
        staging_files = sorted(p.relative_to(root).as_posix() for p in root.rglob(".*")
            if p.is_file() and not p.is_symlink())
        return {"current_revision_id": current["revision_id"], "repaired": repaired,
                "uncommitted_operations": uncommitted, "discarded_operations": discarded,
                "aborted_operations": aborted, "failed_operations": failed,
                "orphan_revisions": orphan_revisions,
                "staging_revisions": staging_revisions, "staging_files": staging_files}
