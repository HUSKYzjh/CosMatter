"""Human-reviewed candidate screening between retrieval and full-text parsing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class CandidateScreeningError(ValueError):
    """Raised when screening decisions are not a complete review of candidates."""


_SCHEMA_VERSION = "1.1"
_TEMPLATE_STATUS = "blank_human_candidate_screening_template_not_a_result"
_REVIEW_STATUS = "human_reviewed_candidate_screening_not_scientific_evidence"
_AUTOMATED_TRIAL_REVIEW_STATUS = "delegated_automated_trial_screening_not_scientific_evidence"
_DECISIONS = {"include_for_fulltext", "exclude", "needs_metadata_review"}
_REASONS = {
    "material_match", "property_match", "scope_match", "method_match", "primary_evidence", "counterevidence",
    "out_of_scope_material", "out_of_scope_property", "review_or_protocol", "duplicate_or_version", "not_enough_metadata",
}


def candidate_screening_template(mission_id: str, candidate_payload: object) -> dict[str, Any]:
    """Create complete blank review slots from the current flattened candidates."""
    document_ids = _candidate_document_ids(candidate_payload)
    return {
        "schema_version": _SCHEMA_VERSION,
        "mission_id": _mission_id(mission_id),
        "trust_status": _TEMPLATE_STATUS,
        "candidate_fingerprint": _candidate_fingerprint(candidate_payload),
        "decisions": [
            {"document_id": document_id, "decision": "unreviewed", "reason_codes": []}
            for document_id in document_ids
        ],
    }


def candidate_screening_from_review(
    mission_id: str,
    candidate_payload: object,
    selection: object,
) -> dict[str, Any]:
    """Validate a complete human decision for every current flattened candidate."""
    expected = _candidate_document_ids(candidate_payload)
    if not isinstance(selection, dict) or set(selection) != {"decisions"} or not isinstance(selection["decisions"], list):
        raise CandidateScreeningError("candidate screening selection must contain only a decisions array")
    decisions = selection["decisions"]
    if len(decisions) != len(expected):
        raise CandidateScreeningError("candidate screening must decide every current candidate exactly once")
    reviewed: list[dict[str, Any]] = []
    reviewed_ids: set[str] = set()
    for item in decisions:
        if not isinstance(item, dict) or set(item) != {"document_id", "decision", "reason_codes"}:
            raise CandidateScreeningError("candidate screening decision has unsupported or missing fields")
        document_id, decision, reason_codes = item.get("document_id"), item.get("decision"), item.get("reason_codes")
        if (
            not isinstance(document_id, str)
            or not document_id.strip()
            or document_id not in expected
            or document_id in reviewed_ids
            or decision not in _DECISIONS
            or not isinstance(reason_codes, list)
            or not reason_codes
            or len(reason_codes) > 6
            or any(not isinstance(code, str) or code not in _REASONS for code in reason_codes)
            or len(set(reason_codes)) != len(reason_codes)
        ):
            raise CandidateScreeningError("candidate screening decision is invalid")
        _validate_reason_compatibility(decision, set(reason_codes))
        reviewed_ids.add(document_id)
        reviewed.append({"document_id": document_id, "decision": decision, "reason_codes": sorted(reason_codes)})
    if reviewed_ids != set(expected):
        raise CandidateScreeningError("candidate screening decisions do not match the current candidates")
    return {
        "schema_version": _SCHEMA_VERSION,
        "mission_id": _mission_id(mission_id),
        "trust_status": _REVIEW_STATUS,
        "candidate_count": len(expected),
        "candidate_fingerprint": _candidate_fingerprint(candidate_payload),
        "decisions": sorted(reviewed, key=lambda item: item["document_id"]),
    }


def candidate_screening_from_automated_trial(
    mission_id: str,
    candidate_payload: object,
    selection: object,
) -> dict[str, Any]:
    """Validate a complete delegated-agent trial screening without humanising it.

    This artifact may authorize only an explicitly opted-in parser trial.  It
    is intentionally written separately from the human screening artifact and
    never upgrades a candidate to accepted scientific evidence.
    """
    artifact = candidate_screening_from_review(mission_id, candidate_payload, selection)
    artifact["trust_status"] = _AUTOMATED_TRIAL_REVIEW_STATUS
    return artifact


def write_candidate_screening_template(run_dir: Path, template: dict[str, Any]) -> Path:
    _validate_template(template)
    return _write(run_dir / "candidate_screening_template.json", template)


def write_candidate_screening(run_dir: Path, artifact: dict[str, Any]) -> Path:
    _validate_screening(artifact)
    return _write(run_dir / "candidate_screening.json", artifact)


def write_automated_trial_candidate_screening(run_dir: Path, artifact: dict[str, Any]) -> Path:
    _validate_screening(artifact, allowed_statuses={_AUTOMATED_TRIAL_REVIEW_STATUS})
    return _write(run_dir / "automated_trial_candidate_screening.json", artifact)


def require_document_screened_for_fulltext(
    run_dir: Path,
    mission_id: str,
    candidate_payload: object,
    document_id: str,
    *,
    allow_delegated_automated_trial: bool = False,
) -> None:
    """Require a current explicit include decision before an external parser call."""
    if not isinstance(document_id, str) or not document_id.strip():
        raise CandidateScreeningError("document_id must be nonempty")
    human_artifact = load_candidate_screening(run_dir / "candidate_screening.json", mission_id)
    automated_artifact = load_automated_trial_candidate_screening(run_dir / "automated_trial_candidate_screening.json", mission_id) if allow_delegated_automated_trial else None
    artifacts = [artifact for artifact in (human_artifact, automated_artifact) if artifact is not None]
    if not artifacts:
        raise CandidateScreeningError("full-text parsing requires a completed human candidate screening or explicit delegated automated trial screening")
    allowed_statuses = {_REVIEW_STATUS, _AUTOMATED_TRIAL_REVIEW_STATUS} if allow_delegated_automated_trial else {_REVIEW_STATUS}
    artifact = next((item for item in artifacts if screening_matches_candidates(item, candidate_payload, allowed_statuses=allowed_statuses)), None)
    if artifact is None:
        raise CandidateScreeningError("candidate screening is stale; review the current retrieval candidate set")
    reviewed = {item["document_id"]: item["decision"] for item in artifact["decisions"]}
    if reviewed.get(document_id) != "include_for_fulltext":
        raise CandidateScreeningError("document is not approved for full-text parsing by candidate screening")


def screening_matches_candidates(
    artifact: object,
    candidate_payload: object,
    *,
    allowed_statuses: set[str] | None = None,
) -> bool:
    """Return whether a reviewed screening still matches the complete candidate set."""
    try:
        _validate_screening(artifact, allowed_statuses=allowed_statuses)
        expected = _candidate_document_ids(candidate_payload)
        reviewed = {item["document_id"] for item in artifact["decisions"]}
        return (
            artifact["candidate_count"] == len(expected)
            and reviewed == set(expected)
            and artifact["candidate_fingerprint"] == _candidate_fingerprint(candidate_payload)
        )
    except CandidateScreeningError:
        return False


def candidate_fingerprint(candidate_payload: object) -> str:
    """Return the bounded candidate-set identity used by human gates."""
    return _candidate_fingerprint(candidate_payload)


def load_candidate_screening(path: Path, mission_id: str) -> dict[str, Any] | None:
    return _load_screening(path, mission_id, {_REVIEW_STATUS})


def load_automated_trial_candidate_screening(path: Path, mission_id: str) -> dict[str, Any] | None:
    """Load an explicitly separate delegated-agent trial screening artifact."""
    return _load_screening(path, mission_id, {_AUTOMATED_TRIAL_REVIEW_STATUS})


def _load_screening(path: Path, mission_id: str, allowed_statuses: set[str]) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise CandidateScreeningError("candidate screening artifact is invalid JSON") from error
    _validate_screening(artifact, allowed_statuses=allowed_statuses)
    if artifact["mission_id"] != _mission_id(mission_id):
        raise CandidateScreeningError("candidate screening does not belong to this mission")
    return artifact


def _candidate_document_ids(payload: object) -> tuple[str, ...]:
    if not isinstance(payload, dict) or not isinstance(payload.get("candidates"), list):
        raise CandidateScreeningError("candidate screening requires a retrieval candidates artifact")
    result: list[str] = []
    seen: set[str] = set()
    for candidate in payload["candidates"]:
        document_id = candidate.get("document_id") if isinstance(candidate, dict) else None
        if not isinstance(document_id, str) or not document_id.strip() or len(document_id) > 255 or document_id in seen:
            raise CandidateScreeningError("retrieval candidate identity is invalid")
        seen.add(document_id)
        result.append(document_id)
    if not result or len(result) > 250:
        raise CandidateScreeningError("candidate screening requires 1 to 250 unique candidates")
    return tuple(result)


def _validate_reason_compatibility(decision: str, reasons: set[str]) -> None:
    inclusion = {"material_match", "property_match", "scope_match", "method_match", "primary_evidence", "counterevidence"}
    exclusion = {"out_of_scope_material", "out_of_scope_property", "review_or_protocol", "duplicate_or_version", "not_enough_metadata"}
    if decision == "include_for_fulltext" and (not reasons & inclusion or reasons & exclusion):
        raise CandidateScreeningError("full-text inclusion requires positive scope reasons only")
    if decision == "exclude" and (not reasons & exclusion or reasons & inclusion):
        raise CandidateScreeningError("exclusion requires negative scope reasons only")
    if decision == "needs_metadata_review" and reasons != {"not_enough_metadata"}:
        raise CandidateScreeningError("metadata-review decisions require only not_enough_metadata")


def _validate_template(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "mission_id", "trust_status", "candidate_fingerprint", "decisions"}:
        raise CandidateScreeningError("candidate screening template fields are invalid")
    if payload.get("schema_version") != _SCHEMA_VERSION or payload.get("trust_status") != _TEMPLATE_STATUS:
        raise CandidateScreeningError("candidate screening template boundary is invalid")
    if not isinstance(payload.get("mission_id"), str) or not payload["mission_id"].strip() or not _is_fingerprint(payload.get("candidate_fingerprint")) or not isinstance(payload.get("decisions"), list):
        raise CandidateScreeningError("candidate screening template identity is invalid")
    expected = [item.get("document_id") for item in payload["decisions"] if isinstance(item, dict)]
    if len(expected) != len(payload["decisions"]) or len(expected) != len(set(expected)) or not expected:
        raise CandidateScreeningError("candidate screening template identifiers are invalid")
    if any(set(item) != {"document_id", "decision", "reason_codes"} or item.get("decision") != "unreviewed" or item.get("reason_codes") != [] for item in payload["decisions"]):
        raise CandidateScreeningError("candidate screening template decisions are invalid")


def _validate_screening(payload: object, *, allowed_statuses: set[str] | None = None) -> None:
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "mission_id", "trust_status", "candidate_count", "candidate_fingerprint", "decisions"}:
        raise CandidateScreeningError("candidate screening artifact fields are invalid")
    allowed_statuses = allowed_statuses or {_REVIEW_STATUS}
    if payload.get("schema_version") != _SCHEMA_VERSION or payload.get("trust_status") not in allowed_statuses:
        raise CandidateScreeningError("candidate screening review boundary is invalid")
    if not isinstance(payload.get("mission_id"), str) or not payload["mission_id"].strip() or not isinstance(payload.get("candidate_count"), int) or not _is_fingerprint(payload.get("candidate_fingerprint")) or not isinstance(payload.get("decisions"), list):
        raise CandidateScreeningError("candidate screening artifact identity is invalid")
    if not 1 <= payload["candidate_count"] <= 250 or payload["candidate_count"] != len(payload["decisions"]):
        raise CandidateScreeningError("candidate screening artifact count is invalid")
    candidate_screening_from_review(payload["mission_id"], {"candidates": [{"document_id": item.get("document_id")} for item in payload["decisions"]]}, {"decisions": payload["decisions"]})


def _mission_id(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 160:
        raise CandidateScreeningError("mission_id is invalid")
    return value.strip()


def _write(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _candidate_fingerprint(
    payload: object,
) -> str:
    """Digest scope-relevant candidate metadata without retaining it in a review."""
    if not isinstance(payload, dict) or not isinstance(payload.get("candidates"), list):
        raise CandidateScreeningError("candidate fingerprint requires retrieval candidates")
    normalized: list[dict[str, object]] = []
    for candidate in payload["candidates"]:
        if not isinstance(candidate, dict):
            raise CandidateScreeningError("candidate fingerprint encountered an invalid candidate")
        document_id = candidate.get("document_id")
        if not isinstance(document_id, str) or not document_id.strip():
            raise CandidateScreeningError("candidate fingerprint encountered a missing document_id")
        normalized.append({
            "document_id": document_id,
            "title": candidate.get("title"),
            "source": candidate.get("source"),
            "publication_year": candidate.get("publication_year"),
            "locator_hint": candidate.get("locator_hint"),
            "score": candidate.get("score"),
            "doi": candidate.get("doi"),
            "deduplication": candidate.get("deduplication"),
            "is_content_accessible": candidate.get("is_content_accessible") is True,
            "retrieval_origins": candidate.get("retrieval_origins", []),
        })
    encoded = json.dumps(sorted(normalized, key=lambda item: str(item["document_id"])), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_fingerprint(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)
