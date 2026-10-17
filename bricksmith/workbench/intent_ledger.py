"""Typed persistent intent ledger operations for explicit offline workspaces.

The operator intake callable is an application boundary, not an OS sandbox. A
process with arbitrary filesystem access can rewrite local files; model-facing
operations cannot mint the in-process trusted-ingress capability or select an
operator/user source.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import uuid
from pathlib import Path
from typing import Any

from . import design, revisions, transactions


def _now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _request(workspace: Path, operation_id: str, base_revision_id: str,
             operations: list[dict[str, Any]], intent: str) -> dict[str, Any]:
    return {"schema": transactions.OPERATION_SCHEMA_V3, "operation_id": operation_id,
        "base_revision_id": base_revision_id, "intent": intent, "operations": operations}


def _propose_and_commit(workspace: Path, request: dict[str, Any], *, trusted: dict[str, Any] | None = None,
                        validator=None, failpoint=None) -> dict[str, Any]:
    created: list[bool] = []
    proposal = transactions.propose_edit(workspace, request, validator=validator,
        failpoint=failpoint, _created_candidate=created, _trusted_ingress=trusted)
    if proposal.get("status") == "failure" or proposal.get("disposition") in {"failed", "aborted", "discarded", "committed"}:
        return proposal
    if not created or not created[0] or not proposal.get("commit_eligible"):
        return proposal
    return transactions.commit_candidate(workspace, request["operation_id"], proposal["candidate_id"],
        validator=validator, failpoint=failpoint)


def upgrade_workspace(workspace: Path, operation_id: str, base_revision_id: str, *, validator=None) -> dict[str, Any]:
    """Explicitly upgrade the current design-v1 revision through operation-v3."""
    request = _request(workspace, operation_id, base_revision_id,
        [{"type": "upgrade_design_v2"}], "explicit offline design-v2 upgrade")
    return _propose_and_commit(workspace, request, validator=validator)


def operator_intake(workspace: Path, *, operation_id: str, base_revision_id: str,
                    instruction_id: str, created_at: str, source: str, instruction_text: str,
                    changes: list[dict[str, Any]], fill_brief: bool = False,
                    validator=None, _failpoint=None) -> dict[str, Any]:
    """Record exact trusted instruction text and bounded structured edits atomically."""
    transactions._id(operation_id, "operation_id"); transactions._id(base_revision_id, "base_revision_id")
    transactions._id(instruction_id, "instruction_id")
    if not isinstance(source, str) or source not in {"user", "operator"}:
        raise transactions.TransactionError("source must be user or operator")
    if type(fill_brief) is not bool:
        raise transactions.TransactionError("fill_brief must be a boolean")
    if not isinstance(instruction_text, str) or not instruction_text or len(instruction_text.encode("utf-8")) > 64 * 1024:
        raise transactions.TransactionError("instruction_text must contain 1-65,536 exact UTF-8 bytes")
    if not isinstance(changes, list) or len(changes) > transactions.MAX_OPERATIONS - 2:
        raise transactions.TransactionError("changes must be an array within the 64-operation transaction limit")
    if not isinstance(created_at, str):
        raise transactions.TransactionError("created_at must be a valid UTC ISO timestamp ending in Z")
    try:
        parsed = datetime.datetime.fromisoformat(created_at[:-1] + "+00:00") if created_at.endswith("Z") else None
    except ValueError as exc: raise transactions.TransactionError("created_at must be a valid UTC ISO timestamp ending in Z") from exc
    if parsed is None or parsed.utcoffset() != datetime.timedelta(0):
        raise transactions.TransactionError("created_at must be a valid UTC ISO timestamp ending in Z")
    instruction = {"id": instruction_id, "text": instruction_text, "source": source,
        "originating_operation_id": operation_id, "created_at": created_at}
    operations: list[dict[str, Any]] = [{"type": "ledger_add_instruction", "record": instruction}]
    for index, change in enumerate(changes):
        if not isinstance(change, dict) or not isinstance(change.get("type"), str):
            raise transactions.TransactionError(f"changes[{index}] must have a structured type")
        kind = change["type"]
        if kind in {"requirement", "decision"}:
            if set(change) != {"type", "record"} or not isinstance(change["record"], dict):
                raise transactions.TransactionError(f"changes[{index}] must contain exactly type and record")
            record = copy.deepcopy(change["record"])
            if "source" in record or "instruction_id" in record or "originating_operation_id" in record:
                raise transactions.TransactionError("operator intake supplies source, instruction, and operation attribution")
            record["source"] = source
            record["instruction_id"] = instruction_id
            record["originating_operation_id"] = operation_id
            operations.append({"type": "ledger_add_requirement" if kind == "requirement" else "ledger_add_decision", "record": record})
        elif kind == "issue":
            allowed = {"type", "issue_id", "kind", "status", "affected_ids", "evidence_reference_ids", "next_proposed_action"}
            if set(change) != allowed: raise transactions.TransactionError(f"changes[{index}] issue shape is invalid")
            operations.append({"type": "ledger_update_issue", **{key: copy.deepcopy(value) for key, value in change.items() if key != "type"}})
        elif kind in {"repair_attempt", "next_action"}:
            if set(change) != {"type", "record"} or not isinstance(change["record"], dict):
                raise transactions.TransactionError(f"changes[{index}] must contain exactly type and record")
            record = copy.deepcopy(change["record"])
            if "originating_operation_id" in record: raise transactions.TransactionError("originating operation is assigned by trusted intake")
            record["originating_operation_id"] = operation_id
            if kind == "next_action":
                if "source" in record: raise transactions.TransactionError("next-action source is assigned by trusted intake")
                record["source"] = "operator"
            else:
                if {"schema", "recorded_revision_id", "outcome_at_recording"} & set(record):
                    raise transactions.TransactionError("repair outcome and recording provenance are assigned by the ledger service")
                record["schema"] = design.REPAIR_ATTEMPT_SCHEMA
            operations.append({"type": "ledger_add_repair_attempt" if kind == "repair_attempt" else "ledger_add_next_action", "record": record})
        else:
            raise transactions.TransactionError(f"unsupported trusted structured change type: {kind!r}")
    if fill_brief: operations.append({"type": "ledger_set_initial_brief", "instruction_id": instruction_id})
    request = _request(workspace, operation_id, base_revision_id, operations,
        "trusted operator intake: exact instruction and structured changes")
    trust = {"capability": transactions._TRUSTED_INGRESS_CAPABILITY,
        "source": source, "instruction_id": instruction_id, "text": instruction_text}
    result = _propose_and_commit(workspace, request, trusted=trust, validator=validator,
        failpoint=_failpoint)
    result = copy.deepcopy(result)
    result["trusted_instruction_id"] = instruction_id
    return result


def _verify_instruction_authority(workspace: Path, revision: dict[str, Any]) -> dict[str, str]:
    """Return verified trusted instruction IDs and reject malformed authority chains."""
    state = revisions.read_state(workspace)
    verified: dict[str, str] = {}
    for instruction in revision.get("intent_ledger", {}).get("instructions", []):
        operation_id = instruction["originating_operation_id"]
        receipt = state.get("receipts", {}).get(operation_id)
        folder = transactions._op_dir(workspace, operation_id)
        intent_path, report_path, candidate_path = folder / "intent.json", folder / "report.json", folder / "candidate" / "design.json"
        if not receipt or receipt.get("disposition") != "committed":
            raise transactions.TransactionError(f"trusted instruction lacks an authoritative committed receipt: {instruction['id']}")
        if any(path.is_symlink() or not path.is_file() for path in (intent_path, report_path, candidate_path)):
            raise transactions.TransactionError(f"trusted instruction evidence is missing or unsafe: {instruction['id']}")
        intent_record = design.read_json(intent_path); report = design.read_json(report_path)
        candidate = design.read_json(candidate_path)
        if (hashlib.sha256(report_path.read_bytes()).hexdigest() != receipt.get("report_sha256")
                or hashlib.sha256(candidate_path.read_bytes()).hexdigest() != receipt.get("candidate_sha256")
                or receipt.get("revision_id") != candidate.get("revision_id")
                or receipt.get("operation_id") != operation_id
                or intent_record.get("operation_id") != operation_id
                or intent_record.get("argument_hash") != receipt.get("argument_hash")
                or report.get("operation_id") != operation_id
                or report.get("candidate_id") != candidate.get("revision_id")):
            raise transactions.TransactionError(f"trusted instruction evidence hashes do not match the receipt: {instruction['id']}")
        frozen = intent_record.get("intent")
        trust = transactions._verify_trusted_ingress(frozen, intent_record.get("argument_hash"), candidate)
        if (trust is None or trust.get("instruction_id") != instruction["id"]
                or receipt.get("trusted_intake_binding_sha256") != trust["binding_sha256"]
                or report.get("trusted_intake_binding_sha256") != trust["binding_sha256"]):
            raise transactions.TransactionError(f"trusted instruction authority binding is invalid: {instruction['id']}")
        verified[instruction["id"]] = trust["source"]
    return verified


def ledger_read(workspace: Path, *, revision_id: str | None = None, offset: int = 0,
                limit: int = 50) -> dict[str, Any]:
    """Read a bounded page from one sealed design-v2 revision without running physics."""
    if type(offset) is not int or offset < 0: raise transactions.TransactionError("offset must be a nonnegative integer")
    if type(limit) is not int or not 1 <= limit <= 100: raise transactions.TransactionError("limit must be an integer from 1 to 100")
    root = workspace.expanduser().absolute()
    state = revisions.read_state(root)
    selected = revision_id or state["current_revision_id"]
    value = revisions.load_revision(root, selected)
    if value["schema"] != design.DESIGN_SCHEMA_V2:
        raise transactions.TransactionError("ledger-read requires explicit transaction-upgrade-v2")
    trusted_sources = _verify_instruction_authority(root, value)
    ledger = value["intent_ledger"]
    for collection in (ledger["repair_attempts"], ledger["next_actions"]):
        for record in collection: transactions._validate_evidence_references(root, record["evidence_references"])
    for source_ref in value["source_references"]:
        relative = source_ref.get("local_artifact_reference")
        if relative is not None:
            canonical_root = root.resolve(strict=True)
            path = canonical_root.joinpath(*Path(relative).parts)
            cursor = canonical_root
            unsafe = False
            for component in Path(relative).parts:
                cursor = cursor / component
                unsafe |= cursor.is_symlink()
            try: path.resolve(strict=True).relative_to(canonical_root)
            except (OSError, ValueError): unsafe = True
            if (unsafe or not path.is_file()
                    or hashlib.sha256(path.read_bytes()).hexdigest() != source_ref["content_hash"]["value"]):
                raise transactions.TransactionError(f"source-reference artifact is missing or corrupt: {source_ref['id']}")

    source_refs = {item["id"]: item for item in value["source_references"]}
    def evidence_for(issue: dict[str, Any], revision: dict[str, Any]) -> list[dict[str, Any]]:
        refs = {item["id"]: item for item in revision.get("source_references", [])}
        return [{"id": identity, "content_hash": refs[identity]["content_hash"],
            "role": refs[identity]["role"]} for identity in issue.get("evidence_reference_ids", [])
            if identity in refs]

    def committed_operation_snapshot(operation_id: str, issue_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
        """Return a source-bound candidate snapshot only for an operation that asserted this issue."""
        receipt = state.get("receipts", {}).get(operation_id)
        if not isinstance(receipt, dict) or receipt.get("disposition") != "committed":
            return None
        folder = transactions._op_dir(root, operation_id)
        intent_path = folder / "intent.json"
        report_path = folder / "report.json"
        candidate_path = folder / "candidate" / "design.json"
        paths = (intent_path, report_path, candidate_path)
        if any(path.is_symlink() or not path.is_file() for path in paths):
            return None
        intent_bytes, report_bytes, candidate_bytes = (path.read_bytes() for path in paths)
        if (hashlib.sha256(report_bytes).hexdigest() != receipt.get("report_sha256")
                or hashlib.sha256(candidate_bytes).hexdigest() != receipt.get("candidate_sha256")):
            return None
        intent_record = design.read_json(intent_path)
        report = design.read_json(report_path)
        candidate = design.read_json(candidate_path)
        if (intent_record.get("operation_id") != operation_id
                or intent_record.get("base_revision_id") != receipt.get("base_revision_id")
                or report.get("operation_id") != operation_id
                or report.get("candidate_id") != candidate.get("revision_id")
                or candidate.get("revision_id") != receipt.get("revision_id")):
            return None
        frozen = intent_record.get("intent", {})
        operations = frozen.get("operations", [])
        explicit_update = any(op.get("type") == "ledger_update_issue" and op.get("issue_id") == issue_id
            for op in operations if isinstance(op, dict))
        legacy_update = any(op.get("type") == "upsert_issue" and op.get("issue_id") == issue_id
            for op in operations if isinstance(op, dict))
        candidate_issue = next((entry for entry in candidate.get("issues", []) if entry.get("id") == issue_id), None)
        policy_created = (candidate_issue is not None
            and candidate_issue.get("originating_operation_id") == operation_id
            and candidate_issue.get("originating_revision_id") == candidate.get("revision_id")
            and candidate_issue.get("kind") in {"provisional", "repair_incomplete"}
            and isinstance(report.get("policy"), dict)
            and report["policy"].get("status") == candidate_issue.get("kind"))
        if not (explicit_update or legacy_update or policy_created) or candidate_issue is None:
            return None
        return candidate_issue, candidate, report

    def claim_view(category: str, record: dict[str, Any]) -> dict[str, Any]:
        item = copy.deepcopy(record)
        operation_id = record.get("originating_operation_id")
        origin_revision_id = record.get("originating_revision_id")
        if operation_id is not None:
            receipt = state.get("receipts", {}).get(operation_id)
            if not isinstance(receipt, dict) or receipt.get("disposition") != "committed":
                raise transactions.TransactionError(f"{category} claim lacks an authoritative committed origin: {record['id']}")
            folder = transactions._op_dir(root, operation_id)
            report_path = folder / "report.json"; candidate_path = folder / "candidate" / "design.json"
            if any(path.is_symlink() or not path.is_file() for path in (report_path, candidate_path)):
                raise transactions.TransactionError(f"{category} claim origin evidence is missing or unsafe: {record['id']}")
            report_bytes = report_path.read_bytes(); candidate_bytes = candidate_path.read_bytes()
            if (hashlib.sha256(report_bytes).hexdigest() != receipt.get("report_sha256")
                    or hashlib.sha256(candidate_bytes).hexdigest() != receipt.get("candidate_sha256")):
                raise transactions.TransactionError(f"{category} claim origin evidence hash is invalid: {record['id']}")
            origin_candidate = design.read_json(candidate_path)
            if origin_candidate.get("revision_id") != receipt.get("revision_id"):
                raise transactions.TransactionError(f"{category} claim origin revision is invalid: {record['id']}")
            if category == "issues":
                present = any(candidate_issue.get("id") == record["id"] for candidate_issue in origin_candidate["issues"])
            else:
                present = any(candidate_record.get("id") == record["id"]
                    and candidate_record == record for candidate_record in origin_candidate[category])
            if not present:
                raise transactions.TransactionError(f"{category} claim does not appear in its origin candidate: {record['id']}")
            origin_revision_id = receipt["revision_id"]
        evidence_ids = record.get("evidence_reference_ids", [])
        evidence = [{"id": identity, "content_hash": source_refs[identity]["content_hash"],
            "role": source_refs[identity]["role"]} for identity in evidence_ids if identity in source_refs]
        item["claim_provenance"] = {"classification": "asserted_claim" if operation_id else "historical_unverified_claim",
            "originating_operation_id": operation_id, "originating_revision_id": origin_revision_id,
            "evidence_references": evidence,
            "interpretation": "Claim attribution and linked artifacts do not prove visual completion or acceptance."}
        if category == "issues":
            observations = []
            for observation_operation_id in dict.fromkeys(record.get("attempted_operation_ids", [])):
                snapshot = committed_operation_snapshot(observation_operation_id, record["id"])
                if snapshot is None:
                    # A durable intent without an authoritative committed
                    # receipt is a staged/terminal attempt, never an observation.
                    observation_folder = transactions._op_dir(root, observation_operation_id)
                    intent_path = observation_folder / "intent.json"
                    if observation_operation_id not in state.get("receipts", {}):
                        if intent_path.exists() or (observation_folder / "receipt.json").exists():
                            # Candidate, discarded, failed, and aborted work is
                            # represented by repair history when present.
                            continue
                        # No durable source exists: retain a clearly unknown
                        # historical marker, but never use it as latest status.
                        observations.append({"classification": "historical_unverified_claim",
                            "operation_id": observation_operation_id, "revision_id": None,
                            "status": None, "kind": None, "affected_ids": [],
                            "evidence_reference_ids": [], "evidence_references": [],
                            "next_proposed_action": None,
                            "meaning": "Legacy issue observation has no retained operation evidence."})
                        continue
                    if not intent_path.is_file() or intent_path.is_symlink():
                        raise transactions.TransactionError(
                            f"committed issue observation intent is missing or unsafe: {observation_operation_id}")
                    intent_value = design.read_json(intent_path).get("intent", {})
                    targets = {op.get("issue_id") for op in intent_value.get("operations", [])
                        if isinstance(op, dict) and op.get("type") in {"ledger_update_issue", "upsert_issue"}}
                    if record["id"] in targets:
                        raise transactions.TransactionError(
                            f"committed issue observation evidence is missing or corrupt: {observation_operation_id}")
                    # A committed update to another issue or a geometry-only
                    # edit is a known non-observation for this issue.
                    continue
                observed_issue, observed_revision, _ = snapshot
                observations.append({"classification": "asserted_claim",
                    "operation_id": observation_operation_id, "revision_id": observed_revision["revision_id"],
                    "status": observed_issue.get("status"), "kind": observed_issue.get("kind"),
                    "affected_ids": copy.deepcopy(observed_issue.get("affected_ids", [])),
                    "evidence_reference_ids": copy.deepcopy(observed_issue.get("evidence_reference_ids", [])),
                    "evidence_references": evidence_for(observed_issue, observed_revision),
                    "next_proposed_action": observed_issue.get("next_proposed_action"),
                    "meaning": "Issue status is an attributed claim; construction checks do not prove visual resolution."})
            creation = None
            origin_operation_id = record.get("originating_operation_id")
            if origin_operation_id is not None:
                created_snapshot = committed_operation_snapshot(origin_operation_id, record["id"])
                if created_snapshot is not None:
                    created_issue, created_revision, _ = created_snapshot
                    creation = {"classification": "asserted_claim", "operation_id": origin_operation_id,
                        "revision_id": created_revision["revision_id"], "status": created_issue.get("status"),
                        "kind": created_issue.get("kind"),
                        "evidence_reference_ids": copy.deepcopy(created_issue.get("evidence_reference_ids", [])),
                        "evidence_references": evidence_for(created_issue, created_revision)}
            observed_revision_id = record.get("last_observation_revision_id")
            latest = next((observation for observation in reversed(observations)
                if observation.get("classification") == "asserted_claim"
                and observation.get("revision_id") == observed_revision_id), None)
            if latest is None:
                latest = {"classification": "historical_unverified_claim", "operation_id": None,
                    "revision_id": None, "status": None, "kind": None,
                    "evidence_reference_ids": [], "evidence_references": [],
                    "meaning": "Selected issue revision has no verified issue-specific status assertion."}
            item["issue_provenance"] = {"creation": creation, "latest_status_assertion": copy.deepcopy(latest)}
            if creation is None:
                item["claim_provenance"]["classification"] = "historical_unverified_claim"
            # The generic origin claim describes creation. Current status/evidence
            # are separately attributed above and never retroactively attached to it.
            item["claim_provenance"]["evidence_references"] = (
                creation["evidence_references"] if creation is not None else evidence_for(record, value))
            item["claim_provenance"]["observations"] = observations
        if category in {"requirements", "decisions"} and record.get("source") in {"user", "operator"}:
            instruction_id = record.get("instruction_id")
            item["authority_verification"] = ("verified" if instruction_id in trusted_sources
                else "unverified_historical_source_claim")
        return item

    all_requirements = [claim_view("requirements", item) for item in value["requirements"]]
    all_decisions = [claim_view("decisions", item) for item in value["decisions"]]
    all_issues = [claim_view("issues", item) for item in value["issues"]]
    all_actions = [copy.deepcopy(item) for item in ledger["next_actions"]]
    def projection(records: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
        superseded = {record.get(key) for record in records if record.get(key) is not None}
        return [copy.deepcopy(record) for record in records if record["id"] not in superseded]

    active_requirements = projection(all_requirements, "supersedes_id")
    active_decisions = projection(all_decisions, "supersedes_id")
    active_actions = projection(all_actions, "supersedes_id")

    revision_chain = []
    seen: set[str] = set()
    cursor: str | None = selected
    while cursor is not None:
        if cursor in seen: raise transactions.TransactionError("revision history contains a cycle")
        seen.add(cursor)
        ancestor = revisions.load_revision(root, cursor)
        revision_meta = design.read_json(revisions.revision_dir(root, cursor) / "revision.json")
        revision_chain.append({"revision_id": cursor, "parent_revision_id": ancestor.get("parent_revision_id"),
            "operation_id": revision_meta.get("operation_id")})
        cursor = ancestor.get("parent_revision_id")

    attempts = []
    for attempt in ledger["repair_attempts"]:
        current_outcome = transactions.resolve_repair_attempt(root, attempt,
            recording_operation_id=attempt["originating_operation_id"],
            recorded_outcome=attempt["outcome_at_recording"])
        item = copy.deepcopy(attempt)
        item["current_reconciled_outcome"] = current_outcome
        attempts.append(item)

    collections = {
        "instructions": ledger["instructions"],
        "requirements": all_requirements,
        "active_requirements": active_requirements,
        "decisions": all_decisions,
        "active_decisions": active_decisions,
        "issues": all_issues,
        "unresolved_issues": [issue for issue in all_issues if issue["status"] != "resolved"],
        "repair_attempts": attempts,
        "next_actions": all_actions,
        "active_next_actions": active_actions,
    }
    pages = {}
    for name, records in collections.items():
        pages[name] = {"count": len(records), "offset": offset, "limit": limit,
            "items": copy.deepcopy(records[offset:offset + limit]),
            "next_offset": offset + limit if offset + limit < len(records) else None,
            "complete": offset + limit >= len(records)}
    return {"schema": "bricksmith-ledger-read-v1", "revision_id": selected,
        "design_hash": value["hashes"]["design"]["value"],
        "appearance_hash": value["hashes"]["appearance"]["value"],
        "structure_hash": value["hashes"]["structure"]["value"],
        "brief": value["brief"], "brief_source": value["brief_source"],
        "brief_instruction_id": value.get("brief_instruction_id"),
        "trusted_instruction_ids": {"count": len(trusted_sources), "offset": offset, "limit": limit,
            "items": sorted(trusted_sources)[offset:offset + limit],
            "next_offset": offset + limit if offset + limit < len(trusted_sources) else None,
            "complete": offset + limit >= len(trusted_sources)},
        "revision_chain": {"count": len(revision_chain), "offset": offset, "limit": limit,
            "items": revision_chain[offset:offset + limit],
            "next_offset": offset + limit if offset + limit < len(revision_chain) else None,
            "complete": offset + limit >= len(revision_chain)}, "offset": offset, "limit": limit,
        "collections": pages}
