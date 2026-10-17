import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bricksmith.workbench.design import _decimal_text, _json_text, import_ldr, load_design, refresh_hashes, sha256_bytes

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/design/tiny.ldr"


def run_cli(*args):
    return subprocess.run([sys.executable, "scripts/workbench.py", *map(str, args)],
        cwd=ROOT, check=True, capture_output=True, text=True)


class DesignCliIntegrationTests(unittest.TestCase):
    def test_actual_cli_import_inspect_export_and_line_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            design_path = root / "tiny.design.json"
            imported = run_cli("design-import", FIXTURE, design_path, "--brief", "CLI fixture",
                "--ground-y", "8", "--minimum-pieces", "1", "--maximum-pieces", "20")
            import_result = json.loads(imported.stdout)
            self.assertEqual(import_result["piece_count"], 3)
            design = load_design(design_path)
            first_part = design["parts"][0]["id"]
            inspected = json.loads(run_cli("design-inspect", design_path,
                "--part-id", first_part).stdout)
            self.assertEqual(inspected["piece_count"], 1)
            self.assertEqual(inspected["selected_part_ids"], [first_part])

            bundle = root / "export-bundle"
            run_cli("design-export", design_path, bundle)
            build = bundle / "build.ldr"
            mapping_path = bundle / "line_map.json"
            line_inspection = json.loads(run_cli("design-inspect", design_path,
                "--line-map", mapping_path, "--export-file", build).stdout)
            exported = import_ldr(build)
            self.assertEqual(exported["hashes"]["appearance"]["value"],
                             design["hashes"]["appearance"]["value"])
            line_map = json.loads(mapping_path.read_text())
            entries = line_map["exports"]["build.ldr"]["placements"]
            ldr_lines = build.read_text().splitlines()
            self.assertEqual(len(entries), 3)
            self.assertEqual(len(line_inspection["export_lines"]), 3)
            self.assertEqual(line_inspection["export_identity"]["file_sha256"],
                             sha256_bytes(build.read_bytes()))
            ordered_parts = sorted(design["parts"], key=lambda part: (part["assembly_id"], part["id"]))
            for index, entry in enumerate(entries):
                self.assertTrue(ldr_lines[entry["line"] - 1].startswith("1 "))
                part = ordered_parts[index]
                self.assertEqual(entry["part_id"], part["id"])
                self.assertEqual(entry["assembly_id"], part["assembly_id"])
                physical_fields = ldr_lines[entry["line"] - 1].split()
                self.assertEqual(physical_fields[1], str(part["color_id"]))
                self.assertEqual(physical_fields[14], part["ldraw_part_reference"])
                self.assertEqual(physical_fields[2:14], [_decimal_text(value) for value in (
                    *part["translation_ldu"], *(value for row in part["rotation"] for value in row))])
            stale = subprocess.run([sys.executable, "scripts/workbench.py", "design-inspect",
                str(design_path), "--line-map", str(mapping_path), "--export-file", str(build),
                "--export-key", "build.ldr"], cwd=ROOT, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(stale.stdout)["piece_count"], 3)

            forged_map = json.loads(mapping_path.read_text())
            forged_map["exports"]["build.ldr"]["placements"][0]["line"] = 999
            forged_path = root / "forged-line-map.json"
            forged_path.write_text(json.dumps(forged_map))
            rejected = subprocess.run([sys.executable, "scripts/workbench.py", "design-inspect",
                str(design_path), "--line-map", str(forged_path), "--export-file", str(build)],
                cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("placements", rejected.stderr)

    def test_actual_cli_export_rejects_multiline_and_mpd_persisted_comments(self):
        for comment in (
            "0 source note\n 1 15 100 0 0 1 0 0 0 1 0 0 0 1 3005.dat",
            "0 FILE hidden.ldr",
        ):
            with self.subTest(comment=comment), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                design = import_ldr(FIXTURE)
                design["source_comments"][0]["text"] = comment
                refresh_hashes(design)
                source = root / "invalid-design.json"
                source.write_text(_json_text(design, indent=2) + "\n")
                destination = root / "must-not-publish"
                result = subprocess.run([sys.executable, "scripts/workbench.py", "design-export",
                    str(source), str(destination)], cwd=ROOT, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(destination.exists())

    def test_actual_cli_migrates_to_a_new_read_only_v2_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "v1"
            (source / "modules").mkdir(parents=True)
            geometry = "1 15 0 -8 0 1 0 0 0 1 0 0 0 1 3024.dat\n"
            (source / "modules/base.ldr").write_text(geometry)
            (source / "build.ldr").write_text("0 assembled\n" + geometry)
            state = {"schema": "bricksmith-agent-session-v1", "brief": "CLI migration",
                "ground_y": 8, "target_pieces": "1-3", "module_order": ["base"], "plan": "old plan"}
            (source / "state.json").write_text(json.dumps(state))
            destination = Path(tmp) / "migrated"
            result = json.loads(run_cli("design-migrate", source, destination).stdout)
            self.assertEqual(result["piece_count"], 1)
            migrated_state = json.loads((destination / "state.json").read_text())
            self.assertEqual(migrated_state["schema"], "bricksmith-agent-session-v2")
            self.assertTrue(migrated_state["read_only"])
            self.assertTrue((destination / "revisions" / result["revision_id"] / "line_map.json").is_file())


if __name__ == "__main__":
    unittest.main()
