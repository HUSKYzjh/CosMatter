"""Review-gated reconciliation for exact-title candidate duplicates.

Retrieval history remains immutable.  This module derives a separate identity
layer: exact normalized DOI equality may authorize an alias mapping, while an
exact normalized-title match alone can only create a human-review queue item.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from .candidate_screening import candidate_fingerprint
from .metadata_enrichment import resolved_dois_for_candidates
from .models import normalized_doi_or_none, utc_now


QUEUE_SCHEMA_VERSION = "cosmatter.candidate-duplicate-queue/v1"
QUEUE_TRUST_STATUS = "derived_exact_title_duplicate_queue_not_scientific_evidence"
REVIEW_SCHEMA_VERSION = "cosmatter.candidate-duplicate-review/v1"
REVIEW_TEMPLATE_TRUST_STATUS = "unreviewed_candidate_duplicate_identity_template"
REVIEW_TRUST_STATUS = "human_reviewed_candidate_duplicate_identity_decisions"
RECONCILIATION_SCHEMA_VERSION = "cosmatter.candidate-duplicate-reconciliation/v1"
RECONCILIATION_TRUST_STATUS = "candidate_identity_alias_layer_not_scientific_evidence"

_QUEUE_STATES = {
    "same_doi_merge_allowed",
    "conflicting_doi_review_required",
    "partial_doi_review_required",
    "title_only_review_required",
}
_DECISIONS = {"same_work", "distinct_works", "unresolved"}
_REASONS = {
    "human_bibliographic_confirmation",
    "preprint_published_version",
    "publisher_duplicate_record",
    "distinct_study_same_title",
    "different_versions_not_equivalent",
    "insufficient_metadata",
}
_SAME_WORK_REASONS = {
    "human_bibliographic_confirmation",
    "preprint_published_version",
    "publisher_duplicate_record",
}
_DISTINCT_REASONS = {"distinct_study_same_title", "different_versions_not_equivalent"}
_MAX_CANDIDATES = 5_000
_MAX_GROUPS = 2_500
_MAX_REVISIONS = 48


class CandidateDuplicateReconciliationError(ValueError):
    """Raised when candidate identity review is stale, incomplete, or unsafe."""


def build_candidate_duplicate_queue(
    mission_id: str,
    candidate_payload: object,
    metadata_enrichment: object | None = None,
) -> dict[str, Any]:
    """Detect exact normalized-title groups without treating title as identity."""
    mission_id = _identifier(mission_id, "mission_id")
    candidates = _candidate_index(candidate_payload)
    enriched_dois = resolved_dois_for_candidates(metadata_enrichment, mission_id, candidate_payload)
    by_title: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        by_title.setdefault(_normalized_title(candidate["title"]), []).append(candidate)

    fingerprint = candidate_fingerprint(candidate_payload)
    groups: list[dict[str, Any]] = []
    for title, matches in by_title.items():
        if len(matches) < 2:
            continue
        document_ids = [candidate["document_id"] for candidate in matches]
        dois = [
            normalized_doi_or_none(enriched_dois.get(candidate["document_id"]) or candidate.get("doi"))
            for candidate in matches
        ]
        present_dois = {doi for doi in dois if doi is not None}
        if len(present_dois) > 1:
            state = "conflicting_doi_review_required"
        elif len(present_dois) == 1 and all(doi is not None for doi in dois):
            state = "same_doi_merge_allowed"
        elif present_dois:
            state = "partial_doi_review_required"
        else:
            state = "title_only_review_required"
        canonical = _preferred_document_id(matches) if state == "same_doi_merge_allowed" else None
        groups.append(
            {
                "group_id": _group_id(fingerprint, title, document_ids),
                "title_sha256": hashlib.sha256(title.encode("utf-8")).hexdigest(),
                "document_ids": document_ids,
                "doi_state": state,
                "canonical_document_id": canonical,
                "alias_document_ids": [item for item in document_ids if item != canonical] if canonical else [],
            }
        )
    if len(groups) > _MAX_GROUPS:
        raise CandidateDuplicateReconciliationError("candidate duplicate group limit exceeded")
    summary = {f"{state}_count": sum(group["doi_state"] == state for group in groups) for state in sorted(_QUEUE_STATES)}
    queue = {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "mission_id": mission_id,
        "trust_status": QUEUE_TRUST_STATUS,
        "candidate_fingerprint": fingerprint,
        "metadata_enrichment_sha256": _optional_artifact_sha256(metadata_enrichment),
        "group_count": len(groups),
        "groups": groups,
        "summary": summary,
    }
    _validate_queue(queue)
    return queue


def write_candidate_duplicate_queue(run_dir: Path, queue: dict[str, Any]) -> Path:
    _validate_queue(queue)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "candidate_duplicate_queue.json"
    path.write_text(json.dumps(queue, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_candidate_duplicate_queue(
    path: Path,
    mission_id: str,
    candidate_payload: object,
    metadata_enrichment: object | None = None,
) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        queue = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CandidateDuplicateReconciliationError("candidate duplicate queue is invalid JSON") from error
    _validate_queue(queue)
    expected = build_candidate_duplicate_queue(mission_id, candidate_payload, metadata_enrichment)
    if queue != expected:
        raise CandidateDuplicateReconciliationError("candidate duplicate queue is stale or has been modified")
    return queue


def candidate_duplicate_review_template(queue: object) -> dict[str, Any]:
    _validate_queue(queue)
    decisions = [
        {"group_id": group["group_id"], "decision": "unreviewed", "canonical_document_id": None, "reason_code": None}
        for group in queue["groups"]
        if group["doi_state"] != "same_doi_merge_allowed"
    ]
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "mission_id": queue["mission_id"],
        "trust_status": REVIEW_TEMPLATE_TRUST_STATUS,
        "candidate_fingerprint": queue["candidate_fingerprint"],
        "queue_sha256": _queue_sha256(queue),
        "decisions": decisions,
    }


def write_candidate_duplicate_review_template(path: Path, template: dict[str, Any]) -> Path:
    _validate_review_envelope(template, allow_unreviewed=True)
    if path.exists():
        raise CandidateDuplicateReconciliationError("candidate duplicate review template already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(template, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def candidate_duplicate_reconciliation_from_review(queue: object, selection: object) -> dict[str, Any]:
    _validate_queue(queue)
    _validate_review_envelope(selection, allow_unreviewed=False)
    if (
        selection["mission_id"] != queue["mission_id"]
        or selection["candidate_fingerprint"] != queue["candidate_fingerprint"]
        or selection["queue_sha256"] != _queue_sha256(queue)
        or selection["trust_status"] != REVIEW_TRUST_STATUS
    ):
        raise CandidateDuplicateReconciliationError("candidate duplicate review is stale or not human reviewed")
    pending = {group["group_id"]: group for group in queue["groups"] if group["doi_state"] != "same_doi_merge_allowed"}
    decisions = selection["decisions"]
    if {decision["group_id"] for decision in decisions} != set(pending) or len(decisions) != len(pending):
        raise CandidateDuplicateReconciliationError("candidate duplicate review must decide every pending group exactly once")

    reviewed = {decision["group_id"]: decision for decision in decisions}
    resolutions: list[dict[str, Any]] = []
    for group in queue["groups"]:
        if group["doi_state"] == "same_doi_merge_allowed":
            resolutions.append(
                {
                    "group_id": group["group_id"],
                    "resolution": "same_work",
                    "basis": "exact_normalized_doi",
                    "canonical_document_id": group["canonical_document_id"],
                    "alias_document_ids": group["alias_document_ids"],
                }
            )
            continue
        decision = reviewed[group["group_id"]]
        canonical = decision["canonical_document_id"]
        if decision["decision"] == "same_work" and canonical not in group["document_ids"]:
            raise CandidateDuplicateReconciliationError("candidate duplicate review canonical document is outside its group")
        resolutions.append(
            {
                "group_id": group["group_id"],
                "resolution": decision["decision"],
                "basis": decision["reason_code"],
                "canonical_document_id": canonical,
                "alias_document_ids": [item for item in group["document_ids"] if item != canonical] if canonical else [],
            }
        )
    artifact = {
        "schema_version": RECONCILIATION_SCHEMA_VERSION,
        "mission_id": queue["mission_id"],
        "trust_status": RECONCILIATION_TRUST_STATUS,
        "candidate_fingerprint": queue["candidate_fingerprint"],
        "queue_sha256": _queue_sha256(queue),
        "resolutions": resolutions,
        "summary": _resolution_summary(resolutions),
        "revision_history": [],
    }
    _validate_reconciliation(artifact, allow_empty_history=True)
    return artifact


def write_candidate_duplicate_reconciliation(run_dir: Path, artifact: dict[str, Any]) -> Path:
    _validate_reconciliation(artifact, allow_empty_history=True)
    path = run_dir / "candidate_duplicate_reconciliation.json"
    history: list[dict[str, Any]] = []
    if path.exists():
        existing = load_candidate_duplicate_reconciliation(path, artifact["mission_id"])
        if existing is None or any(existing[key] != artifact[key] for key in ("candidate_fingerprint", "queue_sha256")):
            raise CandidateDuplicateReconciliationError("cannot replace reconciliation for a different candidate queue")
        history = list(existing["revision_history"])
    if len(history) >= _MAX_REVISIONS:
        raise CandidateDuplicateReconciliationError("candidate duplicate reconciliation revision limit exceeded")
    stored = {**artifact, "revision_history": [*history, _revision(len(history) + 1, artifact["resolutions"])]}
    _validate_reconciliation(stored)
    path.write_text(json.dumps(stored, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_candidate_duplicate_reconciliation(path: Path, mission_id: str, queue: object | None = None) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CandidateDuplicateReconciliationError("candidate duplicate reconciliation is invalid JSON") from error
    _validate_reconciliation(artifact)
    if artifact["mission_id"] != mission_id:
        raise CandidateDuplicateReconciliationError("candidate duplicate reconciliation belongs to another mission")
    if queue is not None:
        _validate_reconciliation_against_queue(artifact, queue)
    return artifact


def _candidate_index(payload: object) -> list[dict[str, Any]]:
    candidates = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= _MAX_CANDIDATES:
        raise CandidateDuplicateReconciliationError("candidate history is missing or exceeds the review boundary")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise CandidateDuplicateReconciliationError("candidate history contains an invalid item")
        document_id = candidate.get("document_id")
        title = candidate.get("title")
        if not isinstance(document_id, str) or not document_id.strip() or len(document_id) > 300 or document_id in seen or not isinstance(title, str) or not title.strip() or len(title) > 500:
            raise CandidateDuplicateReconciliationError("candidate identity metadata is invalid or duplicated")
        seen.add(document_id)
        result.append(candidate)
    return result


def _validate_queue(queue: object) -> None:
    fields = {"schema_version", "mission_id", "trust_status", "candidate_fingerprint", "metadata_enrichment_sha256", "group_count", "groups", "summary"}
    if not isinstance(queue, dict) or set(queue) != fields or queue.get("schema_version") != QUEUE_SCHEMA_VERSION or queue.get("trust_status") != QUEUE_TRUST_STATUS:
        raise CandidateDuplicateReconciliationError("candidate duplicate queue fields are invalid")
    _identifier(queue.get("mission_id"), "mission_id")
    if not _sha256(queue.get("candidate_fingerprint")) or queue.get("metadata_enrichment_sha256") is not None and not _sha256(queue["metadata_enrichment_sha256"]):
        raise CandidateDuplicateReconciliationError("candidate duplicate queue binding is invalid")
    groups = queue.get("groups")
    summary = queue.get("summary")
    if not isinstance(groups, list) or len(groups) > _MAX_GROUPS or queue.get("group_count") != len(groups) or not isinstance(summary, dict) or set(summary) != {f"{state}_count" for state in _QUEUE_STATES}:
        raise CandidateDuplicateReconciliationError("candidate duplicate queue counts are invalid")
    seen_groups: set[str] = set()
    seen_documents: set[str] = set()
    for group in groups:
        expected = {"group_id", "title_sha256", "document_ids", "doi_state", "canonical_document_id", "alias_document_ids"}
        if not isinstance(group, dict) or set(group) != expected or not isinstance(group.get("group_id"), str) or not re.fullmatch(r"candidate_duplicate_[a-f0-9]{24}", group["group_id"]) or group["group_id"] in seen_groups or not _sha256(group.get("title_sha256")) or group.get("doi_state") not in _QUEUE_STATES:
            raise CandidateDuplicateReconciliationError("candidate duplicate group is invalid")
        documents = group.get("document_ids")
        aliases = group.get("alias_document_ids")
        canonical = group.get("canonical_document_id")
        if not isinstance(documents, list) or not 2 <= len(documents) <= _MAX_CANDIDATES or len(set(documents)) != len(documents) or any(not isinstance(item, str) or not item or len(item) > 300 for item in documents) or seen_documents.intersection(documents) or not isinstance(aliases, list):
            raise CandidateDuplicateReconciliationError("candidate duplicate group document identities are invalid")
        merge_allowed = group["doi_state"] == "same_doi_merge_allowed"
        if merge_allowed != (isinstance(canonical, str) and canonical in documents) or (aliases != [item for item in documents if item != canonical] if merge_allowed else aliases != [] or canonical is not None):
            raise CandidateDuplicateReconciliationError("candidate duplicate automatic alias boundary is invalid")
        seen_groups.add(group["group_id"])
        seen_documents.update(documents)
    for state in _QUEUE_STATES:
        count = summary.get(f"{state}_count")
        if not isinstance(count, int) or isinstance(count, bool) or count != sum(group["doi_state"] == state for group in groups):
            raise CandidateDuplicateReconciliationError("candidate duplicate queue summary is invalid")


def _validate_review_envelope(review: object, *, allow_unreviewed: bool) -> None:
    fields = {"schema_version", "mission_id", "trust_status", "candidate_fingerprint", "queue_sha256", "decisions"}
    expected_trust = REVIEW_TEMPLATE_TRUST_STATUS if allow_unreviewed else REVIEW_TRUST_STATUS
    if not isinstance(review, dict) or set(review) != fields or review.get("schema_version") != REVIEW_SCHEMA_VERSION or review.get("trust_status") != expected_trust or not _sha256(review.get("candidate_fingerprint")) or not _sha256(review.get("queue_sha256")):
        raise CandidateDuplicateReconciliationError("candidate duplicate review envelope is invalid")
    _identifier(review.get("mission_id"), "mission_id")
    decisions = review.get("decisions")
    if not isinstance(decisions, list) or len(decisions) > _MAX_GROUPS:
        raise CandidateDuplicateReconciliationError("candidate duplicate review decisions are invalid")
    seen: set[str] = set()
    for item in decisions:
        if not isinstance(item, dict) or set(item) != {"group_id", "decision", "canonical_document_id", "reason_code"} or not isinstance(item.get("group_id"), str) or not re.fullmatch(r"candidate_duplicate_[a-f0-9]{24}", item["group_id"]) or item["group_id"] in seen:
            raise CandidateDuplicateReconciliationError("candidate duplicate review decision identity is invalid")
        decision, canonical, reason = item.get("decision"), item.get("canonical_document_id"), item.get("reason_code")
        if allow_unreviewed:
            if decision != "unreviewed" or canonical is not None or reason is not None:
                raise CandidateDuplicateReconciliationError("candidate duplicate review template must remain blank")
        elif decision not in _DECISIONS or reason not in _REASONS or (decision == "same_work") != isinstance(canonical, str) or isinstance(canonical, str) and (not canonical or len(canonical) > 300) or decision == "same_work" and reason not in _SAME_WORK_REASONS or decision == "distinct_works" and reason not in _DISTINCT_REASONS or decision == "unresolved" and reason != "insufficient_metadata":
            raise CandidateDuplicateReconciliationError("candidate duplicate review decision is invalid")
        seen.add(item["group_id"])


def _validate_reconciliation(artifact: object, *, allow_empty_history: bool = False) -> None:
    fields = {"schema_version", "mission_id", "trust_status", "candidate_fingerprint", "queue_sha256", "resolutions", "summary", "revision_history"}
    if not isinstance(artifact, dict) or set(artifact) != fields or artifact.get("schema_version") != RECONCILIATION_SCHEMA_VERSION or artifact.get("trust_status") != RECONCILIATION_TRUST_STATUS or not _sha256(artifact.get("candidate_fingerprint")) or not _sha256(artifact.get("queue_sha256")):
        raise CandidateDuplicateReconciliationError("candidate duplicate reconciliation fields are invalid")
    _identifier(artifact.get("mission_id"), "mission_id")
    resolutions = artifact.get("resolutions")
    if not isinstance(resolutions, list) or len(resolutions) > _MAX_GROUPS:
        raise CandidateDuplicateReconciliationError("candidate duplicate resolutions are invalid")
    seen: set[str] = set()
    for item in resolutions:
        if not isinstance(item, dict) or set(item) != {"group_id", "resolution", "basis", "canonical_document_id", "alias_document_ids"} or not isinstance(item.get("group_id"), str) or not re.fullmatch(r"candidate_duplicate_[a-f0-9]{24}", item["group_id"]) or item["group_id"] in seen or item.get("resolution") not in _DECISIONS or item.get("basis") not in _REASONS | {"exact_normalized_doi"} or not isinstance(item.get("alias_document_ids"), list):
            raise CandidateDuplicateReconciliationError("candidate duplicate resolution is invalid")
        resolution, basis = item["resolution"], item["basis"]
        canonical, aliases = item.get("canonical_document_id"), item["alias_document_ids"]
        valid_basis = (
            resolution == "same_work" and basis in _SAME_WORK_REASONS | {"exact_normalized_doi"}
            or resolution == "distinct_works" and basis in _DISTINCT_REASONS
            or resolution == "unresolved" and basis == "insufficient_metadata"
        )
        if not valid_basis or (resolution == "same_work") != isinstance(canonical, str) or isinstance(canonical, str) and (not canonical or len(canonical) > 300) or resolution == "same_work" and not aliases or resolution != "same_work" and aliases or len(set(aliases)) != len(aliases) or any(not isinstance(alias, str) or not alias or len(alias) > 300 or alias == canonical for alias in aliases):
            raise CandidateDuplicateReconciliationError("candidate duplicate alias mapping is invalid")
        seen.add(item["group_id"])
    if artifact.get("summary") != _resolution_summary(resolutions):
        raise CandidateDuplicateReconciliationError("candidate duplicate reconciliation summary is invalid")
    history = artifact.get("revision_history")
    if not isinstance(history, list) or len(history) > _MAX_REVISIONS or not history and not allow_empty_history:
        raise CandidateDuplicateReconciliationError("candidate duplicate reconciliation history is invalid")
    for index, revision in enumerate(history, start=1):
        counts = revision.get("resolution_counts") if isinstance(revision, dict) else None
        if not isinstance(revision, dict) or set(revision) != {"revision", "recorded_at", "resolution_counts", "resolutions_sha256"} or revision.get("revision") != index or not _utc_timestamp(revision.get("recorded_at")) or not _valid_resolution_counts(counts) or not _sha256(revision.get("resolutions_sha256")):
            raise CandidateDuplicateReconciliationError("candidate duplicate reconciliation revision is invalid")
    if history and history[-1] != _revision(len(history), resolutions, recorded_at=history[-1]["recorded_at"]):
        raise CandidateDuplicateReconciliationError("candidate duplicate reconciliation history does not match current resolutions")


def _validate_reconciliation_against_queue(artifact: dict[str, Any], queue: object) -> None:
    _validate_queue(queue)
    if artifact["mission_id"] != queue["mission_id"] or artifact["candidate_fingerprint"] != queue["candidate_fingerprint"] or artifact["queue_sha256"] != _queue_sha256(queue):
        raise CandidateDuplicateReconciliationError("candidate duplicate reconciliation is stale for the current queue")
    by_group = {item["group_id"]: item for item in artifact["resolutions"]}
    if set(by_group) != {group["group_id"] for group in queue["groups"]}:
        raise CandidateDuplicateReconciliationError("candidate duplicate reconciliation does not cover the current queue")
    for group in queue["groups"]:
        resolution = by_group[group["group_id"]]
        if group["doi_state"] == "same_doi_merge_allowed":
            if resolution != {
                "group_id": group["group_id"], "resolution": "same_work", "basis": "exact_normalized_doi",
                "canonical_document_id": group["canonical_document_id"], "alias_document_ids": group["alias_document_ids"],
            }:
                raise CandidateDuplicateReconciliationError("exact DOI candidate alias was modified")
        elif resolution["resolution"] == "same_work":
            canonical = resolution["canonical_document_id"]
            if canonical not in group["document_ids"] or resolution["alias_document_ids"] != [item for item in group["document_ids"] if item != canonical]:
                raise CandidateDuplicateReconciliationError("human candidate alias is outside its reviewed group")


def _resolution_summary(resolutions: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "same_work_count": sum(item["resolution"] == "same_work" for item in resolutions),
        "distinct_works_count": sum(item["resolution"] == "distinct_works" for item in resolutions),
        "unresolved_count": sum(item["resolution"] == "unresolved" for item in resolutions),
        "automatic_doi_count": sum(item["basis"] == "exact_normalized_doi" for item in resolutions),
        "human_decision_count": sum(item["basis"] != "exact_normalized_doi" for item in resolutions),
    }


def _valid_resolution_counts(value: object) -> bool:
    keys = {"same_work_count", "distinct_works_count", "unresolved_count", "automatic_doi_count", "human_decision_count"}
    if not isinstance(value, dict) or set(value) != keys or any(not isinstance(item, int) or isinstance(item, bool) or item < 0 or item > _MAX_GROUPS for item in value.values()):
        return False
    total = value["same_work_count"] + value["distinct_works_count"] + value["unresolved_count"]
    return total == value["automatic_doi_count"] + value["human_decision_count"] and value["automatic_doi_count"] <= value["same_work_count"]


def _revision(revision: int, resolutions: list[dict[str, Any]], *, recorded_at: str | None = None) -> dict[str, Any]:
    return {
        "revision": revision,
        "recorded_at": recorded_at or utc_now(),
        "resolution_counts": _resolution_summary(resolutions),
        "resolutions_sha256": hashlib.sha256(_canonical(resolutions).encode("utf-8")).hexdigest(),
    }


def _queue_sha256(queue: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(queue).encode("utf-8")).hexdigest()


def _optional_artifact_sha256(value: object | None) -> str | None:
    return None if value is None else hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalized_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", normalized).strip().rstrip(". ")


def _preferred_document_id(candidates: list[dict[str, Any]]) -> str:
    for candidate in candidates:
        if candidate.get("is_content_accessible") is True:
            return candidate["document_id"]
    return candidates[0]["document_id"]


def _group_id(fingerprint: str, title: str, document_ids: list[str]) -> str:
    digest = hashlib.sha256(_canonical([fingerprint, title, document_ids]).encode("utf-8")).hexdigest()
    return f"candidate_duplicate_{digest[:24]}"


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 300:
        raise CandidateDuplicateReconciliationError(f"{label} is invalid")
    return value.strip()


def _sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _utc_timestamp(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0
