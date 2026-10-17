"""Real checker outcomes for the original M0 fixture categories."""
import unittest
from pathlib import Path

from bricksmith.workbench.feedback import check_model

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/acceptance"
CHECKS = ("mesh_collision_free", "included_base", "no_parts_below_ground",
          "actual_connectivity", "approximate_gravity_equilibrium")


class FixtureIntegrationTests(unittest.TestCase):
    def check(self, name):
        report = check_model(FIXTURES / f"{name}.ldr", ground_y=8)
        self.assertEqual(set(report["checks"]), set(CHECKS), report)
        return report

    def test_supported_fixture_passes_all_checks(self):
        report = self.check("pass")
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["checks"], dict.fromkeys(CHECKS, True))

    def test_collision_fixture_reports_collision_but_ground_support(self):
        report = self.check("collision")
        self.assertEqual(report["checks"], {"mesh_collision_free": False, "included_base": True,
            "no_parts_below_ground": True, "actual_connectivity": False,
            "approximate_gravity_equilibrium": True}, report)

    def test_floating_fixture_has_ground_base_but_is_disconnected(self):
        report = self.check("floating")
        self.assertEqual(report["checks"], {"mesh_collision_free": True, "included_base": True,
            "no_parts_below_ground": True, "actual_connectivity": False,
            "approximate_gravity_equilibrium": False}, report)

    def test_below_ground_fixture_reports_below_ground(self):
        report = self.check("below_ground")
        self.assertEqual(report["checks"], {"mesh_collision_free": True, "included_base": False,
            "no_parts_below_ground": False, "actual_connectivity": True,
            "approximate_gravity_equilibrium": False}, report)


if __name__ == "__main__":
    unittest.main()
