"""Immutable local transaction revisions and durable workspace primitives.

This module is deliberately offline.  ``state.json`` is the only authoritative
pointer; revision directories are sealed before they can be named by that file.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import shutil
import tempfile
import uuid
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from . import design

STATE_SCHEMA = "bricksmith-transaction-state-v1"
REVISION_SCHEMA = "bricksmith-transaction-revision-v1"


class RevisionError(ValueError):
    """Invalid or corrupt transaction workspace."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _flush_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        _flush_dir(path.parent)
    finally:
        tmp.unlink(missing_ok=True)


def _json_bytes(value: Any) -> bytes:
    return (design._json_text(value, indent=2, sort_keys=True) + "\n").encode()


def _safe_root(path: Path, *, must_exist: bool = True) -> Path:
    path = path.expanduser().absolute()
    if path.is_symlink():
        raise RevisionError(f"Transaction workspace cannot be a symlink: {path}")
    if must_exist and (not path.is_dir() or path.is_symlink()):
        raise RevisionError(f"Transaction workspace must be a real directory: {path}")
    # Parent symlinks are common on macOS (/var -> /private/var); allow them,
    # but always operate on the canonical workspace path and reject the root
    # itself when it is a symlink.
    return path.resolve(strict=must_exist)


def _validate_id(value: str, label: str) -> str:
    return design._uuid(value, label)


@contextmanager
def writer_lock(root: Path, *, blocking: bool = False) -> Iterator[None]:
    root = _safe_root(root)
    lock_path = root / ".writer.lock"
    if lock_path.is_symlink():
        raise RevisionError("Writer lock path must not be a symlink")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
        try:
            fcntl.flock(fd, flags)
        except BlockingIOError as exc:
            raise RevisionError("Another transaction writer holds the workspace lock") from exc
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def read_state(root: Path) -> dict[str, Any]:
    root = _safe_root(root)
    state_path = root / "state.json"
    if state_path.is_symlink():
        raise RevisionError("state.json cannot be a symlink")
    state = design.read_json(state_path)
    if not isinstance(state, dict) or state.get("schema") != STATE_SCHEMA:
        raise RevisionError("Unsupported or malformed transaction state")
    _validate_id(state.get("current_revision_id"), "state.current_revision_id")
    if not isinstance(state.get("receipts"), dict):
        raise RevisionError("state.receipts must be an object")
    for operation_id, receipt in state["receipts"].items():
        _validate_id(operation_id, "state.receipts operation ID")
        if not isinstance(receipt, dict) or receipt.get("operation_id") != operation_id or receipt.get("disposition") != "committed":
            raise RevisionError(f"state receipt is malformed for operation {operation_id}")
        if receipt.get("schema") != "bricksmith-operation-receipt-v1":
            raise RevisionError(f"state receipt schema is unsupported for operation {operation_id}")
        _validate_id(receipt.get("revision_id"), f"state.receipts[{operation_id}].revision_id")
        _validate_id(receipt.get("candidate_id"), f"state.receipts[{operation_id}].candidate_id")
        for field in ("argument_hash", "candidate_sha256", "report_sha256"):
            if not isinstance(receipt.get(field), str) or not re.fullmatch(r"[0-9a-f]{64}", receipt[field]):
                raise RevisionError(f"state receipt {field} is malformed for operation {operation_id}")
        event_ref = receipt.get("event_reference")
        if event_ref is not None and (not isinstance(event_ref, str) or not re.fullmatch(r"events/[0-9]{8}\.json", event_ref)):
            raise RevisionError(f"state receipt event reference is unsafe for operation {operation_id}")
    if not isinstance(state.get("events", []), list): raise RevisionError("state.events must be an array")
    for reference in state.get("events", []):
        if not isinstance(reference, str) or not re.fullmatch(r"events/[0-9]{8}\.json", reference):
            raise RevisionError("state.events contains an unsafe reference")
    return state


