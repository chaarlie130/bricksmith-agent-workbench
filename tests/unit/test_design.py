import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
import uuid
from decimal import Decimal, localcontext
from pathlib import Path
from types import SimpleNamespace

from bricksmith.workbench.design import (
    DESIGN_SCHEMA, SESSION_SCHEMA, DesignError, _json_text, export_design,
    file_hash, import_ldr, inspect_design, load_design, load_line_map,
    load_session_v2_design, migrate_v1_session, move_parts, recolor_parts,
    refresh_hashes, validate_design, write_design,
)

ROOT = Path(__file__).resolve().parents[2]
TINY = ROOT / "tests/fixtures/design/tiny.ldr"
CATALOG = SimpleNamespace(
    stem_to_id={"3005": 1, "3024": 2, "3004": 3},
    id_to_stem={1: "3005", 2: "3024", 3: "3004"},
    code_to_color={15: "white", 71: "light bluish gray", 4: "red"},
)


def imported_tiny():
    return import_ldr(TINY, catalog=CATALOG)


def placement_line(part="3005.dat", color=15, x="0", y="0", z="0", matrix=None):
    matrix = matrix or ["1", "0", "0", "0", "1", "0", "0", "0", "1"]
    return "1 " + str(color) + " " + " ".join([x, y, z, *matrix, part])


def _tree_bytes(root: Path):
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*")) if path.is_file()}


def _legacy_session(root: Path, *, disagreement=False):
    (root / "modules").mkdir(parents=True)
    base = "0 base note\n" + placement_line(y="-8") + "\n"
    upper = "0 upper note\n" + placement_line("3024.dat", 71, x="20", y="-32") + "\n"
    (root / "modules/base.ldr").write_text(base)
    (root / "modules/upper.ldr").write_text(upper)
    build = "0 Legacy assembled export\n" + placement_line(y="-8") + "\n"
    build += placement_line("3024.dat", 71, x="40" if disagreement else "20", y="-32") + "\n"
    (root / "build.ldr").write_text(build)
    state = {"schema": "bricksmith-agent-session-v1", "brief": "Tiny migration fixture",
        "ground_y": 8.0, "target_pieces": "2–4", "model": "fixture-model",
        "reference_image": None, "module_order": ["base", "upper"],
        "plan": "Historical plan prose only.", "history": [{"role": "user", "content": "old"}],
        "events": [{"usage": {"input_tokens": 12, "output_tokens": 5, "total_tokens": 17}}],
        "last_validation": {"passed": True}, "submitted_design": {"accepted": True},
        "operator_extension": {"opaque": "retained by source hash, explicitly unmigrated"}}
    (root / "state.json").write_text(json.dumps(state, indent=2) + "\n")
    return state


