from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid
from decimal import Decimal, getcontext
from pathlib import Path

from bricksmith.workbench import design, revisions, transactions

ROOT = Path(__file__).resolve().parents[2]
PASS = ROOT / "tests/fixtures/acceptance/pass.ldr"


def uid(): return str(uuid.uuid4())


def make_design(count=1):
    value = design.import_ldr(PASS, ground_y=Decimal("8"))
    root_assembly = value["assemblies"][0]["id"]
    template = copy.deepcopy(value["parts"][0])
    while len(value["parts"]) < count:
        part = copy.deepcopy(template)
        part["id"] = uid()
        part["translation_ldu"] = [Decimal(len(value["parts"]) * 40), Decimal("0"), Decimal("0")]
        value["parts"].append(part)
    design.refresh_hashes(value); design.validate_design(value)
    return value


def good_validator(path, ground):
    lines = [line for line in Path(path).read_text().splitlines() if line.startswith("1 ")]
    n = len(lines)
    return {"schema": "bricksmith-construction-v1", "passed": True,
        "checks": {key: True for key in transactions.CHECKS}, "errors": [],
        "diagnostics": {"below_ground_indices_complete_flag": True, "below_ground_indices_complete": []},
        "physical_piece_count": n}


def request(value, operations, opid=None):
    return {"schema": transactions.OPERATION_SCHEMA, "operation_id": opid or uid(),
            "base_revision_id": value["revision_id"], "intent": "test transaction",
            "operations": operations}


def transform(value, assembly_id, dx="20"):
    return {"type": "transform", "selector": {"assembly_ids": [assembly_id]},
            "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            "translation_ldu": [Decimal(dx), Decimal("0"), Decimal("0")],
            "pivot_ldu": [Decimal("0"), Decimal("0"), Decimal("0")]}


class TransactionPureTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64)
        patcher.start(); self.addCleanup(patcher.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "session"
        self.value = make_design()
        revisions.initialize(self.root, self.value)

    def propose(self, ops, validator=good_validator, opid=None):
        req = request(self.value, ops, opid)
        result = transactions.propose_edit(self.root, req, validator=validator)
        return req, result

    def test_identity_rotation_and_exact_pivot_formula(self):
        part = self.value["parts"][0]
        part["translation_ldu"] = [Decimal("123456789012345678901234567890.123456789"), 0, 0]
        design.refresh_hashes(self.value)
        self.value["revision_id"] = uid(); design.refresh_hashes(self.value)
        revisions.initialize(Path(self.temp.name) / "precise", self.value)
        op = {"type": "transform", "selector": {"part_ids": [part["id"]]},
              "rotation": [[0, -1, 0], [1, 0, 0], [0, 0, 1]],
              "translation_ldu": [Decimal("0.00000000000000000000001"), 0, 0],
              "pivot_ldu": [0, 0, 0]}
        old = getcontext().prec; getcontext().prec = 5
        try:
            req = request(self.value, [op])
            result = transactions.propose_edit(Path(self.temp.name) / "precise", req, validator=good_validator)
        finally: getcontext().prec = old
        cand = design.read_json(Path(self.temp.name) / "precise/operations" / req["operation_id"] / "candidate/design.json")
        moved = next(p for p in cand["parts"] if p["id"] == part["id"])
        self.assertEqual(moved["id"], part["id"])
        self.assertEqual(moved["translation_ldu"][0], Decimal("0.00000000000000000000001"))
        self.assertEqual(moved["translation_ldu"][1], Decimal("123456789012345678901234567890.123456789"))
        self.assertEqual(revisions.read_state(Path(self.temp.name) / "precise")["current_revision_id"], self.value["revision_id"])

    def test_reflection_uses_world_pivot_without_inherited_assembly_transform(self):
        part_id = self.value["parts"][0]["id"]
        op = {"type": "transform", "selector": {"part_ids": [part_id]},
              "rotation": [[-1,0,0],[0,1,0],[0,0,1]], "translation_ldu": [1,0,0],
              "pivot_ldu": [10,0,0]}
        req = request(self.value, [op]); transactions.propose_edit(self.root, req, validator=good_validator)
        candidate = design.read_json(self.root / "operations" / req["operation_id"] / "candidate/design.json")
        reflected = next(part for part in candidate["parts"] if part["id"] == part_id)
        self.assertEqual(reflected["translation_ldu"][0], Decimal("21"))
        self.assertEqual(reflected["rotation"][0][0], Decimal("-1"))

    def test_operations_support_recolor_membership_metadata_and_clone_provenance(self):
        value = self.value; part_id = value["parts"][0]["id"]; assembly_id = value["assemblies"][0]["id"]
        clone = {"type": "clone_assemblies", "assembly_ids": [assembly_id],
                 "assembly_id_map": {assembly_id: uid()}, "part_id_map": {part_id: uid()},
                 "translation_ldu": [Decimal("100"), 0, 0]}
        ops = [{"type": "recolor", "selector": {"part_ids": [part_id]}, "color_id": 71}, clone]
        req, result = self.propose(ops)
        candidate = design.read_json(self.root / "operations" / req["operation_id"] / "candidate/design.json")
        clone_id = clone["part_id_map"][part_id]
        cloned = next(p for p in candidate["parts"] if p["id"] == clone_id)
        self.assertEqual(cloned["provenance"]["derived_from"], part_id)
        self.assertEqual(cloned["color_id"], 71)
        self.assertIn(clone_id, result["clone_derived_from"])
        self.assertEqual(len(candidate["parts"]), 2)

    def test_replace_delete_and_sequential_selected_part_disallow_deleted_target(self):
        part = copy.deepcopy(self.value["parts"][0]); original_id = part["id"]
        replacement = copy.deepcopy(part); replacement["id"] = uid(); replacement["color_id"] = 71
        req = request(self.value, [{"type": "replace_part", "part_id": original_id,
                                    "replacement": replacement, "retain_id": False}])
        report = transactions.propose_edit(self.root, req, validator=good_validator)
        self.assertIn(replacement["id"], report["created_ids"])
        self.assertIn(original_id, report["deleted_ids"])
        second = request(self.value, [{"type": "delete", "selector": {"part_ids": [original_id]}},
            {"type": "transform", "selector": {"part_ids": [original_id]},
             "rotation": [[1,0,0],[0,1,0],[0,0,1]], "translation_ldu": [1,0,0], "pivot_ldu": [0,0,0]}])
        # This is valid JSON/schema and frozen intent, but application rejects the
        # later operation rather than silently skipping a deleted part.
        failed = transactions.propose_edit(self.root, second, validator=good_validator)
        self.assertEqual(failed["status"], "failure")

    def test_parent_child_selector_deduplicates_and_ordered_operations_repeat(self):
        value = make_design(1)
        top = value["assemblies"][0]
        child = copy.deepcopy(top); child["id"] = uid(); child["name"] = "child"; child["parent_assembly_id"] = top["id"]
        value["assemblies"].append(child); value["parts"][0]["assembly_id"] = child["id"]
        design.refresh_hashes(value); design.validate_design(value)
        root = Path(self.temp.name) / "nested"; revisions.initialize(root, value)
        req = request(value, [transform(value, top["id"]), transform(value, child["id"])])
        rep = transactions.propose_edit(root, req, validator=good_validator)
        cand = design.read_json(root / "operations" / req["operation_id"] / "candidate/design.json")
        self.assertEqual(rep["affected_count"], 1)
        self.assertEqual(cand["parts"][0]["translation_ldu"][0], Decimal("40"))

    def test_lock_and_requirement_authority(self):
        value = copy.deepcopy(self.value); part = value["parts"][0]; aid = value["assemblies"][0]["id"]
        value["assemblies"][0]["field_locks"].append({"id": uid(), "owner": "user", "target_id": part["id"], "fields": ["translation_ldu"]})
        value["requirements"].append({"id": uid(), "description": "preserve facade", "source": "user", "priority": "mandatory",
            "affected_assembly_ids": [aid], "evidence_reference_ids": [], "measurable_predicate": None, "status": "pending"})
        design.refresh_hashes(value); design.validate_design(value)
        root = Path(self.temp.name) / "locked"; revisions.initialize(root, value)
        req = request(value, [transform(value, aid)])
        report = transactions.propose_edit(root, req, validator=good_validator)
        self.assertFalse(report["commit_eligible"])
        self.assertEqual(report["policy_conflicts"][0]["reason"], "user-locked field changed")

    def test_strict_schema_and_size_rejection_before_operation_directory(self):
        req = request(self.value, [transform(self.value, self.value["assemblies"][0]["id"])])
        with self.assertRaises(transactions.TransactionError):
            transactions.propose_edit(self.root, {**req, "surprise": True}, validator=good_validator)
        too_many = request(self.value, [transform(self.value, self.value["assemblies"][0]["id"])] * 65)
        with self.assertRaises(transactions.TransactionError): transactions.normalize_request(too_many)
        giant = request(self.value, [transform(self.value, self.value["assemblies"][0]["id"])])
        giant["intent"] = "x" * (1 << 20)
        with self.assertRaises(transactions.TransactionError): transactions.normalize_request(giant)
        self.assertFalse((self.root / "operations" / req["operation_id"]).exists())

    def test_operation_v2_bulk_replacement_allows_absent_adapter_metadata(self):
        aid = uid(); source_id = uid(); part = copy.deepcopy(self.value["parts"][0])
        part["id"] = uid(); part["assembly_id"] = aid
        part["provenance"] = {**part["provenance"], "source_reference_id": source_id,
            "source": "direct_operation_v2", "operation_id": None}
        source_reference = {"id": source_id, "original_source_identity": "direct-core-test",
            "content_hash": design.file_hash(b"direct core test"), "role": "test_fixture",
            "local_artifact_reference": None, "license_rights_status": "unknown", "missing_data_notes": None}
        req = {"schema": transactions.OPERATION_SCHEMA_V2, "operation_id": uid(),
            "base_revision_id": self.value["revision_id"], "intent": "direct bulk replacement",
            "operations": [
                {"type": "create_assembly", "assembly": {"id": aid, "name": "direct-v2",
                    "role": None, "parent_assembly_id": None, "design_properties": {},
                    "relationships": [], "field_locks": []}},
                {"type": "replace_assembly_contents", "assembly_id": aid, "parts": [part],
                    "source_comments": [], "source_reference": source_reference}]}
        report = transactions.propose_edit(self.root, req, validator=good_validator)
        self.assertTrue(report["commit_eligible"])
        saved_intent = design.read_json(self.root / "operations" / req["operation_id"] / "intent.json")["intent"]
        self.assertEqual(saved_intent["schema"], transactions.OPERATION_SCHEMA_V2)
        self.assertNotIn("adapter_invocation", saved_intent)
        candidate = design.read_json(self.root / "operations" / req["operation_id"] / "candidate/design.json")
        self.assertTrue(any(item["id"] == part["id"] for item in candidate["parts"]))

    def test_operation_v2_malformed_optional_adapter_metadata_is_rejected(self):
        req = request(self.value, [transform(self.value, self.value["assemblies"][0]["id"])])
        req["schema"] = transactions.OPERATION_SCHEMA_V2
        req["adapter_invocation"] = {"schema": "unsupported", "tool_name": "test",
            "arguments": {}, "operation_id": req["operation_id"],
            "expected_base_revision_id": req["base_revision_id"], "expected_export_sha256": "a" * 64}
        with self.assertRaisesRegex(transactions.TransactionError, "adapter_invocation.schema is unsupported"):
            transactions.normalize_request(req)

    def test_identical_retry_and_conflicting_operation_id(self):
        opid = uid(); req, first = self.propose([transform(self.value, self.value["assemblies"][0]["id"])], opid=opid)
        second = transactions.propose_edit(self.root, req, validator=good_validator)
        self.assertEqual(first["candidate_id"], second["candidate_id"])
        changed = copy.deepcopy(req); changed["intent"] = "different intent"
        with self.assertRaisesRegex(transactions.TransactionError, "different arguments"):
            transactions.propose_edit(self.root, changed, validator=good_validator)

    def test_commit_retry_discard_and_stale_base(self):
        req, report = self.propose([transform(self.value, self.value["assemblies"][0]["id"])])
        receipt = transactions.commit_candidate(self.root, req["operation_id"], report["candidate_id"], validator=good_validator)
        self.assertEqual(receipt["disposition"], "committed")
        again = transactions.commit_candidate(self.root, req["operation_id"], report["candidate_id"], validator=good_validator)
        self.assertEqual(again["revision_id"], receipt["revision_id"])
        self.assertEqual(revisions.load_revision(self.root, receipt["revision_id"])["revision_id"], receipt["revision_id"])

        root2 = Path(self.temp.name) / "discard"; revisions.initialize(root2, self.value)
        req2 = request(self.value, [transform(self.value, self.value["assemblies"][0]["id"])])
        report2 = transactions.propose_edit(root2, req2, validator=good_validator)
        d1 = transactions.discard_candidate(root2, req2["operation_id"]); d2 = transactions.discard_candidate(root2, req2["operation_id"])
        self.assertEqual(d1["disposition"], "discarded"); self.assertEqual(d1, d2)
        with self.assertRaisesRegex(transactions.TransactionError, "discarded"):
            transactions.commit_candidate(root2, req2["operation_id"], report2["candidate_id"], validator=good_validator)

    def test_provisional_commit_creates_an_open_issue_without_acceptance(self):
        def provisional(path, ground):
            checks = {key: True for key in transactions.CHECKS}; checks["actual_connectivity"] = False
            return {"passed": False, "checks": checks, "errors": [],
                "diagnostics": {"below_ground_indices_complete_flag": True, "below_ground_indices_complete": []},
                "physical_piece_count": 1}
        req = request(self.value, [transform(self.value, self.value["assemblies"][0]["id"])])
        report = transactions.propose_edit(self.root, req, validator=provisional)
        self.assertTrue(report["commit_eligible"]); self.assertEqual(report["status"], "provisional")
        receipt = transactions.commit_candidate(self.root, req["operation_id"], report["candidate_id"], validator=provisional)
        committed = revisions.load_revision(self.root, receipt["revision_id"])
        self.assertTrue(any(issue["kind"] == "provisional" and issue["status"] == "open" for issue in committed["issues"]))
        self.assertNotIn("accepted", receipt)

    def test_new_operation_with_old_base_is_rejected_after_commit(self):
        req, report = self.propose([transform(self.value, self.value["assemblies"][0]["id"])])
        transactions.commit_candidate(self.root, req["operation_id"], report["candidate_id"], validator=good_validator)
        stale = request(self.value, [transform(self.value, self.value["assemblies"][0]["id"])])
        with self.assertRaisesRegex(transactions.TransactionError, "stale base"):
            transactions.propose_edit(self.root, stale, validator=good_validator)

    def test_modified_candidate_report_and_stale_evaluation_block_commit(self):
        req, report = self.propose([transform(self.value, self.value["assemblies"][0]["id"])])
        candidate_path = self.root / "operations" / req["operation_id"] / "candidate/design.json"
        candidate_path.write_text(candidate_path.read_text() + " ")
        with self.assertRaisesRegex(transactions.TransactionError, "bytes changed"):
            transactions.commit_candidate(self.root, req["operation_id"], report["candidate_id"], validator=good_validator)

    def test_tampered_report_or_saved_evaluation_cannot_reuse_eligibility(self):
        req, report = self.propose([transform(self.value, self.value["assemblies"][0]["id"])])
        opdir = self.root / "operations" / req["operation_id"]
        report_path = opdir / "report.json"; value = design.read_json(report_path); value["commit_eligible"] = False
        report_path.write_text(design._json_text(value))
        with self.assertRaisesRegex(transactions.TransactionError, "report changed"):
            transactions.commit_candidate(self.root, req["operation_id"], report["candidate_id"], validator=good_validator)

        root2 = Path(self.temp.name) / "tampered-eval"; revisions.initialize(root2, self.value)
        req2 = request(self.value, [transform(self.value, self.value["assemblies"][0]["id"])])
        report2 = transactions.propose_edit(root2, req2, validator=good_validator)
        validation_path = root2 / "operations" / req2["operation_id"] / "candidate-validation.json"
        validation = design.read_json(validation_path); validation["evaluation"]["raw_passed"] = False
        validation_path.write_text(design._json_text(validation))
        with self.assertRaisesRegex(transactions.TransactionError, "evaluation evidence changed"):
            transactions.commit_candidate(root2, req2["operation_id"], report2["candidate_id"], validator=good_validator)

    def test_checker_exception_and_unknown_data_identity_block_commit(self):
        req = request(self.value, [transform(self.value, self.value["assemblies"][0]["id"])])
        report = transactions.propose_edit(self.root, req, validator=lambda path, ground: (_ for _ in ()).throw(RuntimeError("checker unavailable")))
        self.assertFalse(report["commit_eligible"])
        self.assertTrue(any(r["code"] == "base_validation_unavailable" for r in report["policy"]["reasons"]))
        root2 = Path(self.temp.name) / "no-data-id"; revisions.initialize(root2, self.value)
        with patch("bricksmith.workbench.transactions._data_identity", return_value=None):
            req2 = request(self.value, [transform(self.value, self.value["assemblies"][0]["id"])])
            report2 = transactions.propose_edit(root2, req2, validator=good_validator)
        self.assertFalse(report2["commit_eligible"])
        self.assertIn("checker_data_identity_unavailable", [r["code"] for r in report2["policy"]["reasons"]])

    def test_valid_provisional_repair_and_offender_identity_policy(self):
        def ev(checks, pairs=(), below=(), complete=True, missing_base=None):
            actual = {k: checks.get(k, True) for k in transactions.CHECKS}
            if pairs: actual["mesh_collision_free"] = False
            if below: actual["no_parts_below_ground"] = False
            return {"available": True, "checks": actual,
                "collision_pairs": [list(x) for x in pairs], "below_ground_part_ids": list(below),
                "below_ground_complete": complete, "missing_base": not checks.get("included_base", True),
                "identity_mapping_complete": True, "evidence_complete": complete}
        passed = {key: True for key in transactions.CHECKS}
        provisional = dict(passed, actual_connectivity=False)
        self.assertEqual(transactions._policy(ev(passed), ev(provisional), [])['status'], "provisional")
        self.assertEqual(transactions._policy(ev(passed, [("a", "b"), ("c", "d")]), ev(passed, [("a", "b")]), [])['status'], "repair_incomplete")
        self.assertFalse(transactions._policy(ev(passed, [("a", "b")]), ev(passed, [("c", "d")]), [])["commit_eligible"])
        self.assertFalse(transactions._policy(ev(passed, below=["a"]), ev(passed, below=["b"]), [])["commit_eligible"])
        self.assertFalse(transactions._policy(ev(passed), ev(passed, complete=False), [])["commit_eligible"])
        self.assertFalse(transactions._policy({"available": False, "exception": "RuntimeError"}, ev(passed), [])["commit_eligible"])
        self.assertFalse(transactions._interpret_report({"checks": {key: None for key in transactions.CHECKS}}, [])["available"])
        base_missing = dict(passed, included_base=False)
        self.assertEqual(transactions._policy(ev(base_missing), ev(passed), [])["status"], "construction_passed")
        self.assertFalse(transactions._policy(ev(base_missing), ev(base_missing), [])["commit_eligible"])

    def test_complete_below_ground_mapping_exceeds_legacy_sample(self):
        value = make_design(40)
        build, placements = design._export_text(value)
        below = list(range(35))
        raw = {"passed": False, "checks": {key: True for key in transactions.CHECKS},
            "errors": [{"kind": "parts_below_ground", "count": 35, "part_indices": below[:30]}],
            "diagnostics": {"below_ground_indices_complete_flag": True,
                            "below_ground_indices_complete": below}}
        raw["checks"]["no_parts_below_ground"] = False
        result = transactions._interpret_report(raw, placements)
        expected = {placements[i]["part_id"] for i in below}
        self.assertTrue(result["evidence_complete"])
        self.assertEqual(set(result["below_ground_part_ids"]), expected)

    def test_large_selection_over_30_placements_is_atomic(self):
        many = make_design(40); root = Path(self.temp.name) / "many"; revisions.initialize(root, many)
        req = request(many, [transform(many, many["assemblies"][0]["id"])])
        report = transactions.propose_edit(root, req, validator=good_validator)
        self.assertEqual(report["affected_count"], 40)
        old = revisions.read_state(root)["current_revision_id"]
        script = r'''
import os,sys
from pathlib import Path
from bricksmith.workbench import transactions
transactions._data_identity=lambda: "a"*64
def val(path,ground): return {"passed":True,"checks":{k:True for k in transactions.CHECKS},"errors":[],"diagnostics":{"below_ground_indices_complete_flag":True,"below_ground_indices_complete":[]}}
transactions.commit_candidate(Path(sys.argv[1]),sys.argv[2],sys.argv[3],validator=val,
 failpoint=lambda p: os._exit(83) if p=="after_seal_before_pointer" else None)
'''
        child = subprocess.run([sys.executable, "-c", script, str(root), req["operation_id"], report["candidate_id"]], cwd=ROOT)
        self.assertEqual(child.returncode, 83)
        self.assertEqual(revisions.read_state(root)["current_revision_id"], old)
        receipt = transactions.commit_candidate(root, req["operation_id"], report["candidate_id"], validator=good_validator)
        moved = revisions.load_revision(root, receipt["revision_id"])
        self.assertEqual(len([p for p in moved["parts"] if p["translation_ldu"][0] >= 20]), 40)

    def test_new_parts_can_be_selected_by_explicit_id_later_in_same_request(self):
        part = copy.deepcopy(self.value["parts"][0]); part["id"] = uid()
        req = request(self.value, [{"type": "add_part", "part": part},
            {"type": "transform", "selector": {"part_ids": [part["id"]]},
             "rotation": [[1,0,0],[0,1,0],[0,0,1]], "translation_ldu": [3,0,0], "pivot_ldu": [0,0,0]}])
        transactions.propose_edit(self.root, req, validator=good_validator)
        candidate = design.read_json(self.root / "operations" / req["operation_id"] / "candidate/design.json")
        created = next(p for p in candidate["parts"] if p["id"] == part["id"])
        self.assertEqual(created["translation_ldu"][0], Decimal("3"))

    def test_assembly_metadata_deletion_and_issue_ledger_operations(self):
        retained = {"id": uid(), "name": "Temporary group", "role": None, "parent_assembly_id": None,
            "design_properties": {}, "relationships": [], "field_locks": []}
        doomed = {"id": uid(), "name": "Empty group", "role": None, "parent_assembly_id": None,
            "design_properties": {}, "relationships": [], "field_locks": []}
        issue_id = uid()
        ops = [{"type": "create_assembly", "assembly": retained},
            {"type": "update_assembly", "assembly_id": retained["id"], "fields": {"name": "Renamed group"}},
            {"type": "create_assembly", "assembly": doomed},
            {"type": "delete_assembly", "assembly_id": doomed["id"], "delete_descendants": False},
            {"type": "upsert_issue", "issue_id": issue_id, "kind": "support_review",
             "status": "open", "affected_ids": [self.value["parts"][0]["id"]],
             "next_proposed_action": "inspect the support"}]
        req = request(self.value, ops)
        transactions.propose_edit(self.root, req, validator=good_validator)
        candidate = design.read_json(self.root / "operations" / req["operation_id"] / "candidate/design.json")
        self.assertNotIn(doomed["id"], {a["id"] for a in candidate["assemblies"]})
        self.assertEqual(next(a for a in candidate["assemblies"] if a["id"] == retained["id"])["name"], "Renamed group")
        issue = next(issue for issue in candidate["issues"] if issue["id"] == issue_id)
        self.assertEqual(issue["attempted_operation_ids"], [req["operation_id"]])
        self.assertEqual(issue["first_observation_revision_id"], candidate["revision_id"])


class CrashRecoveryTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64)
        patcher.start(); self.addCleanup(patcher.stop)

    def test_process_termination_after_pointer_recovers_new_revision_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            patcher = patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64)
            patcher.start(); self.addCleanup(patcher.stop)
            root = Path(tmp) / "session"; value = make_design(); revisions.initialize(root, value)
            req = request(value, [transform(value, value["assemblies"][0]["id"])])
            report = transactions.propose_edit(root, req, validator=good_validator)
            script = r'''
import os,sys
from pathlib import Path
from bricksmith.workbench import transactions
transactions._data_identity=lambda: "a"*64
def val(path,ground):
 return {"passed":True,"checks":{k:True for k in transactions.CHECKS},"errors":[],"diagnostics":{"below_ground_indices_complete_flag":True,"below_ground_indices_complete":[]}}
transactions.commit_candidate(Path(sys.argv[1]),sys.argv[2],sys.argv[3],validator=val,
 failpoint=lambda p: os._exit(87) if p=="after_pointer_commit" else None)
'''
            child = subprocess.run([sys.executable, "-c", script, str(root), req["operation_id"], report["candidate_id"]], cwd=ROOT)
            self.assertEqual(child.returncode, 87)
            state = revisions.read_state(root)
            self.assertEqual(state["current_revision_id"], report["candidate_id"])
            self.assertEqual(state["receipts"][req["operation_id"]]["disposition"], "committed")
            recovered = transactions.recover(root)
            self.assertTrue((root / "build.ldr").is_file())
            self.assertEqual(recovered["current_revision_id"], report["candidate_id"])
            self.assertEqual(len(list((root / "events").glob("*.json"))), 1)
            transactions.recover(root)
            self.assertEqual(len(list((root / "events").glob("*.json"))), 1)

    def test_process_death_matrix_at_pre_and_post_commit_failpoints(self):
        proposal_script = r'''
import json,os,sys
from pathlib import Path
from bricksmith.workbench import transactions
transactions._data_identity=lambda: "a"*64
from bricksmith.workbench.design import read_json
def val(path,ground): return {"passed":True,"checks":{k:True for k in transactions.CHECKS},"errors":[],"diagnostics":{"below_ground_indices_complete_flag":True,"below_ground_indices_complete":[]}}
request=read_json(Path(sys.argv[2]))
transactions.propose_edit(Path(sys.argv[1]),request,validator=val,
 failpoint=lambda p: os._exit(70) if p==sys.argv[3] else None)
'''
        commit_script = r'''
import os,sys
from pathlib import Path
from bricksmith.workbench import transactions
transactions._data_identity=lambda: "a"*64
def val(path,ground): return {"passed":True,"checks":{k:True for k in transactions.CHECKS},"errors":[],"diagnostics":{"below_ground_indices_complete_flag":True,"below_ground_indices_complete":[]}}
transactions.commit_candidate(Path(sys.argv[1]),sys.argv[2],sys.argv[3],validator=val,
 failpoint=lambda p: os._exit(71) if p==sys.argv[4] else None)
'''
        for point in ("before_intent_flush", "after_intent_flush", "during_candidate_writes", "before_report_flush",
                      "after_report_flush", "before_candidate_receipt_flush", "after_candidate_receipt_flush",
                      "after_candidate_seal_before_pointer"):
            with self.subTest(point=point), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "session"; value = make_design(); revisions.initialize(root, value)
                req = request(value, [transform(value, value["assemblies"][0]["id"])])
                req_path = Path(tmp) / "request.json"; req_path.write_text(design._json_text(req))

                child = subprocess.run([sys.executable, "-c", proposal_script, str(root), str(req_path), point], cwd=ROOT)
                self.assertEqual(child.returncode, 70)
                recovered = transactions.recover(root)
                self.assertEqual(recovered["current_revision_id"], value["revision_id"])
                self.assertNotIn(req["operation_id"], revisions.read_state(root)["receipts"])
                if point == "before_intent_flush": self.assertIn(f"removed_empty_staging:{req['operation_id']}", recovered["repaired"])
                elif point in {"after_candidate_receipt_flush", "after_candidate_seal_before_pointer"}:
                    self.assertIn(req["operation_id"], recovered["uncommitted_operations"])
                    inspected = transactions.inspect_candidate(root, req["operation_id"])
                    retry = transactions.propose_edit(root, req, validator=good_validator)
                    self.assertEqual(retry["candidate_id"], inspected["candidate_id"])
                    self.assertEqual(transactions.discard_candidate(root, req["operation_id"])["disposition"], "discarded")
                    self.assertEqual(transactions.recover(root)["aborted_operations"], [])
                else:
                    self.assertIn(req["operation_id"], recovered["aborted_operations"])
                    terminal = transactions.inspect_candidate(root, req["operation_id"])
                    self.assertEqual(terminal["disposition"], "aborted")
                    self.assertEqual(transactions.propose_edit(root, req, validator=good_validator)["disposition"], "aborted")
                    self.assertEqual(transactions.discard_candidate(root, req["operation_id"])["disposition"], "aborted")
                    with self.assertRaisesRegex(transactions.TransactionError, "aborted"):
                        transactions.commit_candidate(root, req["operation_id"], uid(), validator=good_validator)

        for point in ("after_seal_before_pointer", "after_pointer_commit", "during_event_finalization", "during_compatibility_export"):
            with self.subTest(point=point), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "session"; value = make_design(); revisions.initialize(root, value)
                req = request(value, [transform(value, value["assemblies"][0]["id"])])
                proposal = transactions.propose_edit(root, req, validator=good_validator)
                child = subprocess.run([sys.executable, "-c", commit_script, str(root), req["operation_id"], proposal["candidate_id"], point], cwd=ROOT)
                self.assertEqual(child.returncode, 71)
                recovered = transactions.recover(root); state = revisions.read_state(root)
                if point == "after_seal_before_pointer":
                    self.assertEqual(state["current_revision_id"], value["revision_id"])
                    self.assertIn(proposal["candidate_id"], recovered["orphan_revisions"])
                    inspected = transactions.inspect_candidate(root, req["operation_id"])
                    self.assertEqual(transactions.propose_edit(root, req, validator=good_validator)["candidate_id"], inspected["candidate_id"])
                    committed = transactions.commit_candidate(root, req["operation_id"], proposal["candidate_id"], validator=good_validator)
                else:
                    self.assertEqual(state["current_revision_id"], proposal["candidate_id"])
                    self.assertEqual(state["receipts"][req["operation_id"]]["disposition"], "committed")
                    self.assertEqual(len(list((root / "events").glob("*.json"))), 1)
                    self.assertEqual((root / "build.ldr").read_bytes(),
                        (root / "revisions" / proposal["candidate_id"] / "build.ldr").read_bytes())
                    committed = transactions.inspect_candidate(root, req["operation_id"])
                    self.assertEqual(transactions.propose_edit(root, req, validator=good_validator)["candidate_id"], proposal["candidate_id"])
                    self.assertEqual(transactions.commit_candidate(root, req["operation_id"], proposal["candidate_id"], validator=good_validator), committed)
                self.assertEqual(transactions.discard_candidate(root, req["operation_id"])["disposition"], "committed")
                self.assertEqual(transactions.recover(root)["repaired"], [])

    def test_process_death_releases_exclusive_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "session"; revisions.initialize(root, make_design())
            script = r'''
import os,sys,time
from pathlib import Path
from bricksmith.workbench.revisions import writer_lock
with writer_lock(Path(sys.argv[1])): os._exit(86)
'''
            child = subprocess.run([sys.executable, "-c", script, str(root)], cwd=ROOT)
            self.assertEqual(child.returncode, 86)
            with revisions.writer_lock(root): pass

    def test_real_writers_race_for_lock_and_same_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "session"; value = make_design(); revisions.initialize(root, value)
            marker = Path(tmp) / "locked"; release = Path(tmp) / "release"
            holder_script = r'''
import sys,time
from pathlib import Path
from bricksmith.workbench.revisions import writer_lock
root=Path(sys.argv[1]); marker=Path(sys.argv[2]); release=Path(sys.argv[3])
with writer_lock(root):
 marker.write_text("locked")
 while not release.exists(): time.sleep(.01)
'''
            holder = subprocess.Popen([sys.executable, "-c", holder_script, str(root), str(marker), str(release)], cwd=ROOT)
            import time
            deadline = time.time() + 10
            while not marker.exists() and time.time() < deadline: time.sleep(.01)
            self.assertTrue(marker.exists())
            with self.assertRaisesRegex(revisions.RevisionError, "Another transaction writer"):
                with revisions.writer_lock(root): pass
            release.write_text("go"); self.assertEqual(holder.wait(timeout=10), 0)

            reqs = [request(value, [transform(value, value["assemblies"][0]["id"])]) for _ in range(2)]
            reports = [transactions.propose_edit(root, req, validator=good_validator) for req in reqs]
            commit_script = r'''
import sys
from pathlib import Path
from bricksmith.workbench import transactions
transactions._data_identity=lambda: "a"*64
def val(path,ground): return {"passed":True,"checks":{k:True for k in transactions.CHECKS},"errors":[],"diagnostics":{"below_ground_indices_complete_flag":True,"below_ground_indices_complete":[]}}
transactions.commit_candidate(Path(sys.argv[1]),sys.argv[2],sys.argv[3],validator=val)
'''
            processes = [subprocess.Popen([sys.executable, "-c", commit_script, str(root), req["operation_id"], report["candidate_id"]],
                cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for req, report in zip(reqs, reports)]
            outcomes = [process.communicate(timeout=40) + (process.returncode,) for process in processes]
            codes = sorted(item[2] for item in outcomes)
            self.assertEqual(codes, [0, 1])
            winner = revisions.read_state(root)["current_revision_id"]
            self.assertIn(winner, {report["candidate_id"] for report in reports})


if __name__ == "__main__": unittest.main()
