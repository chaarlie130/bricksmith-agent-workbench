import tempfile
import unittest
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from bricksmith.workbench.feedback import check_model
from bricksmith.workbench.prompt import SYSTEM_PROMPT_PATH, load_system_prompt
from bricksmith.workbench.references import inspect_model, load_references, search


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.corpus = Path(self.temp.name)
        (self.corpus / "omr_21009-1_Farnsworth_House.ldr").write_text(
            "0 Farnsworth House\n0 !LICENSE CC BY 4.0\n"
            "1 15 0 -8 0 1 0 0 0 1 0 0 0 1 3031.dat\n"
            "1 47 0 -32 0 1 0 0 0 1 0 0 0 1 3004.dat\n"
        )
        (self.corpus / "omr_21000-1_Sears_Tower.ldr").write_text(
            "0 Sears Tower\n1 0 0 -8 0 1 0 0 0 1 0 0 0 1 3031.dat\n"
        )

    def test_search_and_provenance(self):
        refs = load_references(self.corpus)
        results = search(refs, "modern glass house terrace")
        self.assertEqual(results[0]["id"], "omr_21009-1_Farnsworth_House")
        self.assertEqual(results[0]["piece_count"], 2)
        self.assertEqual(results[0]["license"], "CC BY 4.0")
        self.assertEqual(len(results[0]["sha256"]), 64)
        self.assertIsNone(next(ref for ref in refs if "Sears" in ref.id).license)
        self.assertEqual(search(refs, "impossible phrase zzzyyy"), [])

    def test_inspect_is_bounded_and_numbered(self):
        path = self.corpus / "omr_21009-1_Farnsworth_House.ldr"
        excerpt = inspect_model(path, start=3, count=1)
        self.assertEqual(excerpt["excerpt"][0]["line"], 3)
        self.assertEqual(len(excerpt["excerpt"]), 1)
        with self.assertRaises(ValueError):
            inspect_model(path, count=201)

    def test_collision_indices_are_mapped_to_source_lines(self):
        path = self.corpus / "omr_21009-1_Farnsworth_House.ldr"
        fake_report = {"passed": False, "checks": {}, "errors": [
            {"kind": "mesh_collision", "pairs": [(0, 1)]},
        ]}
        with patch("bricksmith.workbench.feedback.validate_ldraw", return_value=fake_report):
            result = check_model(path)
        self.assertEqual(result["errors"][0]["line_pairs"], [[3, 4]])
        self.assertIn("Assembly order", result["limitations"][1])

    def test_canonical_prompt_documents_and_exposes_tools(self):
        prompt = load_system_prompt()
        self.assertEqual(prompt, SYSTEM_PROMPT_PATH.read_text(encoding="utf-8"))
        for command in ("search", "inspect", "check"):
            self.assertIn(command, prompt)
        self.assertIn('"passed": false', prompt)
        self.assertIn("assembly order", prompt.lower())
        script = Path(__file__).resolve().parents[1] / "scripts/workbench.py"
        output = subprocess.run([sys.executable, str(script), "prompt"],
                                capture_output=True, text=True, check=True)
        self.assertEqual(output.stdout, prompt)


if __name__ == "__main__":
    unittest.main()
