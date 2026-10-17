from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import tempfile
import time
import unittest
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from bricksmith.workbench import design, revisions, transactions, transaction_tools
from bricksmith.workbench.agent_session import _tool

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / ".venv/bin/python"
FIXTURE = ROOT / "tests/fixtures/acceptance/pass.ldr"

CHILD_DISPATCH = r'''import json, os, sys
from pathlib import Path
from bricksmith.workbench import design, revisions, transactions, transaction_tools
from bricksmith.workbench.agent_session import _tool
root = Path(sys.argv[1]); call = json.loads(Path(sys.argv[2]).read_text()); target = sys.argv[3]
def fake(value, workdir, label, validator=None):
    build, placements = design._export_text(value)
    checks = {key: True for key in transactions.CHECKS}
    raw = {"passed": True, "checks": checks, "errors": [],
        "diagnostics": {"below_ground_indices_complete_flag": True, "below_ground_indices_complete": []},
        "physical_piece_count": len(placements)}
    return {"schema": "bricksmith-transaction-validation-v1", "raw_report": raw,
        "evaluation": transactions._interpret_report(raw, placements),
        "export_sha256": __import__("hashlib").sha256(build).hexdigest(),
        "design_hash": value["hashes"]["design"]["value"]}
transactions._run_validation = fake
transactions._evaluation_environment_identity = lambda: {"synthetic": True}
transactions._data_identity = lambda: "a" * 64
transaction_tools._ADAPTER_FAILPOINT = lambda phase: os._exit(77) if phase == target else None
_tool(root, revisions.read_state(root), call["tool_name"], call["arguments"], invocation_context=call)
'''

CHILD_RENDER = r'''import json, os, sys
from pathlib import Path
from unittest.mock import patch
from bricksmith.workbench import transaction_tools, revisions
from bricksmith.workbench.agent_session import _tool
from bricksmith.rendering import rasterizer
root = Path(sys.argv[1]); call = json.loads(Path(sys.argv[2]).read_text()); target = sys.argv[3]
def fake_renderer(source, output, **kwargs):
    Path(output).write_bytes(b"subprocess fake png")
    marker = Path(sys.argv[1], "evidence", "renders", call["operation_id"] + ".renderer_called")
    with marker.open("ab") as stream: stream.write(b"x")
transaction_tools._ADAPTER_FAILPOINT = lambda phase: os._exit(78) if phase == target else None
with patch.object(rasterizer, "render_ldr_to_png", side_effect=fake_renderer):
    _tool(root, revisions.read_state(root), call["tool_name"], call["arguments"], invocation_context=call)
'''


