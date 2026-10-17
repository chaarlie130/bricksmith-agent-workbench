import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bricksmith.workbench.acceptance import CHECK_NAMES, _check, make_acceptance_report


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/acceptance"


class AcceptanceTests(unittest.TestCase):
    def passing_workflow(self, model):
        return {
            "stage_models": [model, model, model],
            "inspected_views": ["front_left", "front_right"],
        }

    def test_rejects_collision_fixture_and_reports_all_actual_failures(self):
        model = FIXTURES / "collision.ldr"
        with tempfile.TemporaryDirectory() as tmp, patch(
            "bricksmith.workbench.acceptance._render",
            side_effect=lambda _ldr, out, _az: {"path": str(out), "status": "rendered"},
        ):
            report = make_acceptance_report(
                model, ground_y=0, render_dir=Path(tmp), **self.passing_workflow(model)
            )
        self.assertFalse(report["accepted"])
        self.assertGreater(report["piece_count"], 0)
        self.assertEqual(set(report["construction"]["checks"]), set(CHECK_NAMES))
        self.assertEqual(report["construction"]["status"], "failed")
        self.assertFalse(report["construction"]["checks"]["mesh_collision_free"])
        self.assertFalse(report["construction"]["checks"]["included_base"])
        self.assertFalse(report["construction"]["checks"]["actual_connectivity"])
        self.assertFalse(report["workflow"]["major_stages_validated"])
        self.assertFalse(report["workflow"]["major_stages_progressed"])
        self.assertTrue(report["workflow"]["two_final_views_rendered"])
        self.assertTrue(report["workflow"]["two_final_views_inspected"])

    def test_accepts_known_passing_fixture_only_with_workflow_evidence(self):
        model = FIXTURES / "pass.ldr"
        with tempfile.TemporaryDirectory() as tmp, patch(
            "bricksmith.workbench.acceptance._render",
            side_effect=lambda _ldr, out, _az: {"path": str(out), "status": "rendered"},
        ) as mocked_render, patch("bricksmith.workbench.acceptance._check") as mocked_check:
            stages = []
            for index in range(1, 4):
                stage = Path(tmp) / f"stage-{index}.ldr"
                stage.write_text("0 stage\n" + "1 15 0 0 0 1 0 0 0 1 0 0 0 1 3005.dat\n" * index)
                stages.append(stage)
            mocked_check.side_effect = lambda _path, _ground: {
                "status": "passed", "checks": {name: True for name in CHECK_NAMES}, "errors": []
            }
            report = make_acceptance_report(
                model, ground_y=8, min_pieces=1, max_pieces=2,
                render_dir=Path(tmp), stage_models=stages,
                inspected_views=["front_left", "front_right"],
            )
            self.assertEqual([call.args[2] for call in mocked_render.call_args_list], [215.0, 325.0])
        self.assertTrue(report["accepted"])
        self.assertEqual(report["piece_count"], 1)
        self.assertEqual(report["construction"]["status"], "passed")
        self.assertEqual(report["construction"]["checks"], {name: True for name in CHECK_NAMES})

    def test_piece_budget_and_distinct_stages_are_required(self):
        model = FIXTURES / "pass.ldr"
        with tempfile.TemporaryDirectory() as tmp, patch(
            "bricksmith.workbench.acceptance._render",
            side_effect=lambda _ldr, out, _az: {"path": str(out), "status": "rendered"},
        ):
            report = make_acceptance_report(
                model, ground_y=8, render_dir=Path(tmp), **self.passing_workflow(model)
            )
        self.assertFalse(report["accepted"])
        self.assertFalse(report["workflow"]["piece_target_met"])
        self.assertFalse(report["workflow"]["major_stages_progressed"])

    def test_missing_check_is_unavailable_and_never_accepted(self):
        with patch("bricksmith.workbench.acceptance.check_model", return_value={
            "passed": False, "checks": {}, "errors": [{"kind": "environment_error"}],
        }), tempfile.TemporaryDirectory() as tmp, patch(
            "bricksmith.workbench.acceptance._render",
            side_effect=lambda _ldr, out, _az: {"path": str(out), "status": "rendered"},
        ):
            report = make_acceptance_report(
                FIXTURES / "floating.ldr",
                ground_y=0, render_dir=Path(tmp), **self.passing_workflow(
                    FIXTURES / "floating.ldr"
                )
            )
        self.assertFalse(report["accepted"])
        self.assertEqual(report["construction"]["status"], "unavailable")
        self.assertTrue(all(v is None for v in report["construction"]["checks"].values()))


if __name__ == "__main__":
    unittest.main()
