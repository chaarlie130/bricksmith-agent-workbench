import unittest
from pathlib import Path
from bricksmith.physics.validator import validate_ldraw

ROOT = Path(__file__).resolve().parents[1]


class TestPhysicsValidator(unittest.TestCase):

    def test_plate_built_base_suggests_alternate_ground_plane(self):
        model = ("1 0 -20 -8 0 1 0 0 0 1 0 0 0 1 3022.dat\n"
                 "1 0 20 -8 0 1 0 0 0 1 0 0 0 1 3022.dat\n")
        report = validate_ldraw(model)
        error = next(error for error in report["errors"]
                     if error["kind"] == "no_ground_baseplate")
        self.assertEqual(error["candidate_ground_y_ldu"], 0.0)
        self.assertFalse(report["checks"]["included_base"])

    def test_misplaced_baseplate_is_reported_below_ground(self):
        wrong = ("1 2 0 8 0 1 0 0 0 1 0 0 0 1 3811.dat\n"
                 "1 70 0 0 0 1 0 0 0 1 0 0 0 1 3022.dat\n")
        report = validate_ldraw(wrong)
        self.assertFalse(report["checks"]["no_parts_below_ground"])
        self.assertIn("parts_below_ground", [error["kind"] for error in report["errors"]])
        correct = wrong.replace("1 2 0 8 0", "1 2 0 0 0").replace("1 70 0 0 0", "1 70 0 -8 0")
        fixed = validate_ldraw(correct)
        self.assertTrue(fixed["checks"]["no_parts_below_ground"])
        self.assertTrue(fixed["checks"]["approximate_gravity_equilibrium"])

    def test_reference_model_validation(self):
        sample_model = ROOT / "data/reference_sets/ldr/bricksafe_21002_Empire_State_Building.ldr"
        if not sample_model.exists():
            self.skipTest("Reference model not found")

        report = validate_ldraw(sample_model)
        self.assertTrue(report.get("passed"), f"Validation failed with errors: {report.get('errors')}")
        self.assertEqual(report.get("physical_piece_count"), 77)
        self.assertTrue(report["checks"]["mesh_collision_free"])
        self.assertTrue(report["checks"]["included_base"])
        self.assertTrue(report["checks"]["actual_connectivity"])
        self.assertTrue(report["checks"]["approximate_gravity_equilibrium"])

    def test_gravity_failure_identifies_unsupported_part(self):
        floating = ("1 2 0 0 0 1 0 0 0 1 0 0 0 1 3811.dat\n"
                    "1 15 0 -88 0 1 0 0 0 1 0 0 0 1 3022.dat\n")
        report = validate_ldraw(floating)
        gravity = next(error for error in report["errors"]
                       if error["kind"] == "gravity_equilibrium_infeasible")
        self.assertFalse(report["checks"]["approximate_gravity_equilibrium"])
        self.assertIn(1, gravity["details"]["suspect_part_indices"])
        self.assertGreater(gravity["details"]["balance_slack_total"], 0)


if __name__ == "__main__":
    unittest.main()