def write_state(root: Path, state: dict[str, Any]) -> None:
    root = _safe_root(root)
    if state.get("schema") != STATE_SCHEMA:
        raise RevisionError("Refusing to write unknown transaction state schema")
    if (root / "state.json").is_symlink(): raise RevisionError("state.json cannot be a symlink")
    _atomic_bytes(root / "state.json", _json_bytes(state))


def revision_dir(root: Path, revision_id: str) -> Path:
    _validate_id(revision_id, "revision_id")
    revisions_root = root / "revisions"
    if revisions_root.is_symlink() or not revisions_root.is_dir() or revisions_root.resolve().parent != root.resolve():
        raise RevisionError("Revision root must be a real directory inside the workspace")
    target = revisions_root / revision_id
    if target.is_symlink() or target.resolve(strict=False).parent != revisions_root.resolve():
        raise RevisionError("Revision path escaped workspace")
    return target


def load_revision(root: Path, revision_id: str) -> dict[str, Any]:
    root = _safe_root(root)
    directory = revision_dir(root, revision_id)
    if not directory.is_dir() or directory.is_symlink():
        raise RevisionError(f"Authoritative revision is missing: {revision_id}")
    meta_path = directory / "revision.json"
    if meta_path.is_symlink():
        raise RevisionError("Revision metadata cannot be a symlink")
    metadata = design.read_json(meta_path)
    if not isinstance(metadata, dict) or metadata.get("schema") != REVISION_SCHEMA or metadata.get("revision_id") != revision_id:
        raise RevisionError(f"Revision metadata is corrupt: {revision_id}")
    design_path = directory / "design.json"
    if design_path.is_symlink(): raise RevisionError("Revision design cannot be a symlink")
    payload = design_path.read_bytes()
    if digest(payload) != metadata.get("design_file_sha256"):
        raise RevisionError(f"Revision design bytes are corrupt: {revision_id}")
    value = design.read_json(design_path)
    design.validate_design(value)
    if value["revision_id"] != revision_id or value["hashes"]["design"]["value"] != metadata.get("design_hash"):
        raise RevisionError("Revision content identity does not match metadata")
    for filename, field in (("build.ldr", "build_sha256"), ("line_map.json", "line_map_sha256")):
        artifact = directory / filename
        if artifact.is_symlink() or not artifact.is_file() or digest(artifact.read_bytes()) != metadata.get(field):
            raise RevisionError(f"Revision artifact is missing or corrupt: {filename}")
    artifact_records = metadata.get("artifact_sha256")
    if not isinstance(artifact_records, dict): raise RevisionError("Revision artifact manifest is missing")
    actual_records = {}
    for artifact in sorted(directory.rglob("*")):
        if artifact.name == "revision.json" or artifact.is_dir(): continue
        relative = artifact.relative_to(directory).as_posix()
        if artifact.is_symlink() or not artifact.is_file(): raise RevisionError(f"Unsafe revision artifact: {relative}")
        actual_records[relative] = digest(artifact.read_bytes())
    if actual_records != artifact_records:
        raise RevisionError(f"Revision artifact set or bytes changed: {revision_id}")
    return value


