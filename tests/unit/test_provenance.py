import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stderr, redirect_stdout

from bricksmith.workbench.provenance import (
    SCHEMA, _bricknet_identity, _records_sha256, _source_fingerprint, hash_tree, manifest_identity, publish_manifest,
    manifest_capture_complete, preflight, validate_manifest,
)


def valid_manifest():
    source_files = [{"path": "bricksmith/sample.py", "sha256": "a" * 64}]
    package_files = [{"path": "src/bricknet/__init__.py", "sha256": "4" * 64}]
    catalog_files = [{"path": ".", "type": "directory", "size": 0},
                     {"path": "catalog.json", "type": "file", "size": 2, "sha256": "5" * 64}]
    return {"schema": SCHEMA, "run_id": "x", "created_at": "2026-10-15T00:00:00Z",
        "brief_sha256": "a" * 64, "generation_source": {
            "baseline_commit": "abc", "baseline_source_sha256": "b" * 64,
            "instrumentation_dirty": True,
            "source_manifest": {"files": source_files, "content_sha256": _records_sha256(source_files),
                "dirty_patch_sha256": "d" * 64, "dirty_paths": [],
                "fingerprint_complete": True, "omitted_paths": []}},
        "prompt_sha256": "e" * 64, "tool_schema_sha256": "f" * 64,
        "source_hashes": {"renderer": "1" * 64, "checker": "2" * 64,
                          "implementation_manifest": _records_sha256(source_files)},
        "provider": None, "model": None, "settings": {}, "execution_track": "offline-provenance",
        "environment": {"python": "3.14", "packages": {}, "bricknet_source": {
            "available": True,
            "version": "0.1", "vcs_commit": "abc", "vcs_dirty": False,
            "source_files": package_files, "source_content_sha256": _records_sha256(package_files),
            "catalog_data": {"available": True, "path": "/package/_data/v1", "files": catalog_files,
                "content_sha256": _records_sha256(catalog_files), "error": None}}},
        "libraries": {"ldraw": {"configured_path": "/one/ldraw", "resolved_path": "/one/ldraw",
            "content_sha256": "5" * 64, "fingerprint_complete": True},
            "bricknet_data": {"configured_path": "/one/data", "resolved_path": "/one/data",
            "content_sha256": "6" * 64, "fingerprint_complete": True}},
        "corpus": {"manifest_sha256": "7" * 64, "content_sha256": "8" * 64},
        "input_provenance": [], "budgets": {}}


def complete_manifest():
    value = valid_manifest()
    value["environment"]["packages"] = {name: "1.0" for name in
        ("bricknet", "meshlib", "numpy", "scipy", "matplotlib", "pillow")}
    value["libraries"]["ldraw"]["fingerprint_complete"] = True
    value["libraries"]["bricknet_data"]["fingerprint_complete"] = True
    value["corpus"].update(manifest_sha256="7" * 64, content_sha256="8" * 64)
    value["source_hashes"].update(renderer="1" * 64, checker="2" * 64,
        implementation_manifest=value["generation_source"]["source_manifest"]["content_sha256"])
    value["capture_status"] = "complete"
    return value


