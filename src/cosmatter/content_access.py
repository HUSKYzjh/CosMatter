"""Hash-only confirmation that a screened Sciverse document read succeeded."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .candidate_screening import CandidateScreeningError, candidate_fingerprint


class ContentAccessError(ValueError):
    pass


_SCHEMA_VERSION = "1.0"
_TRUST_STATUS = "explicit_human_requested_content_access_probe_not_evidence"
_AUTOMATED_TRIAL_TRUST_STATUS = "delegated_automated_trial_content_access_probe_not_evidence"
_FIELDS = {"schema_version", "mission_id", "candidate_fingerprint", "trust_status", "confirmations"}
_ITEM_FIELDS = {"document_id", "provider", "receipt_id", "content_sha256"}


def record_sciverse_content_access(
    run_dir: Path,
    *,
    mission_id: str,
    candidate_payload: object,
    document_id: str,
    receipt: object,
    delegated_automated_trial: bool = False,
) -> Path:
    """Persist only proof of a human-requested successful content read."""
    fingerprint = candidate_fingerprint(candidate_payload)
    item = _confirmation_item(document_id, receipt)
    artifact = load_content_access(run_dir / "content_access_confirmations.json", mission_id)
    desired_trust_status = _AUTOMATED_TRIAL_TRUST_STATUS if delegated_automated_trial else _TRUST_STATUS
    if artifact is None or artifact["candidate_fingerprint"] != fingerprint or artifact["trust_status"] != desired_trust_status:
        artifact = {
            "schema_version": _SCHEMA_VERSION,
            "mission_id": _mission_id(mission_id),
            "candidate_fingerprint": fingerprint,
            "trust_status": desired_trust_status,
            "confirmations": [],
        }
    artifact["confirmations"] = [entry for entry in artifact["confirmations"] if entry["document_id"] != item["document_id"]]
    artifact["confirmations"].append(item)
    artifact["confirmations"].sort(key=lambda entry: entry["document_id"])
    _validate(artifact, allow_delegated_automated_trial=delegated_automated_trial)
    path = run_dir / "content_access_confirmations.json"
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def has_sciverse_content_access(
    run_dir: Path,
    *,
    mission_id: str,
    candidate_payload: object,
    document_id: str,
) -> bool:
    artifact = load_content_access(run_dir / "content_access_confirmations.json", mission_id)
    if artifact is None:
        return False
    try:
        return artifact["candidate_fingerprint"] == candidate_fingerprint(candidate_payload) and any(
            entry["document_id"] == document_id and entry["provider"] == "sciverse"
            for entry in artifact["confirmations"]
        )
    except CandidateScreeningError:
        return False


def load_content_access(path: Path, mission_id: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ContentAccessError("content access confirmation is invalid JSON") from error
    _validate(artifact)
    if artifact["mission_id"] != _mission_id(mission_id):
        raise ContentAccessError("content access confirmation does not belong to this mission")
    return artifact


def _confirmation_item(document_id: str, receipt: object) -> dict[str, str]:
    if not isinstance(document_id, str) or not document_id.strip() or len(document_id.strip()) > 255:
        raise ContentAccessError("content access document_id is invalid")
    if not isinstance(receipt, dict) or receipt.get("provider") != "sciverse" or receipt.get("operation") != "content":
        raise ContentAccessError("content access requires a Sciverse content receipt")
    receipt_id, digest = receipt.get("receipt_id"), receipt.get("content_sha256")
    expected_document_digest = hashlib.sha256(document_id.strip().encode("utf-8")).hexdigest()
    if receipt.get("document_id_sha256") != expected_document_digest or not _identifier(receipt_id) or not _sha256(digest):
        raise ContentAccessError("content access receipt does not match the document")
    return {"document_id": document_id.strip(), "provider": "sciverse", "receipt_id": receipt_id, "content_sha256": digest}


def _validate(artifact: object, *, allow_delegated_automated_trial: bool = True) -> None:
    if not isinstance(artifact, dict) or set(artifact) != _FIELDS:
        raise ContentAccessError("content access confirmation fields are invalid")
    allowed_trust_statuses = {_TRUST_STATUS, _AUTOMATED_TRIAL_TRUST_STATUS} if allow_delegated_automated_trial else {_TRUST_STATUS}
    if artifact.get("schema_version") != _SCHEMA_VERSION or artifact.get("trust_status") not in allowed_trust_statuses or not _identifier(artifact.get("mission_id")) or not _sha256(artifact.get("candidate_fingerprint")):
        raise ContentAccessError("content access confirmation identity is invalid")
    confirmations = artifact.get("confirmations")
    if not isinstance(confirmations, list) or not 1 <= len(confirmations) <= 250:
        raise ContentAccessError("content access confirmation list is invalid")
    seen: set[str] = set()
    for item in confirmations:
        if not isinstance(item, dict) or set(item) != _ITEM_FIELDS or item.get("provider") != "sciverse" or not _identifier(item.get("document_id")) or not _identifier(item.get("receipt_id")) or not _sha256(item.get("content_sha256")) or item["document_id"] in seen:
            raise ContentAccessError("content access confirmation item is invalid")
        seen.add(item["document_id"])


def _mission_id(value: str) -> str:
    if not _identifier(value):
        raise ContentAccessError("mission_id is invalid")
    return value.strip()


def _identifier(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value.strip()) <= 255


def _sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)