def current_revision(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    # Read state exactly once; all subsequent reads use this immutable ID.
    state = read_state(root)
    return state, load_revision(root, state["current_revision_id"])


def _seal_revision(root: Path, value: dict[str, Any], *, parent: str | None,
                   operation_id: str | None, validation_ref: str | None = None) -> dict[str, Any]:
    design.validate_design(value)
    revision_id = value["revision_id"]
    target = revision_dir(root, revision_id)
    if target.exists() or target.is_symlink():
        # A crash after sealing but before the state pointer leaves an immutable
        # orphan. A retry may reuse it only when every authoritative identity
        # matches byte-for-byte; recovery never publishes it on its own.
        try:
            existing = load_revision(root, revision_id)
            if existing["hashes"]["design"]["value"] != value["hashes"]["design"]["value"]:
                raise RevisionError(f"Immutable revision ID conflicts with existing bytes: {revision_id}")
            metadata = design.read_json(target / "revision.json")
            if metadata.get("parent_revision_id") != parent or metadata.get("operation_id") != operation_id:
                raise RevisionError(f"Sealed revision metadata conflicts with retry: {revision_id}")
            return metadata
        except (OSError, design.DesignError) as exc:
            raise RevisionError(f"Immutable revision already exists and is not reusable: {revision_id}") from exc
    temp = Path(tempfile.mkdtemp(prefix=f".{revision_id}.", dir=root / "revisions"))
    try:
        exported = design.export_design(value, temp / "export")
        # Keep the C3 canonical revision filenames at the revision root.
        for name in ("build.ldr", "line_map.json"):
            shutil.copyfile(temp / "export" / name, temp / name)
        shutil.copytree(temp / "export" / "modules", temp / "modules")
        shutil.rmtree(temp / "export")
        payload = _json_bytes(value)
        (temp / "design.json").write_bytes(payload)
        with (temp / "design.json").open("rb") as stream:
            os.fsync(stream.fileno())
        metadata = {"schema": REVISION_SCHEMA, "revision_id": revision_id,
                    "parent_revision_id": parent, "operation_id": operation_id,
                    "design_file_sha256": digest(payload),
                    "design_hash": value["hashes"]["design"]["value"],
                    "appearance_hash": value["hashes"]["appearance"]["value"],
                    "structure_hash": value["hashes"]["structure"]["value"],
                    "build_sha256": digest((temp / "build.ldr").read_bytes()),
                    "line_map_sha256": digest((temp / "line_map.json").read_bytes()),
                    "artifact_sha256": {path.relative_to(temp).as_posix(): digest(path.read_bytes())
                        for path in sorted(temp.rglob("*")) if path.is_file()},
                    "validation_reference": validation_ref}
        (temp / "revision.json").write_bytes(_json_bytes(metadata))
        for path in temp.rglob("*"):
            if path.is_file():
                with path.open("rb") as stream:
                    os.fsync(stream.fileno())
        _flush_dir(temp)
        for directory in sorted((p for p in temp.rglob("*") if p.is_dir()), reverse=True): _flush_dir(directory)
        os.replace(temp, target)
        _flush_dir(target.parent)
        return metadata
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def initialize(workspace: Path, source_design: dict[str, Any], *, source_identity: str | None = None) -> dict[str, Any]:
    """Explicitly create an offline transaction workspace; refuses overwrite."""
    workspace = _safe_root(workspace, must_exist=False)
    if workspace.exists() or workspace.is_symlink():
        raise FileExistsError(f"Transaction destination already exists: {workspace}")
    design.validate_design(source_design)
    if source_design.get("schema") == design.DESIGN_SCHEMA_V2:
        ledger = source_design.get("intent_ledger", {})
        if ledger.get("instructions") or ledger.get("repair_attempts") or ledger.get("next_actions"):
            raise RevisionError("design-v2 ledger authority must be created through transaction operations, not imported into a new workspace")
        if any(record.get("source") in {"user", "operator"} and record.get("originating_operation_id")
               for category in ("requirements", "decisions") for record in source_design.get(category, [])):
            raise RevisionError("design-v2 user/operator records cannot be imported without workspace receipts")
    if len(source_design["parts"]) > 1500:
        raise RevisionError("transaction workspace exceeds the 1,500 physical placement ceiling")
    workspace.parent.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(mode=0o700)
    _flush_dir(workspace.parent)
    try:
        for name in ("revisions", "operations", "events", "evidence"):
            (workspace / name).mkdir()
        _flush_dir(workspace)
        initial = copy.deepcopy(source_design)
        initial["parent_revision_id"] = None
        design.refresh_hashes(initial)
        metadata = _seal_revision(workspace, initial, parent=None, operation_id=None)
        state = {"schema": STATE_SCHEMA, "session_id": str(uuid.uuid4()),
                 "current_revision_id": initial["revision_id"], "receipts": {},
                 "usage": {}, "requests": {}, "events": [],
                 "source_identity": source_identity or source_design["hashes"]["design"]["value"],
                 "execution_mode": "offline_operator_only", "created_from_schema": source_design["schema"]}
        write_state(workspace, state)
        # Compatibility export follows creation of authoritative pointer.
        _atomic_bytes(workspace / "build.ldr", (workspace / "revisions" / initial["revision_id"] / "build.ldr").read_bytes())
        return {"workspace": str(workspace), "revision_id": initial["revision_id"], "metadata": metadata}
    except BaseException:
        # Partial initializations are explicit debris and not silently reopened.
        raise


def append_event(root: Path, event: dict[str, Any]) -> str:
    root = _safe_root(root)
    if (root / "events").is_symlink() or not (root / "events").is_dir() or (root / "events").resolve().parent != root.resolve():
        raise RevisionError("Event root must be a real directory inside the workspace")
    state = read_state(root)
    # Idempotent by operation identity across a crash after event fsync and
    # before its reference is copied into state.
    operation_id = event.get("operation_id")
    if operation_id:
        for existing in sorted((root / "events").glob("[0-9]*.json")):
            record = design.read_json(existing)
            if record.get("operation_id") == operation_id and record.get("kind") == event.get("kind"):
                reference = existing.relative_to(root).as_posix()
                if reference not in state.setdefault("events", []):
                    state["events"].append(reference); write_state(root, state)
                return reference
    sequences = [int(p.stem) for p in (root / "events").glob("[0-9]*.json") if p.stem.isdigit()]
    sequence = max(sequences, default=0) + 1
    filename = f"{sequence:08d}.json"
    path = root / "events" / filename
    if path.exists() or path.is_symlink():
        raise RevisionError(f"Event sequence already exists: {sequence}")
    record = {"schema": "bricksmith-transaction-event-v1", "sequence": sequence, **event}
    _atomic_bytes(path, _json_bytes(record))
    state.setdefault("events", []).append(path.relative_to(root).as_posix())
    write_state(root, state)
    return f"events/{filename}"


def finalize_compatibility_export(root: Path, revision_id: str, *, failpoint=None) -> None:
    value = load_revision(root, revision_id)
    payload, _ = design._export_text(value)
    path = root / "build.ldr"
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=root)
    temp = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        if failpoint: failpoint("during_compatibility_export")
        os.replace(temp, path); _flush_dir(root)
    finally:
        temp.unlink(missing_ok=True)


