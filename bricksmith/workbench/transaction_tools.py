"""Schema-aware offline adapters from legacy BrickSmith tool names to M2 transactions.

The module never publishes geometry itself. Every mutation is lowered to one
operation-v2 request and committed through :mod:`transactions`.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import shutil
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

from . import design, revisions, transactions

CATALOG_SCHEMA = "bricksmith-offline-tool-catalog-v1"
INVOCATION_SCHEMA = transactions.ADAPTER_INVOCATION_SCHEMA
RESULT_SCHEMA = "bricksmith-tool-result-v1"
MUTATION_TOOLS = frozenset({"save_module", "clone_module", "discard_module", "recolor_module_lines",
    "edit_lines", "move_lines", "move_groups", "save_array", "save_floor", "save_wall_runs",
    "save_gable", "save_stepped_roof_beams", "save_roof_tile_caps", "save_support_column",
    "save_roof_seam_column"})
READ_TOOLS = frozenset({"read_module", "inspect_build_region", "inspect_alignment", "check", "render"})
SUPPORTED_TOOLS = MUTATION_TOOLS | READ_TOOLS
UNSUPPORTED_TRANSACTION_TOOLS = frozenset({"set_plan", "review_renders", "submit_design"})
MODULE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,35}$")
VIEWS = {"front_left": (215, 28), "front_right": (325, 28),
         "back_left": (145, 28), "back_right": (35, 28), "top": (215, 70)}
_ADAPTER_FAILPOINT = None


def _adapter_failpoint(phase: str) -> None:
    callback = _ADAPTER_FAILPOINT
    if callback is not None:
        callback(phase)


def _tool_specs() -> dict[str, dict[str, Any]]:
    from .agent_session import TOOLS
    return {tool["name"]: tool for namespace in TOOLS for tool in namespace["tools"]}


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object": return isinstance(value, dict)
    if expected == "array": return isinstance(value, list)
    if expected == "string": return isinstance(value, str)
    if expected == "boolean": return type(value) is bool
    if expected == "integer": return type(value) is int
    if expected == "number": return (type(value) in (int, float, Decimal)
        and not isinstance(value, bool) and math.isfinite(float(value)))
    return True


def validate_arguments(tool_name: str, arguments: Any) -> dict[str, Any]:
    """Validate an offline call against the same strict function schema as the runner."""
    spec = _tool_specs().get(tool_name)
    if spec is None: raise transactions.TransactionError(f"Unsupported BrickSmith tool: {tool_name}")
    schema = spec["parameters"]
    if not isinstance(arguments, dict): raise transactions.TransactionError("tool arguments must be an object")
    props = schema["properties"]
    if set(arguments) - set(props): raise transactions.TransactionError(f"{tool_name} has unknown argument(s): {', '.join(sorted(set(arguments)-set(props)))}")
    missing = set(schema.get("required", [])) - set(arguments)
    if missing: raise transactions.TransactionError(f"{tool_name} is missing argument(s): {', '.join(sorted(missing))}")

    def check(value: Any, rule: dict[str, Any], where: str) -> None:
        kind = rule.get("type")
        if kind and not _matches_type(value, kind): raise transactions.TransactionError(f"{where} must be {kind}")
        if "enum" in rule and value not in rule["enum"]: raise transactions.TransactionError(f"{where} must be one of {rule['enum']}")
        if kind == "object":
            child_props = rule.get("properties", {})
            extra = set(value) - set(child_props)
            if rule.get("additionalProperties") is False and extra:
                raise transactions.TransactionError(f"{where} has unknown field(s): {', '.join(sorted(extra))}")
            absent = set(rule.get("required", [])) - set(value)
            if absent: raise transactions.TransactionError(f"{where} is missing field(s): {', '.join(sorted(absent))}")
            for key, child in value.items():
                if key in child_props: check(child, child_props[key], f"{where}.{key}")
        elif kind == "array":
            item_rule = rule.get("items")
            if item_rule:
                for index, child in enumerate(value): check(child, item_rule, f"{where}[{index}]")

    for key, value in arguments.items(): check(value, props[key], f"{tool_name}.{key}")
    return copy.deepcopy(arguments)


def catalog() -> dict[str, Any]:
    specs = _tool_specs()
    return {"schema": CATALOG_SCHEMA, "invocation_schema": INVOCATION_SCHEMA,
        "required_invocation_context": ["schema", "tool_name", "arguments", "operation_id",
            "expected_base_revision_id", "expected_export_sha256"],
        "tools": [{"name": name, "kind": "mutation" if name in MUTATION_TOOLS else "read",
                   "arguments": specs[name]["parameters"]}
                  for name in sorted(SUPPORTED_TOOLS)]}


def catalog_bytes() -> bytes:
    return (design._json_text(catalog(), indent=2, sort_keys=True) + "\n").encode("utf-8")


def _uuid5(operation_id: str, label: str) -> str:
    return str(uuid.uuid5(uuid.UUID(operation_id), label))


def _validate_invocation(value: Any, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict): raise transactions.TransactionError("offline tool invocation context is required")
    expected = {"schema", "tool_name", "arguments", "operation_id", "expected_base_revision_id", "expected_export_sha256"}
    if set(value) != expected: raise transactions.TransactionError("tool invocation must contain exactly the versioned required fields")
    if value.get("schema") != INVOCATION_SCHEMA: raise transactions.TransactionError(f"invocation schema must be {INVOCATION_SCHEMA}")
    if value.get("tool_name") != tool_name: raise transactions.TransactionError("invocation tool_name differs from dispatched tool")
    checked_args = validate_arguments(tool_name, value.get("arguments"))
    if design.canonical_json(checked_args) != design.canonical_json(args):
        raise transactions.TransactionError("invocation arguments differ from dispatched tool arguments")
    transactions._id(value.get("operation_id"), "invocation.operation_id")
    transactions._id(value.get("expected_base_revision_id"), "invocation.expected_base_revision_id")
    if not isinstance(value.get("expected_export_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", value["expected_export_sha256"]):
        raise transactions.TransactionError("invocation.expected_export_sha256 must be a SHA-256 digest")
    return copy.deepcopy(value)


def _revision_exports(root: Path, revision: dict[str, Any]) -> tuple[Path, bytes, dict[str, Any], dict[str, dict[str, Any]]]:
    folder = revisions.revision_dir(root, revision["revision_id"])
    build_path = folder / "build.ldr"
    line_map_path = folder / "line_map.json"
    if build_path.is_symlink() or line_map_path.is_symlink(): raise transactions.TransactionError("sealed revision export cannot be a symlink")
    build = build_path.read_bytes()
    line_map = design.load_line_map(line_map_path)
    try: exports = design._validate_line_map_for_design(line_map, revision)
    except design.DesignError as exc: raise transactions.TransactionError(f"sealed revision line map is invalid: {exc}") from exc
    for export_path, record in exports.items():
        path = folder / export_path
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != record["file_sha256"]:
            raise transactions.TransactionError(f"sealed export or line map is corrupt: {export_path}")
    build_hash = hashlib.sha256(build).hexdigest()
    if build_hash != exports["build.ldr"]["file_sha256"]:
        raise transactions.TransactionError("sealed build bytes do not match its verified line map")
    return folder, build, line_map, exports


def _module(revision: dict[str, Any], name: str, *, allow_new: bool = False) -> dict[str, Any] | None:
    if not isinstance(name, str) or not name:
        raise transactions.TransactionError("Module name must be a nonempty string")
    matches = [assembly for assembly in revision["assemblies"] if assembly["name"] == name]
    if len(matches) > 1: raise transactions.TransactionError(f"Ambiguous module name {name!r}; resolve it explicitly before adapter use")
    if matches: return matches[0]
    if allow_new:
        if not MODULE_RE.fullmatch(name): raise transactions.TransactionError("New module name must be lowercase letters, digits, hyphens, or underscores")
        return None
    if not matches:
        raise transactions.TransactionError(f"Unknown module {name!r}")


def _parse_module_source(name: str, ldr: str, operation_id: str, assembly_id: str,
                         *, role: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    raw = ldr.encode("utf-8")
    imported = design.import_ldr(raw, source_name=f"modules/{name}.ldr")
    count = len(imported["parts"])
    if not 1 <= count <= 250: raise transactions.TransactionError("A compatibility module must contain 1-250 physical placements")
    source_id = _uuid5(operation_id, f"module-source:{name}")
    raw_hash = hashlib.sha256(raw).hexdigest()
    source_reference = {"id": source_id, "original_source_identity": raw_hash,
        "content_hash": design.file_hash(raw), "role": role,
        "local_artifact_reference": None, "license_rights_status": "unknown", "missing_data_notes": None}
    parts = []
    for ordinal, original in enumerate(imported["parts"]):
        part = copy.deepcopy(original)
        part["id"] = _uuid5(operation_id, f"module-part:{name}:{ordinal}")
        part["assembly_id"] = assembly_id
        part["provenance"] = {"source_reference_id": source_id, "source_file": f"modules/{name}.ldr",
            "source_line": part["provenance"]["source_line"], "placement_ordinal": ordinal,
            "operation_id": operation_id, "source": role}
        parts.append(part)
    comments = [{"text": item["text"], "source_line": item["source_line"]}
                for item in imported["source_comments"]]
    return parts, comments, source_reference


def _bulk_op(assembly_id: str, bundle: tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    parts, comments, reference = bundle
    return {"type": "replace_assembly_contents", "assembly_id": assembly_id,
            "parts": parts, "source_comments": comments, "source_reference": reference}


def _operation_request(invocation: dict[str, Any], operations: list[dict[str, Any]],
                       intent: str, generated_content: str | None = None,
                       result_metadata: dict[str, Any] | None = None,
                       schema: str = transactions.OPERATION_SCHEMA_V2) -> dict[str, Any]:
    request = {"schema": schema,
        "operation_id": invocation["operation_id"],
        "base_revision_id": invocation["expected_base_revision_id"],
        "intent": intent, "operations": operations,
        "adapter_invocation": invocation}
    if generated_content is not None or result_metadata is not None:
        request["adapter_evidence"] = {"schema": "bricksmith-tool-operation-evidence-v1"}
        if generated_content is not None: request["adapter_evidence"]["generated_content"] = generated_content
        if result_metadata is not None: request["adapter_evidence"]["result_metadata"] = copy.deepcopy(result_metadata)
    return request


def _line_lookup(line_map: dict[str, Any], export_path: str) -> dict[int, dict[str, Any]]:
    entry = line_map["exports"][export_path]
    return {item["line"]: item for item in entry["placements"]}


def _result(root: Path, invocation: dict[str, Any], tool_name: str, *,
            report: dict[str, Any] | None = None, receipt: dict[str, Any] | None = None,
            disposition: str | None = None, stale: bool = False,
            extra: dict[str, Any] | None = None) -> dict[str, Any]:
    state = revisions.read_state(root)
    current = revisions.load_revision(root, state["current_revision_id"])
    _, current_build, _, _ = _revision_exports(root, current)
    opid = invocation["operation_id"]
    opdir = root / "operations" / opid
    report_path = opdir / "report.json"
    if report is None and report_path.is_file() and not report_path.is_symlink():
        report = design.read_json(report_path)
    if receipt is None:
        receipt_path = opdir / "receipt.json"
        if receipt_path.is_file() and not receipt_path.is_symlink(): receipt = design.read_json(receipt_path)
    if disposition is None:
        disposition = receipt.get("disposition") if isinstance(receipt, dict) else "candidate"
    policy = report.get("policy", {}) if isinstance(report, dict) else {}
    candidate_id = (receipt or {}).get("candidate_id") or (report or {}).get("candidate_id")
    operation_revision_id = ((receipt or {}).get("revision_id") or
                             (receipt or {}).get("candidate_id") or
                             (report or {}).get("candidate_id"))
    stale_candidate = disposition == "candidate" and current["revision_id"] != invocation["expected_base_revision_id"]
    result = {"schema": RESULT_SCHEMA, "tool": tool_name,
        "operation_id": opid, "candidate_id": candidate_id,
        "operation_revision_id": operation_revision_id,
        "base_revision_id": invocation["expected_base_revision_id"],
        "current_revision_id": current["revision_id"],
        "disposition": disposition,
        "committed": disposition == "committed",
        "stale_base": disposition == "stale_base" or stale or stale_candidate,
        "status": ((receipt or {}).get("construction_status") or (report or {}).get("status")
                   or (receipt or {}).get("status")),
        "policy_reasons": policy.get("reasons", []),
        "affected_ids": (report or {}).get("affected_ids", []),
        "report_reference": f"operations/{opid}/report.json" if report_path.is_file() else None,
        "failure_reference": f"operations/{opid}/failure.json" if (opdir / "failure.json").is_file() else None,
        "invocation_sha256": transactions._canonical_hash(invocation),
        "export_identity": {"revision_id": current["revision_id"],
                            "path": "build.ldr", "sha256": hashlib.sha256(current_build).hexdigest()}}
    if isinstance(report, dict):
        result["policy_status"] = report.get("status")
        if disposition == "candidate":
            result["commit_eligible"] = False if stale_candidate or stale else report.get("commit_eligible", False)
        elif disposition == "committed":
            result["commit_eligible"] = bool((receipt or {}).get("commit_eligible"))
        else:
            result["commit_eligible"] = False
        if stale_candidate or stale:
            result["historical_policy_status"] = report.get("status")
            result["policy_status"] = "stale_base"
    if isinstance(receipt, dict): result["receipt"] = receipt
    if disposition == "stale_base": result["status"] = "stale_base"
    if stale_candidate: result["status"] = "stale_base"
    saved_extra = (report or {}).get("adapter_result", {}) if isinstance(report, dict) else {}
    details: dict[str, Any] = {}
    if isinstance(saved_extra, dict): details.update(saved_extra)
    if isinstance(extra, dict): details.update(extra)
    if details:
        # Adapter details are evidence, never transaction outcomes. Keep all
        # caller-supplied details namespaced so no field can impersonate result
        # authority, even when its key is not currently reserved here.
        result["tool_details"] = copy.deepcopy(details)
    return result


def _existing_operation_result(root: Path, invocation: dict[str, Any], tool_name: str,
                               opdir: Path) -> dict[str, Any]:
    """Resolve an adapter retry from its original durable intent and evidence."""
    if opdir.is_symlink() or not opdir.is_dir():
        raise transactions.TransactionError("Existing operation path is unsafe or incomplete")
    intent_path = opdir / "intent.json"
    if intent_path.is_symlink(): raise transactions.TransactionError("Existing operation intent cannot be a symlink")
    if not intent_path.is_file():
        raise transactions.TransactionError("Existing operation requires recovery; durable intent is missing")
    stored = design.read_json(intent_path)
    if stored.get("operation_id") != invocation["operation_id"]:
        raise transactions.TransactionError("Existing operation intent identity is corrupt")
    frozen = stored.get("intent")
    original = frozen.get("adapter_invocation") if isinstance(frozen, dict) else None
    if not isinstance(original, dict) or design.canonical_json(original) != design.canonical_json(invocation):
        raise transactions.TransactionError("operation ID was reused with a different tool, arguments, base, or export identity")
    report_path = opdir / "report.json"
    if report_path.is_symlink(): raise transactions.TransactionError("Existing operation report cannot be a symlink")
    report = design.read_json(report_path) if report_path.is_file() else None
    state = revisions.read_state(root)
    authoritative = state.get("receipts", {}).get(invocation["operation_id"])
    if authoritative is not None:
        if not isinstance(report, dict) or hashlib.sha256(report_path.read_bytes()).hexdigest() != authoritative.get("report_sha256"):
            raise transactions.TransactionError("Committed operation report is missing or corrupt")
        if report.get("operation_id") != invocation["operation_id"]:
            raise transactions.TransactionError("Committed operation report identity is corrupt")
        if report.get("adapter_invocation_sha256") != transactions._canonical_hash(invocation):
            raise transactions.TransactionError("Committed operation report invocation binding is corrupt")
        return _result(root, invocation, tool_name, report=report, receipt=authoritative)
    receipt_path = opdir / "receipt.json"
    if receipt_path.is_symlink(): raise transactions.TransactionError("Existing operation receipt cannot be a symlink")
    local_receipt = design.read_json(receipt_path) if receipt_path.is_file() else None
    if isinstance(local_receipt, dict) and local_receipt.get("disposition") in {"failed", "aborted", "discarded"}:
        if local_receipt.get("operation_id") != invocation["operation_id"]:
            raise transactions.TransactionError("Existing terminal receipt identity is corrupt")
        return _result(root, invocation, tool_name, report=report, receipt=local_receipt)
    if report is None:
        return _result(root, invocation, tool_name, disposition="recovery_required",
                       extra={"error": "operation staging is incomplete; run transaction-recover before retry"})
    if report.get("adapter_invocation_sha256") != transactions._canonical_hash(invocation):
        raise transactions.TransactionError("Existing candidate report invocation binding is corrupt")
    inspected = transactions.inspect_candidate(root, invocation["operation_id"])
    if inspected.get("disposition") in {"failed", "aborted", "discarded"}:
        return _result(root, invocation, tool_name, report=report, receipt=inspected)
    if inspected.get("status") == "staging":
        return _result(root, invocation, tool_name, disposition="recovery_required",
                       extra={"error": "operation staging is incomplete; run transaction-recover before retry"})
    return _result(root, invocation, tool_name, report=report, disposition="candidate")


def _propose_commit(root: Path, invocation: dict[str, Any], tool_name: str,
                    request: dict[str, Any], *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    created_candidate: list[bool] = []
    try:
        proposal = transactions.propose_edit(root, request, _created_candidate=created_candidate,
            failpoint=lambda phase: _adapter_failpoint(
                "after_intent_flush" if phase == "after_intent_flush" else "after_candidate_seal")
            if phase in {"after_intent_flush", "after_candidate_seal_before_pointer"} else None)
    except transactions.TransactionError as exc:
        current_id = revisions.read_state(root)["current_revision_id"]
        if "stale base" in str(exc).lower():
            return _result(root, invocation, tool_name, disposition="stale_base", stale=True,
                           extra={"error": str(exc), **(extra or {})})
        raise
    if proposal.get("status") == "failure":
        receipt_path = root / "operations" / invocation["operation_id"] / "receipt.json"
        receipt = design.read_json(receipt_path) if receipt_path.is_file() else None
        return _result(root, invocation, tool_name, receipt=receipt, extra=extra)
    if proposal.get("disposition") in {"committed", "failed", "aborted", "discarded"}:
        return _result(root, invocation, tool_name, report=proposal if proposal.get("candidate_id") else None,
                       receipt=proposal, extra=extra)
    # A previously sealed candidate is explicitly staged. An identical retry
    # returns it and never publishes it implicitly.
    if not created_candidate or not created_candidate[0]:
        return _result(root, invocation, tool_name, report=proposal, disposition="candidate",
                       stale=revisions.read_state(root)["current_revision_id"] != invocation["expected_base_revision_id"],
                       extra=extra)
    if not proposal.get("commit_eligible"):
        return _result(root, invocation, tool_name, report=proposal, disposition="candidate", extra=extra)
    try:
        receipt = transactions.commit_candidate(root, invocation["operation_id"], proposal["candidate_id"],
            failpoint=lambda phase: _adapter_failpoint("after_pointer_publication") if phase == "after_pointer_commit" else None)
        return _result(root, invocation, tool_name, report=proposal, receipt=receipt, extra=extra)
    except transactions.TransactionError as exc:
        if "stale base" in str(exc).lower():
            return _result(root, invocation, tool_name, report=proposal, disposition="candidate", stale=True,
                           extra={"error": str(exc), **(extra or {})})
        raise


def _args_to_ldr(tool_name: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    from . import agent_session as legacy
    name = args.get("name")
    if tool_name == "save_module": return args["ldr"], {}
    if tool_name == "save_array":
        return _expand_array_exact(args["template"], args["counts"],
            [args["step_x"], args["step_y"], args["step_z"]]), {
                "pattern": {"counts": args["counts"],
                    "template_parts": sum(line.startswith("1 ") for line in args["template"].splitlines())}}
    generators = {
        "save_floor": lambda: legacy._floor_ldr(args["rectangles"], args["y"], args["color"]),
        "save_wall_runs": lambda: legacy._wall_runs_ldr(args["runs"], args["bottom_y"], args["color"]),
        "save_gable": lambda: legacy._gable_ldr(args["axis"], args["start"], args["end"], args["fixed"], args["bottom_y"], args["courses"], args["inset_studs"], args["color"]),
        "save_stepped_roof_beams": lambda: legacy._stepped_roof_beams_ldr(args["left_x"], args["right_x"], args["front_z"], args["rear_z"], args["gable_bottom_y"], args["courses"], args["beam_studs"], args["color"]),
        "save_roof_tile_caps": lambda: legacy._roof_tile_caps_ldr(args["left_x"], args["right_x"], args["front_z"], args["rear_z"], args["gable_bottom_y"], args["courses"], args["beam_studs"], args["color"]),
        "save_support_column": lambda: legacy._support_column_ldr(args["x"], args["z"], args["bottom_y"], args["bricks"], args["color"], args["cap_color"], args["cap_plate"], args["size_studs"]),
        "save_roof_seam_column": lambda: legacy._roof_seam_column_ldr(args["x"], args["z"], args["bottom_y"], args["bricks"], args["color"], args["cap_color"]),
    }
    if tool_name not in generators: raise transactions.TransactionError(f"{tool_name} is not a module generator")
    # Guard aggregate geometry before invoking expansion helpers; generated
    # placement count is still checked exactly afterward.
    if tool_name == "save_floor":
        cells = sum(max(0, (r["x_max"]-r["x_min"])//20) * max(0, (r["z_max"]-r["z_min"])//20)
                    for r in args["rectangles"])
        if cells > 5000: raise transactions.TransactionError("Floor footprint exceeds the bounded generator expansion")
    if tool_name == "save_wall_runs":
        cells = sum(max(0, (r["end"]-r["start"])//20) * r["courses"] for r in args["runs"])
        if cells > 5000: raise transactions.TransactionError("Wall runs exceed the bounded generator expansion")
    ldr = generators[tool_name]()
    extra_keys = {"save_floor": "generated_floor_parts", "save_wall_runs": "generated_wall_parts",
        "save_gable": "generated_gable_parts", "save_stepped_roof_beams": "generated_roof_parts",
        "save_roof_tile_caps": "generated_roof_cap_parts", "save_support_column": "generated_column_parts",
        "save_roof_seam_column": "generated_column_parts"}
    generated = sum(line.startswith("1 ") for line in ldr.splitlines())
    extra_count = 2 * args["courses"] if tool_name == "save_stepped_roof_beams" else generated
    return ldr, {extra_keys[tool_name]: extra_count}


def _decimal_times_int_exact(value: Decimal, count: int) -> Decimal:
    if count < 0: return -_decimal_times_int_exact(value, -count)
    result = Decimal(0)
    for _ in range(count): result = design._decimal_add_exact(result, value)
    return result


def _expand_array_exact(template: str, counts: list[int], steps: list[list[Any]]) -> str:
    """Transaction array expansion with exact decimal coordinates and M1 parsing."""
    if len(counts) != 3 or any(type(number) is not int or not 1 <= number <= 30 for number in counts):
        raise transactions.TransactionError("counts must contain three integers from 1 to 30")
    if len(steps) != 3 or any(not isinstance(step, list) or len(step) != 3 for step in steps):
        raise transactions.TransactionError("Each array step must contain three finite LDU coordinates")
    normalized_steps: list[list[Decimal]] = []
    for axis, step in enumerate(steps):
        row = []
        for coordinate in step:
            try: number = design._as_decimal(coordinate, f"step_{axis}")
            except design.DesignError as exc: raise transactions.TransactionError(str(exc)) from exc
            if abs(number) > 2000: raise transactions.TransactionError("Each array step must stay within ±2000 LDU")
            row.append(number)
        normalized_steps.append(row)
    try: imported = design.import_ldr(template.encode("utf-8"), source_name="array-template.ldr")
    except design.DesignError as exc: raise transactions.TransactionError(str(exc)) from exc
    template_parts = imported["parts"]
    if not 1 <= len(template_parts) <= 20:
        raise transactions.TransactionError("Array template must contain 1-20 placement lines")
    total = len(template_parts) * counts[0] * counts[1] * counts[2]
    if total > 250: raise transactions.TransactionError("Expanded array exceeds 250 module parts")
    lines = [item["text"] for item in imported["source_comments"]]
    for ix in range(counts[0]):
        for iy in range(counts[1]):
            for iz in range(counts[2]):
                offsets = [design._decimal_add_exact(
                    design._decimal_add_exact(_decimal_times_int_exact(normalized_steps[0][axis], ix),
                                              _decimal_times_int_exact(normalized_steps[1][axis], iy)),
                    _decimal_times_int_exact(normalized_steps[2][axis], iz)) for axis in range(3)]
                for part in template_parts:
                    position = [design._decimal_add_exact(value, offset)
                                for value, offset in zip(part["translation_ldu"], offsets)]
                    rotation = [value for row in part["rotation"] for value in row]
                    fields = ["1", str(part["color_id"])]
                    fields.extend(design._format_number(value) for value in position + rotation)
                    fields.append(part["ldraw_part_reference"])
                    lines.append(" ".join(fields))
    return "\n".join(lines)


def _mutation_request(invocation: dict[str, Any], base: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    name, args, opid = invocation["tool_name"], invocation["arguments"], invocation["operation_id"]
    ops: list[dict[str, Any]] = []
    extra: dict[str, Any] = {}
    evidence: str | None = None
    if name in {"save_module", "save_array", "save_floor", "save_wall_runs", "save_gable",
                "save_stepped_roof_beams", "save_roof_tile_caps", "save_support_column", "save_roof_seam_column"}:
        module_name = args["name"]
        assembly = _module(base, module_name, allow_new=True)
        aid = assembly["id"] if assembly else _uuid5(opid, f"assembly:{module_name}")
        if assembly is None:
            ops.append({"type": "create_assembly", "assembly": {"id": aid, "name": module_name,
                "role": None, "parent_assembly_id": None, "design_properties": {},
                "relationships": [], "field_locks": []}})
        ldr, extra = _args_to_ldr(name, args)
        if not isinstance(ldr, str): raise transactions.TransactionError("generated module content must be text")
        if len(ldr.encode("utf-8")) > transactions.MAX_REQUEST_BYTES // 2:
            raise transactions.TransactionError("generated module content exceeds the bounded adapter input")
        bundle = _parse_module_source(module_name, ldr, opid, aid,
                                      role="agent_generated_module" if name != "save_module" else "agent_authored_module")
        ops.append(_bulk_op(aid, bundle)); evidence = ldr if name != "save_module" else None
        extra.update({"module": module_name, "module_parts": len(bundle[0]),
            "replacement_identity": "delete-add with fresh stable part IDs"})
    elif name == "clone_module":
        source = _module(base, args["source"]); destination = args["name"]
        if _module(base, destination, allow_new=True) is not None: raise transactions.TransactionError("Clone destination must be a new module name")
        source_aid = source["id"]
        if any(a.get("parent_assembly_id") == source_aid for a in base["assemblies"]):
            raise transactions.TransactionError("clone_module is limited to leaf modules")
        offsets = [args["dx"], args["dy"], args["dz"]]
        if any(type(v) is not int or abs(v) > 2000 for v in offsets) or not any(offsets):
            raise transactions.TransactionError("Translation must use integer LDU offsets within ±2000, at least one nonzero")
        destination_id = _uuid5(opid, f"assembly:{destination}")
        ops.append({"type": "create_assembly", "assembly": {"id": destination_id, "name": destination,
            "role": source.get("role"), "parent_assembly_id": None, "design_properties": {},
            "relationships": [], "field_locks": []}})
        source_parts = [part for part in base["parts"] if part["assembly_id"] == source_aid]
        if not 1 <= len(source_parts) <= 250:
            raise transactions.TransactionError("A compatibility module clone must contain 1-250 physical placements")
        parts = []
        source_ref_id = _uuid5(opid, f"module-source:{destination}")
        for i, original in enumerate(source_parts):
            part = copy.deepcopy(original); old_id = part["id"]
            part["id"] = _uuid5(opid, f"clone-part:{source_aid}:{old_id}")
            part["assembly_id"] = destination_id
            part["translation_ldu"] = [design._decimal_add_exact(Decimal(str(v)), Decimal(delta))
                                         for v, delta in zip(part["translation_ldu"], offsets)]
            part["provenance"] = {**part["provenance"], "source_reference_id": source_ref_id,
                "source_file": f"modules/{destination}.ldr", "derived_from": old_id,
                "operation_id": opid, "source": "clone_module"}
            parts.append(part)
        comments = []
        for comment in base["source_comments"]:
            if comment.get("assembly_id") == source_aid:
                comments.append({"text": comment["text"], "source_line": comment["source_line"]})
        evidence_design = copy.deepcopy(base)
        evidence_design["assemblies"].append({"id": destination_id, "name": destination,
            "role": source.get("role"), "parent_assembly_id": None, "design_properties": {},
            "relationships": [], "field_locks": []})
        evidence_design["parts"].extend(copy.deepcopy(parts))
        for comment in comments:
            evidence_design["source_comments"].append({**comment, "assembly_id": destination_id,
                "source_reference_id": source_ref_id, "source_file": f"modules/{destination}.ldr"})
        raw_content = design._export_text(evidence_design, destination_id)[0].decode("utf-8")
        source_hash = hashlib.sha256(raw_content.encode()).hexdigest()
        source_ref = {"id": source_ref_id, "original_source_identity": source_hash,
            "content_hash": design.file_hash(raw_content.encode()), "role": "agent_clone_module",
            "local_artifact_reference": None, "license_rights_status": "unknown", "missing_data_notes": None}
        ops.append({"type": "replace_assembly_contents", "assembly_id": destination_id,
            "parts": parts, "source_comments": comments, "source_reference": source_ref})
        extra = {"module": destination, "cloned_from": source["name"], "translation_ldu": offsets,
                 "derived_from": {part["id"]: part["provenance"]["derived_from"] for part in parts}}
        evidence = raw_content
    elif name == "discard_module":
        assembly = _module(base, args["name"])
        aid = assembly["id"]
        if any(a.get("parent_assembly_id") == aid for a in base["assemblies"]):
            raise transactions.TransactionError("discard_module is limited to leaf modules")
        # The compatibility tool is leaf-only, so deleting descendants also
        # removes its direct physical placements and avoids dangling ownership.
        ops.append({"type": "delete_assembly", "assembly_id": aid, "delete_descendants": True})
        extra = {"discarded_module": args["name"]}
    elif name == "recolor_module_lines":
        assembly = _module(base, args["name"]); aid = assembly["id"]
        lines = args["lines"]
        if not 1 <= len(lines) <= 30 or len(set(lines)) != len(lines):
            raise transactions.TransactionError("Provide 1-30 distinct module-local placement lines")
        raise RuntimeError("internal recolor lowering requires verified export context")
    elif name == "edit_lines":
        raise RuntimeError("internal edit lowering requires verified export context")
    elif name in {"move_lines", "move_groups"}:
        raise RuntimeError("internal move lowering requires verified export context")
    else:
        raise transactions.TransactionError(f"Unsupported mutation adapter {name}")
    schema = transactions.OPERATION_SCHEMA_V3 if base.get("schema") == design.DESIGN_SCHEMA_V2 else transactions.OPERATION_SCHEMA_V2
    request = _operation_request(invocation, ops, f"offline adapter {name}", evidence, schema=schema)
    return request, extra


def _read_export_line(export: bytes, line: int) -> str:
    lines = export.decode("utf-8").splitlines()
    if type(line) is not int or not 1 <= line <= len(lines): raise transactions.TransactionError(f"line {line} is outside the declared export")
    return lines[line - 1]


def _lower_line_mutation(root: Path, invocation: dict[str, Any], base: dict[str, Any], build: bytes,
                         line_map: dict[str, Any], exports: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    name, args, opid = invocation["tool_name"], invocation["arguments"], invocation["operation_id"]
    ops: list[dict[str, Any]] = []; extra: dict[str, Any] = {}
    if name == "recolor_module_lines":
        assembly = _module(base, args["name"]); export_path = f"modules/{assembly['id']}.ldr"
        lookup = _line_lookup(line_map, export_path)
        by_local = {item["line"]: item for item in lookup.values()}
        selected = args["lines"]
        if not 1 <= len(selected) <= 30 or len(set(selected)) != len(selected):
            raise transactions.TransactionError("Provide 1-30 distinct module-local placement lines")
        ids = []
        for number in selected:
            entry = by_local.get(number)
            if entry is None: raise transactions.TransactionError(f"Module line {number} is not a placement in the verified export")
            ids.append(entry["part_id"])
        ops.append({"type": "recolor", "selector": {"part_ids": ids}, "color_id": args["color"]})
        extra = {"recolored_module": args["name"], "module_lines": sorted(selected), "color": args["color"]}
    elif name == "edit_lines":
        edits = args["edits"]
        if not 1 <= len(edits) <= 30 or len({item["line"] for item in edits}) != len(edits):
            raise transactions.TransactionError("Provide 1-30 distinct assembled placement edits")
        lookup = _line_lookup(line_map, "build.ldr")
        for edit in edits:
            line_number = edit["line"]; entry = lookup.get(line_number)
            if entry is None: raise transactions.TransactionError(f"Line {line_number} is not a placement in the verified assembled export")
            line = _read_export_line(build, line_number)
            if not line.startswith("1 "): raise transactions.TransactionError("Only physical placement lines can be edited")
            if edit["action"] == "delete":
                if edit["text"]: raise transactions.TransactionError("Delete edits require empty text")
                ops.append({"type": "delete", "selector": {"part_ids": [entry["part_id"]]}})
            else:
                replacement = edit["text"]
                if "\n" in replacement or "\r" in replacement: raise transactions.TransactionError("Replacement must contain exactly one placement line")
                parsed = design.import_ldr(replacement)
                if len(parsed["parts"]) != 1 or parsed["source_comments"]:
                    raise transactions.TransactionError("Each replacement must contain exactly one placement and no extra records")
                old = next(part for part in base["parts"] if part["id"] == entry["part_id"])
                replacement_part = copy.deepcopy(parsed["parts"][0])
                replacement_part["id"] = old["id"]; replacement_part["assembly_id"] = old["assembly_id"]
                replacement_part["provenance"] = {**old["provenance"], "operation_id": opid, "source": "edit_lines"}
                ops.append({"type": "replace_part", "part_id": old["id"], "replacement": replacement_part, "retain_id": True})
        extra = {"edited_build_lines": sorted(item["line"] for item in edits), "modules": sorted({next(p["assembly_id"] for p in base["parts"] if p["id"] == m["part_id"]) for m in lookup.values() if m["line"] in {i["line"] for i in edits}})}
    else:
        if name == "move_lines": groups = [{"lines": args["lines"], "dx": args["dx"], "dy": args["dy"], "dz": args["dz"]}]
        else: groups = args["groups"]
        if not 1 <= len(groups) <= 8: raise transactions.TransactionError("Provide 1-8 translation groups")
        lookup = _line_lookup(line_map, "build.ldr"); seen_per_group: list[list[int]] = []; all_ids: set[str] = set()
        for index, group in enumerate(groups):
            lines = list(dict.fromkeys(group["lines"]))
            if not 1 <= len(lines) <= 30: raise transactions.TransactionError("Each move group needs 1-30 distinct placement lines")
            offsets = [group["dx"], group["dy"], group["dz"]]
            if any(type(value) is not int or abs(value) > 200 for value in offsets) or not any(offsets):
                raise transactions.TransactionError("dx, dy, dz must be integer LDU offsets within ±200 and at least one nonzero")
            ids = []
            for line_number in lines:
                entry = lookup.get(line_number)
                if entry is None: raise transactions.TransactionError(f"Line {line_number} is not a placement in the verified assembled export")
                ids.append(entry["part_id"]); all_ids.add(entry["part_id"])
            if len(all_ids) > 30: raise transactions.TransactionError("At most 30 distinct placements may move in one call")
            ops.append({"type": "transform", "selector": {"part_ids": ids},
                "rotation": [[1,0,0],[0,1,0],[0,0,1]], "translation_ldu": offsets, "pivot_ldu": [0,0,0]})
            seen_per_group.append(lines)
        extra = {"translation_groups": [{"lines": lines, "offset_ldu": [group["dx"],group["dy"],group["dz"]]} for lines,group in zip(seen_per_group,groups)],
                 "overlap_behavior": "Offsets accumulate in group order; duplicate lines within each group are deduplicated."}
    schema = transactions.OPERATION_SCHEMA_V3 if base.get("schema") == design.DESIGN_SCHEMA_V2 else transactions.OPERATION_SCHEMA_V2
    return _operation_request(invocation, ops, f"offline adapter {name}", schema=schema), extra


def _dispatch_read(root: Path, invocation: dict[str, Any], base: dict[str, Any], build: bytes,
                   line_map: dict[str, Any], exports: dict[str, dict[str, Any]], folder: Path) -> dict[str, Any]:
    name, args = invocation["tool_name"], invocation["arguments"]
    base_hash = hashlib.sha256(build).hexdigest()
    if name == "read_module":
        assembly = _module(base, args["name"]); export_path = f"modules/{assembly['id']}.ldr"
        payload = (folder / export_path).read_bytes(); lines = payload.decode("utf-8").splitlines()
        start, count = args["start"], args["count"]
        if start < 1 or count < 1 or start > len(lines): raise transactions.TransactionError("read_module start/count are outside the verified module export")
        excerpt = [{"line": i+1, "text": lines[i]} for i in range(start-1, min(len(lines), start-1+min(count,60)))]
        return {"schema": RESULT_SCHEMA, "tool": name, "revision_id": base["revision_id"],
            "export_identity": {"path": export_path, "sha256": exports[export_path]["file_sha256"]},
            "module_id": assembly["id"], "module": assembly["name"], "total_lines": len(lines), "excerpt": excerpt}
    if name == "inspect_build_region":
        from .references import inspect_reference_region
        ldr_path = folder / "build.ldr"
        raw = inspect_reference_region(ldr_path, args["x_min"], args["x_max"], args["z_min"], args["z_max"],
            args["h_min"], args["h_max"], args["offset"], min(args["count"],40))
        build_lookup = _line_lookup(line_map, "build.ldr")
        for placement in raw["placements"]:
            entry = build_lookup.get(placement["line"])
            if entry is None: raise transactions.TransactionError("region result did not map to a verified placement")
            placement["part_id"] = entry["part_id"]; placement["assembly_id"] = entry["assembly_id"]
            local = line_map["exports"][f"modules/{entry['assembly_id']}.ldr"]["placements"]
            match = next((item for item in local if item["part_id"] == entry["part_id"]), None)
            placement["module_line"] = match["line"] if match else None
        return {"schema": RESULT_SCHEMA, "tool": name, "revision_id": base["revision_id"],
            "export_identity": {"path": "build.ldr", "sha256": base_hash}, **raw}
    if name == "inspect_alignment":
        from .alignment import analyze_alignment
        lines = args["lines"]
        if not 1 <= len(lines) <= 30 or len(set(lines)) != len(lines): raise transactions.TransactionError("Select 1-30 distinct assembled lines")
        lookup = _line_lookup(line_map, "build.ldr")
        if any(line not in lookup for line in lines): raise transactions.TransactionError("Alignment selection contains a non-placement line")
        raw = analyze_alignment(folder / "build.ldr", lines)
        for item in raw["placements"]: item["part_id"] = lookup[item["line"]]["part_id"]
        return {"schema": RESULT_SCHEMA, "tool": name, "revision_id": base["revision_id"],
            "export_identity": {"path": "build.ldr", "sha256": base_hash}, **raw}
    if name == "check":
        if base.get("ground_y") is None:
            validation = {"available": False, "reason": "ground_y is unknown; construction policy cannot evaluate"}
        else:
            from .feedback import check_model
            try: validation = check_model(folder / "build.ldr", ground_y=float(base["ground_y"]))
            except Exception as exc: validation = {"available": False, "exception": type(exc).__name__, "reason": str(exc)}
        lookup = _line_lookup(line_map, "build.ldr")
        if validation.get("errors"):
            for error in validation["errors"]:
                for field in ("line_samples", "suspect_line_samples"):
                    if isinstance(error.get(field), list):
                        vals = error[field]
                        if field == "line_samples": error["part_ids"] = [lookup[line]["part_id"] for line in vals if line in lookup]
                        else: error["part_ids"] = [lookup[v["line"]]["part_id"] for v in vals if isinstance(v,dict) and v.get("line") in lookup]
                if isinstance(error.get("line_pairs"), list): error["part_id_pairs"] = [[lookup[line]["part_id"] for line in pair if line in lookup] for pair in error["line_pairs"]]
        return {"schema": RESULT_SCHEMA, "tool": name, "revision_id": base["revision_id"],
            "export_identity": {"path": "build.ldr", "sha256": base_hash}, "validation": validation}
    if name == "render":
        with revisions.writer_lock(root):
            return _render_revision(root, invocation, base, folder, base_hash)
    raise transactions.TransactionError(f"Unsupported transaction read adapter: {name}")


def _safe_internal_dir(root: Path, components: tuple[str, ...]) -> Path:
    canonical = root.resolve(strict=True)
    cursor = canonical
    for component in components:
        cursor = cursor / component
        if cursor.is_symlink(): raise transactions.TransactionError(f"Render workspace path component is a symlink: {component}")
        if cursor.exists():
            if not cursor.is_dir(): raise transactions.TransactionError(f"Render workspace path component is not a directory: {component}")
            try: cursor.resolve(strict=True).relative_to(canonical)
            except ValueError as exc: raise transactions.TransactionError("Render artifact path escapes its workspace") from exc
        else:
            cursor.mkdir(mode=0o700)
            revisions._flush_dir(cursor.parent)
    return cursor


def _render_revision(root: Path, invocation: dict[str, Any], base: dict[str, Any],
                     folder: Path, base_hash: str) -> dict[str, Any]:
    view = invocation["arguments"]["view"]
    if view not in VIEWS: raise transactions.TransactionError(f"Unknown render view: {view}")
    canonical = root.resolve(strict=True)
    render_root = _safe_internal_dir(canonical, ("evidence", "renders"))
    operation_id = invocation["operation_id"]
    final_dir = render_root / operation_id
    invocation_hash = transactions._canonical_hash(invocation)
    reservation_path = render_root / f"{operation_id}.reservation.json"
    reservation = {"schema": "bricksmith-transaction-render-reservation-v1",
        "operation_id": operation_id, "invocation": copy.deepcopy(invocation),
        "invocation_sha256": invocation_hash, "source_revision_id": base["revision_id"],
        "source_export_sha256": base_hash}

    def reserve_invocation() -> None:
        if reservation_path.is_symlink():
            raise transactions.TransactionError("Render invocation reservation is a symlink")
        if reservation_path.exists():
            if not reservation_path.is_file():
                raise transactions.TransactionError("Render invocation reservation is unsafe")
            try:
                existing = design.read_json(reservation_path)
            except (OSError, ValueError, TypeError) as exc:
                raise transactions.TransactionError("Render invocation reservation is malformed") from exc
            expected_keys = set(reservation)
            if (not isinstance(existing, dict) or set(existing) != expected_keys
                    or existing.get("schema") != reservation["schema"]
                    or existing.get("operation_id") != operation_id
                    or existing.get("invocation_sha256") != transactions._canonical_hash(existing.get("invocation"))
                    or existing != reservation):
                raise transactions.TransactionError("Render operation ID is bound to a different or corrupt invocation reservation")
            return
        revisions._atomic_bytes(reservation_path, revisions._json_bytes(reservation))
        _adapter_failpoint("render_after_reservation")

    # Bind identity durably before any renderer call or staging output. This
    # reservation is never treated as a completed artifact.
    reserve_invocation()

    def verify_complete(directory: Path) -> dict[str, Any]:
        if directory.is_symlink() or not directory.is_dir():
            raise transactions.TransactionError("Existing render artifact directory is unsafe")
        for filename in ("image.png", "metadata.json"):
            path = directory / filename
            if path.is_symlink() or not path.is_file():
                raise transactions.TransactionError("Existing render artifact is incomplete or unsafe")
            try: path.resolve(strict=True).relative_to(canonical)
            except ValueError as exc: raise transactions.TransactionError("Render artifact escapes its workspace") from exc
        metadata = design.read_json(directory / "metadata.json")
        image_path = directory / "image.png"
        image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
        if (metadata.get("schema") != "bricksmith-transaction-render-v2"
                or metadata.get("operation_id") != operation_id
                or metadata.get("source_revision_id") != base["revision_id"]
                or metadata.get("source_export_sha256") != base_hash
                or metadata.get("invocation_sha256") != invocation_hash
                or metadata.get("view") != view
                or metadata.get("artifact_sha256") != image_hash):
            raise transactions.TransactionError("Render operation ID was reused with different source or invocation identity")
        return metadata

    if final_dir.exists() or final_dir.is_symlink():
        metadata = verify_complete(final_dir)
    else:
        # Only remove our own private incomplete stages. Each candidate is
        # revalidated beneath the canonical workspace before recursive removal.
        for stale in render_root.glob(f".{operation_id}.staging-*"):
            if stale.is_symlink() or not stale.is_dir():
                raise transactions.TransactionError("Unsafe interrupted render staging entry")
            try: stale.resolve(strict=True).relative_to(canonical)
            except ValueError as exc: raise transactions.TransactionError("Render staging escapes its workspace") from exc
            for child in stale.rglob("*"):
                if child.is_symlink():
                    raise transactions.TransactionError("Interrupted render staging contains a symlink")
                try: child.resolve(strict=True).relative_to(canonical)
                except (OSError, ValueError) as exc:
                    raise transactions.TransactionError("Interrupted render staging escapes its workspace") from exc
            shutil.rmtree(stale)
        stage = render_root / f".{operation_id}.staging-{uuid.uuid4()}"
        stage.mkdir(mode=0o700)
        try:
            from bricksmith.rendering.rasterizer import render_ldr_to_png
            image_path = stage / "image.png"
            render_ldr_to_png(folder / "build.ldr", image_path,
                azimuth=VIEWS[view][0], elevation=VIEWS[view][1], resolution=800)
            with image_path.open("rb") as stream: os.fsync(stream.fileno())
            _adapter_failpoint("render_after_image_before_metadata")
            metadata = {"schema": "bricksmith-transaction-render-v2", "operation_id": operation_id,
                "view": view, "source_revision_id": base["revision_id"], "source_export_sha256": base_hash,
                "artifact_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                "invocation_sha256": invocation_hash}
            revisions._atomic_bytes(stage / "metadata.json", revisions._json_bytes(metadata))
            revisions._flush_dir(stage)
            _adapter_failpoint("render_before_publish")
            os.rename(stage, final_dir)
            revisions._flush_dir(render_root)
            _adapter_failpoint("render_after_publish")
        except BaseException:
            # Leave any private stage for safe reconciliation on identical retry.
            raise
    relative = (final_dir / "image.png").relative_to(canonical).as_posix()
    return {"schema": RESULT_SCHEMA, "tool": "render", "operation_id": operation_id,
        "revision_id": base["revision_id"],
        "export_identity": {"path": "build.ldr", "sha256": base_hash},
        "render_path": relative, "render_sha256": metadata["artifact_sha256"],
        "render_created": True, "reviewed": False}


def dispatch(root: Path, tool_name: str, args: dict[str, Any], invocation_value: Any) -> dict[str, Any]:
    """Dispatch one strictly contextualized offline tool call through M2-A."""
    root = root.expanduser().absolute()
    args = validate_arguments(tool_name, args)
    invocation = _validate_invocation(invocation_value, tool_name, args)
    state = revisions.read_state(root)
    if state.get("schema") != revisions.STATE_SCHEMA: raise transactions.TransactionError("Offline adapters require an explicitly initialized transaction workspace")
    if tool_name in MUTATION_TOOLS:
        opdir = root / "operations" / invocation["operation_id"]
        if opdir.exists() or opdir.is_symlink():
            return _existing_operation_result(root, invocation, tool_name, opdir)
    base_id = invocation["expected_base_revision_id"]
    base = revisions.load_revision(root, base_id)
    folder, build, line_map, exports = _revision_exports(root, base)
    actual_hash = hashlib.sha256(build).hexdigest()
    if actual_hash != invocation["expected_export_sha256"]:
        raise transactions.TransactionError("expected_export_sha256 does not match the declared sealed revision")
    if tool_name in READ_TOOLS:
        return _dispatch_read(root, invocation, base, build, line_map, exports, folder)
    if tool_name not in MUTATION_TOOLS:
        if tool_name in UNSUPPORTED_TRANSACTION_TOOLS:
            raise transactions.TransactionError(f"{tool_name} is unavailable for transaction workspaces; offline adapters do not support it and runner integration is pending M7")
        raise transactions.TransactionError(f"Tool {tool_name!r} has no transaction adapter")
    state_current = state["current_revision_id"]
    if state_current != base_id:
        return _result(root, invocation, tool_name, disposition="stale_base", stale=True,
            extra={"error": "stale base revision; reload and create a new invocation"})
    request = None; extra = None
    if tool_name in {"edit_lines", "move_lines", "move_groups", "recolor_module_lines"}:
        request, extra = _lower_line_mutation(root, invocation, base, build, line_map, exports)
    else:
        request, extra = _mutation_request(invocation, base)
    request.setdefault("adapter_evidence", {"schema": "bricksmith-tool-operation-evidence-v1"})
    request["adapter_evidence"]["result_metadata"] = copy.deepcopy(extra or {})
    # The expected export identity is compared to the immutable base above.
    return _propose_commit(root, invocation, tool_name, request, extra=extra)
