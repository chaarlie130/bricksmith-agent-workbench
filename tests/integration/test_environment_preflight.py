"""Real local geometry/render checks; run through the integration command."""
import unittest

from bricksmith.workbench.provenance import preflight
from bricksmith.workbench.agent_session import TOOLS
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch


class EnvironmentIntegrationTests(unittest.TestCase):
    def test_serialized_tool_schema_matches_runtime(self):
        schema = Path(__file__).resolve().parents[2] / "bricksmith/workbench/tool_schema.json"
        self.assertEqual(json.loads(schema.read_text(encoding="utf-8")), TOOLS)

    def test_preflight_cli_reports_missing_site_packages(self):
        root = Path(__file__).resolve().parents[2]
        run = subprocess.run([sys.executable, "-S", str(root / "scripts/workbench.py"),
                              "preflight", "--no-real-check"], cwd=root,
                             capture_output=True, text=True, check=False)
        self.assertEqual(run.returncode, 3, run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual(result["checks"]["status"], "unavailable", result)
        self.assertFalse(result["checks"]["dependencies"]["numpy"]["imported"], result)

    def test_real_checker_and_renderer_available(self):
        report = preflight(real_check=True)
        self.assertEqual(report["checks"]["status"], "passed", report)
        self.assertEqual(report["checks"]["real_check"]["status"], "passed", report)
        self.assertEqual(report["checks"]["real_render"]["status"], "passed", report)

    def test_catalog_and_mesh_failures_are_unavailable(self):
        with patch("bricknet.data.load_catalog", side_effect=RuntimeError("catalog unavailable")):
            report = preflight(real_check=False)
        self.assertEqual(report["checks"]["catalog"]["status"], "unavailable", report)
        self.assertEqual(report["checks"]["status"], "unavailable", report)
        with patch("bricknet.collision._mesh", side_effect=RuntimeError("mesh unavailable")):
            report = preflight(real_check=False)
        self.assertEqual(report["checks"]["mesh"]["status"], "unavailable", report)
        self.assertEqual(report["checks"]["status"], "unavailable", report)

    def test_renderer_failure_and_incomplete_check_remain_unavailable(self):
        with patch("bricksmith.rendering.rasterizer.render_ldr_to_png",
                   side_effect=RuntimeError("renderer unavailable")):
            report = preflight(real_check=True)
        self.assertEqual(report["checks"]["real_render"]["status"], "unavailable", report)
        self.assertEqual(report["checks"]["status"], "unavailable", report)
        with patch("bricksmith.workbench.feedback.check_model", return_value={"checks": {}, "passed": False}):
            report = preflight(real_check=True)
        self.assertEqual(report["checks"]["real_check"]["status"], "unavailable", report)
        self.assertEqual(report["checks"]["status"], "unavailable", report)


if __name__ == "__main__":
    unittest.main()
