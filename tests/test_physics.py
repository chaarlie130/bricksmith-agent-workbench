import unittest
from pathlib import Path
from bricksmith.physics.validator import validate_ldraw

ROOT = Path(__file__).resolve().parents[1]


class TestPhysicsValidator(unittest.TestCase):

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


if __name__ == "__main__":
    unittest.main()
