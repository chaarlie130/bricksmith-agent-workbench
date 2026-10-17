#!/usr/bin/env python3
"""First agent-workbench tools: search, inspect and check LDraw models."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_provenance_spec = importlib.util.spec_from_file_location(
    "_bricksmith_provenance_cli", Path(__file__).resolve().parents[1] / "bricksmith/workbench/provenance.py")
_provenance = importlib.util.module_from_spec(_provenance_spec)
_provenance_spec.loader.exec_module(_provenance)
build_manifest = _provenance.build_manifest
manifest_identity = _provenance.manifest_identity
manifest_capture_complete = _provenance.manifest_capture_complete
preflight = _provenance.preflight
publish_manifest = _provenance.publish_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prompt", help="print the canonical design-agent system prompt")
    find = sub.add_parser("search", help="find relevant reference models")
    find.add_argument("query")
    find.add_argument("--corpus", type=Path,
                      default=Path(__file__).resolve().parents[1] / "data/reference_sets/ldr")
    find.add_argument("--limit", type=int, default=5)
    inspect = sub.add_parser("inspect", help="read a bounded LDraw excerpt")
    inspect.add_argument("path", type=Path)
    inspect.add_argument("--start", type=int, default=1)
    inspect.add_argument("--count", type=int, default=60)
    check = sub.add_parser("check", help="run structured physics checks")
    check.add_argument("path", type=Path)
    check.add_argument("--ground-y", type=float, default=8.0)
    env = sub.add_parser("preflight", help="inspect offline runtime/data and real checker/renderer")
    env.add_argument("--no-real-check", action="store_true", help="inspect dependencies/data only")
    baseline = sub.add_parser("baseline-export", help="write offline provenance manifest; makes no model request")
    baseline.add_argument("output", type=Path)
    baseline.add_argument("--brief", default="")
    baseline.add_argument("--track", default="historical-operator-assisted",
                          choices=("historical-operator-assisted", "historical-hybrid", "offline-provenance"))
    design_import = sub.add_parser("design-import", help="strictly import a flat LDraw file into a stable design document")
    design_import.add_argument("input", type=Path)
    design_import.add_argument("output", type=Path)
    design_import.add_argument("--brief")
    design_import.add_argument("--ground-y", help="explicit ground plane in LDU; omitted remains unknown")
    design_import.add_argument("--minimum-pieces")
    design_import.add_argument("--maximum-pieces")
    design_export = sub.add_parser("design-export", help="export a design document into deterministic LDraw/module views")
    design_export.add_argument("design", type=Path)
    design_export.add_argument("destination", type=Path)
    design_inspect = sub.add_parser("design-inspect", help="inspect a design by stable part or assembly IDs")
    design_inspect.add_argument("design", type=Path)
    design_inspect.add_argument("--part-id", action="append")
    design_inspect.add_argument("--assembly-id", action="append")
    design_inspect.add_argument("--line-map", type=Path)
    design_inspect.add_argument("--export-file", type=Path)
    design_inspect.add_argument("--export-key", default="build.ldr")
    design_migrate = sub.add_parser("design-migrate", help="explicitly migrate an existing v1 session to an inert v2 snapshot")
    design_migrate.add_argument("source", type=Path)
    design_migrate.add_argument("destination", type=Path)
    tx_init = sub.add_parser("transaction-init", help="explicitly initialize an offline transaction workspace from a design")
    tx_init.add_argument("design", type=Path)
    tx_init.add_argument("workspace", type=Path)
    tx_init_v2 = sub.add_parser("transaction-init-v2", help="explicitly open an inert v2 snapshot for offline operator transactions")
    tx_init_v2.add_argument("session", type=Path)
    tx_init_v2.add_argument("workspace", type=Path)
    tx_propose = sub.add_parser("transaction-propose", help="stage and validate an offline transaction request JSON")
    tx_propose.add_argument("workspace", type=Path)
    tx_propose.add_argument("request", type=Path)
    tx_inspect = sub.add_parser("transaction-inspect", help="inspect a staged offline candidate")
    tx_inspect.add_argument("workspace", type=Path)
    tx_inspect.add_argument("operation_id")
    tx_commit = sub.add_parser("transaction-commit", help="commit a fully revalidated offline candidate")
    tx_commit.add_argument("workspace", type=Path)
    tx_commit.add_argument("operation_id")
    tx_commit.add_argument("candidate_id")
    tx_discard = sub.add_parser("transaction-discard", help="persist candidate discard without deleting its evidence")
    tx_discard.add_argument("workspace", type=Path)
    tx_discard.add_argument("operation_id")
    tx_recover = sub.add_parser("transaction-recover", help="reconcile committed transaction artifacts")
    tx_recover.add_argument("workspace", type=Path)
    tx_upgrade = sub.add_parser("transaction-upgrade-v2", help="explicitly upgrade a design-v1 workspace through an offline transaction")
    tx_upgrade.add_argument("workspace", type=Path)
    tx_upgrade.add_argument("operation_id")
    tx_upgrade.add_argument("base_revision_id")
    tx_intake = sub.add_parser("operator-intake", help="record exact operator text and structured intent through trusted intake")
    tx_intake.add_argument("workspace", type=Path)
    tx_intake.add_argument("request", type=Path)
    tx_intake.add_argument("--source", required=True, choices=("user", "operator"))
    ledger = sub.add_parser("ledger-read", help="read one bounded page from a sealed design-v2 intent ledger")
    ledger.add_argument("workspace", type=Path)
    ledger.add_argument("--revision-id")
    ledger.add_argument("--offset", type=int, default=0)
    ledger.add_argument("--limit", type=int, default=50)
    tx_tool = sub.add_parser("transaction-tool", help="dispatch one strictly versioned offline tool invocation")
    tx_tool.add_argument("workspace", type=Path)
    tx_tool.add_argument("invocation", type=Path)
    sub.add_parser("transaction-tool-catalog", help="print the strict offline transaction adapter catalog")
    args = parser.parse_args()
    try:
        if args.command == "prompt":
            from bricksmith.workbench.prompt import load_system_prompt
            print(load_system_prompt(), end="")
            return 0
        if args.command == "search":
            from bricksmith.workbench.references import load_references, search
            from bricksmith.workbench.references import DEFAULT_CORPUS
            result = {"schema": "bricksmith-reference-search-v1", "query": args.query,
                      "corpus_size": 0, "results": []}
            references = load_references(args.corpus)
            result["corpus_size"] = len(references)
            result["results"] = search(references, args.query, args.limit)
        elif args.command == "inspect":
            from bricksmith.workbench.references import inspect_model
            result = inspect_model(args.path, args.start, args.count)
        elif args.command == "preflight":
            result = preflight(real_check=not args.no_real_check)
            print(json.dumps(result, indent=2))
            return 0 if result["checks"]["status"] == "passed" else 3
        elif args.command == "baseline-export":
            result = build_manifest(brief=args.brief, execution_track=args.track)
            result["manifest_identity"] = manifest_identity(result)
            result["baseline_classification"] = "provenance_only_no_design_result"
            result["capture_status"] = "complete" if manifest_capture_complete(result) else "incomplete"
            publish_manifest(args.output, result)
            result["output"] = str(args.output.resolve())
        elif args.command == "design-import":
            from decimal import Decimal
            from bricksmith.workbench.design import import_ldr, write_design
            design = import_ldr(args.input, brief=args.brief,
                ground_y=Decimal(args.ground_y) if args.ground_y is not None else None,
                minimum_pieces=Decimal(args.minimum_pieces) if args.minimum_pieces is not None else None,
                maximum_pieces=Decimal(args.maximum_pieces) if args.maximum_pieces is not None else None)
            result = write_design(args.output, design)
            result["piece_count"] = len(design["parts"])
            result["appearance_hash"] = design["hashes"]["appearance"]["value"]
            result["structure_hash"] = design["hashes"]["structure"]["value"]
        elif args.command == "design-export":
            from bricksmith.workbench.design import export_design, load_design
            result = export_design(load_design(args.design), args.destination)
        elif args.command == "design-inspect":
            from bricksmith.workbench.design import inspect_design, load_design, load_line_map
            design = load_design(args.design)
            if bool(args.line_map) != bool(args.export_file):
                raise ValueError("--line-map and --export-file must be supplied together")
            kwargs = {}
            if args.line_map:
                line_map = load_line_map(args.line_map)
                export_hash = __import__("hashlib").sha256(args.export_file.read_bytes()).hexdigest()
                kwargs = {"line_map": line_map, "export_path": args.export_key,
                          "export_sha256": export_hash}
            result = inspect_design(design, part_ids=args.part_id,
                                    assembly_ids=args.assembly_id, **kwargs)
        elif args.command == "design-migrate":
            from bricksmith.workbench.design import migrate_v1_session
            result = migrate_v1_session(args.source, args.destination)
        elif args.command == "transaction-init":
            from bricksmith.workbench.design import load_design
            from bricksmith.workbench.revisions import initialize
            value = load_design(args.design)
            result = initialize(args.workspace, value, source_identity=__import__("hashlib").sha256(args.design.read_bytes()).hexdigest())
        elif args.command == "transaction-init-v2":
            from bricksmith.workbench import revisions
            state_path = args.session / "state.json"
            state = __import__("json").loads(state_path.read_text())
            if state.get("schema") != "bricksmith-agent-session-v2":
                raise ValueError("source is not an inert v2 session snapshot")
            source_revision = args.session / "revisions" / state.get("current_revision_id", "") / "design.json"
            if not source_revision.is_file(): raise ValueError("v2 source does not contain a readable M1 design revision")
            from bricksmith.workbench.design import load_design
            value = load_design(source_revision)
            result = revisions.initialize(args.workspace, value, source_identity=__import__("hashlib").sha256(state_path.read_bytes()).hexdigest())
        elif args.command == "transaction-propose":
            from bricksmith.workbench import transactions
            request = __import__("json").loads(args.request.read_text(), parse_float=__import__("decimal").Decimal)
            result = transactions.propose_edit(args.workspace, request)
        elif args.command == "transaction-inspect":
            from bricksmith.workbench.transactions import inspect_candidate
            result = inspect_candidate(args.workspace, args.operation_id)
        elif args.command == "transaction-commit":
            from bricksmith.workbench.transactions import commit_candidate
            result = commit_candidate(args.workspace, args.operation_id, args.candidate_id)
        elif args.command == "transaction-discard":
            from bricksmith.workbench.transactions import discard_candidate
            result = discard_candidate(args.workspace, args.operation_id)
        elif args.command == "transaction-recover":
            from bricksmith.workbench.transactions import recover
            result = recover(args.workspace)
        elif args.command == "transaction-upgrade-v2":
            from bricksmith.workbench.intent_ledger import upgrade_workspace
            result = upgrade_workspace(args.workspace, args.operation_id, args.base_revision_id)
        elif args.command == "operator-intake":
            from bricksmith.workbench.intent_ledger import operator_intake
            intake = __import__("json").loads(args.request.read_text(), parse_float=__import__("decimal").Decimal)
            if not isinstance(intake, dict) or set(intake) != {"operation_id", "base_revision_id", "instruction_id", "created_at", "instruction_text", "changes", "fill_brief"}:
                raise ValueError("operator intake JSON must contain exactly operation_id, base_revision_id, instruction_id, created_at, instruction_text, changes, and fill_brief")
            if type(intake["fill_brief"]) is not bool: raise ValueError("fill_brief must be boolean")
            result = operator_intake(args.workspace, source=args.source, **intake)
        elif args.command == "ledger-read":
            from bricksmith.workbench.intent_ledger import ledger_read
            result = ledger_read(args.workspace, revision_id=args.revision_id, offset=args.offset, limit=args.limit)
        elif args.command == "transaction-tool":
            from bricksmith.workbench import revisions
            from bricksmith.workbench.agent_session import _tool
            invocation = __import__("json").loads(args.invocation.read_text(), parse_float=__import__("decimal").Decimal)
            state = revisions.read_state(args.workspace)
            if not isinstance(invocation, dict): raise ValueError("tool invocation must be a JSON object")
            result = _tool(args.workspace, state, invocation.get("tool_name"),
                           invocation.get("arguments"), invocation_context=invocation)
        elif args.command == "transaction-tool-catalog":
            from bricksmith.workbench.transaction_tools import catalog
            result = catalog()
        else:
            from bricksmith.workbench.feedback import check_model
            result = check_model(args.path, ground_y=args.ground_y)
        try:
            from bricksmith.workbench.design import _json_text
            print(_json_text(result, indent=2, sort_keys=True))
        except ImportError:
            print(json.dumps(result, indent=2))
        return 0
    except (FileNotFoundError, ValueError, FileExistsError, OSError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