def recover(root: Path) -> dict[str, Any]:
    """Reconcile post-commit artifacts, never publish loose sealed candidates."""
    root = _safe_root(root)
    with writer_lock(root):
        state, value = current_revision(root)
        revision_id = state["current_revision_id"]
        committed_ops = {receipt.get("operation_id"): receipt for receipt in state["receipts"].values()}
        finalized = []
        for operation_id, receipt in committed_ops.items():
            if not operation_id:
                continue
            event_ref = receipt.get("event_reference")
            if not event_ref or not (root / event_ref).is_file():
                event_ref = append_event(root, {"kind": "operation_committed", "operation_id": operation_id,
                                                "revision_id": receipt["revision_id"]})
                receipt["event_reference"] = event_ref
                finalized.append(f"event:{operation_id}")
        if not (root / "build.ldr").is_file() or digest((root / "build.ldr").read_bytes()) != digest((revision_dir(root, revision_id) / "build.ldr").read_bytes()):
            finalize_compatibility_export(root, revision_id)
            finalized.append("compatibility_export")
        # Receipt references and any recovered event links are kept in the same
        # authoritative state record as the current revision pointer.
        state["receipts"] = {k: v for k, v in state["receipts"].items()}
        write_state(root, state)
        return {"current_revision_id": value["revision_id"], "finalized": finalized,
                "uncommitted_operations": sorted(p.name for p in (root / "operations").iterdir()
                    if p.is_dir() and p.name not in state["receipts"])}
