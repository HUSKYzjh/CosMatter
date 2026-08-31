"""Explicitly non-human fact checks for authorized end-to-end trials."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .source_map import AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS


class AutomatedTrialFactAuditError(ValueError):
    """Raised when a delegated trial fact audit is not source-map bounded."""


_STATUS = "delegated_automated_trial_fact_audit_not_scientific_evidence"
_INPUT_FIELDS = {"document_id", "claims"}
_INPUT_CLAIM_FIELDS = {"claim_id", "segment_id", "claim", "determination", "rationale"}
_ARTIFACT_FIELDS = {"schema_version", "mission_id", "trust_status", "document_id", "source_map_sha256", "claims"}
_DETERMINATIONS = {"directly_supported", "qualified_by_source", "not_supported"}


def automated_trial_fact_audit_from_review(*, mission_id: str, source_map: object, review: object) -> dict[str, Any]:
    """Bind delegated-agent claim checks to exact Source Map segment IDs.

    The function records a reviewer determination, never promotes a claim to a
    material fact or accepted evidence card.  It deliberately accepts only the
    dedicated automated-trial Source Map trust state.
    """
    if not isinstance(mission_id, str) or not mission_id.strip():
        raise AutomatedTrialFactAuditError("mission_id is invalid")
    if not isinstance(source_map, dict) or source_map.get("mission_id") != mission_id or source_map.get("trust_status") != AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS:
        raise AutomatedTrialFactAuditError("automated trial fact audit requires a delegated automated trial Source Map")
    document_id = source_map.get("document_id")
    segments = source_map.get("segments")
    if not isinstance(document_id, str) or not document_id or not isinstance(segments, list) or not segments:
        raise AutomatedTrialFactAuditError("automated trial Source Map is invalid")
    known_segments = {item.get("segment_id") for item in segments if isinstance(item, dict)}
    if not isinstance(review, dict) or set(review) != _INPUT_FIELDS or review.get("document_id") != document_id or not isinstance(review.get("claims"), list):
        raise AutomatedTrialFactAuditError("automated trial fact review must match the Source Map document")
    if not 1 <= len(review["claims"]) <= 24:
        raise AutomatedTrialFactAuditError("automated trial fact review requires one to twenty-four claims")
    claims: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in review["claims"]:
        if not isinstance(item, dict) or set(item) != _INPUT_CLAIM_FIELDS:
            raise AutomatedTrialFactAuditError("automated trial fact claim fields are invalid")
        claim_id, segment_id, claim, determination, rationale = (item.get(key) for key in ("claim_id", "segment_id", "claim", "determination", "rationale"))
        if (
            not all(isinstance(value, str) and value.strip() for value in (claim_id, segment_id, claim, determination, rationale))
            or claim_id in seen
            or segment_id not in known_segments
            or determination not in _DETERMINATIONS
            or len(claim_id) > 120
            or len(claim) > 500
            or len(rationale) > 300
        ):
            raise AutomatedTrialFactAuditError("automated trial fact claim is invalid or lacks a selected source segment")
        seen.add(claim_id)
        claims.append({"claim_id": claim_id, "segment_id": segment_id, "claim": claim, "determination": determination, "rationale": rationale})
    return {
        "schema_version": "1.0",
        "mission_id": mission_id,
        "trust_status": _STATUS,
        "document_id": document_id,
        "source_map_sha256": _source_map_sha256(source_map),
        "claims": sorted(claims, key=lambda item: item["claim_id"]),
    }


def write_automated_trial_fact_audit(run_dir: Path, artifact: dict[str, Any]) -> Path:
    _validate_artifact(artifact)
    path = run_dir / "automated_trial_fact_audits" / f"{hashlib.sha256(artifact['document_id'].encode('utf-8')).hexdigest()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _source_map_sha256(source_map: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(source_map, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _validate_artifact(artifact: object) -> None:
    if not isinstance(artifact, dict) or set(artifact) != _ARTIFACT_FIELDS or artifact.get("schema_version") != "1.0" or artifact.get("trust_status") != _STATUS:
        raise AutomatedTrialFactAuditError("automated trial fact audit artifact is invalid")
    if not isinstance(artifact.get("mission_id"), str) or not artifact["mission_id"] or not isinstance(artifact.get("document_id"), str) or not artifact["document_id"] or not _sha256(artifact.get("source_map_sha256")):
        raise AutomatedTrialFactAuditError("automated trial fact audit identity is invalid")
    claims = artifact.get("claims")
    if not isinstance(claims, list) or not 1 <= len(claims) <= 24:
        raise AutomatedTrialFactAuditError("automated trial fact audit claims are invalid")
    seen: set[str] = set()
    for item in claims:
        if not isinstance(item, dict) or set(item) != _INPUT_CLAIM_FIELDS or any(not isinstance(item.get(key), str) or not item[key] for key in _INPUT_CLAIM_FIELDS) or item["claim_id"] in seen or item["determination"] not in _DETERMINATIONS:
            raise AutomatedTrialFactAuditError("automated trial fact audit claim is invalid")
        seen.add(item["claim_id"])


def _sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)
