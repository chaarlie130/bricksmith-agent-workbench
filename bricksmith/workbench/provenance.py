"""Offline run provenance, content identity, and environment preflight."""
from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import platform
import tempfile
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "bricksmith-run-manifest-v1"
ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOTS = ("bricksmith", "scripts", "configs")
SOURCE_SUFFIXES = {".py", ".md", ".json"}
TOOL_SCHEMA_PATH = ROOT / "bricksmith/workbench/tool_schema.json"
SHA256 = __import__("re").compile(r"^[0-9a-f]{64}$")


def _records_sha256(records: list[dict[str, Any]]) -> str:
    return sha256_bytes(json.dumps(records, sort_keys=True, separators=(",", ":")).encode())


def _validate_sha(value: Any, label: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise ValueError(f"{label} must be a SHA-256 digest" + (" or null" if nullable else ""))


def _validate_source_records(records: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        raise ValueError(f"{label} must be a list")
    seen: set[str] = set()
    for index, record in enumerate(records):
        where = f"{label}[{index}]"
        if not isinstance(record, dict) or not isinstance(record.get("path"), str) or not record["path"]:
            raise ValueError(f"{where} must contain a non-empty path")
        path = Path(record["path"])
        if path.is_absolute() or ".." in path.parts or "\\" in record["path"]:
            raise ValueError(f"{where}.path must be a normalized relative path")
        if record["path"] in seen:
            raise ValueError(f"{label} contains duplicate path {record['path']!r}")
        seen.add(record["path"])
        _validate_sha(record.get("sha256"), f"{where}.sha256")
        if set(record) != {"path", "sha256"}:
            raise ValueError(f"{where} has unexpected fields")
    if records != sorted(records, key=lambda record: record["path"]):
        raise ValueError(f"{label} must be sorted by path")
    return records


def _validate_tree_records(records: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(records, list) or not records:
        raise ValueError(f"{label} must be a non-empty list")
    for index, record in enumerate(records):
        where = f"{label}[{index}]"
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise ValueError(f"{where} must contain a path")
        path = Path(record["path"])
        if path.is_absolute() or ".." in path.parts or "\\" in record["path"]:
            raise ValueError(f"{where}.path must be a normalized relative path")
        kind = record.get("type")
        if not isinstance(kind, str):
            raise ValueError(f"{where}.type must be a string")
        if kind in {"file", "symlink_file"}:
            _validate_sha(record.get("sha256"), f"{where}.sha256")
            if not isinstance(record.get("size"), int) or record["size"] < 0 or set(record) != {"path", "type", "size", "sha256"}:
                raise ValueError(f"{where} has invalid file metadata")
        elif kind in {"directory", "symlink_directory"}:
            if record.get("size") != 0 or set(record) != {"path", "type", "size"}:
                raise ValueError(f"{where} has invalid directory metadata")
        else:
            raise ValueError(f"{where}.type is unsupported")
    if not any(record.get("type") in {"file", "symlink_file"} for record in records):
        raise ValueError(f"{label} must contain at least one file record")
    if records != sorted(records, key=lambda record: record["path"]):
        raise ValueError(f"{label} must be sorted by path")
    return records


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: Path) -> str | None:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError:
        return None


def _canonical_tree(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Fingerprint a tree with unambiguous file records and explicit symlink handling."""
    records: list[dict[str, Any]] = []
    problems: list[str] = []
    root = root.resolve()
    active: set[Path] = set()

    def visit(directory: Path, rel: str) -> None:
        real = directory.resolve(strict=False)
        if real in active:
            problems.append(f"symlink_cycle:{rel or '.'}")
            return
        if not real.exists() or not real.is_dir():
            problems.append(f"unreadable_directory:{rel or '.'}")
            return
        active.add(real)
        records.append({"path": rel or ".", "type": "directory", "size": 0})
        try:
            for entry in sorted(real.iterdir(), key=lambda p: p.name):
                child_rel = f"{rel}/{entry.name}" if rel else entry.name
                try:
                    if entry.is_symlink():
                        target = entry.resolve(strict=True)
                        if target.is_dir():
                            records.append({"path": child_rel, "type": "symlink_directory", "size": 0})
                            visit(target, child_rel)
                        elif target.is_file():
                            data = target.read_bytes()
                            records.append({"path": child_rel, "type": "symlink_file", "size": len(data),
                                            "sha256": sha256_bytes(data)})
                        else:
                            problems.append(f"unsupported_symlink_target:{child_rel}")
                    elif entry.is_dir():
                        visit(entry, child_rel)
                    elif entry.is_file():
                        data = entry.read_bytes()
                        records.append({"path": child_rel, "type": "file", "size": len(data),
                                        "sha256": sha256_bytes(data)})
                    else:
                        problems.append(f"unsupported_file_type:{child_rel}")
                except (OSError, RuntimeError) as exc:
                    problems.append(f"unreadable:{child_rel}:{type(exc).__name__}")
        finally:
            active.remove(real)

    visit(root, "")
    records.sort(key=lambda item: item["path"])
    return records, problems


def hash_tree(path: Path) -> str | None:
    """Hash a relocation-invariant canonical file manifest; None means incomplete."""
    if not path.exists():
        return None
    try:
        if path.is_file():
            data = path.read_bytes()
            records, problems = ([{"path": path.name, "type": "file", "size": len(data),
                                   "sha256": sha256_bytes(data)}], [])
        else:
            records, problems = _canonical_tree(path)
    except OSError:
        return None
    if problems:
        return None
    return sha256_bytes(json.dumps(records, sort_keys=True, separators=(",", ":")).encode())


def _git(*args: str, cwd: Path = ROOT) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                              text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _source_paths(root: Path = ROOT) -> list[Path]:
    selected: set[Path] = set()
    for root_name in SOURCE_ROOTS:
        source_root = root / root_name
        if source_root.exists():
            selected.update(p for p in source_root.rglob("*") if p.is_file() and not p.is_symlink()
                            and p.suffix in SOURCE_SUFFIXES
                            and not any(part in {"__pycache__", ".venv", "runs", ".git"} for part in p.parts)
                            and p.resolve().is_relative_to(root.resolve()))
    selected.add(root / "bricksmith/workbench/system_prompt.md")
    return sorted(p for p in selected if p.is_file())


def _source_fingerprint(root: Path = ROOT) -> dict[str, Any]:
    records = []
    omitted = []
    for path in _source_paths(root):
        rel = path.relative_to(root).as_posix()
        digest = hash_file(path)
        if digest is not None:
            records.append({"path": rel, "sha256": digest})
        else:
            omitted.append(rel)
    records.sort(key=lambda record: record["path"])
    tracked = set((_git("ls-files", "--", *SOURCE_ROOTS, cwd=root) or "").splitlines())
    patch = _git("diff", "--binary", "HEAD", "--", *SOURCE_ROOTS, cwd=root) or ""
    staged_patch = _git("diff", "--cached", "--binary", "HEAD", "--", *SOURCE_ROOTS, cwd=root) or ""
    dirty_hash = sha256_bytes((staged_patch + "\0" + patch + "\0" + json.dumps(
        [record for record in records if record["path"] not in tracked], sort_keys=True)).encode())
    changed = _git("status", "--porcelain=v1", "--", *SOURCE_ROOTS, cwd=root) or ""
    return {"files": records, "content_sha256": _records_sha256(records),
            "dirty_patch_sha256": dirty_hash, "fingerprint_complete": not omitted,
            "omitted_paths": omitted,
            "dirty": bool(changed) or any(record["path"] not in tracked for record in records),
            "dirty_paths": changed.splitlines()}


def _committed_source_hash(commit: str | None) -> str | None:
    if not commit:
        return None
    listing = _git("ls-tree", "-r", "--name-only", commit, "--", *SOURCE_ROOTS)
    if listing is None:
        return None
    records = []
    for rel in listing.splitlines():
        if Path(rel).suffix not in SOURCE_SUFFIXES:
            continue
        try:
            content = subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=ROOT,
                                     check=True, capture_output=True).stdout
        except (OSError, subprocess.CalledProcessError):
            return None
        records.append({"path": rel, "sha256": sha256_bytes(content)})
    return sha256_bytes(json.dumps(records, sort_keys=True, separators=(",", ":")).encode())


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _bricknet_identity(*, package_file: Path | None = None,
                       package_data_path: Path | None = None) -> dict[str, Any]:
    try:
        if package_file is None:
            module = importlib.import_module("bricknet")
            package_path = Path(module.__file__).resolve()
        else:
            package_path = package_file.resolve()
    except Exception as exc:
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}
    source_root = package_path.parent
    for parent in package_path.parents:
        if (parent / ".git").exists():
            source_root = parent
            break
    commit = _git("rev-parse", "HEAD", cwd=source_root) if (source_root / ".git").exists() else None
    dirty = _git("status", "--porcelain", cwd=source_root) if commit else None
    try:
        direct_url = importlib.metadata.distribution("bricknet").read_text("direct_url.json")
        direct_url = json.loads(direct_url) if direct_url else None
    except Exception:
        direct_url = None
    local_files = []
    if source_root.exists():
        for file in sorted(source_root.rglob("*.py")):
            if ".git" not in file.parts and "__pycache__" not in file.parts and file.is_file() and not file.is_symlink():
                digest = hash_file(file)
                if digest is not None:
                    local_files.append({"path": file.relative_to(source_root).as_posix(), "sha256": digest})
    if not local_files:
        return {"available": False,
                "error": "BrickNet package has no readable Python source files"}
    data_problem = None
    if package_data_path is None:
        try:
            data_module = importlib.import_module("bricknet.data")
            package_data_path = Path(str(data_module._DATA)).resolve()
        except Exception as exc:
            data_problem = f"{type(exc).__name__}: {exc}"
    data_records: list[dict[str, Any]] = []
    if package_data_path is not None:
        data_records, data_problems = _canonical_tree(package_data_path)
        if data_problems:
            data_problem = "; ".join(data_problems)
    else:
        data_problems = [data_problem or "package_data_path_unavailable"]
    data_complete = package_data_path is not None and not data_problems and any(
        item.get("type") in {"file", "symlink_file"} for item in data_records)
    catalog_data = {"available": data_complete,
                    "path": str(package_data_path) if package_data_path is not None else None,
                    "content_sha256": _records_sha256(data_records) if data_complete else None,
                    "files": data_records if data_complete else [],
                    "error": None if data_complete else data_problem or "; ".join(data_problems)}
    return {"available": True, "version": _package_version("bricknet"),
            "import_path": str(package_path), "source_root": str(source_root),
            "vcs_commit": commit, "vcs_dirty": bool(dirty) if dirty is not None else None,
            "vcs_status": dirty, "direct_url": direct_url,
            "source_content_sha256": _records_sha256(local_files), "source_files": local_files,
            "catalog_data": catalog_data}


def _effective_library(name: str, root: Path = ROOT) -> dict[str, Any]:
    environment_value = os.environ.get("BRICKNET_DATA") if name == "bricknet_data" else None
    configured = environment_value
    if not configured:
        configured = str(root / ("data/bricknet-data" if name == "bricknet_data" else "data/ldraw"))
    default_path = (root / "data/bricknet-data").resolve()
    effective_path = Path(configured).expanduser().resolve() if Path(configured).expanduser().exists() else Path(configured).expanduser()
    is_override = bool(environment_value and effective_path != default_path)
    path = Path(configured).expanduser()
    target = path.resolve() if path.exists() else None
    complete_hash = hash_tree(target) if target else None
    return {"configured_path": str(path), "resolved_path": str(target) if target else None,
            "target_exists": target is not None, "content_sha256": complete_hash,
            "fingerprint_complete": complete_hash is not None,
            "source": "BRICKNET_DATA" if is_override else "repository_default"}


def _tool_schema() -> dict[str, Any]:
    if TOOL_SCHEMA_PATH.is_file():
        return json.loads(TOOL_SCHEMA_PATH.read_text(encoding="utf-8"))
    from bricksmith.workbench.agent_session import TOOLS
    return TOOLS


def build_manifest(*, brief: str = "", provider: str | None = None,
                   model: str | None = None, settings: dict[str, Any] | None = None,
                   execution_track: str = "offline-provenance") -> dict[str, Any]:
    prompt = ROOT / "bricksmith/workbench/system_prompt.md"
    source = _source_fingerprint()
    selected_ref = os.environ.get("BRICKSMITH_GENERATION_BASELINE", "HEAD")
    generation_commit = _git("rev-parse", f"{selected_ref}^{{commit}}")
    corpus_manifest = ROOT / "data/reference_sets/manifest.json"
    library_records = {key: _effective_library(key) for key in ("ldraw", "bricknet_data")}
    schema = _tool_schema()
    schema_bytes = json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    effective_settings = dict(settings or {})
    if execution_track == "offline-provenance":
        catalog_path = ROOT / "bricksmith/workbench/transaction_tool_catalog.json"
        if catalog_path.is_file():
            effective_settings["offline_tool_catalog_sha256"] = sha256_bytes(catalog_path.read_bytes())
            effective_settings["offline_tool_catalog_schema"] = "bricksmith-offline-tool-catalog-v1"
    return {
        "schema": SCHEMA,
        "run_id": hashlib.sha256((brief + "\0" + datetime.now(timezone.utc).isoformat()).encode()).hexdigest()[:16],
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "brief_sha256": sha256_bytes(brief.encode()),
        "generation_source": {"baseline_commit": generation_commit,
                              "baseline_clean_commit": bool(generation_commit),
                              "baseline_source_sha256": _committed_source_hash(generation_commit),
                              "instrumentation_commit": _git("rev-parse", "HEAD"),
                              "instrumentation_dirty": source["dirty"],
                              "source_manifest": source,
                              "implementation_files": source["files"]},
        "prompt_sha256": hash_file(prompt),
        "tool_schema_sha256": sha256_bytes(schema_bytes),
        "source_hashes": {"renderer": hash_file(ROOT / "bricksmith/rendering/rasterizer.py"),
                          "checker": hash_file(ROOT / "bricksmith/physics/validator.py"),
                          "implementation_manifest": source["content_sha256"]},
        "provider": provider, "model": model, "settings": effective_settings,
        "execution_track": execution_track,
        "environment": {"python": sys.version, "implementation": platform.python_implementation(),
                        "platform": platform.platform(), "machine": platform.machine(),
                        "packages": {name: _package_version(name) for name in
                                     ("bricknet", "meshlib", "numpy", "scipy", "matplotlib", "pillow")},
                        "bricknet_source": _bricknet_identity()},
        "libraries": library_records,
        "corpus": {"manifest_sha256": hash_file(corpus_manifest),
                   "content_sha256": hash_tree(ROOT / "data/reference_sets/ldr"),
                   "manifest_path": "data/reference_sets/manifest.json"},
        "input_provenance": [], "budgets": {}, "baseline_result": None,
    }


def validate_manifest(value: Any) -> None:
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise ValueError(f"Expected {SCHEMA} manifest")
    required = {"run_id": str, "created_at": str, "brief_sha256": str,
                "generation_source": dict, "prompt_sha256": (str, type(None)),
                "tool_schema_sha256": str, "source_hashes": dict,
                "environment": dict, "libraries": dict, "corpus": dict,
                "execution_track": str, "provider": (str, type(None)),
                "model": (str, type(None)), "settings": dict,
                "input_provenance": list, "budgets": dict}
    for key, expected in required.items():
        if key not in value or not isinstance(value[key], expected):
            raise ValueError(f"Manifest field {key!r} has invalid or missing type")
    try:
        datetime.fromisoformat(value["created_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Manifest created_at must be an ISO-8601 timestamp") from exc
    for field in ("brief_sha256", "tool_schema_sha256"):
        _validate_sha(value[field], f"Manifest field {field!r}")
    _validate_sha(value["prompt_sha256"], "Manifest field 'prompt_sha256'", nullable=True)
    for key in ("renderer", "checker", "implementation_manifest"):
        digest = value["source_hashes"].get(key)
        _validate_sha(digest, f"Invalid source hash {key!r}", nullable=True)
    if not value["generation_source"].get("baseline_commit"):
        raise ValueError("generation_source.baseline_commit is required")
    source = value["generation_source"]
    baseline_source_hash = source.get("baseline_source_sha256")
    if not isinstance(baseline_source_hash, str) or not SHA256.fullmatch(baseline_source_hash):
        raise ValueError("generation_source.baseline_source_sha256 must be a SHA-256 digest")
    if not isinstance(source.get("instrumentation_dirty"), bool):
        raise ValueError("generation_source.instrumentation_dirty must be boolean")
    if not isinstance(source.get("source_manifest"), dict):
        raise ValueError("generation_source.source_manifest must be an object")
    source_manifest = source["source_manifest"]
    for key in ("content_sha256", "dirty_patch_sha256"):
        _validate_sha(source_manifest.get(key), f"generation_source.source_manifest.{key}")
    files = _validate_source_records(source_manifest.get("files"), "generation_source.source_manifest.files")
    if _records_sha256(files) != source_manifest["content_sha256"]:
        raise ValueError("generation_source.source_manifest content digest does not match files")
    if not isinstance(source_manifest.get("fingerprint_complete"), bool):
        raise ValueError("generation_source.source_manifest.fingerprint_complete must be boolean")
    omitted = source_manifest.get("omitted_paths")
    if not isinstance(omitted, list) or any(not isinstance(item, str) for item in omitted):
        raise ValueError("generation_source.source_manifest.omitted_paths must be a list of strings")
    if source_manifest["fingerprint_complete"] != (not omitted):
        raise ValueError("generation source fingerprint completeness disagrees with omitted paths")
    if not isinstance(source_manifest.get("dirty_paths"), list) or any(not isinstance(x, str) for x in source_manifest["dirty_paths"]):
        raise ValueError("generation_source.source_manifest.dirty_paths must be a list of strings")
    if value["source_hashes"].get("implementation_manifest") != source_manifest["content_sha256"]:
        raise ValueError("source_hashes.implementation_manifest does not match source manifest content")
    if value["execution_track"] not in {"offline-provenance", "historical-hybrid",
                                         "historical-operator-assisted"}:
        raise ValueError("Unsupported execution_track")
    if not isinstance(value["environment"].get("packages"), dict):
        raise ValueError("environment.packages must be an object")
    if not isinstance(value["environment"].get("bricknet_source"), dict):
        raise ValueError("environment.bricknet_source must be an object")
    bricknet = value["environment"]["bricknet_source"]
    if not isinstance(bricknet.get("available"), bool):
        raise ValueError("environment.bricknet_source.available must be boolean")
    if bricknet["available"]:
        for key in ("version", "vcs_commit"):
            if bricknet.get(key) is not None and not isinstance(bricknet[key], str):
                raise ValueError(f"environment.bricknet_source.{key} must be a string or null")
        if not isinstance(bricknet.get("vcs_dirty"), (bool, type(None))):
            raise ValueError("environment.bricknet_source.vcs_dirty must be boolean or null")
        source_files = _validate_source_records(bricknet.get("source_files"), "environment.bricknet_source.source_files")
        if not source_files:
            raise ValueError("Available BrickNet source requires at least one source file")
        _validate_sha(bricknet.get("source_content_sha256"), "environment.bricknet_source.source_content_sha256")
        if _records_sha256(source_files) != bricknet["source_content_sha256"]:
            raise ValueError("BrickNet source content digest does not match source_files")
        catalog_data = bricknet.get("catalog_data")
        if not isinstance(catalog_data, dict) or not isinstance(catalog_data.get("available"), bool):
            raise ValueError("environment.bricknet_source.catalog_data must identify availability")
        if catalog_data["available"]:
            tree_files = _validate_tree_records(catalog_data.get("files"), "environment.bricknet_source.catalog_data.files")
            _validate_sha(catalog_data.get("content_sha256"), "environment.bricknet_source.catalog_data.content_sha256")
            if _records_sha256(tree_files) != catalog_data["content_sha256"]:
                raise ValueError("BrickNet package-data digest does not match files")
            if not isinstance(catalog_data.get("path"), str):
                raise ValueError("BrickNet package-data path is required when available")
        else:
            if catalog_data.get("content_sha256") is not None or catalog_data.get("files") != []:
                raise ValueError("Unavailable BrickNet package data must have null digest and empty files")
        if catalog_data.get("error") is not None and not isinstance(catalog_data.get("error"), str):
            raise ValueError("BrickNet package-data error must be a string or null")
    if set(value["libraries"]) != {"ldraw", "bricknet_data"}:
        raise ValueError("libraries must identify ldraw and bricknet_data")
    for key in ("manifest_sha256", "content_sha256"):
        digest = value["corpus"].get(key)
        _validate_sha(digest, f"Invalid corpus hash {key!r}", nullable=True)
    for name, version in value["environment"]["packages"].items():
        if version is not None and not isinstance(version, str):
            raise ValueError(f"Invalid package version for {name!r}")
    for key, record in value["libraries"].items():
        if not isinstance(record, dict) or not isinstance(record.get("fingerprint_complete"), bool):
            raise ValueError(f"Invalid library record {key!r}")
        digest = record.get("content_sha256")
        _validate_sha(digest, f"Invalid library digest {key!r}", nullable=True)
    if "capture_status" in value:
        capture_status = value["capture_status"]
        if not isinstance(capture_status, str) or capture_status not in {"complete", "incomplete"}:
            raise ValueError("capture_status must be complete or incomplete")
        if capture_status == "complete" and not _capture_evidence_present(value):
            raise ValueError("capture_status is complete but required provenance evidence is incomplete")
    def check_finite(item: Any) -> None:
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("Manifest contains nonfinite numeric values")
        if isinstance(item, dict):
            for sub in item.values(): check_finite(sub)
        elif isinstance(item, list):
            for sub in item: check_finite(sub)
    check_finite(value)
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Manifest is not standards-compliant JSON: {exc}") from exc


def manifest_identity(value: dict[str, Any]) -> str:
    """Hash content/configuration only; omit all physical paths and run metadata."""
    validate_manifest(value)
    source = value["generation_source"]
    libraries = {name: {"content_sha256": record["content_sha256"],
                        "fingerprint_complete": record["fingerprint_complete"]}
                 for name, record in sorted(value["libraries"].items())}
    environment = {k: v for k, v in value["environment"].items() if k != "bricknet_source"}
    bricknet = value["environment"].get("bricknet_source", {})
    environment["bricknet_source"] = {k: bricknet.get(k) for k in
        ("version", "vcs_commit", "vcs_dirty", "source_content_sha256")}
    environment["bricknet_source"]["catalog_data_sha256"] = (bricknet.get("catalog_data") or {}).get("content_sha256")
    projection = {"schema": value["schema"], "brief_sha256": value["brief_sha256"],
        "generation_baseline": {"commit": source["baseline_commit"],
                                "source_sha256": source["baseline_source_sha256"]},
        "instrumentation_source_sha256": source["source_manifest"]["content_sha256"],
        "instrumentation_dirty_patch_sha256": source["source_manifest"]["dirty_patch_sha256"],
        "prompt_sha256": value["prompt_sha256"], "tool_schema_sha256": value["tool_schema_sha256"],
        "source_hashes": value["source_hashes"], "provider": value["provider"],
        "model": value["model"], "settings": value["settings"],
        "execution_track": value["execution_track"], "environment": environment,
        "libraries": libraries,
        "corpus": {"manifest_sha256": value["corpus"].get("manifest_sha256"),
                   "content_sha256": value["corpus"].get("content_sha256")},
        "input_provenance": value["input_provenance"], "budgets": value["budgets"]}
    encoded = json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return sha256_bytes(encoded.encode())


def _capture_evidence_present(value: dict[str, Any]) -> bool:
    source = value["generation_source"]
    source_hashes = value["source_hashes"]
    bricknet = value["environment"]["bricknet_source"]
    package_names = ("bricknet", "meshlib", "numpy", "scipy", "matplotlib", "pillow")
    return bool(source.get("baseline_source_sha256") and
        source.get("source_manifest", {}).get("content_sha256") and
        source.get("source_manifest", {}).get("files") and
        source.get("source_manifest", {}).get("fingerprint_complete") is True and
        not source.get("source_manifest", {}).get("omitted_paths") and
        source.get("source_manifest", {}).get("dirty_patch_sha256") and
        value.get("prompt_sha256") and value.get("tool_schema_sha256") and
        all(source_hashes.get(name) for name in ("renderer", "checker", "implementation_manifest")) and
        all(value["environment"]["packages"].get(name) for name in package_names) and
        bricknet.get("available") is True and bricknet.get("source_content_sha256") and
        (bricknet.get("catalog_data") or {}).get("available") is True and
        (bricknet.get("catalog_data") or {}).get("content_sha256") and
        all(value["libraries"][name].get("fingerprint_complete") and
            value["libraries"][name].get("content_sha256") for name in ("ldraw", "bricknet_data")) and
        value["corpus"].get("manifest_sha256") and value["corpus"].get("content_sha256"))


def manifest_capture_complete(value: dict[str, Any]) -> bool:
    """True only when all source, runtime, corpus, and external-data fingerprints exist."""
    validate_manifest(value)
    return bool(_capture_evidence_present(value))


def publish_manifest(path: Path, value: dict[str, Any]) -> None:
    """Validate and atomically create a new manifest without replacing evidence."""
    validate_manifest(value)
    if value.get("capture_status") == "complete" and not _capture_evidence_present(value):
        raise ValueError("Cannot publish a complete manifest without all required provenance evidence")
    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _dependency_probe(module_name: str, distribution: str | None = None) -> dict[str, Any]:
    try:
        module = importlib.import_module(module_name)
        imported = True
        import_error = None
    except Exception as exc:
        module = None
        imported = False
        import_error = f"{type(exc).__name__}: {exc}"
    version = _package_version(distribution or module_name.split(".")[0])
    return {"imported": imported, "import_error": import_error,
            "distribution_version": version,
            "metadata_available": version is not None,
            "module_path": getattr(module, "__file__", None)}


def preflight(*, real_check: bool = True, root: Path = ROOT) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for name in ("bricknet", "meshlib.mrmeshnumpy", "matplotlib", "numpy", "scipy"):
        checks.setdefault("dependencies", {})[name] = _dependency_probe(name)
    for name in ("ldraw", "bricknet_data"):
        lib = _effective_library(name, root=root)
        checks[name] = {**lib, "available": lib["target_exists"] and lib["fingerprint_complete"]}
    checks["catalog"] = {"status": "unavailable"}
    checks["connectors"] = {"status": "unavailable"}
    checks["mesh"] = {"status": "unavailable"}
    try:
        from bricknet.data import load_catalog, load_connector_list, load_connectors
        catalog = load_catalog()
        connector_list, connectors = load_connector_list(), load_connectors()
        checks["catalog"] = {"status": "available", "parts": len(catalog.id_to_name)}
        checks["connectors"] = {"status": "available", "connector_parts": len(connector_list),
                                 "connector_records": len(connectors)}
        from bricknet.collision import _mesh
        mesh, _, _ = _mesh(catalog.stem_to_id["3024"])
        checks["mesh"] = {"status": "available", "fixture_part": "3024", "loaded": mesh is not None}
        if mesh is None:
            raise RuntimeError("BrickNet returned no mesh for 3024.dat")
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        for key in ("catalog", "connectors", "mesh"):
            if checks[key]["status"] == "unavailable": checks[key] = {"status": "unavailable", "error": error}
    checks["real_check"] = {"status": "not_run"}
    checks["real_render"] = {"status": "not_run"}
    if real_check:
        try:
            from bricksmith.workbench.feedback import check_model
            from bricksmith.workbench.acceptance import CHECK_NAMES
            import tempfile
            tiny = "0 M0 single 1x1 plate preflight plumbing fixture\n1 15 0 0 0 1 0 0 0 1 0 0 0 1 3024.dat\n"
            with tempfile.TemporaryDirectory(prefix="bricksmith-preflight-") as directory:
                model = Path(directory) / "tiny.ldr"
                model.write_text(tiny, encoding="utf-8")
                result = check_model(model, ground_y=8)
                states = (result.get("checks") or {})
                complete = all(isinstance(states.get(name), bool) for name in CHECK_NAMES)
                passed = complete and all(states[name] for name in CHECK_NAMES) and result.get("passed") is True
                checks["real_check"] = {"status": "passed" if passed else "failed" if complete else "unavailable",
                    "checks": {name: states.get(name) for name in CHECK_NAMES}, "errors": result.get("errors")}
                try:
                    from bricksmith.rendering.rasterizer import render_ldr_to_png
                    output = Path(directory) / "tiny.png"
                    render_ldr_to_png(model, output, resolution=128)
                    checks["real_render"] = {"status": "passed" if output.is_file() and output.stat().st_size else "failed"}
                except Exception as exc:
                    checks["real_render"] = {"status": "unavailable", "error": f"{type(exc).__name__}: {exc}"}
        except Exception as exc:
            checks["real_check"] = {"status": "unavailable", "error": f"{type(exc).__name__}: {exc}"}
    unavailable = any(item.get("imported") is False or item.get("metadata_available") is False
                      for item in checks["dependencies"].values()) or any(
        checks[k].get("status") == "unavailable" for k in ("catalog", "connectors", "mesh")) or any(
        checks[k].get("available") is False for k in ("ldraw", "bricknet_data"))
    failed = any(checks[key].get("status") == "failed" for key in ("real_check", "real_render"))
    complete = (not real_check or checks["real_check"]["status"] == checks["real_render"]["status"] == "passed")
    status = "unavailable" if unavailable or (real_check and "unavailable" in
        (checks["real_check"]["status"], checks["real_render"]["status"])) else "failed" if failed else "passed" if complete else "unavailable"
    checks["status"] = status
    return {"schema": "bricksmith-environment-preflight-v1", "checks": checks}
