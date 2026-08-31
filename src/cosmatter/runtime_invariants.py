"""Read-only cross-artifact invariants for a single CosMatter mission run.

This companion deliberately checks relationships rather than content.  Its
output contains counts, fixed artifact names, and digests only: it never
copies a question, provider request/response, URL, task identifier, source
excerpt, or credential into the audit artifact.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .external_dispatch import ExternalDispatchError, load_external_dispatch_ledger
from .citation_expansion import CitationExpansionError, validate_citation_expansion
from .models import MissionState
from .provider_receipts import ProviderReceiptError, audit_source_parse_receipt_links
from .source_parse import SourceParseArtifactError, load_source_parse_tasks
from .state_machine import InvalidTransitionError, MissionMachine


RUNTIME_INVARIANT_SCHEMA_VERSION = "1.0"
RUNTIME_INVARIANT_FILENAME = "runtime_invariant_audit.json"
_ARTIFACTS = (
    "mission.json", "approved_plan.json", "retrieval_candidates.json",
    "candidate_screening.json", "source_parse_tasks.json",
    "evidence_cards.json", "verification_decisions.json",
    "provider_receipts.jsonl", "external_dispatch_ledger.json",
    "citation_expansion.json",
)
_AUDIT_FIELDS = {
    "schema_version", "mission_id", "trust_status", "passed", "checks",
    "artifact_hashes", "checked_artifact_count",
}
_CHECK_FIELDS = {
    "state_transitions", "authorization_dispatch", "provider_results",
    "evidence_decisions",
}


class RuntimeInvariantError(ValueError):
    """Raised when a run cannot be inspected without guessing its state."""


def audit_runtime_invariants(run_dir: Path, mission_id: str) -> dict[str, Any]:
    """Inspect durable run relationships without I/O beyond local artifacts.

    A failed audit is intentionally non-mutating.  In particular, ``unknown``
    dispatches remain recoverable records, but keep ``passed`` false until a
    separately authorized, read-only provider-status check resolves them.
    """
    if not isinstance(mission_id, str) or not mission_id.strip():
        raise RuntimeInvariantError("mission_id is invalid")
    state = _state_transition_check(run_dir)
    dispatch = _authorization_dispatch_check(run_dir, mission_id)
    provider = _provider_result_check(run_dir, mission_id, dispatch["ledger"])
    evidence = _evidence_decision_check(run_dir, mission_id)
    checks = {
        "state_transitions": state,
        "authorization_dispatch": {key: value for key, value in dispatch.items() if key != "ledger"},
        "provider_results": provider,
        "evidence_decisions": evidence,
    }
    hashes = _artifact_hashes(run_dir)
    return {
        "schema_version": RUNTIME_INVARIANT_SCHEMA_VERSION,
        "mission_id": mission_id,
        "trust_status": "runtime_relationship_audit_not_scientific_evidence_or_provider_status_verification",
        "passed": all(check["passed"] for check in checks.values()),
        "checks": checks,
        "artifact_hashes": hashes,
        "checked_artifact_count": len(hashes),
    }


def write_runtime_invariant_audit(run_dir: Path, artifact: dict[str, Any]) -> Path:
    """Persist a validated, redacted runtime-invariant audit."""
    _validate_audit(artifact)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / RUNTIME_INVARIANT_FILENAME
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _state_transition_check(run_dir: Path) -> dict[str, Any]:
    events = _events(run_dir / "events.jsonl")
    machine = MissionMachine()
    invalid = 0
    checked = 0
    for event in events:
        # Most audit records carry the phase in which an action happened; they
        # are not state-machine transitions (a retried authorization may be
        # logged while the run is already in RETRIEVE, for example).  Only the
        # explicit orchestrator transition event is authoritative here.
        if event.get("event_type") != "state_transition":
            continue
        value = event.get("state")
        if not isinstance(value, str):
            invalid += 1
            continue
        try:
            target = MissionState(value)
        except ValueError:
            invalid += 1
            continue
        if target is machine.state:
            continue
        checked += 1
        try:
            machine.transition(target)
        except InvalidTransitionError:
            invalid += 1
    return {
        "passed": invalid == 0,
        "event_count": len(events),
        "checked_transition_count": checked,
        "invalid_transition_count": invalid,
    }


def _authorization_dispatch_check(run_dir: Path, mission_id: str) -> dict[str, Any]:
    try:
        ledger = load_external_dispatch_ledger(run_dir, mission_id)
    except ExternalDispatchError as error:
        raise RuntimeInvariantError("external dispatch ledger is invalid") from error
    authorizations: set[tuple[str, str]] = set()
    for event in _events(run_dir / "events.jsonl"):
        if event.get("event_type") != "external_plugin_dispatch_authorized":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        plugin = payload.get("plugin_id")
        call = payload.get("dsh_call_id_sha256")
        if isinstance(plugin, str) and isinstance(call, str) and _sha256(call):
            authorizations.add((plugin, call))
    entries = ledger["entries"]
    unpaired = sum((entry["plugin_id"], entry["call_id_sha256"]) not in authorizations for entry in entries)
    dispatched = sum(entry["state"] == "dispatched" for entry in entries)
    unknown = sum(entry["state"] == "unknown" for entry in entries)
    return {
        "passed": unpaired == 0 and dispatched == 0 and unknown == 0,
        "dispatch_count": len(entries),
        "authorized_dispatch_count": len(entries) - unpaired,
        "unpaired_dispatch_count": unpaired,
        "incomplete_dispatch_count": dispatched,
        "unknown_outcome_count": unknown,
        "ledger": ledger,
    }


def _provider_result_check(run_dir: Path, mission_id: str, ledger: dict[str, Any]) -> dict[str, Any]:
    receipts = _receipt_ids(run_dir / "provider_receipts.jsonl")
    missing_receipts = 0
    missing_results = 0
    mineru_completed = 0
    for entry in ledger["entries"]:
        if entry["state"] != "completed":
            continue
        operation = entry["operation"]
        if operation in {"metadata_query", "mineru_submit", "mineru_poll"}:
            missing_receipts += sum(receipt not in receipts for receipt in entry["provider_receipt_ids"])
        if operation == "metadata_query" and not (run_dir / "retrieval_candidates.json").is_file():
            missing_results += 1
        if operation == "deepseek_plan_draft" and not (run_dir / "research_plan_draft.json").is_file():
            missing_results += 1
        if operation == "deepseek_graph_plan_draft" and not (run_dir / "graph_model_plan_drafts.jsonl").is_file():
            missing_results += 1
        if operation == "citation_expansion" and not _valid_citation_expansion(run_dir / "citation_expansion.json", mission_id):
            missing_results += 1
        if operation in {"mineru_submit", "mineru_poll"}:
            mineru_completed += 1
    parse_valid = 1
    if mineru_completed:
        try:
            tasks = load_source_parse_tasks(run_dir / "source_parse_tasks.json", mission_id)
            if tasks is None:
                parse_valid = 0
            else:
                linked = audit_source_parse_receipt_links(tasks, run_dir / "provider_receipts.jsonl")
                parse_valid = int(linked["unlinked_task_count"] == 0 and linked["stale_task_state_count"] == 0)
        except (SourceParseArtifactError, ProviderReceiptError):
            parse_valid = 0
    return {
        "passed": missing_receipts == 0 and missing_results == 0 and parse_valid == 1,
        "completed_dispatch_count": sum(entry["state"] == "completed" for entry in ledger["entries"]),
        "recorded_provider_receipt_count": len(receipts),
        "missing_receipt_link_count": missing_receipts,
        "missing_result_artifact_count": missing_results,
        "mineru_receipt_task_pair_valid": parse_valid,
    }


def _valid_citation_expansion(path: Path, mission_id: str) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_citation_expansion(payload)
    except (OSError, json.JSONDecodeError, CitationExpansionError):
        return False
    return payload.get("mission_id") == mission_id


def _evidence_decision_check(run_dir: Path, mission_id: str) -> dict[str, Any]:
    cards = _array(run_dir / "evidence_cards.json")
    decisions = _array(run_dir / "verification_decisions.json")
    card_ids = {item.get("evidence_id") for item in cards if isinstance(item.get("evidence_id"), str) and item["evidence_id"].strip()}
    decisions_for_mission = [item for item in decisions if item.get("mission_id") == mission_id]
    decision_ids = [item.get("evidence_id") for item in decisions_for_mission if isinstance(item.get("evidence_id"), str)]
    duplicate = len(decision_ids) - len(set(decision_ids))
    orphan = sum(evidence_id not in card_ids for evidence_id in decision_ids)
    unpaired = sum(card_id not in set(decision_ids) for card_id in card_ids)
    accepted = sum(item.get("status") == "accepted" for item in decisions_for_mission)
    malformed = sum(
        not isinstance(item.get("decision_id"), str) or not item["decision_id"].strip()
        or item.get("status") not in {"accepted", "rejected", "unreviewed"}
        or not isinstance(item.get("reason"), str) or not item["reason"].strip()
        for item in decisions_for_mission
    )
    return {
        "passed": duplicate == 0 and orphan == 0 and unpaired == 0 and malformed == 0,
        "evidence_card_count": len(card_ids),
        "verification_decision_count": len(decisions_for_mission),
        "accepted_with_verification_decision_count": accepted,
        "unpaired_evidence_card_count": unpaired,
        "orphan_verification_decision_count": orphan,
        "duplicate_verification_decision_count": duplicate,
        "malformed_verification_decision_count": malformed,
    }


def _events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeInvariantError("event log is invalid") from error
    if not all(isinstance(item, dict) for item in rows):
        raise RuntimeInvariantError("event log is invalid")
    return rows


def _array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeInvariantError(f"{path.name} is invalid") from error
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise RuntimeInvariantError(f"{path.name} is invalid")
    return payload


def _receipt_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeInvariantError("provider receipt log is invalid") from error
    identifiers = {row.get("receipt_id") for row in rows if isinstance(row, dict) and isinstance(row.get("receipt_id"), str)}
    if len(identifiers) != len(rows) or any(not value.startswith("receipt_") for value in identifiers):
        raise RuntimeInvariantError("provider receipt log is invalid")
    return identifiers


def _artifact_hashes(run_dir: Path) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for name in _ARTIFACTS:
        path = run_dir / name
        if path.is_file():
            result.append({"name": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return result


def _validate_audit(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != _AUDIT_FIELDS:
        raise RuntimeInvariantError("runtime invariant audit fields are invalid")
    if payload.get("schema_version") != RUNTIME_INVARIANT_SCHEMA_VERSION or not isinstance(payload.get("mission_id"), str) or not payload["mission_id"].strip() or payload.get("trust_status") != "runtime_relationship_audit_not_scientific_evidence_or_provider_status_verification" or not isinstance(payload.get("passed"), bool):
        raise RuntimeInvariantError("runtime invariant audit identity is invalid")
    checks = payload.get("checks")
    if not isinstance(checks, dict) or set(checks) != _CHECK_FIELDS:
        raise RuntimeInvariantError("runtime invariant audit checks are invalid")
    if not isinstance(payload.get("artifact_hashes"), list) or not isinstance(payload.get("checked_artifact_count"), int) or payload["checked_artifact_count"] != len(payload["artifact_hashes"]):
        raise RuntimeInvariantError("runtime invariant audit artifact hashes are invalid")
    for item in payload["artifact_hashes"]:
        if not isinstance(item, dict) or set(item) != {"name", "sha256"} or item.get("name") not in _ARTIFACTS or not _sha256(item.get("sha256")):
            raise RuntimeInvariantError("runtime invariant audit artifact hash is invalid")
    if len({item["name"] for item in payload["artifact_hashes"]}) != len(payload["artifact_hashes"]):
        raise RuntimeInvariantError("runtime invariant audit artifact hashes are duplicated")
    for check in checks.values():
        if not isinstance(check, dict) or not isinstance(check.get("passed"), bool) or any(not isinstance(value, (bool, int)) or isinstance(value, bool) and key != "passed" for key, value in check.items()):
            raise RuntimeInvariantError("runtime invariant audit check is invalid")


def _sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)