class M2BReviewRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.temp_root = Path(self.temp.name)

    def initialize(self, name: str, value: dict | None = None) -> tuple[Path, dict]:
        if value is None:
            value = design.import_ldr(FIXTURE, ground_y=8)
        root = self.temp_root / name
        revisions.initialize(root, value)
        return root, value

    def invocation(self, root: Path, tool: str, args: dict) -> dict:
        state = revisions.read_state(root)
        revision = revisions.load_revision(root, state["current_revision_id"])
        build = (revisions.revision_dir(root, revision["revision_id"]) / "build.ldr").read_bytes()
        return {"schema": transactions.ADAPTER_INVOCATION_SCHEMA, "tool_name": tool,
            "arguments": copy.deepcopy(args), "operation_id": str(uuid.uuid4()),
            "expected_base_revision_id": revision["revision_id"],
            "expected_export_sha256": hashlib.sha256(build).hexdigest()}

    def cli_dispatch(self, root: Path, call: dict) -> dict:
        return _tool(root, revisions.read_state(root), call["tool_name"], call["arguments"], invocation_context=call)

    def child(self, root: Path, call: dict, failpoint: str, code: str = CHILD_DISPATCH) -> subprocess.CompletedProcess:
        call_path = self.temp_root / f"call-{uuid.uuid4()}.json"
        call_path.write_text(design._json_text(call))
        env = dict(os.environ, BRICKNET_DATA=str(ROOT / "data/bricknet-data"))
        return subprocess.run([str(PYTHON), "-c", code, str(root), str(call_path), failpoint],
            cwd=ROOT, env=env, capture_output=True, text=True)

    def synthetic_parent(self):
        def fake(value, workdir, label, validator=None):
            build, placements = design._export_text(value)
            checks = {key: True for key in transactions.CHECKS}
            raw = {"passed": True, "checks": checks, "errors": [],
                "diagnostics": {"below_ground_indices_complete_flag": True, "below_ground_indices_complete": []},
                "physical_piece_count": len(placements)}
            return {"schema": "bricksmith-transaction-validation-v1", "raw_report": raw,
                "evaluation": transactions._interpret_report(raw, placements),
                "export_sha256": hashlib.sha256(build).hexdigest(),
                "design_hash": value["hashes"]["design"]["value"]}
        return (patch("bricksmith.workbench.transactions._run_validation", side_effect=fake),
            patch("bricksmith.workbench.transactions._evaluation_environment_identity", return_value={"synthetic": True}),
            patch("bricksmith.workbench.transactions._data_identity", return_value="a" * 64))

    def test_subprocess_death_recovery_for_80_part_save_and_multimodule_move(self):
        sample = next(line for line in FIXTURE.read_text().splitlines() if line.startswith("1 "))
        root, source = self.initialize("save-80")
        args = {"name": "eighty", "ldr": (sample + "\n") * 80}
        call = self.invocation(root, "save_module", args)
        dead = self.child(root, call, "after_candidate_seal")
        self.assertEqual(dead.returncode, 77, dead.stderr)
        with self.synthetic_parent()[0], self.synthetic_parent()[1], self.synthetic_parent()[2]:
            transactions.recover(root)
            staged = self.cli_dispatch(root, call)
            self.assertEqual(staged["disposition"], "candidate")
            self.assertFalse(staged["committed"])
            receipt = transactions.commit_candidate(root, call["operation_id"], staged["candidate_id"])
            current = revisions.load_revision(root, receipt["revision_id"])
            new_assembly = next(item for item in current["assemblies"] if item["name"] == "eighty")
            self.assertEqual(sum(part["assembly_id"] == new_assembly["id"] for part in current["parts"]), 80)
            replay = self.cli_dispatch(root, call)
            self.assertTrue(replay["committed"])
            self.assertEqual(replay["operation_revision_id"], receipt["revision_id"])
            self.assertEqual(len(replay["affected_ids"]), len(set(replay["affected_ids"])))

        multi = design.import_ldr(FIXTURE, ground_y=8)
        first = multi["parts"][0]
        second_assembly = copy.deepcopy(multi["assemblies"][0])
        second_assembly.update({"id": str(uuid.uuid4()), "name": "second-module"})
        second = copy.deepcopy(first)
        second.update({"id": str(uuid.uuid4()), "assembly_id": second_assembly["id"],
                       "translation_ldu": [Decimal(100), Decimal(0), Decimal(0)]})
        multi["assemblies"].append(second_assembly); multi["parts"].append(second)
        design.refresh_hashes(multi); design.validate_design(multi)
        move_root, _ = self.initialize("move-multimodule", multi)
        revision = revisions.load_revision(move_root, revisions.read_state(move_root)["current_revision_id"])
        line_map = design.load_line_map(revisions.revision_dir(move_root, revision["revision_id"]) / "line_map.json")
        placements = line_map["exports"]["build.ldr"]["placements"]
        line_a = next(item["line"] for item in placements if item["part_id"] == first["id"])
        line_b = next(item["line"] for item in placements if item["part_id"] == second["id"])
        move_args = {"groups": [{"lines": [line_a], "dx": 20, "dy": 0, "dz": 0},
                                 {"lines": [line_b], "dx": 0, "dy": 0, "dz": 20}]}
        move_call = self.invocation(move_root, "move_groups", move_args)
        dead = self.child(move_root, move_call, "after_pointer_publication")
        self.assertEqual(dead.returncode, 77, dead.stderr)
        with self.synthetic_parent()[0], self.synthetic_parent()[1], self.synthetic_parent()[2]:
            transactions.recover(move_root)
            replay = self.cli_dispatch(move_root, move_call)
        self.assertTrue(replay["committed"])
        current = revisions.load_revision(move_root, replay["current_revision_id"])
        moved_first = next(part for part in current["parts"] if part["id"] == first["id"])
        moved_second = next(part for part in current["parts"] if part["id"] == second["id"])
        self.assertEqual(moved_first["translation_ldu"][0], Decimal(20))
        self.assertEqual(moved_second["translation_ldu"][2], Decimal(20))
        self.assertEqual(len(current["parts"]), 2)
        self.assertEqual(len(revisions.read_state(move_root)["receipts"]), 1)

    def test_subprocess_death_before_report_recovers_aborted_adapter_outcome(self):
        sample = next(line for line in FIXTURE.read_text().splitlines() if line.startswith("1 "))
        root, source = self.initialize("abort-before-report")
        args = {"name": "interrupted-before-candidate", "ldr": sample + "\n"}
        call = self.invocation(root, "save_module", args)
        dead = self.child(root, call, "after_intent_flush")
        self.assertEqual(dead.returncode, 77, dead.stderr)
        transactions.recover(root)
        with self.synthetic_parent()[0], self.synthetic_parent()[1], self.synthetic_parent()[2]:
            result = self.cli_dispatch(root, call)
        self.assertEqual(result["disposition"], "aborted")
        self.assertFalse(result["committed"])
        self.assertNotIn("commit_eligible", result)
        self.assertEqual(revisions.read_state(root)["current_revision_id"], source["revision_id"])

    def test_render_subprocess_interruption_before_and_after_atomic_publication(self):
        root, _ = self.initialize("render-interrupt")
        before_call = self.invocation(root, "render", {"view": "front_left"})
        dead = self.child(root, before_call, "render_before_publish", CHILD_RENDER)
        self.assertEqual(dead.returncode, 78, dead.stderr)
        with patch("bricksmith.rendering.rasterizer.render_ldr_to_png",
                   side_effect=lambda src, out, **kw: Path(out).write_bytes(b"recovered render")) as renderer:
            before = self.cli_dispatch(root, before_call)
            self.assertEqual(renderer.call_count, 1)
        image = root / before["render_path"]
        before_hash = hashlib.sha256(image.read_bytes()).hexdigest()
        self.assertEqual(before_hash, before["render_sha256"])

        after_call = self.invocation(root, "render", {"view": "top"})
        dead = self.child(root, after_call, "render_after_publish", CHILD_RENDER)
        self.assertEqual(dead.returncode, 78, dead.stderr)
        with patch("bricksmith.rendering.rasterizer.render_ldr_to_png", side_effect=AssertionError("rerendered")) as renderer:
            after = self.cli_dispatch(root, after_call)
            renderer.assert_not_called()
        self.assertEqual(after["render_sha256"], hashlib.sha256((root / after["render_path"]).read_bytes()).hexdigest())
        self.assertEqual(before_hash, hashlib.sha256(image.read_bytes()).hexdigest())

    def test_render_reservation_rejects_changed_invocation_after_subprocess_death(self):
        for index, phase in enumerate(("render_after_reservation",
                                       "render_after_image_before_metadata",
                                       "render_before_publish")):
            with self.subTest(phase=phase):
                root, _ = self.initialize(f"render-reservation-{index}")
                call = self.invocation(root, "render", {"view": "front_left"})
                dead = self.child(root, call, phase, CHILD_RENDER)
                self.assertEqual(dead.returncode, 78, dead.stderr)
                render_root = root / "evidence" / "renders"
                reservation = render_root / f"{call['operation_id']}.reservation.json"
                self.assertTrue(reservation.is_file())
                before = {item.relative_to(render_root).as_posix():
                    hashlib.sha256(item.read_bytes()).hexdigest()
                    for item in render_root.rglob("*") if item.is_file()}
                renderer_marker = render_root / f"{call['operation_id']}.renderer_called"
                marker_before = renderer_marker.read_bytes() if renderer_marker.exists() else b""
                changed = copy.deepcopy(call)
                changed["arguments"] = {"view": "top"}
                call_path = self.temp_root / f"mismatch-{uuid.uuid4()}.json"
                call_path.write_text(design._json_text(changed))
                mismatch = subprocess.run([str(PYTHON), "-c", CHILD_RENDER,
                    str(root), str(call_path), "never"], cwd=ROOT,
                    env=dict(os.environ, BRICKNET_DATA=str(ROOT / "data/bricknet-data")),
                    capture_output=True, text=True)
                self.assertNotEqual(mismatch.returncode, 0)
                after = {item.relative_to(render_root).as_posix():
                    hashlib.sha256(item.read_bytes()).hexdigest()
                    for item in render_root.rglob("*") if item.is_file()}
                self.assertEqual(after, before)
                self.assertEqual(renderer_marker.read_bytes() if renderer_marker.exists() else b"", marker_before)
                recovered = self.child(root, call, "never", CHILD_RENDER)
                self.assertEqual(recovered.returncode, 0, recovered.stderr)
                self.assertEqual(renderer_marker.read_bytes(), marker_before + b"x")
                self.assertTrue((render_root / call["operation_id"] / "metadata.json").is_file())
                self.assertTrue(reservation.is_file())

    def test_render_artifact_lock_excludes_a_competing_process(self):
        root, _ = self.initialize("render-lock")
        ready = self.temp_root / "writer-ready"
        holder_code = r'''import sys, time
from pathlib import Path
from bricksmith.workbench.revisions import writer_lock
root=Path(sys.argv[1]); ready=Path(sys.argv[2])
with writer_lock(root):
 ready.write_text("locked")
 time.sleep(8)
'''
        env = dict(os.environ, BRICKNET_DATA=str(ROOT / "data/bricknet-data"))
        process = subprocess.Popen([str(PYTHON), "-c", holder_code, str(root), str(ready)],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline: time.sleep(0.05)
            self.assertTrue(ready.exists(), "competing writer did not acquire the workspace lock")
            call = self.invocation(root, "render", {"view": "front_left"})
            with self.assertRaises(revisions.RevisionError): self.cli_dispatch(root, call)
        finally:
            process.terminate(); process.communicate(timeout=5)


if __name__ == "__main__": unittest.main()
