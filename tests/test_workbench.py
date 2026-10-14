import tempfile
import unittest
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from bricksmith.workbench.feedback import check_model
from bricksmith.workbench.omr import _parse_results, fetch_omr_file
from bricksmith.workbench.prompt import SYSTEM_PROMPT_PATH, load_system_prompt
from bricksmith.workbench.references import inspect_model, inspect_reference_region, load_references, search, study_reference


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
            "1 15 0 -32 0 1 0 0 0 1 0 0 0 1 3937.dat\n"
        )

    def test_search_and_provenance(self):
        refs = load_references(self.corpus)
        results = search(refs, "modern glass house terrace")
        self.assertEqual(results[0]["id"], "omr_21009-1_Farnsworth_House")
        self.assertEqual(results[0]["piece_count"], 2)
        self.assertEqual(results[0]["license"], "CC BY 4.0")
        self.assertIn("house", results[0]["matched_query_terms"])
        self.assertGreater(results[0]["query_coverage"], 0)
        self.assertEqual(len(results[0]["sha256"]), 64)
        self.assertIsNone(next(ref for ref in refs if "Sears" in ref.id).license)
        self.assertEqual(search(refs, "impossible phrase zzzyyy"), [])
        hinge = search(refs, "hinge")
        self.assertEqual(hinge[0]["id"], "omr_21000-1_Sears_Tower")
        self.assertEqual(hinge[0]["matched_part_families"], ["hinge"])

    def test_inspect_is_bounded_and_numbered(self):
        path = self.corpus / "omr_21009-1_Farnsworth_House.ldr"
        excerpt = inspect_model(path, start=3, count=1)
        self.assertEqual(excerpt["excerpt"][0]["line"], 3)
        self.assertEqual(len(excerpt["excerpt"]), 1)
        with self.assertRaises(ValueError):
            inspect_model(path, count=201)

    def test_study_reference_sorts_placements_by_height(self):
        path = self.corpus / "omr_21009-1_Farnsworth_House.ldr"
        result = study_reference(path, "overview")
        self.assertEqual(result["piece_count"], 2)
        self.assertEqual([p["h_plates"] for p in result["placements"]], [1, 4])
        self.assertEqual(result["height_layers"][1]["parts"], 1)
        self.assertEqual(result["placements"][0]["line"], 3)

    def test_region_inspection_is_spatial_bounded_and_source_linked(self):
        path = self.corpus / "omr_21009-1_Farnsworth_House.ldr"
        result = inspect_reference_region(path, -1, 1, -1, 1, 3, 5)
        self.assertEqual(result["total_matches"], 1)
        self.assertEqual(result["placements"][0]["line"], 4)
        self.assertIn("3004.dat", result["placements"][0]["text"])
        self.assertEqual(result["license"], "CC BY 4.0")
        self.assertEqual(len(result["sha256"]), 64)
        first = inspect_reference_region(path, -1, 1, -1, 1, 0, 5, count=1)
        self.assertEqual(first["total_matches"], 2)
        self.assertEqual(first["next_offset"], 1)
        second = inspect_reference_region(path, -1, 1, -1, 1, 0, 5, offset=1, count=1)
        self.assertEqual(second["placements"][0]["line"], 4)
        self.assertIsNone(second["next_offset"])
        with self.assertRaisesRegex(ValueError, "minimum"):
            inspect_reference_region(path, 2, 1, -1, 1, 0, 5)
        with self.assertRaisesRegex(ValueError, "count"):
            inspect_reference_region(path, -1, 1, -1, 1, 0, 5, count=61)

    def test_collision_indices_are_mapped_to_source_lines(self):
        path = self.corpus / "omr_21009-1_Farnsworth_House.ldr"
        fake_report = {"passed": False, "checks": {}, "errors": [
            {"kind": "mesh_collision", "pairs": [(0, 1)]},
            {"kind": "disconnected_assembly", "component_sizes": [1, 1],
             "component_members": [[0], [1]]},
            {"kind": "gravity_equilibrium_infeasible",
             "details": {"suspect_part_indices": [1]}},
        ]}
        with patch("bricksmith.workbench.feedback.validate_ldraw", return_value=fake_report):
            result = check_model(path)
        self.assertEqual(result["errors"][0]["line_pairs"], [[3, 4]])
        self.assertEqual(result["errors"][1]["component_line_samples"], [[3], [4]])
        self.assertEqual(result["errors"][2]["suspect_line_samples"],
                         [{"line": 4, "text": path.read_text().splitlines()[3]}])
        self.assertIn("Assembly order", result["limitations"][1])

    def test_canonical_prompt_documents_and_exposes_tools(self):
        prompt = load_system_prompt()
        self.assertEqual(prompt, SYSTEM_PROMPT_PATH.read_text(encoding="utf-8"))
        for command in ("search", "inspect", "check", "search_omr_sets", "fetch_omr_set"):
            self.assertIn(command, prompt)
        self.assertIn('"passed": false', prompt)
        self.assertIn("assembly order", prompt.lower())
        script = Path(__file__).resolve().parents[1] / "scripts/workbench.py"
        output = subprocess.run([sys.executable, str(script), "prompt"],
                                capture_output=True, text=True, check=True)
        self.assertEqual(output.stdout, prompt)


class OmrTests(unittest.TestCase):
    """Parsing tests against a trimmed sample of the real Livewire search
    response markup, captured from library.ldraw.org, without hitting the
    network in CI."""

    SAMPLE_RESULT_HTML = """
        <div wire:key="group-omr-models">
            <a href="https://library.ldraw.org/omr/sets/74" wire:key="item-74">
                <img src="https://library.ldraw.org/media/omr_models/80/conversions/21006-1-thumb.png" />
                <p class="text-sm font-semibold text-gray-900 truncate">The White House</p>
                <p class="text-xs font-mono text-gray-500 truncate">21006-1</p>
            </a>
        </div>
    """

    def test_parse_results_extracts_model_number_and_title(self):
        results = _parse_results(self.SAMPLE_RESULT_HTML)
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result.model_id, "74")
        self.assertEqual(result.title, "The White House")
        self.assertEqual(result.model_number, "21006-1")
        self.assertTrue(result.thumbnail_url.endswith("21006-1-thumb.png"))

    def test_fetch_omr_file_rejects_malformed_model_number(self):
        with self.assertRaises(ValueError):
            fetch_omr_file("../etc/passwd")


if __name__ == "__main__":
    unittest.main()