class ProvenanceTests(unittest.TestCase):
    def test_identity_ignores_run_and_absolute_library_locations(self):
        first = valid_manifest()
        second = copy.deepcopy(first)
        second["run_id"] = "elsewhere"
        second["created_at"] = "2030-01-01T00:00:00Z"
        second["libraries"]["ldraw"]["configured_path"] = "/different/checkout/ldraw"
        second["libraries"]["ldraw"]["resolved_path"] = "/different/checkout/ldraw"
        second["libraries"]["bricknet_data"]["configured_path"] = "/different/checkout/data"
        second["libraries"]["bricknet_data"]["resolved_path"] = "/different/checkout/data"
        self.assertEqual(manifest_identity(first), manifest_identity(second))

    def test_identity_detects_content_changes(self):
        base = valid_manifest()
        for mutate in (
            lambda m: m.update(prompt_sha256="9" * 64),
            lambda m: m["libraries"]["ldraw"].update(content_sha256="9" * 64),
            lambda m: m["source_hashes"].update(renderer="9" * 64),
        ):
            changed = copy.deepcopy(base)
            mutate(changed)
            self.assertNotEqual(manifest_identity(base), manifest_identity(changed))

    def test_source_content_identity_detects_same_status_content_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "bricksmith" / "sample.py"
            source.parent.mkdir(parents=True)
            source.write_text("value = 'baseline'\n")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "m0@example.test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "M0 Test"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
            source.write_text("value = 'behavior A'\n")
            a = _source_fingerprint(root)
            source.write_text("value = 'behavior B'\n")
            b = _source_fingerprint(root)
            self.assertEqual(a["dirty_paths"], b["dirty_paths"])
            self.assertNotEqual(a["content_sha256"], b["content_sha256"])
            self.assertNotEqual(a["dirty_patch_sha256"], b["dirty_patch_sha256"])
            subprocess.run(["git", "add", "bricksmith/sample.py"], cwd=root, check=True)
            staged = _source_fingerprint(root)
            source.write_text("value = 'behavior C'\n")
            staged_and_unstaged = _source_fingerprint(root)
            self.assertNotEqual(staged["dirty_patch_sha256"], staged_and_unstaged["dirty_patch_sha256"])

    def test_untracked_runtime_module_bytes_flow_into_full_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "bricksmith/workbench/core.py"
            source.parent.mkdir(parents=True)
            source.write_text("value = 0\n")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "m0@example.test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "M0 Test"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
            helper = root / "bricksmith/workbench/arbitrary_new_runtime_module.py"
            identities = []
            statuses = []
            for contents in ("value = 'A'\n", "value = 'B'\n"):
                helper.write_text(contents)
                fingerprint = _source_fingerprint(root)
                statuses.append(subprocess.run(["git", "status", "--porcelain=v1", "--", "bricksmith"],
                    cwd=root, check=True, capture_output=True, text=True).stdout.strip())
                self.assertIn("bricksmith/workbench/arbitrary_new_runtime_module.py",
                    {item["path"] for item in fingerprint["files"]})
                manifest = valid_manifest()
                manifest["generation_source"]["source_manifest"] = fingerprint
                manifest["source_hashes"]["implementation_manifest"] = fingerprint["content_sha256"]
                identities.append(manifest_identity(manifest))
            self.assertEqual(statuses, ["?? bricksmith/workbench/arbitrary_new_runtime_module.py"] * 2)
            self.assertNotEqual(*identities)

    def test_bricknet_package_json_bytes_flow_into_identity_and_relocate(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "package-a"
            package = root / "src/bricknet"
            data = package / "_data/v1"
            data.mkdir(parents=True)
            package_file = package / "__init__.py"
            package_file.write_text("VERSION = 'fixture'\n")
            (package / "runtime.py").write_text("def run(): return 1\n")
            catalog = data / "catalog.json"
            catalog.write_text('{"part":"plate"}\n')
            (data / "aliases.json").write_text('{"alias":"plate"}\n')
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "m0@example.test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "M0 Test"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
            catalog.write_text('{"part":"plate-modified"}\n')
            identity_a = _bricknet_identity(package_file=package_file, package_data_path=data)
            catalog.write_text('{"part":"brick"}\n')
            identity_b = _bricknet_identity(package_file=package_file, package_data_path=data)
            self.assertEqual(identity_a["vcs_commit"], identity_b["vcs_commit"])
            self.assertEqual(identity_a["vcs_dirty"], identity_b["vcs_dirty"])
            self.assertEqual(identity_a["source_content_sha256"], identity_b["source_content_sha256"])
            self.assertNotEqual(identity_a["catalog_data"]["content_sha256"],
                                identity_b["catalog_data"]["content_sha256"])
            manifest_a, manifest_b = valid_manifest(), valid_manifest()
            manifest_a["environment"]["bricknet_source"] = identity_a
            manifest_b["environment"]["bricknet_source"] = identity_b
            self.assertNotEqual(manifest_identity(manifest_a), manifest_identity(manifest_b))
            relocated = Path(tmp) / "package-b"
            shutil.copytree(root, relocated)
            moved = _bricknet_identity(package_file=relocated / "src/bricknet/__init__.py",
                package_data_path=relocated / "src/bricknet/_data/v1")
            manifest_moved = valid_manifest()
            manifest_moved["environment"]["bricknet_source"] = moved
            self.assertEqual(manifest_identity(manifest_b), manifest_identity(manifest_moved))

    def test_bricknet_collector_marks_missing_python_sources_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            package_data = root / "bricknet/_data/v1"
            package_data.mkdir(parents=True)
            (package_data / "catalog.json").write_text("{}\n")
            identity = _bricknet_identity(package_file=root / "bricknet/__init__.py",
                package_data_path=package_data)
            self.assertFalse(identity["available"])
            self.assertIn("no readable Python source", identity["error"])

    def test_tree_hash_is_relocation_invariant_and_framed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, b = root / "a", root / "b"
            a.mkdir(); b.mkdir()
            (a / "f").write_bytes(b"x\0b\0y")
            (b / "f").write_bytes(b"x")
            (b / "g").write_bytes(b"y")
            c = root / "copy"
            import shutil
            shutil.copytree(a, c)
            self.assertEqual(hash_tree(a), hash_tree(c))
            self.assertNotEqual(hash_tree(a), hash_tree(b))

    def test_symlink_file_and_directory_changes_are_included(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.mkdir()
            (target / "part.dat").write_bytes(b"mesh A")
            linked = root / "linked"
            linked.mkdir()
            (linked / "mesh-link.dat").symlink_to(target / "part.dat")
            (linked / "library-link").symlink_to(target, target_is_directory=True)
            first = hash_tree(linked)
            (target / "part.dat").write_bytes(b"mesh B")
            self.assertNotEqual(first, hash_tree(linked))

    def test_effective_bricknet_data_override_is_fingerprinted(self):
        from bricksmith.workbench.provenance import _effective_library
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "data-a"; first.mkdir(); (first / "catalog").write_bytes(b"A")
            second = Path(tmp) / "data-b"; second.mkdir(); (second / "catalog").write_bytes(b"B")
            with patch.dict(os.environ, {"BRICKNET_DATA": str(first)}):
                a = _effective_library("bricknet_data", root=Path(tmp))
            with patch.dict(os.environ, {"BRICKNET_DATA": str(second)}):
                b = _effective_library("bricknet_data", root=Path(tmp))
            self.assertEqual(a["source"], "BRICKNET_DATA")
            self.assertNotEqual(a["content_sha256"], b["content_sha256"])

    def test_dangling_and_cyclic_links_are_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dangling").symlink_to(root / "absent")
            self.assertIsNone(hash_tree(root))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "child"
            child.mkdir()
            (child / "back").symlink_to(root, target_is_directory=True)
            self.assertIsNone(hash_tree(root))

    def test_invalid_manifest_values_rejected(self):
        candidates = []
        item = valid_manifest(); item["generation_source"] = None; candidates.append(item)
        item = valid_manifest(); item["brief_sha256"] = "not-a-hash"; candidates.append(item)
        item = valid_manifest(); item["settings"] = {"n": float("nan")}; candidates.append(item)
        item = valid_manifest(); item["libraries"]["ldraw"]["content_sha256"] = "bad"; candidates.append(item)
        for item in candidates:
            with self.assertRaises(ValueError):
                validate_manifest(item)

    def test_nested_identity_digests_and_records_are_validated(self):
        candidates = []
        item = complete_manifest(); item["prompt_sha256"] = "not-a-hash"; candidates.append(item)
        item = complete_manifest(); item["environment"]["bricknet_source"]["source_content_sha256"] = "not-a-hash"; candidates.append(item)
        item = complete_manifest(); del item["generation_source"]["source_manifest"]["files"]; candidates.append(item)
        item = complete_manifest(); item["generation_source"]["source_manifest"]["files"][0]["sha256"] = 12; candidates.append(item)
        item = complete_manifest(); item["environment"]["bricknet_source"]["catalog_data"]["files"][1]["sha256"] = "bad"; candidates.append(item)
        for item in candidates:
            with self.subTest(item=item):
                with self.assertRaises(ValueError):
                    validate_manifest(item)
                with self.assertRaises(ValueError):
                    publish_manifest(Path(tempfile.gettempdir()) / "must-not-publish-malformed-m0.json", item)

    def test_complete_capture_requires_bricknet_source_and_package_data_files(self):
        cases = []
        item = complete_manifest()
        bricknet = item["environment"]["bricknet_source"]
        bricknet["source_files"] = []
        bricknet["source_content_sha256"] = _records_sha256([])
        cases.append(("empty BrickNet source files", item))

        item = complete_manifest()
        bricknet = item["environment"]["bricknet_source"]
        root_only = [{"path": ".", "type": "directory", "size": 0}]
        bricknet["catalog_data"]["files"] = root_only
        bricknet["catalog_data"]["content_sha256"] = _records_sha256(root_only)
        cases.append(("directory-only package data", item))

        for label, item in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    validate_manifest(item)
                target = Path(tmp) / "must-not-exist.json"
                with self.assertRaises(ValueError):
                    publish_manifest(target, item)
                self.assertFalse(target.exists())

    def test_untrusted_enum_types_raise_value_error_and_incomplete_records_remain_valid(self):
        for malformed in ([], {}):
            item = complete_manifest()
            item["environment"]["bricknet_source"]["catalog_data"]["files"][1]["type"] = malformed
            with self.subTest(tree_type=malformed), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "must-not-exist.json"
                with self.assertRaises(ValueError):
                    validate_manifest(item)
                with self.assertRaises(ValueError):
                    publish_manifest(target, item)
                self.assertFalse(target.exists())

            item = complete_manifest()
            item["capture_status"] = malformed
            with self.subTest(capture_status=malformed), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "must-not-exist.json"
                with self.assertRaises(ValueError):
                    validate_manifest(item)
                with self.assertRaises(ValueError):
                    publish_manifest(target, item)
                self.assertFalse(target.exists())

        item = complete_manifest()
        self.assertTrue(manifest_capture_complete(item))
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "complete.json"
            publish_manifest(target, item)
            self.assertTrue(target.is_file())

        unavailable = valid_manifest()
        unavailable["environment"]["bricknet_source"] = {"available": False,
            "error": "BrickNet unavailable"}
        unavailable["capture_status"] = "incomplete"
        validate_manifest(unavailable)
        self.assertFalse(manifest_capture_complete(unavailable))
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "incomplete.json"
            publish_manifest(target, unavailable)
            self.assertTrue(target.is_file())

        unavailable_data = valid_manifest()
        package_data = unavailable_data["environment"]["bricknet_source"]["catalog_data"]
        package_data.update(available=False, content_sha256=None, files=[], error="data missing")
        unavailable_data["capture_status"] = "incomplete"
        validate_manifest(unavailable_data)
        self.assertFalse(manifest_capture_complete(unavailable_data))

    def test_null_prompt_is_valid_only_as_incomplete_capture(self):
        item = valid_manifest()
        item["prompt_sha256"] = None
        item["capture_status"] = "incomplete"
        validate_manifest(item)
        self.assertFalse(manifest_capture_complete(item))
        item["capture_status"] = "complete"
        with self.assertRaises(ValueError):
            validate_manifest(item)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                publish_manifest(Path(tmp) / "bad.json", item)
            self.assertFalse((Path(tmp) / "bad.json").exists())

    def test_export_no_clobber_and_validation_preserves_existing_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.json"
            path.write_bytes(b"previous evidence\n")
            with self.assertRaises(FileExistsError):
                publish_manifest(path, valid_manifest())
            self.assertEqual(path.read_bytes(), b"previous evidence\n")
            invalid = valid_manifest(); invalid["tool_schema_sha256"] = "invalid"
            with self.assertRaises(ValueError):
                publish_manifest(path, invalid)
            self.assertEqual(path.read_bytes(), b"previous evidence\n")

    def test_real_cli_entry_point_refuses_overwrite(self):
        script = Path(__file__).resolve().parents[2] / "scripts/workbench.py"
        spec = importlib.util.spec_from_file_location("workbench_cli", script)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "existing.json"
            target.write_bytes(b"keep me\n")
            with patch.object(sys, "argv", ["workbench.py", "baseline-export", str(target)]), \
                 patch.object(cli, "build_manifest", return_value=valid_manifest()), \
                 redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(), 2)
            self.assertEqual(target.read_bytes(), b"keep me\n")

    def test_cli_marks_incomplete_fingerprint_as_incomplete(self):
        script = Path(__file__).resolve().parents[2] / "scripts/workbench.py"
        spec = importlib.util.spec_from_file_location("workbench_cli_incomplete", script)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "manifest.json"
            with patch.object(sys, "argv", ["workbench.py", "baseline-export", str(target)]), \
                 patch.object(cli, "build_manifest", return_value=valid_manifest()), \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(), 0)
            exported = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(exported["capture_status"], "incomplete")

    def test_preflight_reports_missing_imports_and_no_real_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("ldraw", "bricknet-data"):
                (root / "data" / name).mkdir(parents=True)
            with patch("bricksmith.workbench.provenance.importlib.import_module",
                       side_effect=ModuleNotFoundError("simulated missing runtime")):
                report = preflight(real_check=False, root=root)
            self.assertEqual(report["checks"]["status"], "unavailable")
            self.assertFalse(report["checks"]["dependencies"]["bricknet"]["imported"])
            self.assertEqual(report["checks"]["real_check"]["status"], "not_run")

    def test_unknown_or_incomplete_manifest_rejected(self):
        with self.assertRaises(ValueError):
            validate_manifest({"schema": "bricksmith-run-manifest-v2"})
        item = valid_manifest(); del item["tool_schema_sha256"]
        with self.assertRaises(ValueError):
            manifest_identity(item)

    def test_incomplete_capture_cannot_be_labeled_complete(self):
        item = valid_manifest()
        self.assertFalse(manifest_capture_complete(item))
        item["libraries"]["ldraw"]["fingerprint_complete"] = False
        self.assertFalse(manifest_capture_complete(item))


if __name__ == "__main__":
    unittest.main()
