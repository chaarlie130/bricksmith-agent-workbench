from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from decimal import Decimal
from pathlib import Path

from bricksmith.workbench import design

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / ".venv/bin/python"
FIXTURE = ROOT / "tests/fixtures/acceptance/pass.ldr"


class OfflineTransactionCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def cli(self, *args, ok=True):
        env = dict(os.environ, BRICKNET_DATA=str(ROOT / "data/bricknet-data"))
        result = subprocess.run([str(PYTHON), "scripts/workbench.py", *map(str, args)], cwd=ROOT,
                                env=env, text=True, capture_output=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_explicit_v2_upgrade_ledger_lifecycle_cli_and_bounded_read(self):
        source = self.root / "source.json"
        self.cli("design-import", FIXTURE, source, "--ground-y", "8")
        workspace = self.root / "workspace"
        self.cli("transaction-init", source, workspace)
        before = design.load_design(source)
        upgrade_id = str(uuid.uuid4())
        upgraded = json.loads(self.cli("transaction-upgrade-v2", workspace, upgrade_id,
            before["revision_id"]).stdout)
        self.assertEqual(upgraded["disposition"], "committed")
        instruction_id, requirement_id, decision_id, issue_id = (str(uuid.uuid4()) for _ in range(4))
        intake = {"operation_id": str(uuid.uuid4()), "base_revision_id": upgraded["revision_id"],
            "instruction_id": instruction_id, "created_at": "2026-10-16T12:00:00Z",
            "instruction_text": "Please retain the round east window.", "fill_brief": False,
            "changes": [
                {"type": "requirement", "record": {"id": requirement_id,
                    "description": "Retain the round east window", "priority": "mandatory",
                    "affected_assembly_ids": [], "measurable_predicate": None,
                    "evidence_reference_ids": [], "status": "pending", "supersedes_id": None}},
                {"type": "decision", "record": {"id": decision_id,
                    "statement": "Use a bonded stepped roof lap", "rationale": "Keep roof connection review local to this design.",
                    "status": "active", "related_assembly_ids": [], "related_requirement_ids": [],
                    "evidence_reference_ids": [], "supersedes_id": None}},
                {"type": "issue", "issue_id": issue_id, "kind": "roof_connectivity", "status": "open",
                    "affected_ids": [], "evidence_reference_ids": [], "next_proposed_action": "inspect the roof bonds"},
                {"type": "next_action", "record": {"id": str(uuid.uuid4()),
                    "description": "Inspect roof bonds", "kind": "inspect", "related_requirement_ids": [],
                    "related_issue_ids": [issue_id], "evidence_references": [], "status": "pending",
                    "supersedes_id": None}}
            ]}
        request_path = self.root / "intake.json"
        request_path.write_text(json.dumps(intake))
        recorded = json.loads(self.cli("operator-intake", workspace, request_path,
            "--source", "user").stdout)
        self.assertEqual(recorded["disposition"], "committed")
        current = recorded["revision_id"]

        # A real checker failure is retained as a candidate, not committed as a repair.
        initial = design.load_design(workspace / "revisions" / current / "design.json")
        colliding = copy.deepcopy(initial["parts"][0]); colliding["id"] = str(uuid.uuid4())
        failed_operation = {"schema": "bricksmith-operation-v3", "operation_id": str(uuid.uuid4()),
            "base_revision_id": current, "intent": "deliberately test a colliding repair",
            "operations": [{"type": "add_part", "part": colliding}]}
        failed_path = self.root / "failed.json"; failed_path.write_text(design._json_text(failed_operation))
        failed = json.loads(self.cli("transaction-propose", workspace, failed_path).stdout)
        self.assertFalse(failed["commit_eligible"])

        # An ordinary M2 transform passes all real checks and is committed.
        assembly_id = initial["assemblies"][0]["id"]
        successful_operation = {"schema": "bricksmith-operation-v3", "operation_id": str(uuid.uuid4()),
            "base_revision_id": current, "intent": "shift the support plate on the ground plane",
            "operations": [{"type": "transform", "selector": {"assembly_ids": [assembly_id]},
                "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                "translation_ldu": [20, 0, 0], "pivot_ldu": [0, 0, 0]}]}
        successful_path = self.root / "successful.json"; successful_path.write_text(design._json_text(successful_operation))
        success_report = json.loads(self.cli("transaction-propose", workspace, successful_path).stdout)
        self.assertTrue(success_report["commit_eligible"])
        success_receipt = json.loads(self.cli("transaction-commit", workspace,
            successful_operation["operation_id"], success_report["candidate_id"]).stdout)

        followup = {"operation_id": str(uuid.uuid4()), "base_revision_id": success_receipt["revision_id"],
            "instruction_id": str(uuid.uuid4()), "created_at": "2026-10-16T12:01:00Z",
            "instruction_text": "The operator interrupted Argon and requested a render-only handoff to Flash.", "fill_brief": False,
            "changes": [
                {"type": "repair_attempt", "record": {"id": str(uuid.uuid4()), "issue_ids": [issue_id],
                    "attempted_operation_id": failed_operation["operation_id"], "observed_revision_id": current,
                    "evidence_references": [], "note": "Collision regression was retained and not committed."}},
                {"type": "repair_attempt", "record": {"id": str(uuid.uuid4()), "issue_ids": [issue_id],
                    "attempted_operation_id": successful_operation["operation_id"],
                    "observed_revision_id": success_receipt["revision_id"],
                    "evidence_references": [], "note": "Later construction checks passed."}},
                {"type": "next_action", "record": {"id": str(uuid.uuid4()),
                    "description": "Render only; keep visual requirement pending", "kind": "render",
                    "related_requirement_ids": [requirement_id], "related_issue_ids": [issue_id],
                    "evidence_references": [], "status": "pending", "supersedes_id": None}}
            ]}
        followup_path = self.root / "followup.json"; followup_path.write_text(json.dumps(followup))
        final_receipt = json.loads(self.cli("operator-intake", workspace, followup_path,
            "--source", "operator").stdout)
        ledger = json.loads(self.cli("ledger-read", workspace, "--limit", "10").stdout)
        self.assertEqual(final_receipt["disposition"], "committed")
        self.assertEqual(ledger["collections"]["instructions"]["count"], 2)
        self.assertEqual(ledger["collections"]["requirements"]["items"][0]["description"],
            "Retain the round east window")
        self.assertEqual(ledger["collections"]["requirements"]["items"][0]["status"], "pending")
        self.assertEqual(ledger["collections"]["issues"]["items"][0]["status"], "open")
        outcomes = {item["attempted_operation_id"]: item["current_reconciled_outcome"]
                    for item in ledger["collections"]["repair_attempts"]["items"]}
        self.assertEqual(outcomes[failed_operation["operation_id"]]["disposition"], "candidate")
        self.assertEqual(outcomes[failed_operation["operation_id"]]["policy_status"], "blocked")
        self.assertEqual(outcomes[successful_operation["operation_id"]]["construction_status"], "construction_passed")
        recorded = {item["attempted_operation_id"]: item["outcome_at_recording"]
                    for item in ledger["collections"]["repair_attempts"]["items"]}
        self.assertEqual(recorded[failed_operation["operation_id"]]["disposition"], "candidate")
        handoff_page = json.loads(self.cli("ledger-read", workspace, "--offset", "1", "--limit", "1").stdout)
        self.assertEqual(handoff_page["collections"]["next_actions"]["items"][0]["description"],
            "Render only; keep visual requirement pending")
        self.assertEqual(handoff_page["collections"]["active_next_actions"]["items"][0]["status"], "pending")

    def test_cli_import_multiassembly_commit_real_checks_render_and_retry(self):
        source_design = self.root / "source.json"
        self.cli("design-import", FIXTURE, source_design, "--ground-y", "8")
        workspace = self.root / "workspace"
        self.cli("transaction-init", source_design, workspace)
        value = design.load_design(source_design)
        part = copy.deepcopy(value["parts"][0]); part["id"] = str(uuid.uuid4())
        part["translation_ldu"][1] = -8
        new_assembly = {"id": str(uuid.uuid4()), "name": "Upper plate", "role": "upper_course",
            "parent_assembly_id": None, "design_properties": {}, "relationships": [], "field_locks": []}
        request = {"schema": "bricksmith-operation-v1", "operation_id": str(uuid.uuid4()),
            "base_revision_id": value["revision_id"], "intent": "add a supported plate in a second assembly",
            "operations": [{"type": "create_assembly", "assembly": new_assembly}, {"type": "add_part", "part": part}]}
        request_path = self.root / "request.json"
        request_path.write_text(design._json_text(request))
        proposed = json.loads(self.cli("transaction-propose", workspace, request_path).stdout)
        self.assertTrue(proposed["commit_eligible"])
        self.assertEqual(proposed["status"], "construction_passed")
        self.assertEqual(proposed["affected_count"], 2)
        inspected = json.loads(self.cli("transaction-inspect", workspace, request["operation_id"]).stdout)
        self.assertEqual(inspected["candidate_id"], proposed["candidate_id"])
        receipt = json.loads(self.cli("transaction-commit", workspace, request["operation_id"], proposed["candidate_id"]).stdout)
        self.assertEqual(receipt["disposition"], "committed")
        self.assertEqual(receipt["construction_status"], "construction_passed")
        build = workspace / "build.ldr"
        check = json.loads(self.cli("check", build, "--ground-y", "8").stdout)
        self.assertTrue(all(check["checks"].values()))
        image = self.root / "committed.png"
        rendered = subprocess.run([str(PYTHON), "scripts/render.py", str(build), "--output", str(image)],
            cwd=ROOT, env=dict(os.environ, BRICKNET_DATA=str(ROOT / "data/bricknet-data")),
            text=True, capture_output=True)
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        self.assertTrue(image.is_file())
        before = hashlib.sha256(build.read_bytes()).hexdigest()
        retry = json.loads(self.cli("transaction-propose", workspace, request_path).stdout)
        self.assertEqual(retry["disposition"], "committed")
        self.assertEqual(hashlib.sha256(build.read_bytes()).hexdigest(), before)

    def test_collision_regression_candidate_is_retained_then_discarded(self):
        source = self.root / "source.json"; self.cli("design-import", FIXTURE, source, "--ground-y", "8")
        workspace = self.root / "workspace"; self.cli("transaction-init", source, workspace)
        value = design.load_design(source); part = copy.deepcopy(value["parts"][0]); part["id"] = str(uuid.uuid4())
        request = {"schema": "bricksmith-operation-v1", "operation_id": str(uuid.uuid4()),
            "base_revision_id": value["revision_id"], "intent": "deliberately collide",
            "operations": [{"type": "add_part", "part": part}]}
        path = self.root / "request.json"; path.write_text(design._json_text(request))
        report = json.loads(self.cli("transaction-propose", workspace, path).stdout)
        self.assertFalse(report["commit_eligible"])
        self.assertEqual(report["policy"]["reasons"][0]["code"], "hard_check_regression")
        candidate_path = workspace / "operations" / request["operation_id"] / "candidate/design.json"
        self.assertTrue(candidate_path.is_file())
        refused = self.cli("transaction-commit", workspace, request["operation_id"], report["candidate_id"], ok=False)
        self.assertEqual(refused.returncode, 2)
        discarded = json.loads(self.cli("transaction-discard", workspace, request["operation_id"]).stdout)
        self.assertEqual(discarded["disposition"], "discarded")
        again = json.loads(self.cli("transaction-discard", workspace, request["operation_id"]).stdout)
        self.assertEqual(again, discarded)

    def test_transaction_tool_catalog_and_dispatch_cli(self):
        catalog = json.loads(self.cli("transaction-tool-catalog").stdout)
        self.assertEqual(catalog["schema"], "bricksmith-offline-tool-catalog-v1")
        self.assertIn("save_module", {item["name"] for item in catalog["tools"]})
        source = self.root / "source.json"
        self.cli("design-import", FIXTURE, source, "--ground-y", "8")
        workspace = self.root / "workspace"
        self.cli("transaction-init", source, workspace)
        state = json.loads((workspace / "state.json").read_text())
        revision_id = state["current_revision_id"]
        revision = workspace / "revisions" / revision_id
        build = (revision / "build.ldr").read_bytes()
        invocation = {"schema": "bricksmith-tool-invocation-v1", "tool_name": "read_module",
            "arguments": {"name": design.load_design(source)["assemblies"][0]["name"], "start": 1, "count": 5},
            "operation_id": str(uuid.uuid4()), "expected_base_revision_id": revision_id,
            "expected_export_sha256": hashlib.sha256(build).hexdigest()}
        call = self.root / "invocation.json"
        call.write_text(json.dumps(invocation))
        result = json.loads(self.cli("transaction-tool", workspace, call).stdout)
        self.assertEqual(result["revision_id"], revision_id)
        self.assertEqual(result["tool"], "read_module")
        assembly = design.load_design(source)["assemblies"][0]
        module_path = revision / "modules" / (assembly["id"] + ".ldr")
        self.assertEqual(result["export_identity"]["sha256"], hashlib.sha256(module_path.read_bytes()).hexdigest())
        save_args = {"name": assembly["name"], "ldr": module_path.read_text()}
        save_call = {"schema": "bricksmith-tool-invocation-v1", "tool_name": "save_module",
            "arguments": save_args, "operation_id": str(uuid.uuid4()),
            "expected_base_revision_id": revision_id,
            "expected_export_sha256": hashlib.sha256(build).hexdigest()}
        save_path = self.root / "save-invocation.json"
        save_path.write_text(json.dumps(save_call))
        saved = json.loads(self.cli("transaction-tool", workspace, save_path).stdout)
        self.assertTrue(saved["committed"], saved)
        self.assertEqual(saved["status"], "construction_passed")

    def test_cli_adapter_mutations_collision_retry_check_and_render(self):
        source = self.root / "source.json"
        self.cli("design-import", FIXTURE, source, "--ground-y", "8")
        workspace = self.root / "workspace"
        self.cli("transaction-init", source, workspace)

        def invoke(tool, arguments, operation_id=None):
            state = json.loads((workspace / "state.json").read_text())
            revision_id = state["current_revision_id"]
            revision = workspace / "revisions" / revision_id
            build = (revision / "build.ldr").read_bytes()
            call = {"schema": "bricksmith-tool-invocation-v1", "tool_name": tool,
                "arguments": arguments, "operation_id": operation_id or str(uuid.uuid4()),
                "expected_base_revision_id": revision_id,
                "expected_export_sha256": hashlib.sha256(build).hexdigest()}
            path = self.root / f"invocation-{tool}-{call['operation_id']}.json"
            path.write_text(json.dumps(call))
            return call, json.loads(self.cli("transaction-tool", workspace, path).stdout)

        initial = design.load_design(source)
        assembly = initial["assemblies"][0]
        original_module = workspace / "revisions" / initial["revision_id"] / "modules" / f"{assembly['id']}.ldr"
        _, saved = invoke("save_module", {"name": assembly["name"], "ldr": original_module.read_text()})
        self.assertTrue(saved["committed"], saved)

        def first_build_line():
            state = json.loads((workspace / "state.json").read_text())
            revision = workspace / "revisions" / state["current_revision_id"]
            line_map = design.load_line_map(revision / "line_map.json")
            return next(item["line"] for item in line_map["exports"]["build.ldr"]["placements"])

        _, moved = invoke("move_lines", {"lines": [first_build_line()], "dx": 20, "dy": 0, "dz": 0})
        self.assertTrue(moved["committed"], moved)
        state = json.loads((workspace / "state.json").read_text())
        revision = workspace / "revisions" / state["current_revision_id"]
        line_map = design.load_line_map(revision / "line_map.json")
        module_line = line_map["exports"][f"modules/{assembly['id']}.ldr"]["placements"][0]["line"]
        _, recolored = invoke("recolor_module_lines", {"name": assembly["name"], "lines": [module_line], "color": 4})
        self.assertTrue(recolored["committed"], recolored)
        _, cloned = invoke("clone_module", {"source": assembly["name"], "name": "clone-module",
            "dx": 100, "dy": 0, "dz": 0})
        self.assertTrue(cloned["committed"], cloned)
        self.assertEqual(cloned["tool_details"]["cloned_from"], assembly["name"])

        state = json.loads((workspace / "state.json").read_text())
        revision_id = state["current_revision_id"]
        revision = workspace / "revisions" / revision_id
        colliding_module = revision / "modules" / f"{assembly['id']}.ldr"
        collision_call, collision = invoke("save_module", {"name": "collision", "ldr": colliding_module.read_text()})
        self.assertFalse(collision["committed"])
        self.assertEqual(collision["disposition"], "candidate")
        self.assertEqual(json.loads((workspace / "state.json").read_text())["current_revision_id"], revision_id)
        collision_path = self.root / f"retry-{collision_call['operation_id']}.json"
        collision_path.write_text(json.dumps(collision_call))
        retry = json.loads(self.cli("transaction-tool", workspace, collision_path).stdout)
        self.assertFalse(retry["committed"])
        self.assertEqual(retry["candidate_id"], collision["candidate_id"])

        _, check = invoke("check", {})
        self.assertEqual(check["revision_id"], revision_id)
        _, rendered = invoke("render", {"view": "front_left"})
        self.assertFalse(rendered["reviewed"])
        self.assertTrue((workspace / rendered["render_path"]).is_file())

    def test_cli_decimal_array_uses_exact_json_decimal_positions(self):
        source = self.root / "source.json"
        self.cli("design-import", FIXTURE, source, "--ground-y", "8")
        workspace = self.root / "workspace"
        self.cli("transaction-init", source, workspace)
        state = json.loads((workspace / "state.json").read_text())
        revision_id = state["current_revision_id"]
        revision = workspace / "revisions" / revision_id
        build = (revision / "build.ldr").read_bytes()
        source_line = next(line for line in FIXTURE.read_text().splitlines() if line.startswith("1 "))
        fields = source_line.split(); fields[2] = "0.0000000000000000001"
        args = {"name": "decimal-array", "template": "0 decimal template\n" + " ".join(fields),
            "counts": [2, 1, 1], "step_x": [Decimal("0.5"), 0, 0],
            "step_y": [0, 0, 0], "step_z": [0, 0, 0]}
        invocation = {"schema": "bricksmith-tool-invocation-v1", "tool_name": "save_array",
            "arguments": args, "operation_id": str(uuid.uuid4()),
            "expected_base_revision_id": revision_id,
            "expected_export_sha256": hashlib.sha256(build).hexdigest()}
        path = self.root / "decimal-array-invocation.json"
        path.write_text(design._json_text(invocation))
        proposed = json.loads(self.cli("transaction-tool", workspace, path).stdout)
        self.assertFalse(proposed["committed"])
        candidate = design.read_json(workspace / "operations" / invocation["operation_id"] / "candidate/design.json")
        assembly = next(item for item in candidate["assemblies"] if item["name"] == "decimal-array")
        positions = sorted(part["translation_ldu"][0] for part in candidate["parts"]
                           if part["assembly_id"] == assembly["id"])
        self.assertEqual(positions, [Decimal("1e-19"), Decimal("0.5000000000000000001")])
        intent = design.read_json(workspace / "operations" / invocation["operation_id"] / "intent.json")["intent"]
        self.assertIn("0.5000000000000000001", intent["adapter_evidence"]["generated_content"])
        retry = json.loads(self.cli("transaction-tool", workspace, path).stdout)
        self.assertEqual(retry["candidate_id"], proposed["candidate_id"])
        self.assertEqual(retry["affected_ids"], proposed["affected_ids"])
        self.assertEqual(retry["policy_status"], proposed["policy_status"])


if __name__ == "__main__": unittest.main()
