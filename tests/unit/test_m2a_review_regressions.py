from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from bricksmith.workbench import design, revisions, transactions, provenance
from tests.unit.test_transactions import ROOT, good_validator, make_design, request, transform, uid


class M2AReviewRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "session"
        self.value = make_design()
        revisions.initialize(self.root, self.value)
        self.data_patch = patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64)
        self.data_patch.start(); self.addCleanup(self.data_patch.stop)

    def _propose(self, root, value, operations, validator=good_validator):
        req = request(value, operations)
        return req, transactions.propose_edit(root, req, validator=validator)

    def _clone(self, value, part_id=None, assembly_id=None):
        part_id = part_id or value["parts"][0]["id"]
        assembly_id = assembly_id or value["assemblies"][0]["id"]
        return {"type": "clone_assemblies", "assembly_ids": [assembly_id],
            "assembly_id_map": {assembly_id: uid()}, "part_id_map": {part_id: uid()},
            "translation_ldu": [100, 0, 0]}

    def test_r1_lock_holder_deletion_and_direct_target_deletion_are_blocked(self):
        value = copy.deepcopy(self.value); part = value["parts"][0]
        holder = copy.deepcopy(value["assemblies"][0]); holder["id"] = uid(); holder["name"] = "empty holder"
        holder["field_locks"] = [{"id": uid(), "owner": "user", "target_id": part["id"], "fields": ["translation_ldu"]}]
        value["assemblies"].append(holder); design.refresh_hashes(value); design.validate_design(value)
        root = Path(self.temp.name) / "lock-holder"; revisions.initialize(root, value)
        req, report = self._propose(root, value, [{"type": "delete_assembly", "assembly_id": holder["id"], "delete_descendants": False}])
        self.assertFalse(report["commit_eligible"])
        self.assertTrue(any(c["reason"] == "user lock identity or protective semantics changed" for c in report["policy_conflicts"]))
        with self.assertRaises(transactions.TransactionError): transactions.commit_candidate(root, req["operation_id"], report["candidate_id"], validator=good_validator)
        state, current = revisions.current_revision(root)
        self.assertEqual(state["current_revision_id"], value["revision_id"])
        self.assertIn(holder["field_locks"][0], next(a for a in current["assemblies"] if a["id"] == holder["id"])["field_locks"])
        bypass, rejected = self._propose(root, value, [transform(value, value["assemblies"][0]["id"])])
        self.assertFalse(rejected["commit_eligible"])
        self.assertEqual(revisions.read_state(root)["current_revision_id"], value["revision_id"])

        target_root = Path(self.temp.name) / "lock-target"; revisions.initialize(target_root, value)
        direct = request(value, [{"type": "delete", "selector": {"part_ids": [part["id"]]}}])
        failure = transactions.propose_edit(target_root, direct, validator=good_validator)
        self.assertEqual(failure["status"], "failure")
        with self.assertRaisesRegex(transactions.TransactionError, "failed operation"):
            transactions.commit_candidate(target_root, direct["operation_id"], uid(), validator=good_validator)
        self.assertEqual(revisions.read_state(target_root)["current_revision_id"], value["revision_id"])
        self.assertEqual(next(a for a in revisions.load_revision(target_root, value["revision_id"])["assemblies"] if a["id"] == holder["id"])["field_locks"], holder["field_locks"])

        unrelated_value = make_design(2); locked = unrelated_value["parts"][0]
        empty_holder = copy.deepcopy(unrelated_value["assemblies"][0]); empty_holder["id"] = uid(); empty_holder["name"] = "lock holder"
        empty_holder["field_locks"] = [{"id": uid(), "owner": "user", "target_id": locked["id"], "fields": ["translation_ldu"]}]
        unrelated_value["assemblies"].append(empty_holder); design.refresh_hashes(unrelated_value)
        unrelated_root = Path(self.temp.name) / "unrelated"; revisions.initialize(unrelated_root, unrelated_value)
        other = unrelated_value["parts"][1]["id"]
        op = {"type": "transform", "selector": {"part_ids": [other]}, "rotation": [[1,0,0],[0,1,0],[0,0,1]],
              "translation_ldu": [1,0,0], "pivot_ldu": [0,0,0]}
        _, allowed = self._propose(unrelated_root, unrelated_value, [op])
        self.assertTrue(allowed["commit_eligible"])

        # A lock holder nested under a deleted subtree is also protected.
        subtree_value = copy.deepcopy(value)
        parent = copy.deepcopy(subtree_value["assemblies"][0]); parent["id"] = uid(); parent["name"] = "parent"
        holder_copy = next(a for a in subtree_value["assemblies"] if a["id"] == holder["id"])
        holder_copy["parent_assembly_id"] = parent["id"]; subtree_value["assemblies"].append(parent)
        design.refresh_hashes(subtree_value); design.validate_design(subtree_value)
        subtree_root = Path(self.temp.name) / "subtree-lock"; revisions.initialize(subtree_root, subtree_value)
        _, subtree_report = self._propose(subtree_root, subtree_value, [{"type": "delete_assembly", "assembly_id": parent["id"], "delete_descendants": True}])
        self.assertFalse(subtree_report["commit_eligible"])
        self.assertEqual(revisions.read_state(subtree_root)["current_revision_id"], subtree_value["revision_id"])

        replacement = copy.deepcopy(part); replacement["id"] = uid()
        replace_req = request(value, [{"type": "replace_part", "part_id": part["id"], "replacement": replacement, "retain_id": False}])
        replace_failure = transactions.propose_edit(target_root, replace_req, validator=good_validator)
        self.assertEqual(replace_failure["status"], "failure")

    def test_r2_clone_uses_values_at_its_ordered_position(self):
        part = self.value["parts"][0]; assembly = self.value["assemblies"][0]
        cases = [
            ("transform", transform(self.value, assembly["id"], "20"), {"translation": True}),
            ("recolor", {"type": "recolor", "selector": {"part_ids": [part["id"]]}, "color_id": 71}, {"color": 71}),
            ("retained_replace", {"type": "replace_part", "part_id": part["id"], "replacement": {**copy.deepcopy(part), "color_id": 72}, "retain_id": True}, {"color": 72}),
            ("assembly_update", {"type": "update_assembly", "assembly_id": assembly["id"], "fields": {"name": "Updated"}}, {"name": "Updated copy"}),
        ]
        for label, earlier, expected in cases:
            with self.subTest(label=label):
                root = Path(self.temp.name) / f"ordered-{label}"; revisions.initialize(root, self.value)
                clone = self._clone(self.value); req = request(self.value, [earlier, clone])
                report = transactions.propose_edit(root, req, validator=good_validator)
                self.assertTrue(report["commit_eligible"])
                candidate = design.read_json(root / "operations" / req["operation_id"] / "candidate/design.json")
                cloned = next(p for p in candidate["parts"] if p["id"] == clone["part_id_map"][part["id"]])
                source = next(p for p in candidate["parts"] if p["id"] == part["id"])
                if expected.get("translation"): self.assertEqual(cloned["translation_ldu"][0], source["translation_ldu"][0] + 100)
                if "color" in expected: self.assertEqual(cloned["color_id"], expected["color"])
                self.assertEqual(next(a for a in candidate["assemblies"] if a["id"] == clone["assembly_id_map"][assembly["id"]])["name"], expected.get("name", assembly["name"] + " copy"))
                self.assertEqual(transactions.propose_edit(root, req, validator=good_validator)["candidate_id"], report["candidate_id"])
        deleted_then_cloned = request(self.value, [
            {"type": "delete", "selector": {"part_ids": [part["id"]]}}, self._clone(self.value)])
        failed = transactions.propose_edit(self.root, deleted_then_cloned, validator=good_validator)
        self.assertEqual(failed["status"], "failure")
        invalid = design.read_json(self.root / "operations" / deleted_then_cloned["operation_id"] / "candidate/invalid-design.json")
        self.assertNotIn(part["id"], {p["id"] for p in invalid["parts"]})

    def test_r3_deleted_ids_are_not_reused_after_reopen_or_recovery(self):
        part = copy.deepcopy(self.value["parts"][0]); part_id = part["id"]
        same_category = {"id": part_id, "name": "cross-category collision", "role": None, "parent_assembly_id": None,
            "design_properties": {}, "relationships": [], "field_locks": []}
        cross = transactions.propose_edit(self.root, request(self.value, [{"type": "create_assembly", "assembly": same_category}]), validator=good_validator)
        self.assertEqual(cross["status"], "failure"); self.assertIn("already been used", cross["error"])
        part_with_assembly_id = copy.deepcopy(part); part_with_assembly_id["id"] = self.value["assemblies"][0]["id"]
        other_cross = transactions.propose_edit(self.root, request(self.value, [{"type": "add_part", "part": part_with_assembly_id}]), validator=good_validator)
        self.assertEqual(other_cross["status"], "failure"); self.assertIn("already been used", other_cross["error"])
        deletion, proposed = self._propose(self.root, self.value, [{"type": "delete", "selector": {"part_ids": [part_id]}}])
        deleted = transactions.commit_candidate(self.root, deletion["operation_id"], proposed["candidate_id"], validator=good_validator)
        _, current = revisions.current_revision(self.root)
        reuse = request(current, [{"type": "add_part", "part": part}])
        request_path = Path(self.temp.name) / "reuse-part.json"; request_path.write_text(design._json_text(reuse))
        script = r'''
import json,sys
from pathlib import Path
from bricksmith.workbench import transactions
transactions._data_identity=lambda: "a"*64
def val(path,ground): return {"passed":True,"checks":{k:True for k in transactions.CHECKS},"errors":[],"diagnostics":{"below_ground_indices_complete_flag":True,"below_ground_indices_complete":[]}}
print(transactions.propose_edit(Path(sys.argv[1]),json.loads(Path(sys.argv[2]).read_text()),validator=val)["status"])
'''
        child = subprocess.run([sys.executable, "-c", script, str(self.root), str(request_path)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr); self.assertIn("failure", child.stdout)
        self.assertIn("already been used", child.stdout + (self.root / "operations" / reuse["operation_id"] / "failure.json").read_text())

        # Historical assembly identity is reserved even after a later deletion.
        after_delete = revisions.load_revision(self.root, deleted["revision_id"])
        assembly = {"id": uid(), "name": "historical", "role": None, "parent_assembly_id": None,
                    "design_properties": {}, "relationships": [], "field_locks": []}
        create, create_report = self._propose(self.root, after_delete, [{"type": "create_assembly", "assembly": assembly}])
        created = transactions.commit_candidate(self.root, create["operation_id"], create_report["candidate_id"], validator=good_validator)
        after_create = revisions.load_revision(self.root, created["revision_id"])
        delete_asm, delete_report = self._propose(self.root, after_create, [{"type": "delete_assembly", "assembly_id": assembly["id"], "delete_descendants": False}])
        removed = transactions.commit_candidate(self.root, delete_asm["operation_id"], delete_report["candidate_id"], validator=good_validator)
        after_removal = revisions.load_revision(self.root, removed["revision_id"])
        reused_assembly, result = self._propose(self.root, after_removal, [{"type": "create_assembly", "assembly": assembly}])
        self.assertEqual(result["status"], "failure"); self.assertIn("already been used", result["error"])
        transient = {"id": uid(), "name": "transient", "role": None, "parent_assembly_id": None,
                     "design_properties": {}, "relationships": [], "field_locks": []}
        same_request = request(after_removal, [{"type": "create_assembly", "assembly": transient},
            {"type": "delete_assembly", "assembly_id": transient["id"], "delete_descendants": False},
            {"type": "create_assembly", "assembly": transient}])
        create_delete_create = transactions.propose_edit(self.root, same_request, validator=good_validator)
        self.assertEqual(create_delete_create["status"], "failure")
        self.assertIn("already been used", create_delete_create["error"])

        fresh_part = copy.deepcopy(part); fresh_part["id"] = uid()
        current_state, current = revisions.current_revision(self.root)
        publish_req, publish_report = self._propose(self.root, current, [{"type": "add_part", "part": fresh_part}])
        commit_script = r'''
import os,sys
from pathlib import Path
from bricksmith.workbench import transactions
transactions._data_identity=lambda: "a"*64
def val(path,ground): return {"passed":True,"checks":{k:True for k in transactions.CHECKS},"errors":[],"diagnostics":{"below_ground_indices_complete_flag":True,"below_ground_indices_complete":[]}}
transactions.commit_candidate(Path(sys.argv[1]),sys.argv[2],sys.argv[3],validator=val,failpoint=lambda p: os._exit(81) if p=="after_pointer_commit" else None)
'''
        child = subprocess.run([sys.executable, "-c", commit_script, str(self.root), publish_req["operation_id"], publish_report["candidate_id"]], cwd=ROOT)
        self.assertEqual(child.returncode, 81)
        self.assertEqual(revisions.read_state(self.root)["current_revision_id"], publish_report["candidate_id"])
        transactions.recover(self.root)
        reopened = revisions.load_revision(self.root, publish_report["candidate_id"])
        reuse_after_recovery = request(reopened, [{"type": "add_part", "part": fresh_part}])
        failed = transactions.propose_edit(self.root, reuse_after_recovery, validator=good_validator)
        self.assertEqual(failed["status"], "failure"); self.assertIn("already been used", failed["error"])

    def test_r3a_committed_transient_and_nested_ids_remain_reserved(self):
        transient = {"id": uid(), "name": "transient committed", "role": None, "parent_assembly_id": None,
            "design_properties": {}, "relationships": [], "field_locks": []}
        req = request(self.value, [{"type": "create_assembly", "assembly": transient},
            {"type": "delete_assembly", "assembly_id": transient["id"], "delete_descendants": False}])
        report = transactions.propose_edit(self.root, req, validator=good_validator)
        receipt = transactions.commit_candidate(self.root, req["operation_id"], report["candidate_id"], validator=good_validator)
        self.assertIn(transient["id"], design.read_json(self.root / "operations" / req["operation_id"] / "report.json")["allocated_entity_ids"])
        current = revisions.load_revision(self.root, receipt["revision_id"])
        reuse = transactions.propose_edit(self.root, request(current, [{"type": "create_assembly", "assembly": transient}]), validator=good_validator)
        self.assertEqual(reuse["status"], "failure")

        transient_part = copy.deepcopy(current["parts"][0]); transient_part["id"] = uid()
        part_lifecycle = request(current, [{"type": "add_part", "part": transient_part},
            {"type": "delete", "selector": {"part_ids": [transient_part["id"]]}}])
        part_report = transactions.propose_edit(self.root, part_lifecycle, validator=good_validator)
        part_receipt = transactions.commit_candidate(self.root, part_lifecycle["operation_id"], part_report["candidate_id"], validator=good_validator)
        current = revisions.load_revision(self.root, part_receipt["revision_id"])
        part_reuse = transactions.propose_edit(self.root, request(current, [{"type": "add_part", "part": transient_part}]), validator=good_validator)
        self.assertEqual(part_reuse["status"], "failure")

        lock_id = uid(); lock_holder = {"id": uid(), "name": "temporary lock holder", "role": None,
            "parent_assembly_id": None, "design_properties": {}, "relationships": [],
            "field_locks": [{"id": lock_id, "owner": "agent", "target_id": current["parts"][0]["id"], "fields": ["translation_ldu"]}]}
        lock_lifecycle = request(current, [{"type": "create_assembly", "assembly": lock_holder},
            {"type": "delete_assembly", "assembly_id": lock_holder["id"], "delete_descendants": False}])
        lock_report = transactions.propose_edit(self.root, lock_lifecycle, validator=good_validator)
        lock_receipt = transactions.commit_candidate(self.root, lock_lifecycle["operation_id"], lock_report["candidate_id"], validator=good_validator)
        current = revisions.load_revision(self.root, lock_receipt["revision_id"])
        lock_reuse = copy.deepcopy(current["parts"][0]); lock_reuse["id"] = lock_id
        self.assertEqual(transactions.propose_edit(self.root, request(current, [{"type": "add_part", "part": lock_reuse}]), validator=good_validator)["status"], "failure")

        relation_id = uid(); assembly_id = current["assemblies"][0]["id"]
        relation = {"id": relation_id, "kind": "contains", "target_assembly_id": assembly_id, "source": "agent"}
        add_req = request(current, [{"type": "update_assembly", "assembly_id": assembly_id,
            "fields": {"relationships": [relation]}}])
        add = transactions.propose_edit(self.root, add_req, validator=good_validator)
        added = transactions.commit_candidate(self.root, add_req["operation_id"], add["candidate_id"], validator=good_validator)
        after_add = revisions.load_revision(self.root, added["revision_id"])
        retained_req = request(after_add, [{"type": "update_assembly", "assembly_id": assembly_id,
            "fields": {"relationships": [{**relation, "kind": "supports"}]}}])
        retained = transactions.propose_edit(self.root, retained_req, validator=good_validator)
        retained_receipt = transactions.commit_candidate(self.root, retained_req["operation_id"], retained["candidate_id"], validator=good_validator)
        after_add = revisions.load_revision(self.root, retained_receipt["revision_id"])
        remove_req = request(after_add, [{"type": "update_assembly", "assembly_id": assembly_id, "fields": {"relationships": []}}])
        remove = transactions.propose_edit(self.root, remove_req, validator=good_validator)
        removed = transactions.commit_candidate(self.root, remove_req["operation_id"], remove["candidate_id"], validator=good_validator)
        after_remove = revisions.load_revision(self.root, removed["revision_id"])
        reused_part = copy.deepcopy(after_remove["parts"][0]); reused_part["id"] = relation_id
        collision = transactions.propose_edit(self.root, request(after_remove, [{"type": "add_part", "part": reused_part}]), validator=good_validator)
        self.assertEqual(collision["status"], "failure")

    def test_r5a_recovery_resumes_after_preservation_and_failure_record(self):
        for point in ("after_interrupted_receipt_preserved", "after_interrupted_failure_record"):
            with self.subTest(point=point):
                root = Path(self.temp.name) / f"recover-{point}"; value = make_design(); revisions.initialize(root, value)
                req = request(value, [transform(value, value["assemblies"][0]["id"])])
                report = transactions.propose_edit(root, req, validator=good_validator)
                candidate_path = root / "operations" / req["operation_id"] / "candidate/design.json"
                candidate_path.write_text("{}\n")
                state_before = revisions.read_state(root)["current_revision_id"]
                script = r'''import os,sys
from pathlib import Path
from bricksmith.workbench import transactions
transactions.recover(Path(sys.argv[1]), failpoint=lambda p: os._exit(87) if p==sys.argv[2] else None)
'''
                child = subprocess.run([sys.executable, "-c", script, str(root), point], cwd=ROOT)
                self.assertEqual(child.returncode, 87)
                first = transactions.recover(root)
                self.assertIn(req["operation_id"], first["aborted_operations"])
                terminal = transactions.inspect_candidate(root, req["operation_id"])
                self.assertEqual(terminal["disposition"], "aborted")
                self.assertEqual(revisions.read_state(root)["current_revision_id"], state_before)
                self.assertEqual(transactions.recover(root)["repaired"], [])
                self.assertEqual(transactions.propose_edit(root, req, validator=good_validator)["disposition"], "aborted")
                self.assertEqual(transactions.discard_candidate(root, req["operation_id"])["disposition"], "aborted")

    def test_r5a_mismatched_preserved_receipt_fails_closed(self):
        root = Path(self.temp.name) / "recover-mismatch"; value = make_design(); revisions.initialize(root, value)
        req = request(value, [transform(value, value["assemblies"][0]["id"])])
        transactions.propose_edit(root, req, validator=good_validator)
        opdir = root / "operations" / req["operation_id"]
        (opdir / "candidate/design.json").write_text("{}\n")
        with self.assertRaisesRegex(RuntimeError, "interrupt"):
            transactions.recover(root, failpoint=lambda point: (_ for _ in ()).throw(RuntimeError("interrupt"))
                if point == "after_interrupted_receipt_preserved" else None)
        preserved = opdir / "interrupted-candidate-receipt.json"
        preserved.write_text(preserved.read_text() + " ")
        with self.assertRaisesRegex(transactions.TransactionError, "does not match original"):
            transactions.recover(root)

    def test_r4_deletion_repairs_keep_live_issues_valid_and_status_provisional(self):
        value = make_design(2); root = Path(self.temp.name) / "provisional-delete"; revisions.initialize(root, value)
        deleted_id = value["parts"][1]["id"]
        def checker(path, ground):
            n = sum(line.startswith("1 ") for line in Path(path).read_text().splitlines())
            checks = {key: True for key in transactions.CHECKS}
            if n == 1: checks["actual_connectivity"] = False
            return {"passed": all(checks.values()), "checks": checks, "errors": [],
                    "diagnostics": {"below_ground_indices_complete_flag": True, "below_ground_indices_complete": []}}
        req, report = self._propose(root, value, [{"type": "delete", "selector": {"part_ids": [deleted_id]}}], checker)
        inspected = transactions.inspect_candidate(root, req["operation_id"])
        candidate = design.read_json(root / "operations" / req["operation_id"] / "candidate/design.json")
        issue = next(i for i in candidate["issues"] if i["kind"] == "provisional")
        self.assertEqual(report["status"], "provisional"); self.assertIn(deleted_id, inspected["deleted_ids"])
        self.assertNotIn(deleted_id, issue["affected_ids"]); self.assertIn(req["operation_id"], issue["attempted_operation_ids"])
        receipt = transactions.commit_candidate(root, req["operation_id"], report["candidate_id"], validator=checker)
        loaded = revisions.load_revision(root, receipt["revision_id"])
        self.assertEqual(receipt["construction_status"], "provisional")
        self.assertEqual(next(i for i in loaded["issues"] if i["id"] == issue["id"])["status"], "open")

        repair_root = Path(self.temp.name) / "repair-delete"; base = make_design(2); revisions.initialize(repair_root, base)
        export_order = design._export_text(base)[1]
        ids = [record["part_id"] for record in export_order]
        def repair_checker(path, ground):
            n = sum(line.startswith("1 ") for line in Path(path).read_text().splitlines())
            checks = {key: True for key in transactions.CHECKS}; checks["no_parts_below_ground"] = False
            errors = [{"kind": "parts_below_ground", "count": 1, "part_indices": [0]}]
            if n == 2:
                checks["mesh_collision_free"] = False
                errors.insert(0, {"kind": "mesh_collision", "count": 1, "pairs": [[0,1]]})
            return {"passed": False, "checks": checks, "errors": errors,
                "diagnostics": {"below_ground_indices_complete_flag": True, "below_ground_indices_complete": [0]}}
        repair_req, repair_report = self._propose(repair_root, base, [{"type": "delete", "selector": {"part_ids": [ids[1]]}}], repair_checker)
        self.assertEqual(repair_report["status"], "repair_incomplete")
        repair_candidate = design.read_json(repair_root / "operations" / repair_req["operation_id"] / "candidate/design.json")
        repair_issue = next(i for i in repair_candidate["issues"] if i["kind"] == "repair_incomplete")
        self.assertNotIn(ids[1], repair_issue["affected_ids"])
        repair_receipt = transactions.commit_candidate(repair_root, repair_req["operation_id"], repair_report["candidate_id"], validator=repair_checker)
        self.assertEqual(repair_receipt["construction_status"], "repair_incomplete")
        self.assertEqual(next(i for i in revisions.load_revision(repair_root, repair_receipt["revision_id"])["issues"] if i["id"] == repair_issue["id"])["status"], "open")

    def test_r4_existing_dangling_issue_requires_explicit_upsert(self):
        value = copy.deepcopy(self.value); part_id = value["parts"][0]["id"]; issue_id = uid()
        value["issues"].append({"id": issue_id, "kind": "repair", "status": "open", "affected_ids": [part_id],
            "evidence_reference_ids": [], "first_observation_revision_id": value["revision_id"],
            "last_observation_revision_id": value["revision_id"], "attempted_operation_ids": [], "next_proposed_action": "repair"})
        design.refresh_hashes(value); design.validate_design(value)
        root = Path(self.temp.name) / "existing-issue"; revisions.initialize(root, value)
        delete = {"type": "delete", "selector": {"part_ids": [part_id]}}
        failure = transactions.propose_edit(root, request(value, [delete]), validator=good_validator)
        self.assertEqual(failure["status"], "failure"); self.assertIn("upsert the issue", failure["error"])
        update = {"type": "upsert_issue", "issue_id": issue_id, "kind": "repair", "status": "open", "affected_ids": [],
                  "next_proposed_action": "retain deleted target in operation evidence"}
        req = request(value, [delete, update]); report = transactions.propose_edit(root, req, validator=good_validator)
        self.assertTrue(report["commit_eligible"])
        candidate = design.read_json(root / "operations" / req["operation_id"] / "candidate/design.json")
        self.assertEqual(next(i for i in candidate["issues"] if i["id"] == issue_id)["affected_ids"], [])

    def test_r6_all_operation_required_shapes_fail_before_intent(self):
        assembly = self.value["assemblies"][0]; part = self.value["parts"][0]
        complete_assembly = {"id": uid(), "name": "A", "role": None, "parent_assembly_id": None,
            "design_properties": {}, "relationships": [], "field_locks": []}
        clone = self._clone(self.value)
        valid_ops = [
            {"type": "add_part", "part": copy.deepcopy(part)},
            {"type": "replace_part", "part_id": part["id"], "replacement": copy.deepcopy(part), "retain_id": True},
            {"type": "delete", "selector": {"part_ids": [part["id"]]}},
            transform(self.value, assembly["id"]),
            {"type": "recolor", "selector": {"part_ids": [part["id"]]}, "color_id": 71},
            clone,
            {"type": "create_assembly", "assembly": complete_assembly},
            {"type": "update_assembly", "assembly_id": assembly["id"], "fields": {"name": "Renamed"}},
            {"type": "set_membership", "part_ids": [part["id"]], "assembly_id": assembly["id"]},
            {"type": "delete_assembly", "assembly_id": assembly["id"], "delete_descendants": False},
            {"type": "upsert_issue", "issue_id": uid(), "kind": "repair", "status": "open", "affected_ids": [], "next_proposed_action": "repair"},
        ]
        required = {"add_part": "part", "replace_part": "retain_id", "delete": "selector", "transform": "rotation",
            "recolor": "color_id", "clone_assemblies": "translation_ldu", "create_assembly": "assembly",
            "update_assembly": "fields", "set_membership": "assembly_id", "delete_assembly": "delete_descendants",
            "upsert_issue": "kind"}
        for good in valid_ops:
            with self.subTest(kind=good["type"]):
                bad = copy.deepcopy(good); bad.pop(required[bad["type"]]); op_id = uid()
                req = request(self.value, [bad], opid=op_id)
                with self.assertRaisesRegex(transactions.TransactionError, r"operations\[0\]"):
                    transactions.propose_edit(self.root, req, validator=good_validator)
                self.assertFalse((self.root / "operations" / op_id).exists())
        malformed = [
            {"type": "transform", "selector": {"part_ids": [part["id"]]}},
            {"type": "recolor", "selector": {"part_ids": [part["id"]]}},
            {"type": "upsert_issue", "issue_id": uid(), "kind": "repair", "status": [], "affected_ids": [], "next_proposed_action": "x"},
            {"type": "recolor", "selector": {"part_ids": [part["id"]]}, "color_id": True},
            {"type": "delete_assembly", "assembly_id": assembly["id"], "delete_descendants": 1},
            {"type": "transform", "selector": {"part_ids": [part["id"]]}, "rotation": [[1,0],[0,1]], "translation_ldu": [0,0,0], "pivot_ldu": [0,0,0]},
            {"type": "transform", "selector": {"part_ids": [part["id"]]}, "rotation": [[1,0,0],[0,1,0],[0,0,1]], "translation_ldu": [Decimal("NaN"),0,0], "pivot_ldu": [0,0,0]},
        ]
        for bad in malformed:
            op_id = uid(); req = request(self.value, [bad], opid=op_id)
            with self.subTest(op=bad), self.assertRaises(transactions.TransactionError): transactions.propose_edit(self.root, req, validator=good_validator)
            self.assertFalse((self.root / "operations" / op_id).exists())

    def test_r7_evaluation_environment_changes_invalidate_constant_reports(self):
        base_env = {"schema": "checker-env", "local_code": {"validator.py": "a"},
                    "bricknet": {"version": "1", "source_content_sha256": "b", "package_data_sha256": "c"},
                    "mesh_data_sha256": "d", "dependencies": {"numpy": "1"}}
        changes = [
            lambda e: e["local_code"].update({"validator.py": "changed"}),
            lambda e: e["bricknet"].update({"package_data_sha256": "changed"}),
            lambda e: e.update({"mesh_data_sha256": "changed"}),
            lambda e: e["dependencies"].update({"numpy": "changed"}),
        ]
        for index, mutate in enumerate(changes):
            with self.subTest(index=index):
                root = Path(self.temp.name) / f"environment-{index}"; revisions.initialize(root, self.value)
                req = request(self.value, [transform(self.value, self.value["assemblies"][0]["id"])])
                with patch("bricksmith.workbench.transactions._evaluation_environment_identity", return_value=copy.deepcopy(base_env)):
                    report = transactions.propose_edit(root, req, validator=good_validator)
                self.assertTrue(report["commit_eligible"])
                changed = copy.deepcopy(base_env); mutate(changed)
                with patch("bricksmith.workbench.transactions._evaluation_environment_identity", return_value=changed):
                    with self.assertRaisesRegex(transactions.TransactionError, "checker environment changed"):
                        transactions.commit_candidate(root, req["operation_id"], report["candidate_id"], validator=good_validator)

    def test_r7_environment_identity_is_path_independent_and_requires_complete_inputs(self):
        source = {"available": True, "version": "1.0", "import_path": "/one/site/bricknet.py",
            "source_root": "/one/src", "source_content_sha256": "src", "catalog_data": {
                "available": True, "path": "/one/data", "content_sha256": "catalog"}}
        versions = {name: "1" for name in ("bricknet", "meshlib", "numpy", "scipy")}
        with patch.object(provenance, "_bricknet_identity", return_value=copy.deepcopy(source)), \
             patch.object(provenance, "_package_version", side_effect=lambda name: versions.get(name)), \
             patch("bricksmith.workbench.transactions._data_identity", return_value="mesh"):
            first = transactions._evaluation_environment_identity()
        source["import_path"] = "/elsewhere/site/bricknet.py"; source["source_root"] = "/elsewhere/src"
        source["catalog_data"]["path"] = "/elsewhere/data"
        with patch.object(provenance, "_bricknet_identity", return_value=source), \
             patch.object(provenance, "_package_version", side_effect=lambda name: versions.get(name)), \
             patch("bricksmith.workbench.transactions._data_identity", return_value="mesh"):
            second = transactions._evaluation_environment_identity()
        self.assertEqual(first, second)
        source["catalog_data"]["available"] = False
        with patch.object(provenance, "_bricknet_identity", return_value=source), \
             patch.object(provenance, "_package_version", side_effect=lambda name: versions.get(name)), \
             patch("bricksmith.workbench.transactions._data_identity", return_value="mesh"):
            self.assertIsNone(transactions._evaluation_environment_identity())


class ProposalRecoveryReviewRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.data_patch = patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64)
        self.data_patch.start(); self.addCleanup(self.data_patch.stop)

    def _crash_after_failure_record(self, root, value, req):
        request_path = Path(self.temp.name) / f"{req['operation_id']}.json"
        request_path.write_text(design._json_text(req))
        script = r'''
import json,os,sys
from pathlib import Path
from bricksmith.workbench import transactions
transactions._data_identity=lambda: "a"*64
def val(path,ground): return {"passed":True,"checks":{k:True for k in transactions.CHECKS},"errors":[],"diagnostics":{"below_ground_indices_complete_flag":True,"below_ground_indices_complete":[]}}
req=json.loads(Path(sys.argv[2]).read_text())
transactions.propose_edit(Path(sys.argv[1]),req,validator=val,failpoint=lambda p: os._exit(88) if p=="after_failure_flush" else None)
'''
        child = subprocess.run([sys.executable, "-c", script, str(root), str(request_path)], cwd=ROOT)
        self.assertEqual(child.returncode, 88)
        return root / "operations" / req["operation_id"]

    def _failed_edit_request(self, value):
        part_id = value["parts"][0]["id"]
        return request(value, [{"type": "delete", "selector": {"part_ids": [part_id]}},
            transform(value, value["assemblies"][0]["id"])])

    def test_r5b_failed_proposal_receipt_is_recovered_without_rewriting_failure(self):
        root = Path(self.temp.name) / "failed-recovery"; value = make_design(); revisions.initialize(root, value)
        req = self._failed_edit_request(value); before_revision = revisions.read_state(root)["current_revision_id"]
        opdir = self._crash_after_failure_record(root, value, req)
        failure_path = opdir / "failure.json"; original_bytes = failure_path.read_bytes()
        original = json.loads(original_bytes)
        self.assertEqual(original["status"], "failure")
        self.assertEqual(original["error_type"], "TransactionError")
        self.assertEqual(original["candidate_artifact"], "candidate/invalid-design.json")
        interrupted_recovery = r'''import os,sys
from pathlib import Path
from bricksmith.workbench import transactions
transactions.recover(Path(sys.argv[1]), failpoint=lambda p: os._exit(89) if p=="after_failed_receipt_flush" else None)
'''
        interrupted = subprocess.run([sys.executable, "-c", interrupted_recovery, str(root)], cwd=ROOT)
        self.assertEqual(interrupted.returncode, 89)
        recover_script = r'''import sys
from pathlib import Path
from bricksmith.workbench import transactions
transactions._data_identity=lambda: "a"*64
transactions.recover(Path(sys.argv[1]))
result=transactions.recover(Path(sys.argv[1]))
assert result["repaired"] == []
'''
        recovered = subprocess.run([sys.executable, "-c", recover_script, str(root)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertEqual(failure_path.read_bytes(), original_bytes)
        terminal = transactions.inspect_candidate(root, req["operation_id"])
        self.assertEqual(terminal["disposition"], "failed")
        self.assertEqual(terminal["failure"], original)
        self.assertEqual(transactions.propose_edit(root, req, validator=good_validator)["disposition"], "failed")
        self.assertEqual(transactions.discard_candidate(root, req["operation_id"])["disposition"], "failed")
        with self.assertRaisesRegex(transactions.TransactionError, "failed"):
            transactions.commit_candidate(root, req["operation_id"], uid(), validator=good_validator)
        self.assertEqual(transactions.recover(root)["repaired"], [])
        self.assertEqual(revisions.read_state(root)["current_revision_id"], before_revision)

    def test_r5b_malformed_or_mismatched_failure_evidence_fails_closed(self):
        for field, replacement in (("operation_id", uid()), ("error_type", None)):
            with self.subTest(field=field):
                root = Path(self.temp.name) / f"failed-invalid-{field}"; value = make_design(); revisions.initialize(root, value)
                req = self._failed_edit_request(value); opdir = self._crash_after_failure_record(root, value, req)
                failure_path = opdir / "failure.json"; damaged = json.loads(failure_path.read_bytes())
                if replacement is None: damaged.pop(field)
                else: damaged[field] = replacement
                failure_path.write_text(design._json_text(damaged) + "\n")
                damaged_bytes = failure_path.read_bytes()
                with self.assertRaises(transactions.TransactionError): transactions.recover(root)
                self.assertEqual(failure_path.read_bytes(), damaged_bytes)
                self.assertFalse((opdir / "receipt.json").exists())

    def test_r5_incomplete_proposals_abort_and_candidate_receipts_survive(self):
        propose_script = r'''
import json,os,sys
from pathlib import Path
from bricksmith.workbench import transactions
transactions._data_identity=lambda: "a"*64
def val(path,ground): return {"passed":True,"checks":{k:True for k in transactions.CHECKS},"errors":[],"diagnostics":{"below_ground_indices_complete_flag":True,"below_ground_indices_complete":[]}}
req=json.loads(Path(sys.argv[2]).read_text())
transactions.propose_edit(Path(sys.argv[1]),req,validator=val,failpoint=lambda point: os._exit(79) if point==sys.argv[3] else None)
'''
        points = ("after_intent_flush", "during_candidate_writes", "after_report_flush",
                  "before_candidate_receipt_flush", "after_candidate_receipt_flush")
        for point in points:
            with self.subTest(point=point):
                root = Path(self.temp.name) / f"crash-{point}"; value = make_design(); revisions.initialize(root, value)
                req = request(value, [transform(value, value["assemblies"][0]["id"])])
                req_path = Path(self.temp.name) / f"{point}.json"; req_path.write_text(design._json_text(req))
                child = subprocess.run([sys.executable, "-c", propose_script, str(root), str(req_path), point], cwd=ROOT)
                self.assertEqual(child.returncode, 79)
                first = transactions.recover(root); second = transactions.recover(root)
                self.assertEqual(second["repaired"], [])
                if point == "after_candidate_receipt_flush":
                    self.assertIn(req["operation_id"], first["uncommitted_operations"])
                    inspected = transactions.inspect_candidate(root, req["operation_id"])
                    self.assertTrue(inspected["commit_eligible"])
                    retry = transactions.propose_edit(root, req, validator=good_validator)
                    self.assertEqual(retry["candidate_id"], inspected["candidate_id"])
                    discarded = transactions.discard_candidate(root, req["operation_id"])
                    self.assertEqual(discarded["disposition"], "discarded")
                    with self.assertRaisesRegex(transactions.TransactionError, "discarded"):
                        transactions.commit_candidate(root, req["operation_id"], inspected["candidate_id"], validator=good_validator)
                else:
                    self.assertIn(req["operation_id"], first["aborted_operations"])
                    terminal = transactions.inspect_candidate(root, req["operation_id"])
                    self.assertEqual(terminal["disposition"], "aborted")
                    self.assertEqual(transactions.propose_edit(root, req, validator=good_validator)["disposition"], "aborted")
                    self.assertEqual(transactions.discard_candidate(root, req["operation_id"])["disposition"], "aborted")
                    with self.assertRaisesRegex(transactions.TransactionError, "aborted"):
                        transactions.commit_candidate(root, req["operation_id"], uid(), validator=good_validator)
                    fresh = revisions.load_revision(root, value["revision_id"])
                    replacement_req = request(fresh, [transform(fresh, fresh["assemblies"][0]["id"])])
                    replacement = transactions.propose_edit(root, replacement_req, validator=good_validator)
                    self.assertEqual(replacement["status"], "construction_passed")

    def test_r5_failed_proposal_is_terminal_and_local_commit_without_state_is_corruption(self):
        root = Path(self.temp.name) / "terminal"; value = make_design(); revisions.initialize(root, value)
        part_id = value["parts"][0]["id"]
        bad_req = request(value, [{"type": "delete", "selector": {"part_ids": [part_id]}}, transform(value, value["assemblies"][0]["id"])])
        failure = transactions.propose_edit(root, bad_req, validator=good_validator)
        self.assertEqual(failure["status"], "failure")
        self.assertEqual(transactions.inspect_candidate(root, bad_req["operation_id"])["disposition"], "failed")
        self.assertEqual(transactions.discard_candidate(root, bad_req["operation_id"])["disposition"], "failed")
        recovered = transactions.recover(root)
        self.assertIn(bad_req["operation_id"], recovered["failed_operations"])

        candidate_req = request(value, [transform(value, value["assemblies"][0]["id"])])
        report = transactions.propose_edit(root, candidate_req, validator=good_validator)
        receipt_path = root / "operations" / candidate_req["operation_id"] / "receipt.json"
        local = design.read_json(receipt_path); local["disposition"] = "committed"; receipt_path.write_text(design._json_text(local))
        with self.assertRaisesRegex(transactions.TransactionError, "without authoritative state receipt"):
            transactions.recover(root)