class DesignContractTests(unittest.TestCase):
    def test_duplicate_physical_placements_remain_distinct(self):
        design = imported_tiny()
        self.assertEqual(len(design["parts"]), 3)
        self.assertNotEqual(design["parts"][0]["id"], design["parts"][1]["id"])
        one_copy = copy.deepcopy(design)
        one_copy["parts"] = one_copy["parts"][:1]
        refresh_hashes(one_copy)
        self.assertNotEqual(design["hashes"]["appearance"]["value"],
                            one_copy["hashes"]["appearance"]["value"])
        self.assertNotEqual(design["hashes"]["structure"]["value"],
                            one_copy["hashes"]["structure"]["value"])

    def test_reordering_comments_and_numeric_formatting_do_not_change_physical_hashes(self):
        first = "0 first comment\n" + placement_line(x="1", y="-0.0") + "\n"
        first += placement_line("3024.dat", 71, x="1.000000", y="-8.0",
                                matrix=["-1.0", "0", "0", "0", "1", "0", "0", "0", "-1"]) + "\n"
        second = "  0 second explanatory comment\n"
        second += "1 71 1 -8 0 -1 0 0 0 1.0 0 0 0 -1.0 3024.dat\n"
        second += "0 first comment\n1 15 1.0 0 0 1.0 0 0 0 1 0 0 0 1.0 3005.dat\n"
        a = import_ldr(first, catalog=CATALOG)
        b = import_ldr(second, catalog=CATALOG)
        self.assertEqual(a["hashes"]["appearance"]["value"], b["hashes"]["appearance"]["value"])
        self.assertEqual(a["hashes"]["structure"]["value"], b["hashes"]["structure"]["value"])

    def test_recolor_and_move_semantics_keep_stable_ids(self):
        design = imported_tiny()
        selected = design["parts"][0]["id"]
        recolored = recolor_parts(design, [selected], 4, catalog=CATALOG)
        self.assertEqual(recolored["parts"][0]["id"], selected)
        self.assertEqual(design["hashes"]["structure"]["value"], recolored["hashes"]["structure"]["value"])
        self.assertNotEqual(design["hashes"]["appearance"]["value"], recolored["hashes"]["appearance"]["value"])
        moved = move_parts(design, [selected], dx=Decimal("0.0000000000001"), catalog=CATALOG)
        self.assertEqual(moved["parts"][0]["id"], selected)
        self.assertNotEqual(design["hashes"]["structure"]["value"], moved["hashes"]["structure"]["value"])
        self.assertNotEqual(design["hashes"]["appearance"]["value"], moved["hashes"]["appearance"]["value"])
        self.assertEqual(design["parts"][0]["translation_ldu"][0], Decimal("0"))

    def test_move_parts_addition_is_exact_under_low_decimal_context(self):
        exact_x = Decimal("1.00000000000000000000000000001")
        design = import_ldr(placement_line(x=str(exact_x)) + "\n", catalog=CATALOG)
        original_hash = design["hashes"]["appearance"]["value"]
        original_id = design["parts"][0]["id"]
        with localcontext() as context:
            context.prec = 5
            zero_move = move_parts(design, [original_id], catalog=CATALOG)
            self.assertEqual(zero_move["parts"][0]["translation_ldu"][0], exact_x)
            self.assertEqual(zero_move["hashes"]["appearance"]["value"], original_hash)
            tiny_delta = Decimal("0.00000000000000000000000000001")
            tiny_move = move_parts(design, [original_id], dx=tiny_delta, catalog=CATALOG)
            expected = Decimal("1.00000000000000000000000000002")
            self.assertEqual(tiny_move["parts"][0]["translation_ldu"][0], expected)
            self.assertEqual(tiny_move["parts"][0]["id"], original_id)
            restored = move_parts(tiny_move, [original_id], dx=-tiny_delta, catalog=CATALOG)
            self.assertEqual(restored["parts"][0]["translation_ldu"][0], exact_x)
            self.assertEqual(restored["hashes"]["appearance"]["value"], original_hash)
            self.assertEqual(design["parts"][0]["translation_ldu"][0], exact_x)
        with tempfile.TemporaryDirectory() as tmp:
            moved_path = Path(tmp) / "moved.json"
            write_design(moved_path, tiny_move, catalog=CATALOG)
            loaded = load_design(moved_path, catalog=CATALOG)
            bundle = Path(tmp) / "export"
            export_design(loaded, bundle, catalog=CATALOG)
            reparsed = import_ldr(bundle / "build.ldr", catalog=CATALOG)
            self.assertEqual(reparsed["parts"][0]["translation_ldu"][0], expected)
            self.assertEqual(reparsed["hashes"]["appearance"]["value"],
                             loaded["hashes"]["appearance"]["value"])

    def test_persisted_comments_must_be_single_strict_type_zero_lines(self):
        invalid_comments = [
            "0 source note\n 1 15 100 0 0 1 0 0 0 1 0 0 0 1 3005.dat",
            "0 FILE hidden.ldr", "0 NOFILE", "0 !DATA payload.dat", "0 !: inline.ldr",
            "00 malformed prefix", "0FILE malformed prefix", " 1 not a comment",
        ]
        separators = "\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029"
        invalid_comments.extend(f"0 comment{separator}1 injected" for separator in separators)
        for text in invalid_comments:
            with self.subTest(text=repr(text)):
                design = imported_tiny()
                design["source_comments"][0]["text"] = text
                refresh_hashes(design)
                with self.assertRaises(DesignError):
                    validate_design(design, catalog=CATALOG)
                with tempfile.TemporaryDirectory() as tmp:
                    with self.assertRaises(DesignError):
                        write_design(Path(tmp) / "invalid.json", design, catalog=CATALOG)
                    self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_json_decimal_roundtrip_export_and_hash_remain_lossless(self):
        text = placement_line(x="0.0000000000001") + "\n"
        design = import_ldr(text, catalog=CATALOG)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "design.json"
            write_design(path, design, catalog=CATALOG)
            loaded = load_design(path, catalog=CATALOG)
            self.assertEqual(loaded["parts"][0]["translation_ldu"][0], Decimal("0.0000000000001"))
            output = Path(tmp) / "export"
            export_design(loaded, output, catalog=CATALOG)
            exported = (output / "build.ldr").read_text()
            self.assertIn("1e-13", exported)
            reparsed = import_ldr(exported, catalog=CATALOG)
            self.assertEqual(reparsed["hashes"]["appearance"]["value"],
                             loaded["hashes"]["appearance"]["value"])
            changed = import_ldr(placement_line(x="0.0000000000002") + "\n", catalog=CATALOG)
            self.assertNotEqual(loaded["hashes"]["appearance"]["value"],
                                changed["hashes"]["appearance"]["value"])
        self.assertEqual(_json_text(Decimal("1.0"), indent=None), "1")
        self.assertEqual(_json_text(Decimal("-0.000"), indent=None), "0")

    def test_orthonormal_reflection_and_stated_tolerance(self):
        valid = import_ldr(placement_line(matrix=["-1", "0", "0", "0", "1", "0", "0", "0", "-1"]) + "\n",
                           catalog=CATALOG)
        validate_design(valid, catalog=CATALOG)
        within = placement_line(matrix=["1.0000004", "0", "0", "0", "1", "0", "0", "0", "1"])
        import_ldr(within + "\n", catalog=CATALOG)
        outside = placement_line(matrix=["1.0000006", "0", "0", "0", "1", "0", "0", "0", "1"])
        with self.assertRaisesRegex(DesignError, "orthonormal"):
            import_ldr(outside + "\n", catalog=CATALOG)

    def test_bad_ids_ownership_cycles_references_and_numeric_values_rejected(self):
        cases = []
        value = imported_tiny(); value["parts"][1]["id"] = value["parts"][0]["id"]; refresh_hashes(value); cases.append(value)
        value = imported_tiny(); value["parts"][0]["assembly_id"] = str(uuid.uuid4()); refresh_hashes(value); cases.append(value)
        value = imported_tiny(); value["assemblies"][0]["parent_assembly_id"] = value["assemblies"][0]["id"]; refresh_hashes(value); cases.append(value)
        value = imported_tiny(); value["parts"][0]["translation_ldu"] = [Decimal("NaN"), 0, 0]; cases.append(value)
        value = imported_tiny(); value["parts"][0]["rotation"] = [[1, 0], [0, 1], [0, 0]]; refresh_hashes(value); cases.append(value)
        value = imported_tiny(); value["parts"][0]["rotation"] = [[2, 0, 0], [0, 1, 0], [0, 0, 1]]; refresh_hashes(value); cases.append(value)
        value = imported_tiny(); value["parts"][0]["rotation"] = [[1, Decimal("0.01"), 0], [0, 1, 0], [0, 0, 1]]; refresh_hashes(value); cases.append(value)
        for item in cases:
            with self.subTest(item=item):
                with self.assertRaises(DesignError):
                    validate_design(item, catalog=CATALOG)

    def test_flat_import_rejects_unresolved_and_unsupported_records_with_lines(self):
        invalid = [
            ("0 title\n2 16 0 0 0 1 1 1\n", "type-2"),
            ("0 title\n3 16 0 0 0 1 0 0 0 1 0\n", "type-3"),
            ("0 title\n4 geometry\n", "type-4"),
            ("0 title\n5 geometry\n", "type-5"),
            ("0 FILE sub.ldr\n", "MPD"),
            ("0 NOFILE\n", "MPD"),
            ("0 !DATA name\n", "MPD"),
            ("0 title\n1 15 0 0 0 1 0 0 0 1 0 0 0 1 submodel.ldr\n", r"\.ldr"),
            ("0 title\n1 999 0 0 0 1 0 0 0 1 0 0 0 1 3005.dat\n", "color"),
            ("0 title\n1 15 0 0 0 1 0 0 0 1 0 0 0 1 missing.dat\n", "part"),
            ("0 title\n1 15 0 0 0 1 0 0 0 1 0 0 0 1 3005.dat extra\n", "15 fields"),
            ("0 title\n1 15 NaN 0 0 1 0 0 0 1 0 0 0 1 3005.dat\n", "decimal"),
        ]
        for source, error in invalid:
            with self.subTest(source=source):
                with self.assertRaisesRegex(DesignError, error):
                    import_ldr(source, catalog=CATALOG, source_name="fixture.ldr")
        with self.assertRaisesRegex(DesignError, "fixture.ldr:2"):
            import_ldr("0 header\n2 bad\n", catalog=CATALOG, source_name="fixture.ldr")

    def test_catalog_unavailable_is_not_an_empty_success(self):
        with self.assertRaisesRegex(DesignError, "catalog is unavailable"):
            import_ldr("0 empty\n", catalog=SimpleNamespace(stem_to_id={}, code_to_color={}))

    def test_generic_relationships_requirements_decisions_issues_and_locks_validate(self):
        design = imported_tiny()
        assembly = design["assemblies"][0]
        part = design["parts"][0]
        root_id = assembly["id"]
        child_id = str(uuid.uuid4())
        assembly["relationships"].append({"id": str(uuid.uuid4()), "kind": "adjacent_to",
            "target_assembly_id": child_id, "source": "user", "assertion": "asserted only"})
        assembly["field_locks"].append({"id": str(uuid.uuid4()), "owner": "user",
            "target_id": part["id"], "fields": ["translation_ldu"]})
        design["assemblies"].append({"id": child_id, "name": "detail", "role": None,
            "parent_assembly_id": root_id, "design_properties": {}, "relationships": [], "field_locks": []})
        requirement_id = str(uuid.uuid4())
        design["requirements"].append({"id": requirement_id, "description": "Keep the entrance visible",
            "source": "user", "priority": "mandatory", "affected_assembly_ids": [child_id],
            "measurable_predicate": None, "evidence_reference_ids": [], "status": "unverified"})
        decision_id = str(uuid.uuid4())
        design["decisions"].append({"id": decision_id, "statement": "Use a compact frame",
            "rationale": "Small test fixture", "source": "agent", "related_assembly_ids": [root_id],
            "related_requirement_ids": [requirement_id], "evidence_reference_ids": [],
            "supersedes_id": None, "status": "active"})
        design["issues"].append({"id": str(uuid.uuid4()), "kind": "unknown_support",
            "affected_ids": [part["id"], requirement_id], "first_observation_revision_id": design["revision_id"],
            "last_observation_revision_id": design["revision_id"], "evidence_reference_ids": [],
            "attempted_operation_ids": [], "status": "open", "next_proposed_action": "inspect"})
        refresh_hashes(design)
        validate_design(design, catalog=CATALOG)
        selected = inspect_design(design, assembly_ids=[root_id, child_id], catalog=CATALOG)
        self.assertEqual(selected["piece_count"], len(design["parts"]))
        self.assertEqual(len(selected["selected_part_ids"]), len(set(selected["selected_part_ids"])))

    def test_selector_unknowns_and_line_map_export_binding(self):
        design = imported_tiny()
        with self.assertRaisesRegex(DesignError, "Unknown part selector"):
            inspect_design(design, part_ids=[str(uuid.uuid4())], catalog=CATALOG)
        with self.assertRaisesRegex(DesignError, "Unknown assembly selector"):
            inspect_design(design, assembly_ids=[str(uuid.uuid4())], catalog=CATALOG)
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            export_design(design, bundle, catalog=CATALOG)
            mapping = load_line_map(bundle / "line_map.json")
            exact_hash = hashlib.sha256((bundle / "build.ldr").read_bytes()).hexdigest()
            inspected = inspect_design(design, assembly_ids=[design["assemblies"][0]["id"]],
                line_map=mapping, export_path="build.ldr", export_sha256=exact_hash,
                catalog=CATALOG)
            self.assertEqual(len(inspected["export_lines"]), len(design["parts"]))
            self.assertEqual(inspected["export_identity"]["file_sha256"], exact_hash)
            with self.assertRaisesRegex(DesignError, "file hash"):
                inspect_design(design, line_map=mapping, export_path="build.ldr", export_sha256="0" * 64,
                               catalog=CATALOG)
            lines = (bundle / "build.ldr").read_text().splitlines()
            line_records = mapping["exports"]["build.ldr"]["placements"]
            self.assertEqual(len(line_records), sum(line.startswith("1 ") for line in lines))
            for entry in line_records:
                self.assertTrue(lines[entry["line"] - 1].startswith("1 "))
                self.assertIn(entry["part_id"], {part["id"] for part in design["parts"]})
                self.assertIn(entry["assembly_id"], {assembly["id"] for assembly in design["assemblies"]})
            with self.assertRaises(FileExistsError):
                export_design(design, bundle)

    def test_line_map_rejects_forged_lines_ids_ownership_coverage_and_shapes(self):
        design = imported_tiny()
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            export_design(design, bundle, catalog=CATALOG)
            valid = load_line_map(bundle / "line_map.json")
            export_hash = hashlib.sha256((bundle / "build.ldr").read_bytes()).hexdigest()

            def inspect(mapping):
                return inspect_design(design, line_map=mapping, export_path="build.ldr",
                    export_sha256=export_hash, catalog=CATALOG)

            self.assertEqual(inspect(valid)["piece_count"], 3)
            bad_maps = []
            changed = copy.deepcopy(valid)
            changed["exports"]["build.ldr"]["placements"][0]["line"] = 999
            bad_maps.append(changed)
            changed = copy.deepcopy(valid)
            placements = changed["exports"]["build.ldr"]["placements"]
            placements[0]["part_id"], placements[2]["part_id"] = placements[2]["part_id"], placements[0]["part_id"]
            bad_maps.append(changed)
            changed = copy.deepcopy(valid)
            changed["exports"]["build.ldr"]["placements"][0]["assembly_id"] = str(uuid.uuid4())
            bad_maps.append(changed)
            changed = copy.deepcopy(valid)
            changed["exports"]["build.ldr"]["placements"].pop()
            bad_maps.append(changed)
            changed = copy.deepcopy(valid)
            placements = changed["exports"]["build.ldr"]["placements"]
            placements.append(copy.deepcopy(placements[0]))
            bad_maps.append(changed)
            changed = copy.deepcopy(valid)
            changed["revision_id"] = str(uuid.uuid4())
            bad_maps.append(changed)
            changed = copy.deepcopy(valid)
            changed["exports"]["build.ldr"]["file_sha256"] = "0" * 64
            bad_maps.append(changed)
            changed = copy.deepcopy(valid)
            changed["exports"]["build.ldr"]["placements"][0] = []
            bad_maps.append(changed)
            changed = copy.deepcopy(valid)
            changed["exports"]["build.ldr"]["placements"][0]["line"] = True
            bad_maps.append(changed)
            for mapping in bad_maps:
                with self.subTest(mapping=mapping):
                    with self.assertRaises(DesignError):
                        inspect(mapping)

            assembly_id = design["assemblies"][0]["id"]
            module_key = f"modules/{assembly_id}.ldr"
            module_hash = hashlib.sha256((bundle / module_key).read_bytes()).hexdigest()
            module_view = inspect_design(design, assembly_ids=[assembly_id], line_map=valid,
                export_path=module_key, export_sha256=module_hash, catalog=CATALOG)
            self.assertEqual(module_view["piece_count"], 3)

            multi = imported_tiny()
            second_assembly = str(uuid.uuid4())
            multi["assemblies"].append({"id": second_assembly, "name": "second", "role": None,
                "parent_assembly_id": None, "design_properties": {}, "relationships": [], "field_locks": []})
            moved_part_id = multi["parts"][0]["id"]
            multi["parts"][0]["assembly_id"] = second_assembly
            refresh_hashes(multi)
            multi_bundle = Path(tmp) / "multi-bundle"
            export_design(multi, multi_bundle, catalog=CATALOG)
            multi_map = load_line_map(multi_bundle / "line_map.json")
            multi_hash = hashlib.sha256((multi_bundle / "build.ldr").read_bytes()).hexdigest()
            wrong_owner = copy.deepcopy(multi_map)
            target = next(row for row in wrong_owner["exports"]["build.ldr"]["placements"]
                          if row["part_id"] == moved_part_id)
            target["assembly_id"] = multi["assemblies"][0]["id"]
            with self.assertRaisesRegex(DesignError, "does not own"):
                inspect_design(multi, line_map=wrong_owner, export_path="build.ldr",
                    export_sha256=multi_hash, catalog=CATALOG)

    def test_migration_is_deterministic_inert_and_preserves_source_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "v1"
            root.mkdir()
            state = _legacy_session(root)
            before = _tree_bytes(root)
            migrated_a = Path(tmp) / "migrated-a"
            migrated_b = Path(tmp) / "migrated-b"
            result_a = migrate_v1_session(root, migrated_a, catalog=CATALOG)
            result_b = migrate_v1_session(root, migrated_b, catalog=CATALOG)
            self.assertEqual(before, _tree_bytes(root))
            for key in ("session_id", "revision_id", "source_content_identity", "design_hash",
                        "appearance_hash", "structure_hash"):
                self.assertEqual(result_a[key], result_b[key])
            self.assertEqual(result_a["piece_count"], 2)
            design = load_session_v2_design(migrated_a, catalog=CATALOG)
            self.assertEqual(design["brief"], state["brief"])
            self.assertEqual(design["ground_y"], Decimal("8.0"))
            self.assertEqual(design["piece_range"], {"minimum": Decimal("2"), "maximum": Decimal("4")})
            self.assertEqual(len(design["historical_notes"]), 1)
            self.assertEqual(design["historical_notes"][0]["status"], "historical_unverified")
            session_state = json.loads((migrated_a / "state.json").read_text())
            self.assertEqual(session_state["schema"], SESSION_SCHEMA)
            self.assertEqual(session_state["run_state"], "paused")
            self.assertTrue(session_state["read_only"])
            self.assertFalse(session_state["execution_enabled"])
            self.assertEqual(session_state["pending_image_ids"], [])
            self.assertEqual(session_state["cumulative_usage"], {"input_tokens": 12, "output_tokens": 5, "total_tokens": 17})
            manifest = json.loads((migrated_a / "manifest.json").read_text())
            self.assertIn("submitted_design", manifest["migration"]["unmigrated_fields"])
            self.assertIn("operator_extension", manifest["migration"]["unmigrated_fields"])
            self.assertEqual(manifest["migration"]["field_dispositions"]["plan"],
                             "retained_as_historical_unverified_prose")
            line_map = load_line_map(migrated_a / "revisions" / result_a["revision_id"] / "line_map.json")
            self.assertEqual(len(line_map["exports"]["build.ldr"]["placements"]), 2)

    def test_migration_refuses_duplicate_missing_escaped_and_disagreeing_sources_cleanly(self):
        for mode in ("duplicate", "missing", "escape", "disagree"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "v1"
                root.mkdir()
                _legacy_session(root, disagreement=mode == "disagree")
                state_path = root / "state.json"
                state = json.loads(state_path.read_text())
                if mode == "duplicate":
                    state["module_order"] = ["base", "base"]
                elif mode == "missing":
                    (root / "modules/upper.ldr").unlink()
                elif mode == "escape":
                    state["module_order"] = ["../outside"]
                state_path.write_text(json.dumps(state))
                destination = Path(tmp) / "new-session"
                with self.assertRaises(DesignError):
                    migrate_v1_session(root, destination, catalog=CATALOG)
                self.assertFalse(destination.exists())
                self.assertFalse(list(Path(tmp).glob(".new-session.*")))

    def test_migration_refuses_existing_or_inside_source_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "v1"
            root.mkdir()
            _legacy_session(root)
            inside = root / "nested" / "v2"
            with self.assertRaisesRegex(DesignError, "inside the source"):
                migrate_v1_session(root, inside, catalog=CATALOG)
            existing = Path(tmp) / "existing"
            existing.mkdir()
            with self.assertRaises(FileExistsError):
                migrate_v1_session(root, existing, catalog=CATALOG)
            self.assertEqual(list(existing.iterdir()), [])

    def test_migration_reports_external_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "v1"
            outside = Path(tmp) / "outside.ldr"
            root.mkdir()
            _legacy_session(root)
            outside.write_text(placement_line() + "\n")
            (root / "modules/base.ldr").unlink()
            (root / "modules/base.ldr").symlink_to(outside)
            with self.assertRaisesRegex(DesignError, "escapes|Symlinked"):
                migrate_v1_session(root, Path(tmp) / "dest", catalog=CATALOG)


if __name__ == "__main__":
    unittest.main()
