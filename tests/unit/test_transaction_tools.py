from __future__ import annotations

import copy
import hashlib
import tempfile
import os
import shutil
import subprocess
import unittest
import uuid
from decimal import Decimal, localcontext
from pathlib import Path
from unittest.mock import patch

from bricksmith.workbench import design, revisions, transactions, transaction_tools
from bricksmith.workbench.agent_session import _tool
from bricksmith.workbench import agent_session
from bricksmith.workbench.transaction_tools import INVOCATION_SCHEMA

ROOT = Path(__file__).resolve().parents[2]


def synthetic_validation(value, workdir, label, validator=None):
    """Synthetic all-green checker evidence; tests transaction semantics only."""
    build, placements = design._export_text(value)
    checks = {key: True for key in transactions.CHECKS}
    raw = {"schema": "bricksmith-construction-v1", "passed": True, "checks": checks,
           "errors": [], "diagnostics": {"below_ground_indices_complete_flag": True,
           "below_ground_indices_complete": []}, "physical_piece_count": len(placements)}
    return {"schema": "bricksmith-transaction-validation-v1", "raw_report": raw,
            "evaluation": transactions._interpret_report(raw, placements),
            "export_sha256": hashlib.sha256(build).hexdigest(),
            "design_hash": value["hashes"]["design"]["value"]}


class TransactionToolAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "workspace"
        source = design.import_ldr(ROOT / "tests/fixtures/acceptance/pass.ldr", ground_y=8)
        revisions.initialize(self.root, source)
        self.patchers = [
            patch("bricksmith.workbench.transactions._run_validation", side_effect=synthetic_validation),
            patch("bricksmith.workbench.transactions._evaluation_environment_identity", return_value={"synthetic": True}),
            patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64),
        ]
        for item in self.patchers:
            item.start()
            self.addCleanup(item.stop)

    def invocation(self, tool, args, operation_id=None):
        state = revisions.read_state(self.root)
        current = revisions.load_revision(self.root, state["current_revision_id"])
        build = (revisions.revision_dir(self.root, current["revision_id"]) / "build.ldr").read_bytes()
        return {"schema": INVOCATION_SCHEMA, "tool_name": tool, "arguments": copy.deepcopy(args),
                "operation_id": operation_id or str(uuid.uuid4()),
                "expected_base_revision_id": current["revision_id"],
                "expected_export_sha256": hashlib.sha256(build).hexdigest()}

    def dispatch(self, tool, args, invocation=None):
        state = revisions.read_state(self.root)
        context = invocation or self.invocation(tool, args)
        return _tool(self.root, state, tool, args, invocation_context=context)

    def test_save_module_over_64_parts_commits_once_and_replay_is_idempotent(self):
        sample = next(line for line in (ROOT / "tests/fixtures/acceptance/pass.ldr").read_text().splitlines()
                      if line.startswith("1 "))
        # Unique stable instances are expected even when submitted placements match.
        source = "\n".join([sample] * 80) + "\n"
        args = {"name": "bulk-test", "ldr": source}
        call = self.invocation("save_module", args)
        first = self.dispatch("save_module", args, call)
        self.assertTrue(first["committed"], first)
        self.assertEqual(first["status"], "construction_passed")
        current = revisions.load_revision(self.root, first["current_revision_id"])
        assembly = next(a for a in current["assemblies"] if a["name"] == "bulk-test")
        parts = [p for p in current["parts"] if p["assembly_id"] == assembly["id"]]
        self.assertEqual(len(parts), 80)
        self.assertEqual(len({p["id"] for p in parts}), 80)
        second = self.dispatch("save_module", args, call)
        self.assertTrue(second["committed"])
        self.assertEqual(first["candidate_id"], second["candidate_id"])
        self.assertEqual(first["current_revision_id"], second["current_revision_id"])
        changed = {"name": "bulk-test", "ldr": source + "0 changed\n"}
        changed_call = copy.deepcopy(call)
        changed_call["arguments"] = changed
        with self.assertRaisesRegex(transactions.TransactionError, "different tool, arguments"):
            self.dispatch("save_module", changed, changed_call)

    def test_generator_uses_same_dispatch_and_records_evidence(self):
        args = {"name": "column", "x": 10, "z": 10, "bottom_y": 0,
                "bricks": 1, "color": 4, "cap_color": 4,
                "cap_plate": False, "size_studs": 1}
        result = self.dispatch("save_support_column", args)
        self.assertTrue(result["committed"], result)
        op = self.root / "operations" / result["operation_id"]
        intent = design.read_json(op / "intent.json")
        self.assertEqual(intent["intent"]["adapter_invocation"]["tool_name"], "save_support_column")
        self.assertEqual(intent["intent"]["schema"], transactions.OPERATION_SCHEMA_V2)
        self.assertEqual(intent["intent"]["adapter_invocation"]["arguments"], args)
        self.assertTrue((op / "report.json").is_file())

    def test_committed_generator_replay_uses_durable_report_without_regeneration(self):
        args = {"name": "first-column", "x": 10, "z": 10, "bottom_y": 0,
                "bricks": 1, "color": 4, "cap_color": 4,
                "cap_plate": False, "size_studs": 1}
        invocation = self.invocation("save_support_column", args)
        first = self.dispatch("save_support_column", args, invocation)
        self.assertTrue(first["committed"])
        other = self.dispatch("save_support_column", {**args, "name": "later-column", "x": 30})
        self.assertTrue(other["committed"])
        with patch("bricksmith.workbench.transaction_tools._args_to_ldr", side_effect=AssertionError("generator reran")):
            retry = self.dispatch("save_support_column", args, invocation)
        meaningful = ("operation_id", "candidate_id", "operation_revision_id", "base_revision_id",
            "disposition", "committed", "stale_base", "status", "policy_status", "policy_reasons",
            "affected_ids", "invocation_sha256", "tool_details")
        self.assertEqual({key: retry.get(key) for key in meaningful},
                         {key: first.get(key) for key in meaningful})
        self.assertNotEqual(retry["current_revision_id"], first["current_revision_id"])
        self.assertFalse(first["stale_base"])

    def test_invocation_conflict_is_rejected_before_generator(self):
        args = {"name": "conflict-column", "x": 10, "z": 10, "bottom_y": 0,
                "bricks": 1, "color": 4, "cap_color": 4,
                "cap_plate": False, "size_studs": 1}
        invocation = self.invocation("save_support_column", args)
        self.dispatch("save_support_column", args, invocation)
        changed = {**args, "x": 30}
        changed_invocation = copy.deepcopy(invocation)
        changed_invocation["arguments"] = changed
        with patch("bricksmith.workbench.transaction_tools._args_to_ldr", side_effect=AssertionError("generator reran")):
            with self.assertRaisesRegex(transactions.TransactionError, "different tool, arguments"):
                self.dispatch("save_support_column", changed, changed_invocation)

    def test_adapter_metadata_cannot_override_authoritative_outcomes(self):
        sample = next(line for line in (ROOT / "tests/fixtures/acceptance/pass.ldr").read_text().splitlines()
                      if line.startswith("1 "))
        attack = {"committed": True, "disposition": "committed", "status": "accepted",
            "commit_eligible": True, "policy_status": "accepted", "affected_ids": ["forged"],
            "export_identity": {"sha256": "f" * 64}, "module": "claimed-success"}
        prior_root = self.root
        for index, mode in enumerate(("committed", "provisional", "blocked", "discarded")):
            with self.subTest(mode=mode):
                self.root = Path(self.tmp.name) / f"metadata-{mode}"
                source = design.import_ldr(ROOT / "tests/fixtures/acceptance/pass.ldr", ground_y=8)
                revisions.initialize(self.root, source)
                args = {"name": "metadata-check", "ldr": sample + "\n"}
                invocation = self.invocation("save_module", args)
                base = revisions.load_revision(self.root, invocation["expected_base_revision_id"])
                request, _ = transaction_tools._mutation_request(invocation, base)
                request.setdefault("adapter_evidence", {"schema": "bricksmith-tool-operation-evidence-v1"})
                request["adapter_evidence"]["result_metadata"] = copy.deepcopy(attack)

                def validate(value, workdir, label, validator=None):
                    if mode in {"blocked", "discarded"}:
                        return {"schema": "bricksmith-transaction-validation-v1", "raw_report": None,
                            "evaluation": {"available": False, "reason": "synthetic unavailable", "checks": None}}
                    result = synthetic_validation(value, workdir, label, validator)
                    if mode == "provisional" and label == "candidate":
                        raw = copy.deepcopy(result["raw_report"])
                        raw["checks"]["actual_connectivity"] = False
                        raw["passed"] = False
                        result["raw_report"] = raw
                        _, placements = design._export_text(value)
                        result["evaluation"] = transactions._interpret_report(raw, placements)
                    return result

                with patch("bricksmith.workbench.transactions._run_validation", side_effect=validate), \
                     patch("bricksmith.workbench.transactions._evaluation_environment_identity", return_value={"synthetic": mode}), \
                     patch("bricksmith.workbench.transactions._data_identity", return_value="b" * 64):
                    proposal = transactions.propose_edit(self.root, request)
                    if mode in {"committed", "provisional"}:
                        receipt = transactions.commit_candidate(self.root, invocation["operation_id"], proposal["candidate_id"])
                        self.assertEqual(receipt["disposition"], "committed")
                    if mode == "discarded":
                        transactions.discard_candidate(self.root, invocation["operation_id"])
                    actual_current = revisions.read_state(self.root)["current_revision_id"]
                    replay = self.dispatch("save_module", args, invocation)
                    self.assertEqual(replay["committed"], mode in {"committed", "provisional"})
                    self.assertNotEqual(replay["disposition"], "committed" if mode in {"blocked", "discarded"} else "failed")
                    self.assertEqual(replay["current_revision_id"], actual_current)
                    self.assertNotEqual(replay["status"], "accepted")
                    self.assertNotEqual(replay["affected_ids"], ["forged"])
                    self.assertNotEqual(replay["export_identity"].get("sha256"), "f" * 64)
                    self.assertEqual(replay["tool_details"]["committed"], True)
                    self.assertEqual(replay["tool_details"]["status"], "accepted")
                    self.assertEqual(replay["tool_details"]["module"], "claimed-success")
                    immediate = transaction_tools._result(self.root, invocation, "save_module",
                        report=design.read_json(self.root / "operations" / invocation["operation_id"] / "report.json"),
                        extra=attack)
                    self.assertEqual(immediate["committed"], replay["committed"])
                    self.assertNotEqual(immediate["status"], "accepted")
                    self.assertEqual(immediate["tool_details"]["disposition"], "committed")
        self.root = prior_root

    def test_adapter_replays_provisional_repair_blocked_and_unavailable_outcomes(self):
        sample = next(line for line in (ROOT / "tests/fixtures/acceptance/pass.ldr").read_text().splitlines()
                      if line.startswith("1 "))
        previous = self.root
        for index, mode in enumerate(("provisional", "repair_incomplete", "blocked", "unavailable")):
            with self.subTest(mode=mode):
                root = Path(self.tmp.name) / f"outcome-{mode}"
                source = design.import_ldr(ROOT / "tests/fixtures/acceptance/pass.ldr", ground_y=8)
                revisions.initialize(root, source)
                self.root = root

                def validation(value, workdir, label, validator=None):
                    _, placements = design._export_text(value)
                    checks = {key: True for key in transactions.CHECKS}
                    errors = []
                    diagnostics = {"below_ground_indices_complete_flag": True,
                                   "below_ground_indices_complete": []}
                    if mode == "unavailable":
                        return {"schema": "bricksmith-transaction-validation-v1", "raw_report": None,
                            "evaluation": {"available": False, "reason": "synthetic unavailable checker", "checks": None}}
                    if mode == "provisional": checks["actual_connectivity"] = False
                    if mode == "repair_incomplete":
                        checks["included_base"] = False
                        if label == "base":
                            checks["no_parts_below_ground"] = False
                            diagnostics["below_ground_indices_complete"] = [0]
                            errors = [{"kind": "parts_below_ground", "count": 1}]
                    if mode == "blocked" and label == "candidate":
                        checks["mesh_collision_free"] = False
                        errors = [{"kind": "mesh_collision", "count": 1, "pairs": [[0, 1]]}]
                    raw = {"passed": all(checks.values()), "checks": checks, "errors": errors,
                        "diagnostics": diagnostics, "physical_piece_count": len(placements)}
                    build, _ = design._export_text(value)
                    return {"schema": "bricksmith-transaction-validation-v1", "raw_report": raw,
                        "evaluation": transactions._interpret_report(raw, placements),
                        "export_sha256": hashlib.sha256(build).hexdigest(),
                        "design_hash": value["hashes"]["design"]["value"]}

                with patch("bricksmith.workbench.transactions._run_validation", side_effect=validation), \
                     patch("bricksmith.workbench.transactions._evaluation_environment_identity", return_value={"synthetic": mode}), \
                     patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
                    args = {"name": "outcome-module", "ldr": sample + "\n"}
                    invocation = self.invocation("save_module", args)
                    before = revisions.read_state(root)["current_revision_id"]
                    first = self.dispatch("save_module", args, invocation)
                    retry = self.dispatch("save_module", args, invocation)
                    self.assertEqual(retry["operation_id"], first["operation_id"])
                    self.assertEqual(retry["candidate_id"], first["candidate_id"])
                    self.assertEqual(retry["status"], first["status"])
                    self.assertEqual(retry["policy_status"], first["policy_status"])
                    self.assertEqual(retry["policy_reasons"], first["policy_reasons"])
                    self.assertEqual(retry["affected_ids"], first["affected_ids"])
                    if mode in {"provisional", "repair_incomplete"}:
                        expected = mode
                        self.assertTrue(first["committed"], first)
                        self.assertEqual(first["status"], expected)
                        committed = revisions.load_revision(root, first["current_revision_id"])
                        self.assertTrue(any(issue["kind"] == mode and issue["status"] == "open"
                                            for issue in committed["issues"]))
                        self.assertEqual(retry["disposition"], "committed")
                    else:
                        self.assertFalse(first["committed"])
                        self.assertEqual(revisions.read_state(root)["current_revision_id"], before)
                        self.assertEqual(retry["disposition"], "candidate")
                        self.assertFalse(retry["commit_eligible"])
                        if mode == "blocked":
                            self.assertEqual(first["policy_reasons"][0]["code"], "hard_check_regression")
                            discarded = transactions.discard_candidate(root, invocation["operation_id"])
                            terminal = self.dispatch("save_module", args, invocation)
                            self.assertEqual(discarded["disposition"], "discarded")
                            self.assertEqual(terminal["disposition"], "discarded")
                            self.assertFalse(terminal.get("commit_eligible", False))
                        else: self.assertEqual(first["policy_reasons"][0]["code"], "base_validation_unavailable")
        self.root = previous

    def test_mutations_require_exact_invocation_context(self):
        args = {"name": "one", "ldr": "0 test\n" + next(
            line for line in (ROOT / "tests/fixtures/acceptance/pass.ldr").read_text().splitlines()
            if line.startswith("1 ")) + "\n"}
        with self.assertRaisesRegex(RuntimeError, "explicit offline invocation context"):
            _tool(self.root, revisions.read_state(self.root), "save_module", args)
        bad = self.invocation("save_module", args)
        bad["expected_export_sha256"] = "0" * 64
        with self.assertRaisesRegex(transactions.TransactionError, "does not match"):
            self.dispatch("save_module", args, bad)
        with self.assertRaisesRegex(transactions.TransactionError, "unavailable for transaction workspaces"):
            self.dispatch("set_plan", {"plan": "A bounded offline test plan."})

    def test_transaction_runner_rejects_before_provider_call(self):
        with patch.object(agent_session, "respond") as provider:
            with self.assertRaisesRegex(RuntimeError, "pending M7"):
                agent_session.step_session(self.root)
            with self.assertRaisesRegex(RuntimeError, "pending M7"):
                agent_session.run_session(self.root, max_requests=1)
            provider.assert_not_called()

    def test_module_replacement_refuses_locked_parts_and_retains_candidate(self):
        value = revisions.load_revision(self.root, revisions.read_state(self.root)["current_revision_id"])
        locked = copy.deepcopy(value)
        part = locked["parts"][0]
        locked["assemblies"][0]["field_locks"].append({"id": str(uuid.uuid4()), "owner": "user",
            "target_id": part["id"], "fields": ["translation_ldu"]})
        design.refresh_hashes(locked)
        root = Path(self.tmp.name) / "locked"
        revisions.initialize(root, locked)
        previous = self.root
        self.root = root
        sample = next(line for line in (ROOT / "tests/fixtures/acceptance/pass.ldr").read_text().splitlines()
                      if line.startswith("1 "))
        args = {"name": "Imported design", "ldr": sample + "\n"}
        call = self.invocation("save_module", args)
        result = self.dispatch("save_module", args, call)
        self.assertFalse(result["committed"])
        self.assertEqual(result["disposition"], "failed")
        self.assertTrue(result["failure_reference"])
        self.assertEqual(revisions.read_state(root)["current_revision_id"], locked["revision_id"])
        self.assertTrue((root / result["failure_reference"]).is_file())
        retried = self.dispatch("save_module", args, call)
        self.assertEqual(retried["disposition"], "failed")
        self.assertFalse(retried.get("commit_eligible", False))
        self.assertEqual(retried["failure_reference"], result["failure_reference"])
        self.root = previous

    def test_module_and_line_identity_errors_fail_closed(self):
        duplicate = copy.deepcopy(revisions.load_revision(self.root,
            revisions.read_state(self.root)["current_revision_id"]))
        second = copy.deepcopy(duplicate["assemblies"][0])
        second["id"] = str(uuid.uuid4())
        duplicate["assemblies"].append(second)
        design.refresh_hashes(duplicate)
        root = Path(self.tmp.name) / "ambiguous"
        revisions.initialize(root, duplicate)
        previous = self.root
        self.root = root
        with self.assertRaisesRegex(transactions.TransactionError, "Ambiguous module name"):
            self.dispatch("recolor_module_lines", {"name": "Imported design", "lines": [1], "color": 4})
        self.root = previous
        with self.assertRaisesRegex(transactions.TransactionError, "not a placement"):
            self.dispatch("move_lines", {"lines": [99999], "dx": 20, "dy": 0, "dz": 0})

    def test_forged_sealed_line_map_is_rejected_and_reads_ignore_compatibility_export(self):
        state = revisions.read_state(self.root)
        revision = revisions.load_revision(self.root, state["current_revision_id"])
        root_build = self.root / "build.ldr"
        original_compat = root_build.read_bytes()
        root_build.write_bytes(b"0 forged compatibility export\n")
        read = self.dispatch("read_module", {"name": revision["assemblies"][0]["name"], "start": 1, "count": 10})
        self.assertEqual(read["revision_id"], revision["revision_id"])
        self.assertNotEqual(read["excerpt"][0]["text"], "0 forged compatibility export")
        root_build.write_bytes(original_compat)

        line_map_path = revisions.revision_dir(self.root, revision["revision_id"]) / "line_map.json"
        original_map = line_map_path.read_bytes()
        line_map_path.write_bytes(original_map + b" ")
        with self.assertRaisesRegex(revisions.RevisionError, "artifact is missing or corrupt"):
            self.dispatch("move_lines", {"lines": [2], "dx": 20, "dy": 0, "dz": 0})
        self.assertEqual(list((self.root / "operations").iterdir()), [])

    def test_stale_base_during_adapter_commit_retains_candidate(self):
        args = {"name": "racing-module", "ldr": "0 race\n" + next(
            line for line in (ROOT / "tests/fixtures/acceptance/pass.ldr").read_text().splitlines()
            if line.startswith("1 ")) + "\n"}
        operation_id = str(uuid.uuid4())
        invocation = self.invocation("save_module", args, operation_id)
        real_commit = transactions.commit_candidate
        switched = False

        def race(root, opid, candidate_id, **kwargs):
            nonlocal switched
            if opid == operation_id and not switched:
                switched = True
                with patch.object(transactions, "commit_candidate", real_commit):
                    other = self.dispatch("save_support_column", {"name": "concurrent", "x": 10,
                        "z": 10, "bottom_y": 0, "bricks": 1, "color": 4,
                        "cap_color": 4, "cap_plate": False, "size_studs": 1})
                    self.assertTrue(other["committed"])
                return real_commit(root, opid, candidate_id, **kwargs)
            return real_commit(root, opid, candidate_id, **kwargs)

        with patch.object(transactions, "commit_candidate", side_effect=race):
            result = self.dispatch("save_module", args, invocation)
        self.assertFalse(result["committed"])
        self.assertTrue(result["stale_base"])
        self.assertEqual(result["disposition"], "candidate")
        self.assertTrue((self.root / result["report_reference"]).is_file())
        self.assertNotEqual(result["base_revision_id"], result["current_revision_id"])

    def test_interrupted_auto_commit_retry_does_not_publish_staged_candidate(self):
        args = {"name": "interrupted", "ldr": "0 staged\n" + next(
            line for line in (ROOT / "tests/fixtures/acceptance/pass.ldr").read_text().splitlines()
            if line.startswith("1 ")) + "\n"}
        invocation = self.invocation("save_module", args)
        with patch.object(transactions, "commit_candidate", side_effect=SystemExit("simulated process stop")):
            with self.assertRaisesRegex(SystemExit, "simulated process stop"):
                self.dispatch("save_module", args, invocation)
        operation = self.root / "operations" / invocation["operation_id"]
        self.assertTrue((operation / "report.json").is_file())
        self.assertEqual(revisions.read_state(self.root)["current_revision_id"], invocation["expected_base_revision_id"])
        with patch.object(transactions, "commit_candidate") as publish:
            retry = self.dispatch("save_module", args, invocation)
            publish.assert_not_called()
        self.assertFalse(retry["committed"])
        self.assertEqual(retry["disposition"], "candidate")

    def test_decimal_array_preserves_exact_positions_and_generated_evidence(self):
        source_line = next(line for line in (ROOT / "tests/fixtures/acceptance/pass.ldr").read_text().splitlines()
                           if line.startswith("1 "))
        fields = source_line.split()
        fields[2] = "0.0000000000000000001"
        template = "0 template note\n" + " ".join(fields)
        args = {"name": "fractional-array", "template": template, "counts": [2, 1, 1],
            "step_x": [Decimal("0.5"), 0, 0], "step_y": [0, 0, 0], "step_z": [0, 0, 0]}
        with localcontext() as context:
            context.prec = 3
            result = self.dispatch("save_array", args)
        self.assertTrue(result["committed"], result)
        current = revisions.load_revision(self.root, result["current_revision_id"])
        assembly = next(item for item in current["assemblies"] if item["name"] == "fractional-array")
        positions = sorted(part["translation_ldu"][0] for part in current["parts"]
                           if part["assembly_id"] == assembly["id"])
        self.assertEqual(positions, [Decimal("1e-19"), Decimal("0.5000000000000000001")])
        intent = design.read_json(self.root / "operations" / result["operation_id"] / "intent.json")["intent"]
        generated = intent["adapter_evidence"]["generated_content"]
        self.assertIn("0.5000000000000000001", generated)
        self.assertEqual(sum(line.startswith("1 ") for line in generated.splitlines()), 2)
        zero_args = {**args, "name": "zero-offset-array", "counts": [1, 1, 1],
            "step_x": [0, 0, 0]}
        zero_result = self.dispatch("save_array", zero_args)
        self.assertTrue(zero_result["committed"], zero_result)
        with self.assertRaises(transactions.TransactionError):
            self.dispatch("save_array", {**args, "name": "bad-bool", "step_x": [True, 0, 0]})

    def test_clone_module_enforces_250_part_cap_at_and_above_boundary(self):
        sample = next(line for line in (ROOT / "tests/fixtures/acceptance/pass.ldr").read_text().splitlines()
                      if line.startswith("1 "))
        for count, should_pass in ((250, True), (251, False)):
            with self.subTest(count=count):
                root = Path(self.tmp.name) / f"clone-{count}"
                source = design.import_ldr((sample + "\n") * count, ground_y=8)
                revisions.initialize(root, source)
                previous = self.root
                self.root = root
                args = {"source": source["assemblies"][0]["name"], "name": "bounded-clone",
                    "dx": 100, "dy": 0, "dz": 0}
                if should_pass:
                    result = self.dispatch("clone_module", args)
                    self.assertTrue(result["committed"], result)
                    current = revisions.load_revision(root, result["current_revision_id"])
                    clone = next(item for item in current["assemblies"] if item["name"] == "bounded-clone")
                    self.assertEqual(sum(part["assembly_id"] == clone["id"] for part in current["parts"]), 250)
                else:
                    with self.assertRaisesRegex(transactions.TransactionError, "1-250 physical placements"):
                        self.dispatch("clone_module", args)
                    self.assertEqual(revisions.read_state(root)["current_revision_id"], source["revision_id"])
                    self.assertEqual(list((root / "operations").iterdir()), [])
                self.root = previous

    def test_sealed_revision_read_check_and_render_adapters(self):
        value = revisions.load_revision(self.root, revisions.read_state(self.root)["current_revision_id"])
        line_map = design.load_line_map(revisions.revision_dir(self.root, value["revision_id"]) / "line_map.json")
        local_name = value["assemblies"][0]["name"]
        module = self.dispatch("read_module", {"name": local_name, "start": 1, "count": 10})
        self.assertEqual(module["revision_id"], value["revision_id"])
        self.assertTrue(module["excerpt"])
        placement_line = line_map["exports"]["build.ldr"]["placements"][0]["line"]
        alignment = self.dispatch("inspect_alignment", {"lines": [placement_line]})
        self.assertEqual(alignment["revision_id"], value["revision_id"])
        region = self.dispatch("inspect_build_region", {"x_min": -1, "x_max": 1,
            "z_min": -1, "z_max": 1, "h_min": -1, "h_max": 10, "offset": 0, "count": 5})
        self.assertEqual(region["revision_id"], value["revision_id"])
        check = self.dispatch("check", {})
        self.assertEqual(check["revision_id"], value["revision_id"])
        rendered = self.dispatch("render", {"view": "front_left"})
        self.assertFalse(rendered["reviewed"])
        image = self.root / rendered["render_path"]
        self.assertTrue(image.is_file())
        self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(), rendered["render_sha256"])

    def test_render_rejects_symlink_escape_recovers_incomplete_stage_and_binds_invocation(self):
        from bricksmith.workbench import transaction_tools
        args = {"view": "front_left"}
        invocation = self.invocation("render", args)
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        shutil.rmtree(self.root / "evidence")
        (self.root / "evidence").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(transactions.TransactionError, "symlink"):
            self.dispatch("render", args, invocation)
        self.assertEqual(list(outside.iterdir()), [])
        (self.root / "evidence").unlink()

        from bricksmith.rendering import rasterizer
        def interrupted(_source, output, **_kwargs):
            Path(output).write_bytes(b"partial render")
            raise RuntimeError("simulated renderer interruption")
        with patch.object(rasterizer, "render_ldr_to_png", side_effect=interrupted):
            with self.assertRaisesRegex(RuntimeError, "interruption"):
                self.dispatch("render", args, invocation)
        stage_root = self.root / "evidence" / "renders"
        stages = list(stage_root.glob(f".{invocation['operation_id']}.staging-*"))
        self.assertEqual(len(stages), 1)
        outside_image = outside / "protected.png"
        outside_image.write_bytes(b"do not follow or delete")
        (stages[0] / "image.png").unlink()
        (stages[0] / "image.png").symlink_to(outside_image)
        with self.assertRaisesRegex(transactions.TransactionError, "contains a symlink"):
            self.dispatch("render", args, invocation)
        self.assertEqual(outside_image.read_bytes(), b"do not follow or delete")
        (stages[0] / "image.png").unlink()
        (stages[0] / "image.png").write_bytes(b"partial render")
        def successful(_source, output, **_kwargs): Path(output).write_bytes(b"complete fake PNG bytes")
        with patch.object(rasterizer, "render_ldr_to_png", side_effect=successful) as renderer:
            rendered = self.dispatch("render", args, invocation)
            self.assertEqual(renderer.call_count, 1)
        with patch.object(rasterizer, "render_ldr_to_png", side_effect=AssertionError("rerendered")) as renderer:
            replay = self.dispatch("render", args, invocation)
            renderer.assert_not_called()
        self.assertEqual(replay["render_sha256"], rendered["render_sha256"])
        changed = self.invocation("render", {"view": "top"}, invocation["operation_id"])
        with self.assertRaisesRegex(transactions.TransactionError, "different or corrupt invocation reservation"):
            self.dispatch("render", {"view": "top"}, changed)
        with revisions.writer_lock(self.root):
            with self.assertRaises(revisions.RevisionError): self.dispatch("render", args,
                self.invocation("render", args))

    def test_line_operations_preserve_identity_until_explicit_delete(self):
        part_id = revisions.load_revision(self.root,
            revisions.read_state(self.root)["current_revision_id"])["parts"][0]["id"]
        value = revisions.load_revision(self.root, revisions.read_state(self.root)["current_revision_id"])
        line_map = design.load_line_map(revisions.revision_dir(self.root, value["revision_id"]) / "line_map.json")
        assembly_id = value["assemblies"][0]["id"]
        module_line = next(item["line"] for item in line_map["exports"][f"modules/{assembly_id}.ldr"]["placements"]
                           if item["part_id"] == part_id)
        self.dispatch("recolor_module_lines", {"name": value["assemblies"][0]["name"],
            "lines": [module_line], "color": 4})
        after_recolor = revisions.load_revision(self.root,
            revisions.read_state(self.root)["current_revision_id"])["parts"][0]
        self.assertEqual(after_recolor["id"], part_id)
        self.assertEqual(after_recolor["color_id"], 4)
        value = revisions.load_revision(self.root, revisions.read_state(self.root)["current_revision_id"])
        line_map = design.load_line_map(revisions.revision_dir(self.root, value["revision_id"]) / "line_map.json")
        build_line = next(item["line"] for item in line_map["exports"]["build.ldr"]["placements"]
                          if item["part_id"] == part_id)
        assembled = (revisions.revision_dir(self.root, value["revision_id"]) / "build.ldr").read_text().splitlines()
        replacement = assembled[build_line - 1].replace("3024.dat", "3023.dat")
        expected_catalog_id = design.import_ldr(replacement)["parts"][0]["part_id"]
        self.dispatch("edit_lines", {"edits": [{"line": build_line, "action": "replace", "text": replacement}]})
        replaced = revisions.load_revision(self.root,
            revisions.read_state(self.root)["current_revision_id"])["parts"][0]
        self.assertEqual(replaced["id"], part_id)
        self.assertEqual(replaced["part_id"], expected_catalog_id)
        after_recolor = replaced
        before_move = copy.deepcopy(after_recolor)
        value = revisions.load_revision(self.root, revisions.read_state(self.root)["current_revision_id"])
        line_map = design.load_line_map(revisions.revision_dir(self.root, value["revision_id"]) / "line_map.json")
        build_line = next(item["line"] for item in line_map["exports"]["build.ldr"]["placements"]
                          if item["part_id"] == part_id)
        self.dispatch("move_lines", {"lines": [build_line], "dx": 20, "dy": 0, "dz": 0})
        moved = revisions.load_revision(self.root,
            revisions.read_state(self.root)["current_revision_id"])["parts"][0]
        self.assertEqual(moved["id"], part_id)
        self.assertEqual(moved["translation_ldu"][0], before_move["translation_ldu"][0] + 20)
        value = revisions.load_revision(self.root, revisions.read_state(self.root)["current_revision_id"])
        line_map = design.load_line_map(revisions.revision_dir(self.root, value["revision_id"]) / "line_map.json")
        build_line = next(item["line"] for item in line_map["exports"]["build.ldr"]["placements"]
                          if item["part_id"] == part_id)
        self.dispatch("edit_lines", {"edits": [{"line": build_line, "action": "delete", "text": ""}]})
        self.assertFalse(any(part["id"] == part_id for part in revisions.load_revision(self.root,
            revisions.read_state(self.root)["current_revision_id"])["parts"]))

    def test_every_mutation_name_runs_through_transaction_dispatch(self):
        sample = next(line for line in (ROOT / "tests/fixtures/acceptance/pass.ldr").read_text().splitlines()
                      if line.startswith("1 "))
        base = revisions.load_revision(self.root, revisions.read_state(self.root)["current_revision_id"])
        line_map = design.load_line_map(revisions.revision_dir(self.root, base["revision_id"]) / "line_map.json")
        build_line = line_map["exports"]["build.ldr"]["placements"][0]["line"]
        module_line = line_map["exports"][f"modules/{base['assemblies'][0]['id']}.ldr"]["placements"][0]["line"]
        cases = [
            ("save_module", {"name": "new-module", "ldr": "0 retained comment\n" + sample + "\n"}),
            ("clone_module", {"source": "Imported design", "name": "clone", "dx": 100, "dy": 0, "dz": 0}),
            ("discard_module", {"name": "Imported design"}),
            ("recolor_module_lines", {"name": "Imported design", "lines": [module_line], "color": 4}),
            ("edit_lines", {"edits": [{"line": build_line, "action": "replace", "text": sample.replace("1 15 ", "1 4 ", 1)}]}),
            ("move_lines", {"lines": [build_line, build_line], "dx": 20, "dy": 0, "dz": 0}),
            ("move_groups", {"groups": [{"lines": [build_line, build_line], "dx": 20, "dy": 0, "dz": 0},
                                               {"lines": [build_line], "dx": 0, "dy": 0, "dz": 20}]}),
            ("save_array", {"name": "array", "template": sample, "counts": [1, 1, 1],
                             "step_x": [20, 0, 0], "step_y": [0, 0, 0], "step_z": [0, 0, 20]}),
            ("save_floor", {"name": "floor", "color": 4, "y": 0,
                             "rectangles": [{"x_min": 0, "x_max": 20, "z_min": 0, "z_max": 20}]}),
            ("save_wall_runs", {"name": "walls", "color": 4, "bottom_y": 0,
                             "runs": [{"axis": "x", "start": 0, "end": 20, "fixed": 10,
                                       "courses": 1, "openings": []}]}),
            ("save_gable", {"name": "gable", "color": 4, "axis": "x", "start": 0, "end": 40,
                             "fixed": 10, "bottom_y": 0, "courses": 1, "inset_studs": 1}),
            ("save_stepped_roof_beams", {"name": "beams", "color": 4, "left_x": 10, "right_x": 30,
                             "front_z": 10, "rear_z": 70, "gable_bottom_y": 0, "courses": 1, "beam_studs": 4}),
            ("save_roof_tile_caps", {"name": "caps", "color": 4, "left_x": 10, "right_x": 30,
                             "front_z": 10, "rear_z": 70, "gable_bottom_y": 0, "courses": 1, "beam_studs": 4}),
            ("save_support_column", {"name": "column", "x": 10, "z": 10, "bottom_y": 0, "bricks": 1,
                             "color": 4, "cap_color": 4, "cap_plate": False, "size_studs": 1}),
            ("save_roof_seam_column", {"name": "seam", "x": 10, "z": 0, "bottom_y": 0, "bricks": 1,
                             "color": 4, "cap_color": 4}),
        ]
        initial_root = self.root
        for index, (name, args) in enumerate(cases):
            with self.subTest(tool=name):
                self.root = Path(self.tmp.name) / f"case-{index}"
                source = design.import_ldr(ROOT / "tests/fixtures/acceptance/pass.ldr", ground_y=8)
                revisions.initialize(self.root, source)
                result = self.dispatch(name, args)
                self.assertEqual(result["schema"], "bricksmith-tool-result-v1")
                self.assertEqual(result["tool"], name)
                self.assertTrue(result["committed"], result)
                receipt = revisions.read_state(self.root)["receipts"][result["operation_id"]]
                self.assertEqual(receipt["disposition"], "committed")
        self.root = initial_root


if __name__ == "__main__":
    unittest.main()
