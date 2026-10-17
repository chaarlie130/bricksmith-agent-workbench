from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
import json
import os
import subprocess
import tempfile
import unittest
import uuid
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from bricksmith.workbench import design, intent_ledger, revisions, transactions

ROOT = Path(__file__).resolve().parents[2]
PASS = ROOT / "tests/fixtures/acceptance/pass.ldr"


def uid(): return str(uuid.uuid4())


def validator(path, ground):
    count = sum(line.startswith("1 ") for line in Path(path).read_text().splitlines())
    return {"schema": "bricksmith-construction-v1", "passed": True,
        "checks": {key: True for key in transactions.CHECKS}, "errors": [],
        "diagnostics": {"below_ground_indices_complete_flag": True, "below_ground_indices_complete": []},
        "physical_piece_count": count}


class IntentLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "workspace"
        value = design.import_ldr(PASS, ground_y=Decimal("8"))
        revisions.initialize(self.root, value)
        self.base = value["revision_id"]

    def upgrade(self):
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            result = intent_ledger.upgrade_workspace(self.root, uid(), self.base, validator=validator)
        self.assertEqual(result["disposition"], "committed")
        return result["revision_id"]

    def test_trusted_correction_preserves_record_and_ledger_reads_without_physics(self):
        base = self.upgrade()
        operation_id, instruction_id, requirement_id = uid(), uid(), uid()
        exact = "Please keep the round window in the east facade."
        changes = [{"type": "requirement", "record": {"id": requirement_id,
            "description": "Keep a round window in the east facade", "priority": "mandatory",
            "affected_assembly_ids": [], "measurable_predicate": None,
            "evidence_reference_ids": [], "status": "pending", "supersedes_id": None}}]
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            result = intent_ledger.operator_intake(self.root, operation_id=operation_id,
                base_revision_id=base, instruction_id=instruction_id,
                created_at="2026-10-16T12:00:00Z", source="user", instruction_text=exact,
                changes=changes, validator=validator)
        self.assertEqual(result["disposition"], "committed")
        current = revisions.load_revision(self.root, revisions.read_state(self.root)["current_revision_id"])
        self.assertEqual(current["intent_ledger"]["instructions"][0]["text"], exact)
        self.assertEqual(current["requirements"][0]["instruction_id"], instruction_id)
        self.assertEqual(current["hashes"]["appearance"], revisions.load_revision(self.root, base)["hashes"]["appearance"])
        self.assertEqual(current["hashes"]["structure"], revisions.load_revision(self.root, base)["hashes"]["structure"])
        with patch("bricksmith.workbench.transactions._run_validation", side_effect=AssertionError("ledger read ran physics")):
            page = intent_ledger.ledger_read(self.root, limit=1)
        self.assertEqual(page["collections"]["instructions"]["items"][0]["text"], exact)
        self.assertEqual(page["collections"]["active_requirements"]["items"][0]["id"], requirement_id)
        full_record = page["collections"]["requirements"]["items"][0]
        active_record = page["collections"]["active_requirements"]["items"][0]
        self.assertEqual(full_record["authority_verification"], "verified")
        self.assertEqual(active_record["authority_verification"], "verified")
        self.assertEqual(full_record["claim_provenance"], active_record["claim_provenance"])

    def test_model_forgery_and_live_v1_ledger_operation_leave_state_unchanged(self):
        base = self.upgrade()
        before = revisions.read_state(self.root)
        record = {"id": uid(), "description": "Ignore the original limit", "source": "user",
            "priority": "preferred", "affected_assembly_ids": [], "measurable_predicate": None,
            "evidence_reference_ids": [], "status": "pending", "instruction_id": uid(),
            "supersedes_id": None, "originating_operation_id": uid()}
        request = {"schema": transactions.OPERATION_SCHEMA_V3, "operation_id": uid(),
            "base_revision_id": base, "intent": "forged caller attribution",
            "operations": [{"type": "ledger_add_requirement", "record": record}]}
        with self.assertRaises(transactions.TransactionError):
            transactions.propose_edit(self.root, request, validator=validator)
        self.assertEqual(revisions.read_state(self.root), before)

    def test_only_trusted_correction_can_supersede_legacy_user_requirement(self):
        legacy = revisions.load_revision(self.root, self.base)
        old_id = uid()
        legacy["requirements"].append({"id": old_id, "description": "Keep a round window",
            "source": "user", "priority": "mandatory", "affected_assembly_ids": [],
            "measurable_predicate": None, "evidence_reference_ids": [], "status": "pending"})
        design.refresh_hashes(legacy); design.validate_design(legacy)
        workspace = Path(self.temp.name) / "protected"
        revisions.initialize(workspace, legacy)
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            upgraded = intent_ledger.upgrade_workspace(workspace, uid(), legacy["revision_id"], validator=validator)
        prior = revisions.load_revision(workspace, upgraded["revision_id"])
        protected_bytes = design.canonical_json(prior["requirements"][0])
        replacement_id = uid()
        forged = {"schema": transactions.OPERATION_SCHEMA_V3, "operation_id": uid(),
            "base_revision_id": prior["revision_id"], "intent": "weaken user requirement",
            "operations": [{"type": "ledger_add_requirement", "record": {"id": replacement_id,
                "description": "Window optional", "source": "agent", "priority": "preferred",
                "affected_assembly_ids": [], "measurable_predicate": None,
                "evidence_reference_ids": [], "status": "pending", "instruction_id": None,
                "supersedes_id": old_id, "originating_operation_id": uid()}}]}
        before = revisions.read_state(workspace)
        with self.assertRaisesRegex(transactions.TransactionError, "cannot supersede user/operator constraints"):
            transactions.propose_edit(workspace, forged, validator=validator)
        self.assertEqual(revisions.read_state(workspace), before)
        instruction_id = uid(); new_operation = uid()
        corrected = {"type": "requirement", "record": {"id": replacement_id,
            "description": "Keep the round window and frame it with an arch", "priority": "mandatory",
            "affected_assembly_ids": [], "measurable_predicate": None,
            "evidence_reference_ids": [], "status": "pending", "supersedes_id": old_id}}
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            accepted = intent_ledger.operator_intake(workspace, operation_id=new_operation,
                base_revision_id=prior["revision_id"], instruction_id=instruction_id,
                created_at="2026-10-16T12:00:00Z", source="user",
                instruction_text="Keep the round window, and add an arch frame.",
                changes=[corrected], validator=validator)
        self.assertEqual(accepted["disposition"], "committed")
        final = revisions.load_revision(workspace, accepted["revision_id"])
        self.assertEqual(design.canonical_json(final["requirements"][0]), protected_bytes)
        self.assertEqual(intent_ledger.ledger_read(workspace)["collections"]["active_requirements"]["items"][0]["id"], replacement_id)

    def test_v1_upgrade_is_explicit_and_legacy_records_survive(self):
        old = revisions.load_revision(self.root, self.base)
        old["requirements"].append({"id": uid(), "description": "legacy user claim", "source": "user",
            "priority": "unknown", "affected_assembly_ids": [], "measurable_predicate": None,
            "evidence_reference_ids": [], "status": "pending"})
        design.refresh_hashes(old); design.validate_design(old)
        source = Path(self.temp.name) / "legacy"; revisions.initialize(source, old)
        prior = revisions.load_revision(source, old["revision_id"])
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            result = intent_ledger.upgrade_workspace(source, uid(), prior["revision_id"], validator=validator)
        upgraded = revisions.load_revision(source, result["revision_id"])
        self.assertEqual(upgraded["requirements"], prior["requirements"])
        self.assertEqual(upgraded["intent_ledger"]["instructions"], [])
        self.assertEqual(revisions.load_revision(source, prior["revision_id"])["schema"], design.DESIGN_SCHEMA)
        historical_ledger = intent_ledger.ledger_read(source, revision_id=result["revision_id"])
        old_claim = historical_ledger["collections"]["active_requirements"]["items"][0]
        self.assertEqual(old_claim["authority_verification"], "unverified_historical_source_claim")

    def test_subprocess_death_after_publication_recovers_trusted_correction_once(self):
        base = self.upgrade()
        operation_id, instruction_id = uid(), uid()
        script = """
import os, sys
from pathlib import Path
from bricksmith.workbench import intent_ledger, transactions
transactions._data_identity = lambda: 'a' * 64
def validator(path, ground):
    return {'schema': 'bricksmith-construction-v1', 'passed': True,
        'checks': {key: True for key in transactions.CHECKS}, 'errors': [],
        'diagnostics': {'below_ground_indices_complete_flag': True, 'below_ground_indices_complete': []},
        'physical_piece_count': sum(line.startswith('1 ') for line in Path(path).read_text().splitlines())}
intent_ledger.operator_intake(Path(sys.argv[1]), operation_id=sys.argv[2], base_revision_id=sys.argv[3],
    instruction_id=sys.argv[4], created_at='2026-10-16T12:00:00Z', source='user',
    instruction_text='Keep the window', changes=[], validator=validator,
    _failpoint=lambda point: os._exit(89) if point == 'after_pointer_commit' else None)
"""
        environment = dict(os.environ, BRICKNET_DATA=str(ROOT / "data/bricknet-data"))
        child = subprocess.run([str(ROOT / ".venv/bin/python"), "-c", script,
            str(self.root), operation_id, base, instruction_id], cwd=ROOT, env=environment)
        self.assertEqual(child.returncode, 89)
        transactions.recover(self.root)
        page = intent_ledger.ledger_read(self.root)
        self.assertEqual(page["collections"]["instructions"]["count"], 1)
        self.assertEqual(page["collections"]["instructions"]["items"][0]["id"], instruction_id)
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            replay = intent_ledger.operator_intake(self.root, operation_id=operation_id,
                base_revision_id=base, instruction_id=instruction_id,
                created_at="2026-10-16T12:00:00Z", source="user",
                instruction_text="Keep the window", changes=[], validator=validator)
        self.assertEqual(replay["disposition"], "committed")
        self.assertEqual(intent_ledger.ledger_read(self.root)["collections"]["instructions"]["count"], 1)

    def test_issue_decision_attempt_and_next_action_follow_validated_geometry_revision(self):
        base = self.upgrade()
        issue_id = uid()
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            created = intent_ledger.operator_intake(self.root, operation_id=uid(), base_revision_id=base,
                instruction_id=uid(), created_at="2026-10-16T12:00:00Z", source="operator",
                instruction_text="Record the roof connection concern.", changes=[{"type": "issue",
                    "issue_id": issue_id, "kind": "roof_connectivity", "status": "open",
                    "affected_ids": [], "evidence_reference_ids": [],
                    "next_proposed_action": "inspect roof bonds"}], validator=validator)
        operation_id = uid()
        operation = {"schema": transactions.OPERATION_SCHEMA_V3, "operation_id": operation_id,
            "base_revision_id": created["revision_id"], "intent": "move the reviewed assembly",
            "operations": [{"type": "transform", "selector": {"assembly_ids": [
                revisions.load_revision(self.root, created["revision_id"])["assemblies"][0]["id"]]},
                "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                "translation_ldu": [Decimal("20"), 0, 0], "pivot_ldu": [0, 0, 0]}]}
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            proposed = transactions.propose_edit(self.root, operation, validator=validator)
            committed = transactions.commit_candidate(self.root, operation_id, proposed["candidate_id"], validator=validator)
        recording_id = uid()
        changes = [
            {"type": "decision", "record": {"id": uid(), "statement": "Use a bonded roof lap",
                "rationale": "The revised arrangement is locally supported.", "status": "active",
                "related_assembly_ids": [], "related_requirement_ids": [],
                "evidence_reference_ids": [], "supersedes_id": None}},
            {"type": "repair_attempt", "record": {"id": uid(), "issue_ids": [issue_id],
                "attempted_operation_id": operation_id, "observed_revision_id": committed["revision_id"],
                "evidence_references": [], "note": "Recorded the checked geometry attempt."}},
            {"type": "next_action", "record": {"id": uid(), "description": "Render the revised roof",
                "kind": "render", "related_requirement_ids": [], "related_issue_ids": [issue_id],
                "evidence_references": [], "status": "pending", "supersedes_id": None}}
        ]
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            recorded = intent_ledger.operator_intake(self.root, operation_id=recording_id,
                base_revision_id=committed["revision_id"], instruction_id=uid(),
                created_at="2026-10-16T12:01:00Z", source="operator",
                instruction_text="Record the repair outcome and render handoff.",
                changes=changes, validator=validator)
        page = intent_ledger.ledger_read(self.root)
        attempt = page["collections"]["repair_attempts"]["items"][0]
        self.assertEqual(attempt["current_reconciled_outcome"]["disposition"], "committed")
        self.assertEqual(attempt["current_reconciled_outcome"]["revision_id"], committed["revision_id"])
        self.assertIn(operation_id, page["collections"]["issues"]["items"][0]["attempted_operation_ids"])
        issue_observations = page["collections"]["issues"]["items"][0]["claim_provenance"]["observations"]
        self.assertEqual([item["operation_id"] for item in issue_observations], [
            page["collections"]["issues"]["items"][0]["originating_operation_id"]])
        self.assertEqual(page["collections"]["next_actions"]["items"][0]["status"], "pending")
        self.assertEqual(page["collections"]["decisions"]["items"][0]["statement"], "Use a bonded roof lap")
        self.assertEqual(recorded["disposition"], "committed")

    def test_issue_observations_keep_their_own_status_and_evidence_snapshots(self):
        base = self.upgrade()
        issue_id = uid()
        source_ref = revisions.load_revision(self.root, base)["source_references"][0]
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            created = intent_ledger.operator_intake(self.root, operation_id=uid(),
                base_revision_id=base, instruction_id=uid(), created_at="2026-10-16T12:00:00Z",
                source="operator", instruction_text="Record an unresolved roof issue.", changes=[{
                    "type": "issue", "issue_id": issue_id, "kind": "roof_connectivity",
                    "status": "open", "affected_ids": [], "evidence_reference_ids": [],
                    "next_proposed_action": "inspect the roof"}], validator=validator)
            resolved = intent_ledger.operator_intake(self.root, operation_id=uid(),
                base_revision_id=revisions.read_state(self.root)["current_revision_id"],
                instruction_id=uid(), created_at="2026-10-16T12:01:00Z", source="operator",
                instruction_text="Resolve the issue using the linked source.", changes=[{
                    "type": "issue", "issue_id": issue_id, "kind": "roof_connectivity",
                    "status": "resolved", "affected_ids": [],
                    "evidence_reference_ids": [source_ref["id"],],
                    "next_proposed_action": "retain the source link"}], validator=validator)
            reopened = intent_ledger.operator_intake(self.root, operation_id=uid(),
                base_revision_id=revisions.read_state(self.root)["current_revision_id"],
                instruction_id=uid(), created_at="2026-10-16T12:02:00Z", source="operator",
                instruction_text="Reopen the issue for another visual inspection.", changes=[{
                    "type": "issue", "issue_id": issue_id, "kind": "roof_connectivity",
                    "status": "open", "affected_ids": [], "evidence_reference_ids": [],
                    "next_proposed_action": "inspect the roof again"}], validator=validator)
        with patch("bricksmith.workbench.transactions._run_validation", side_effect=AssertionError("ledger read ran physics")):
            current_page = intent_ledger.ledger_read(self.root, limit=100)
            old_page = intent_ledger.ledger_read(self.root, revision_id=resolved["revision_id"], limit=100)
        issue = current_page["collections"]["issues"]["items"][0]
        observations = issue["claim_provenance"]["observations"]
        self.assertEqual([item["status"] for item in observations], ["open", "resolved", "open"])
        self.assertEqual([item["revision_id"] for item in observations], [
            created["revision_id"], resolved["revision_id"], reopened["revision_id"]])
        self.assertEqual(observations[0]["evidence_reference_ids"], [])
        self.assertEqual(observations[0]["evidence_references"], [])
        self.assertEqual(observations[1]["evidence_reference_ids"], [source_ref["id"]])
        self.assertEqual(observations[1]["evidence_references"][0]["content_hash"], source_ref["content_hash"])
        self.assertEqual(observations[2]["evidence_reference_ids"], [])
        self.assertEqual(issue["issue_provenance"]["creation"]["operation_id"], observations[0]["operation_id"])
        self.assertEqual(issue["issue_provenance"]["creation"]["evidence_reference_ids"], [])
        self.assertEqual(issue["issue_provenance"]["latest_status_assertion"]["operation_id"], observations[2]["operation_id"])
        self.assertEqual(issue["issue_provenance"]["latest_status_assertion"]["status"], "open")
        self.assertEqual(issue["claim_provenance"]["evidence_references"], [])
        old_issue = old_page["collections"]["issues"]["items"][0]
        self.assertEqual(old_issue["status"], "resolved")
        self.assertEqual([item["status"] for item in old_issue["claim_provenance"]["observations"]], ["open", "resolved"])

    def test_unpublished_and_other_issue_updates_never_displace_latest_observation(self):
        base = self.upgrade(); issue_a, issue_b = uid(), uid()
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            created = intent_ledger.operator_intake(self.root, operation_id=uid(), base_revision_id=base,
                instruction_id=uid(), created_at="2026-10-16T12:00:00Z", source="operator",
                instruction_text="Create two independent issues.", changes=[
                    {"type": "issue", "issue_id": issue_a, "kind": "roof", "status": "open",
                     "affected_ids": [], "evidence_reference_ids": [], "next_proposed_action": "inspect A"},
                    {"type": "issue", "issue_id": issue_b, "kind": "window", "status": "open",
                     "affected_ids": [], "evidence_reference_ids": [], "next_proposed_action": "inspect B"}],
                validator=validator)
        base = created["revision_id"]
        staged_id = uid()
        staged_update = {"schema": transactions.OPERATION_SCHEMA_V3, "operation_id": staged_id,
            "base_revision_id": base, "intent": "stage A resolution only",
            "operations": [{"type": "ledger_update_issue", "issue_id": issue_a,
                "kind": "roof", "status": "resolved", "affected_ids": [],
                "evidence_reference_ids": [], "next_proposed_action": "none"}]}
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            staged = transactions.propose_edit(self.root, staged_update, validator=validator)
            intake = intent_ledger.operator_intake(self.root, operation_id=uid(), base_revision_id=base,
                instruction_id=uid(), created_at="2026-10-16T12:01:00Z", source="operator",
                instruction_text="Record the staged resolution attempt.", changes=[{
                    "type": "repair_attempt", "record": {"id": uid(), "issue_ids": [issue_a],
                        "attempted_operation_id": staged_id, "observed_revision_id": base,
                        "evidence_references": [], "note": "The resolution remains unpublished."}}],
                validator=validator)
        current = intent_ledger.ledger_read(self.root, limit=100)
        a_now = next(item for item in current["collections"]["issues"]["items"] if item["id"] == issue_a)
        self.assertEqual(a_now["status"], "open")
        self.assertEqual([item["status"] for item in a_now["claim_provenance"]["observations"]], ["open"])
        self.assertEqual(a_now["issue_provenance"]["latest_status_assertion"]["status"], "open")
        self.assertEqual(a_now["issue_provenance"]["latest_status_assertion"]["revision_id"], base)
        transactions.discard_candidate(self.root, staged_id)
        after_discard = intent_ledger.ledger_read(self.root, limit=100)
        a_after_discard = next(item for item in after_discard["collections"]["issues"]["items"] if item["id"] == issue_a)
        self.assertEqual(a_after_discard["status"], "open")
        self.assertEqual([item["status"] for item in a_after_discard["claim_provenance"]["observations"]], ["open"])
        staged_attempt = next(item for item in after_discard["collections"]["repair_attempts"]["items"]
            if item["attempted_operation_id"] == staged_id)
        self.assertEqual(staged_attempt["outcome_at_recording"]["disposition"], "candidate")
        self.assertEqual(staged_attempt["current_reconciled_outcome"]["disposition"], "discarded")

        unrelated_id = uid()
        unrelated_update = {"schema": transactions.OPERATION_SCHEMA_V3, "operation_id": unrelated_id,
            "base_revision_id": intake["revision_id"], "intent": "resolve B, not A",
            "operations": [{"type": "ledger_update_issue", "issue_id": issue_b,
                "kind": "window", "status": "resolved", "affected_ids": [],
                "evidence_reference_ids": [], "next_proposed_action": "none"}]}
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            proposal = transactions.propose_edit(self.root, unrelated_update, validator=validator)
            committed = transactions.commit_candidate(self.root, unrelated_id,
                proposal["candidate_id"], validator=validator)
            recorded = intent_ledger.operator_intake(self.root, operation_id=uid(),
                base_revision_id=committed["revision_id"], instruction_id=uid(),
                created_at="2026-10-16T12:02:00Z", source="operator",
                instruction_text="Record unrelated operation as repair history for A.", changes=[{
                    "type": "repair_attempt", "record": {"id": uid(), "issue_ids": [issue_a],
                        "attempted_operation_id": unrelated_id, "observed_revision_id": committed["revision_id"],
                        "evidence_references": [], "note": "This operation updated B only."}}],
                validator=validator)
        final = intent_ledger.ledger_read(self.root, limit=100)
        a_final = next(item for item in final["collections"]["issues"]["items"] if item["id"] == issue_a)
        b_final = next(item for item in final["collections"]["issues"]["items"] if item["id"] == issue_b)
        self.assertEqual([item["status"] for item in a_final["claim_provenance"]["observations"]], ["open"])
        self.assertEqual(a_final["issue_provenance"]["latest_status_assertion"]["status"], "open")
        self.assertEqual(a_final["issue_provenance"]["latest_status_assertion"]["revision_id"], base)
        self.assertEqual([item["status"] for item in b_final["claim_provenance"]["observations"]], ["open", "resolved"])
        self.assertEqual(b_final["issue_provenance"]["latest_status_assertion"]["revision_id"], committed["revision_id"])
        unrelated_attempt = next(item for item in final["collections"]["repair_attempts"]["items"]
            if item["attempted_operation_id"] == unrelated_id)
        self.assertEqual(unrelated_attempt["current_reconciled_outcome"]["disposition"], "committed")
        historical = intent_ledger.ledger_read(self.root, revision_id=base, limit=100)
        a_historical = next(item for item in historical["collections"]["issues"]["items"] if item["id"] == issue_a)
        self.assertEqual(a_historical["issue_provenance"]["latest_status_assertion"]["status"], "open")

    def test_checker_policy_issue_has_source_bound_latest_observation(self):
        base = self.upgrade(); value = revisions.load_revision(self.root, base)
        operation_id = uid(); assembly_id = value["assemblies"][0]["id"]
        request = {"schema": transactions.OPERATION_SCHEMA_V3, "operation_id": operation_id,
            "base_revision_id": base, "intent": "exercise provisional policy issue provenance",
            "operations": [{"type": "transform", "selector": {"assembly_ids": [assembly_id]},
                "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                "translation_ldu": [Decimal("20"), 0, 0], "pivot_ldu": [0, 0, 0]}]}
        calls = 0
        def provisional_validator(path, ground):
            nonlocal calls
            result = validator(path, ground); calls += 1
            if calls % 2 == 0:
                result["checks"]["actual_connectivity"] = False
                result["passed"] = False
            return result
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            proposal = transactions.propose_edit(self.root, request, validator=provisional_validator)
            self.assertEqual(proposal["status"], "provisional")
            receipt = transactions.commit_candidate(self.root, operation_id,
                proposal["candidate_id"], validator=provisional_validator)
        page = intent_ledger.ledger_read(self.root, limit=100)
        policy_issue = next(item for item in page["collections"]["issues"]["items"]
            if item["kind"] == "provisional")
        latest = policy_issue["issue_provenance"]["latest_status_assertion"]
        self.assertEqual(latest["classification"], "asserted_claim")
        self.assertEqual(latest["operation_id"], operation_id)
        self.assertEqual(latest["revision_id"], receipt["revision_id"])
        self.assertEqual(latest["status"], "open")

    def test_legacy_issue_observation_attribution_remains_unknown(self):
        legacy = design.import_ldr(PASS, ground_y=Decimal("8"))
        legacy["issues"].append({"id": uid(), "kind": "legacy_visual", "status": "open",
            "affected_ids": [], "evidence_reference_ids": [], "first_observation_revision_id": None,
            "last_observation_revision_id": None, "attempted_operation_ids": [],
            "next_proposed_action": "inspect"})
        design.refresh_hashes(legacy); design.validate_design(legacy)
        workspace = Path(self.temp.name) / "legacy-issue-workspace"
        revisions.initialize(workspace, legacy)
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            upgrade = intent_ledger.upgrade_workspace(workspace, uid(), legacy["revision_id"], validator=validator)
        issue = intent_ledger.ledger_read(workspace, revision_id=upgrade["revision_id"])['collections']['issues']['items'][0]
        self.assertEqual(issue["claim_provenance"]["classification"], "historical_unverified_claim")
        self.assertEqual(issue["issue_provenance"]["latest_status_assertion"]["classification"], "historical_unverified_claim")
        self.assertIsNone(issue["issue_provenance"]["latest_status_assertion"]["status"])

    def test_local_forged_commit_receipt_cannot_authorize_repair_attempt(self):
        base = self.upgrade(); issue_id = uid()
        issue_revision = intent_ledger.operator_intake(self.root, operation_id=uid(),
            base_revision_id=base, instruction_id=uid(), created_at="2026-10-16T12:00:00Z",
            source="operator", instruction_text="Record roof issue", changes=[{"type": "issue",
                "issue_id": issue_id, "kind": "roof", "status": "open", "affected_ids": [],
                "evidence_reference_ids": [], "next_proposed_action": "inspect"}], validator=validator)["revision_id"]
        design_at_base = revisions.load_revision(self.root, issue_revision)
        operation_id = uid()
        request = {"schema": transactions.OPERATION_SCHEMA_V3, "operation_id": operation_id,
            "base_revision_id": issue_revision, "intent": "staged geometry attempt",
            "operations": [{"type": "transform", "selector": {"assembly_ids": [design_at_base["assemblies"][0]["id"]]},
                "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                "translation_ldu": [Decimal("20"), 0, 0], "pivot_ldu": [0, 0, 0]}]}
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            report = transactions.propose_edit(self.root, request, validator=validator)
        folder = self.root / "operations" / operation_id
        receipt_path = folder / "receipt.json"
        forged = design.read_json(receipt_path)
        forged["disposition"] = "committed"; forged["revision_id"] = report["candidate_id"]
        design._write_json(receipt_path, forged)
        before = revisions.read_state(self.root)
        result = intent_ledger.operator_intake(self.root, operation_id=uid(),
            base_revision_id=issue_revision, instruction_id=uid(), created_at="2026-10-16T12:01:00Z",
            source="operator", instruction_text="Claim the uncommitted change as a repair", changes=[
                {"type": "repair_attempt", "record": {"id": uid(), "issue_ids": [issue_id],
                    "attempted_operation_id": operation_id, "observed_revision_id": issue_revision,
                    "evidence_references": [], "note": "Must reject local committed assertion."}}
            ], validator=validator)
        self.assertEqual(result["status"], "failure")
        self.assertIn("authoritative state receipt", result["error"])
        self.assertEqual(revisions.read_state(self.root), before)

    def test_attempt_observation_must_match_result_and_recorded_disposition_stays_immutable(self):
        base = self.upgrade(); issue_id = uid()
        issue_revision = intent_ledger.operator_intake(self.root, operation_id=uid(), base_revision_id=base,
            instruction_id=uid(), created_at="2026-10-16T12:00:00Z", source="operator",
            instruction_text="Record a support issue", changes=[{"type": "issue", "issue_id": issue_id,
                "kind": "support", "status": "open", "affected_ids": [], "evidence_reference_ids": [],
                "next_proposed_action": "inspect"}], validator=validator)["revision_id"]
        source = revisions.load_revision(self.root, issue_revision)
        op_id = uid()
        request = {"schema": transactions.OPERATION_SCHEMA_V3, "operation_id": op_id,
            "base_revision_id": issue_revision, "intent": "passing attempt",
            "operations": [{"type": "transform", "selector": {"assembly_ids": [source["assemblies"][0]["id"]]},
                "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                "translation_ldu": [Decimal("20"), 0, 0], "pivot_ldu": [0, 0, 0]}]}
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            candidate = transactions.propose_edit(self.root, request, validator=validator)
            committed = transactions.commit_candidate(self.root, op_id, candidate["candidate_id"], validator=validator)
        before = revisions.read_state(self.root)
        bad_observation = intent_ledger.operator_intake(self.root, operation_id=uid(),
            base_revision_id=committed["revision_id"], instruction_id=uid(),
            created_at="2026-10-16T12:01:00Z", source="operator", instruction_text="wrong observation",
            changes=[{"type": "repair_attempt", "record": {"id": uid(), "issue_ids": [issue_id],
                "attempted_operation_id": op_id, "observed_revision_id": issue_revision,
                "evidence_references": [], "note": None}}], validator=validator)
        self.assertEqual(bad_observation["status"], "failure")
        self.assertIn("observed_revision_id", bad_observation["error"])
        self.assertEqual(revisions.read_state(self.root), before)

        # Stage a second attempt, record that staged outcome, then discard it.
        staged_id = uid()
        staged = {**request, "operation_id": staged_id, "base_revision_id": committed["revision_id"],
            "intent": "candidate later discarded"}
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            staged_report = transactions.propose_edit(self.root, staged, validator=validator)
        record = intent_ledger.operator_intake(self.root, operation_id=uid(),
            base_revision_id=committed["revision_id"], instruction_id=uid(),
            created_at="2026-10-16T12:02:00Z", source="operator", instruction_text="Record staged attempt",
            changes=[{"type": "repair_attempt", "record": {"id": uid(), "issue_ids": [issue_id],
                "attempted_operation_id": staged_id, "observed_revision_id": committed["revision_id"],
                "evidence_references": [], "note": "Recorded before discard."}}], validator=validator)
        self.assertEqual(record["disposition"], "committed")
        self.assertEqual(transactions.discard_candidate(self.root, staged_id)["disposition"], "discarded")
        page = intent_ledger.ledger_read(self.root)
        matching = next(item for item in page["collections"]["repair_attempts"]["items"]
            if item["attempted_operation_id"] == staged_id)
        self.assertEqual(matching["outcome_at_recording"]["disposition"], "candidate")
        self.assertEqual(matching["current_reconciled_outcome"]["disposition"], "discarded")

    def test_failed_attempt_requires_intact_terminal_evidence(self):
        base = self.upgrade(); issue_id = uid()
        issue_revision = intent_ledger.operator_intake(self.root, operation_id=uid(), base_revision_id=base,
            instruction_id=uid(), created_at="2026-10-16T12:00:00Z", source="operator",
            instruction_text="Record an issue", changes=[{"type": "issue", "issue_id": issue_id,
                "kind": "window", "status": "open", "affected_ids": [], "evidence_reference_ids": [],
                "next_proposed_action": "inspect"}], validator=validator)["revision_id"]

        def failed_color_op(base_id):
            operation_id = uid()
            request = {"schema": transactions.OPERATION_SCHEMA_V3, "operation_id": operation_id,
                "base_revision_id": base_id, "intent": "invalid color for terminal-failure evidence",
                "operations": [{"type": "recolor", "selector": {"part_ids": [
                    revisions.load_revision(self.root, base_id)["parts"][0]["id"]]}, "color_id": 999}]}
            result = transactions.propose_edit(self.root, request, validator=validator)
            self.assertEqual(result["status"], "failure")
            return operation_id

        failed_id = failed_color_op(issue_revision)
        recorded = intent_ledger.operator_intake(self.root, operation_id=uid(),
            base_revision_id=issue_revision, instruction_id=uid(), created_at="2026-10-16T12:01:00Z",
            source="operator", instruction_text="Record the genuine failed outcome", changes=[
                {"type": "repair_attempt", "record": {"id": uid(), "issue_ids": [issue_id],
                    "attempted_operation_id": failed_id, "observed_revision_id": issue_revision,
                    "evidence_references": [], "note": "The invalid color candidate failed before sealing."}}
            ], validator=validator)
        self.assertEqual(recorded["disposition"], "committed")
        first_attempt = intent_ledger.ledger_read(self.root)["collections"]["repair_attempts"]["items"][0]
        self.assertEqual(first_attempt["outcome_at_recording"]["disposition"], "failed")
        self.assertEqual(first_attempt["current_reconciled_outcome"]["disposition"], "failed")

        next_base = recorded["revision_id"]
        missing_id = failed_color_op(next_base)
        missing_failure = self.root / "operations" / missing_id / "failure.json"
        missing_failure.unlink()
        before = revisions.read_state(self.root)
        rejected = intent_ledger.operator_intake(self.root, operation_id=uid(),
            base_revision_id=next_base, instruction_id=uid(), created_at="2026-10-16T12:02:00Z",
            source="operator", instruction_text="Attempt to cite missing failure evidence", changes=[
                {"type": "repair_attempt", "record": {"id": uid(), "issue_ids": [issue_id],
                    "attempted_operation_id": missing_id, "observed_revision_id": next_base,
                    "evidence_references": [], "note": None}}
            ], validator=validator)
        self.assertEqual(rejected["status"], "failure")
        self.assertIn("terminal failure evidence is missing", rejected["error"])
        self.assertEqual(revisions.read_state(self.root), before)

        failure_path = self.root / "operations" / failed_id / "failure.json"
        failure_path.write_text("{}\n")
        with self.assertRaisesRegex(transactions.TransactionError, "terminal failure evidence"):
            intent_ledger.ledger_read(self.root)

    def test_v2_ingress_types_text_boundaries_and_legacy_issue_guard(self):
        base = self.upgrade(); before = revisions.read_state(self.root)
        for issue_op, message in (
            ({"type": "ledger_update_issue", "issue_id": uid(), "kind": "x" * 20_000,
              "status": "open", "affected_ids": [], "evidence_reference_ids": [],
              "next_proposed_action": "inspect"}, "16 KiB"),
            ({"type": "ledger_update_issue", "issue_id": uid(), "kind": "roof",
              "status": [], "affected_ids": [], "evidence_reference_ids": [],
              "next_proposed_action": "inspect"}, "status enum"),
            ({"type": "ledger_update_issue", "issue_id": uid(), "kind": "roof",
              "status": "open", "affected_ids": [], "evidence_reference_ids": [],
              "next_proposed_action": "é" * 8193}, "16 KiB"),
        ):
            request = {"schema": transactions.OPERATION_SCHEMA_V3, "operation_id": uid(),
                "base_revision_id": base, "intent": "malformed issue operation", "operations": [issue_op]}
            with self.assertRaisesRegex(transactions.TransactionError, message):
                transactions.propose_edit(self.root, request, validator=validator)
            self.assertEqual(revisions.read_state(self.root), before)

        legacy_issue = {"type": "upsert_issue", "issue_id": uid(), "kind": "roof",
            "status": "resolved", "affected_ids": [], "next_proposed_action": "none"}
        legacy_request = {"schema": transactions.OPERATION_SCHEMA_V2, "operation_id": uid(),
            "base_revision_id": base, "intent": "legacy envelope on upgraded design", "operations": [legacy_issue]}
        with self.assertRaisesRegex(transactions.TransactionError, "design-v2 issue changes"):
            transactions.propose_edit(self.root, legacy_request, validator=validator)
        self.assertEqual(revisions.read_state(self.root), before)

        with self.assertRaisesRegex(transactions.TransactionError, "fill_brief must be a boolean"):
            intent_ledger.operator_intake(self.root, operation_id=uid(), base_revision_id=base,
                instruction_id=uid(), created_at="2026-10-16T12:00:00Z", source="operator",
                instruction_text="Do not coerce bools", changes=[], fill_brief="false", validator=validator)
        self.assertEqual(revisions.read_state(self.root), before)

        # 8,192 two-byte characters are exactly 16 KiB and remain accepted.
        exact = intent_ledger.operator_intake(self.root, operation_id=uid(), base_revision_id=base,
            instruction_id=uid(), created_at="2026-10-16T12:00:00Z", source="operator",
            instruction_text="boundary", changes=[{"type": "next_action", "record": {
                "id": uid(), "description": "é" * 8192, "kind": "review",
                "related_requirement_ids": [], "related_issue_ids": [], "evidence_references": [],
                "status": "pending", "supersedes_id": None}}], validator=validator)
        self.assertEqual(exact["disposition"], "committed")

    def test_v2_aggregate_record_count_and_size_exact_boundaries(self):
        base_id = self.upgrade()
        original = revisions.load_revision(self.root, base_id)
        opid = uid()
        def action(index, description="x"):
            return {"id": uid(), "description": description, "kind": "review",
                "related_requirement_ids": [], "related_issue_ids": [], "source": "agent",
                "evidence_references": [], "status": "pending", "supersedes_id": None,
                "originating_operation_id": opid}
        value = copy.deepcopy(original)
        existing = (len(value["requirements"]) + len(value["decisions"]) + len(value["issues"])
            + len(value["source_references"]) + len(value["intent_ledger"]["instructions"])
            + len(value["intent_ledger"]["repair_attempts"]))
        value["intent_ledger"]["next_actions"] = [action(i) for i in range(2000 - existing)]
        design.refresh_hashes(value); design.validate_design(value)
        value["intent_ledger"]["next_actions"].append(action(2000))
        design.refresh_hashes(value)
        with self.assertRaisesRegex(design.DesignError, "record count exceeds 2,000"):
            design.validate_design(value)

        target_size = 2 * 1024 * 1024
        max_text = 16 * 1024 - 1
        count = 0
        while True:
            value = copy.deepcopy(original)
            value["intent_ledger"]["next_actions"] = [action(i, "x" * max_text) for i in range(count)]
            tail = action(count, "")
            value["intent_ledger"]["next_actions"].append(tail)
            current_size = len(design.canonical_json({key: value[key] for key in
                ("requirements", "decisions", "issues", "source_references", "intent_ledger")}).encode("utf-8"))
            remaining = target_size - current_size
            if 0 <= remaining < max_text:
                tail["description"] = "x" * remaining
                break
            count += 1 if remaining >= max_text else -1
            self.assertGreaterEqual(count, 0)
        design.refresh_hashes(value); design.validate_design(value)
        exact_size = len(design.canonical_json({key: value[key] for key in
            ("requirements", "decisions", "issues", "source_references", "intent_ledger")}).encode("utf-8"))
        self.assertEqual(exact_size, target_size)
        value["intent_ledger"]["next_actions"][-1]["description"] += "x"
        design.refresh_hashes(value)
        with self.assertRaisesRegex(design.DesignError, "exceeds 2 MiB"):
            design.validate_design(value)

    def test_supersession_self_cycle_and_competing_branch_are_rejected(self):
        base = self.upgrade()
        def requirement(identifier, supersedes=None):
            return {"id": identifier, "description": "A bounded requirement", "source": "agent",
                "priority": "preferred", "affected_assembly_ids": [], "measurable_predicate": None,
                "evidence_reference_ids": [], "status": "pending", "instruction_id": None,
                "supersedes_id": supersedes, "originating_operation_id": uid()}
        original = revisions.load_revision(self.root, base)
        parent_id, first_child, competing = uid(), uid(), uid()
        branched = copy.deepcopy(original)
        branched["requirements"].extend([requirement(parent_id), requirement(first_child, parent_id),
            requirement(competing, parent_id)])
        design.refresh_hashes(branched)
        with self.assertRaisesRegex(design.DesignError, "competing active replacements"):
            design.validate_design(branched)

        self_link = copy.deepcopy(original)
        self_id = uid(); self_link["requirements"].append(requirement(self_id, self_id))
        design.refresh_hashes(self_link)
        with self.assertRaisesRegex(design.DesignError, "cannot supersede itself"):
            design.validate_design(self_link)

        cyclic = copy.deepcopy(original)
        first_id, later_id = uid(), uid()
        cyclic["requirements"].extend([requirement(first_id, later_id), requirement(later_id, first_id)])
        design.refresh_hashes(cyclic)
        with self.assertRaisesRegex(design.DesignError, "earlier record"):
            design.validate_design(cyclic)

    def test_evidence_reference_rejects_symlink_escape_and_hash_mismatch(self):
        outside = Path(self.temp.name) / "outside.txt"
        outside.write_text("private evidence")
        link = self.root / "evidence-link.txt"
        link.symlink_to(outside)
        digest = design.sha256_bytes(outside.read_bytes())
        with self.assertRaisesRegex(transactions.TransactionError, "symlink"):
            transactions._validate_evidence_references(self.root, [{"path": "evidence-link.txt", "sha256": digest}])
        local = self.root / "evidence.txt"; local.write_text("original")
        reference = {"path": "evidence.txt", "sha256": design.sha256_bytes(local.read_bytes())}
        local.write_text("changed")
        with self.assertRaisesRegex(transactions.TransactionError, "hash does not match"):
            transactions._validate_evidence_references(self.root, [reference])

    def test_subprocess_death_before_publication_recovers_and_trusted_retry_is_exact(self):
        base = self.upgrade(); operation_id, instruction_id = uid(), uid()
        script = """
import os, sys
from pathlib import Path
from bricksmith.workbench import intent_ledger, transactions
transactions._data_identity = lambda: 'a' * 64
def validator(path, ground):
    return {'schema':'bricksmith-construction-v1','passed':True,
        'checks':{key:True for key in transactions.CHECKS},'errors':[],
        'diagnostics':{'below_ground_indices_complete_flag':True,'below_ground_indices_complete':[]},
        'physical_piece_count':sum(line.startswith('1 ') for line in Path(path).read_text().splitlines())}
intent_ledger.operator_intake(Path(sys.argv[1]),operation_id=sys.argv[2],base_revision_id=sys.argv[3],
    instruction_id=sys.argv[4],created_at='2026-10-16T12:00:00Z',source='user',instruction_text='Exact retry text',
    changes=[],validator=validator,_failpoint=lambda point:os._exit(88) if point=='before_intent_flush' else None)
"""
        environment = dict(os.environ, BRICKNET_DATA=str(ROOT / "data/bricknet-data"))
        child = subprocess.run([str(ROOT / ".venv/bin/python"), "-c", script, str(self.root),
            operation_id, base, instruction_id], cwd=ROOT, env=environment)
        self.assertEqual(child.returncode, 88)
        recovered = transactions.recover(self.root)
        self.assertIn(f"removed_empty_staging:{operation_id}", recovered["repaired"])
        self.assertEqual(revisions.read_state(self.root)["current_revision_id"], base)
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            committed = intent_ledger.operator_intake(self.root, operation_id=operation_id,
                base_revision_id=base, instruction_id=instruction_id,
                created_at="2026-10-16T12:00:00Z", source="user", instruction_text="Exact retry text",
                changes=[], validator=validator)
        self.assertEqual(committed["disposition"], "committed")
        current = revisions.read_state(self.root)
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            with self.assertRaisesRegex(transactions.TransactionError, "different arguments"):
                intent_ledger.operator_intake(self.root, operation_id=operation_id,
                    base_revision_id=base, instruction_id=instruction_id,
                    created_at="2026-10-16T12:00:00Z", source="user", instruction_text="Changed text",
                    changes=[], validator=validator)
            reused = intent_ledger.operator_intake(self.root, operation_id=uid(),
                base_revision_id=current["current_revision_id"], instruction_id=instruction_id,
                created_at="2026-10-16T12:01:00Z", source="user", instruction_text="Reuse old authority id",
                changes=[], validator=validator)
        self.assertEqual(reused["status"], "failure")
        self.assertIn("ID has already been used", reused["error"])
        self.assertEqual(revisions.read_state(self.root), current)

    def test_v3_competing_candidates_stale_commit_and_replay_conflict(self):
        base = self.upgrade(); value = revisions.load_revision(self.root, base)
        assembly_id = value["assemblies"][0]["id"]
        def request(dx, opid):
            return {"schema": transactions.OPERATION_SCHEMA_V3, "operation_id": opid,
                "base_revision_id": base, "intent": f"move {dx}",
                "operations": [{"type": "transform", "selector": {"assembly_ids": [assembly_id]},
                    "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                    "translation_ldu": [Decimal(dx), 0, 0], "pivot_ldu": [0, 0, 0]}]}
        first, second = request("20", uid()), request("40", uid())
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            a = transactions.propose_edit(self.root, first, validator=validator)
            b = transactions.propose_edit(self.root, second, validator=validator)
            def attempt_commit(req, report):
                try:
                    return transactions.commit_candidate(self.root, req["operation_id"],
                        report["candidate_id"], validator=validator)
                except (transactions.TransactionError, revisions.RevisionError) as exc:
                    return exc
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda args: attempt_commit(*args), ((first, a), (second, b))))
        successful = [result for result in results if isinstance(result, dict)]
        stale_results = [result for result in results if isinstance(result, (transactions.TransactionError, revisions.RevisionError))]
        self.assertEqual(len(successful), 1)
        self.assertEqual(len(stale_results), 1)
        # Lock contention may refuse the loser before publication; its retry is
        # then deterministically stale against the winner's published revision.
        committed = successful[0]
        winner = next((req, report) for req, report in ((first, a), (second, b))
            if req["operation_id"] == committed["operation_id"])
        loser = (second, b) if winner[0] is first else (first, a)
        before = revisions.read_state(self.root)
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            with self.assertRaisesRegex(transactions.TransactionError, "stale base"):
                transactions.commit_candidate(self.root, loser[0]["operation_id"], loser[1]["candidate_id"], validator=validator)
            changed = {**winner[0], "intent": "conflicting replay"}
            with self.assertRaisesRegex(transactions.TransactionError, "different arguments"):
                transactions.propose_edit(self.root, changed, validator=validator)
            stale = request("60", uid())
            with self.assertRaisesRegex(transactions.TransactionError, "stale base_revision_id"):
                transactions.propose_edit(self.root, stale, validator=validator)
        self.assertEqual(revisions.read_state(self.root), before)
        self.assertEqual(before["current_revision_id"], committed["revision_id"])

    def test_original_ten_event_lifecycle_reopens_between_edits(self):
        fixture = json.loads((ROOT / "tests/fixtures/intent_ledger/victorian_ten_edits.json").read_text())
        self.assertEqual([event["edit"] for event in fixture["events"]], list(range(1, 11)))
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            upgrade = intent_ledger.upgrade_workspace(self.root, uid(), self.base, validator=validator)
        current = upgrade["revision_id"]
        initial = revisions.load_revision(self.root, current)
        requirement_id, issue_id = uid(), uid()
        source_ref = initial["source_references"][0]["id"]

        def reopen(expected=None):
            state = revisions.read_state(self.root)
            revision = revisions.load_revision(self.root, state["current_revision_id"])
            if expected is not None: self.assertEqual(revision["revision_id"], expected)
            return revision["revision_id"], revision

        def intake(text, changes, *, source="operator"):
            nonlocal current
            with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
                result = intent_ledger.operator_intake(self.root, operation_id=uid(),
                    base_revision_id=current, instruction_id=uid(),
                    created_at="2026-10-16T12:00:00Z", source=source,
                    instruction_text=text, changes=changes, validator=validator)
            self.assertEqual(result["disposition"], "committed", result)
            current = result["revision_id"]
            reopen(current)
            return result

        # Edit 1: capture the early user requirement exactly.
        first_event = intake(fixture["events"][0]["text"], [{"type": "requirement", "record": {
            "id": requirement_id, "description": "Keep a round east-facing window",
            "priority": "mandatory", "affected_assembly_ids": [], "measurable_predicate": None,
            "evidence_reference_ids": [], "status": "pending", "supersedes_id": None}}], source="user")
        # Edit 2: create the issue before any repair attempt refers to it.
        intake("Record the roof connection issue.", [{"type": "issue", "issue_id": issue_id,
            "kind": "roof_connectivity", "status": "open", "affected_ids": [],
            "evidence_reference_ids": [], "next_proposed_action": "inspect the roof bonds"}])
        # Edit 3: retain an evidence-linked design decision.
        intake("Choose the roof lap after source inspection.", [{"type": "decision", "record": {
            "id": uid(), "statement": fixture["events"][2]["statement"],
            "rationale": "Inspected source reference informs this local connection choice.",
            "status": "active", "related_assembly_ids": [], "related_requirement_ids": [],
            "evidence_reference_ids": [source_ref], "supersedes_id": None}}])

        # Edit 4: a deliberately colliding candidate is retained but not committed.
        observed_revision, observed = reopen(current)
        colliding = copy.deepcopy(observed["parts"][0]); colliding["id"] = uid()
        failed_op = {"schema": transactions.OPERATION_SCHEMA_V3, "operation_id": uid(),
            "base_revision_id": current, "intent": "deliberately failed roof repair",
            "operations": [{"type": "add_part", "part": colliding}]}
        def collision_validator(path, ground):
            count = sum(line.startswith("1 ") for line in Path(path).read_text().splitlines())
            checks = {key: True for key in transactions.CHECKS}
            errors = []
            if count > 1:
                checks["mesh_collision_free"] = False
                errors = [{"kind": "mesh_collision", "count": 1, "pairs": [[0, 1]]}]
            return {"schema": "bricksmith-construction-v1", "passed": all(checks.values()),
                "checks": checks, "errors": errors,
                "diagnostics": {"below_ground_indices_complete_flag": True, "below_ground_indices_complete": []},
                "physical_piece_count": count}
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            failed_report = transactions.propose_edit(self.root, failed_op, validator=collision_validator)
        self.assertFalse(failed_report["commit_eligible"])
        self.assertEqual(failed_report["status"], "blocked")
        self.assertEqual(reopen(current)[0], current)

        # Edit 5: record the failed candidate against the observed base revision.
        intake(fixture["events"][4]["note"], [{"type": "repair_attempt", "record": {
            "id": uid(), "issue_ids": [issue_id], "attempted_operation_id": failed_op["operation_id"],
            "observed_revision_id": observed_revision, "evidence_references": [],
            "note": "Collision evidence blocked this candidate."}}])

        # Edit 6: a later ordinary geometry edit passes the complete synthetic policy fixture.
        geometry_op = {"schema": transactions.OPERATION_SCHEMA_V3, "operation_id": uid(),
            "base_revision_id": current, "intent": "checked geometry progress",
            "operations": [{"type": "transform", "selector": {"assembly_ids": [observed["assemblies"][0]["id"]]},
                "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                "translation_ldu": [Decimal("20"), 0, 0], "pivot_ldu": [0, 0, 0]}]}
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            geometry_report = transactions.propose_edit(self.root, geometry_op, validator=validator)
            geometry_receipt = transactions.commit_candidate(self.root, geometry_op["operation_id"],
                geometry_report["candidate_id"], validator=validator)
        self.assertEqual(geometry_receipt["construction_status"], "construction_passed")
        current = geometry_receipt["revision_id"]; reopen(current)

        # Edit 7: record the later checked attempt separately from the original failure.
        intake(fixture["events"][6]["note"], [{"type": "repair_attempt", "record": {
            "id": uid(), "issue_ids": [issue_id], "attempted_operation_id": geometry_op["operation_id"],
            "observed_revision_id": geometry_receipt["revision_id"], "evidence_references": [],
            "note": "The checked geometry changed; visual requirements remain separate."}}])
        # Edit 8: keep the issue open and the window requirement pending after construction success.
        update = {"schema": transactions.OPERATION_SCHEMA_V3, "operation_id": uid(),
            "base_revision_id": current, "intent": "record unresolved visual requirement",
            "operations": [{"type": "ledger_update_issue", "issue_id": issue_id,
                "kind": "roof_connectivity", "status": "open", "affected_ids": [],
                "evidence_reference_ids": [], "next_proposed_action": "review the roof visually"}]}
        with patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64):
            updated = transactions.propose_edit(self.root, update, validator=validator)
            update_receipt = transactions.commit_candidate(self.root, update["operation_id"],
                updated["candidate_id"], validator=validator)
        current = update_receipt["revision_id"]; reopen(current)

        # Edits 9–10: persist a pending render-only action and the operator interruption.
        intake(fixture["events"][8]["description"], [{"type": "next_action", "record": {
            "id": uid(), "description": "Render only after review", "kind": "render",
            "related_requirement_ids": [requirement_id], "related_issue_ids": [issue_id],
            "evidence_references": [], "status": "pending", "supersedes_id": None}}])
        intake(fixture["events"][9]["instruction"], [{"type": "next_action", "record": {
            "id": uid(), "description": "Operator-requested render-only handoff to Flash",
            "kind": "render", "related_requirement_ids": [requirement_id],
            "related_issue_ids": [issue_id], "evidence_references": [],
            "status": "pending", "supersedes_id": None}}])

        page = intent_ledger.ledger_read(self.root, limit=3)
        self.assertEqual(page["collections"]["requirements"]["items"][0]["status"], "pending")
        active_requirement = page["collections"]["active_requirements"]["items"][0]
        self.assertEqual(active_requirement["authority_verification"], "verified")
        self.assertEqual(active_requirement["claim_provenance"]["classification"], "asserted_claim")
        self.assertEqual(page["collections"]["issues"]["items"][0]["status"], "open")
        attempts = page["collections"]["repair_attempts"]["items"]
        outcomes = {item["attempted_operation_id"]: item for item in attempts}
        self.assertEqual(outcomes[failed_op["operation_id"]]["outcome_at_recording"]["disposition"], "candidate")
        self.assertEqual(outcomes[failed_op["operation_id"]]["current_reconciled_outcome"]["policy_status"], "blocked")
        self.assertEqual(outcomes[geometry_op["operation_id"]]["current_reconciled_outcome"]["construction_status"], "construction_passed")
        decision = page["collections"]["decisions"]["items"][0]
        self.assertEqual(decision["evidence_reference_ids"], [source_ref])
        self.assertEqual(decision["claim_provenance"]["evidence_references"][0]["content_hash"],
            initial["source_references"][0]["content_hash"])
        all_instructions = intent_ledger.ledger_read(self.root, limit=100)["collections"]["instructions"]["items"]
        self.assertEqual(all_instructions[-1]["text"], fixture["events"][9]["instruction"])
        pending_actions = intent_ledger.ledger_read(self.root, limit=100)["collections"]["active_next_actions"]["items"]
        self.assertTrue(any(action["status"] == "pending" and "Flash" in action["description"]
            for action in pending_actions))
        self.assertGreater(page["revision_chain"]["count"], 10)
        self.assertFalse(page["revision_chain"]["complete"])
        next_page = intent_ledger.ledger_read(self.root, offset=3, limit=3)
        self.assertEqual(len(next_page["revision_chain"]["items"]), 3)
        self.assertEqual(next_page["revision_chain"]["count"], page["revision_chain"]["count"])
        historical = intent_ledger.ledger_read(self.root, revision_id=first_event["revision_id"], limit=5)
        self.assertEqual(len(historical["collections"]["requirements"]["items"]), 1)
        self.assertEqual(historical["collections"]["issues"]["count"], 0)


if __name__ == "__main__": unittest.main()
