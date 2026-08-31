"""Hash-bound, redacted review records for untrusted DSH market snapshots."""

from __future__ import annotations

from datetime import date
import hashlib
import json
import re
from typing import Any


class MarketSnapshotReviewError(ValueError):
    """Raised when a market snapshot or its review record is inconsistent."""


_SNAPSHOT_FIELDS = {"schema_version", "snapshot_id", "generated_on", "trust_status", "review_status", "candidates"}
_CANDIDATE_FIELDS = {"candidate_id", "category", "source_url", "observed_ref", "status"}
_REVIEW_FIELDS = {
    "schema_version", "trust_status", "baseline_snapshot_sha256", "current_snapshot_sha256",
    "reviewed_on", "reviewer", "added_count", "removed_count", "changed_count", "change_fingerprint",
}
_SNAPSHOT_TRUST = "untrusted_public_plugin_discovery_not_install_authorization_or_scientific_evidence"
_REVIEW_TRUST = "human_reviewed_market_snapshot_diff_not_admission_or_install_authorization"


def snapshot_sha256(snapshot: object) -> str:
    """Return the canonical identity of a validated snapshot without exposing it."""
    validate_market_snapshot(snapshot)
    payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def snapshot_diff(baseline: object, current: object) -> dict[str, Any]:
    """Compare snapshots while retaining only candidate IDs and field counts."""
    validate_market_snapshot(baseline)
    validate_market_snapshot(current)
    before = {item["candidate_id"]: item for item in baseline["candidates"]}
    after = {item["candidate_id"]: item for item in current["candidates"]}
    changes: list[dict[str, Any]] = []
    for candidate_id in sorted(after.keys() - before.keys()):
        changes.append({"candidate_id": candidate_id, "change_type": "added", "changed_field_count": 0})
    for candidate_id in sorted(before.keys() - after.keys()):
        changes.append({"candidate_id": candidate_id, "change_type": "removed", "changed_field_count": 0})
    for candidate_id in sorted(before.keys() & after.keys()):
        changed_count = sum(before[candidate_id][field] != after[candidate_id][field] for field in _CANDIDATE_FIELDS - {"candidate_id"})
        if changed_count:
            changes.append({"candidate_id": candidate_id, "change_type": "changed", "changed_field_count": changed_count})
    canonical = json.dumps(changes, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "added_count": sum(item["change_type"] == "added" for item in changes),
        "removed_count": sum(item["change_type"] == "removed" for item in changes),
        "changed_count": sum(item["change_type"] == "changed" for item in changes),
        "change_fingerprint": hashlib.sha256(canonical).hexdigest(),
    }


def verify_market_snapshot_review(*, baseline: object, current: object, review: object) -> dict[str, Any]:
    """Verify that a human review record covers this exact snapshot delta."""
    validate_market_snapshot(baseline)
    validate_market_snapshot(current)
    validate_market_snapshot_review(review)
    expected = snapshot_diff(baseline, current)
    if review["baseline_snapshot_sha256"] != snapshot_sha256(baseline) or review["current_snapshot_sha256"] != snapshot_sha256(current):
        raise MarketSnapshotReviewError("market snapshot review does not bind the baseline and current snapshots")
    if any(review[field] != expected[field] for field in expected):
        raise MarketSnapshotReviewError("market snapshot review does not match the current redacted diff")
    return {
        "schema_version": "1.0",
        "trust_status": "market_snapshot_review_verified_not_admission_or_install_authorization",
        **expected,
    }


def validate_market_snapshot(snapshot: object) -> None:
    if not isinstance(snapshot, dict) or set(snapshot) != _SNAPSHOT_FIELDS:
        raise MarketSnapshotReviewError("market snapshot fields are invalid")
    if snapshot.get("schema_version") != "1.0" or not _nonempty(snapshot.get("snapshot_id")) or not _date(snapshot.get("generated_on")) or snapshot.get("trust_status") != _SNAPSHOT_TRUST or snapshot.get("review_status") != "human_reviewed_discovery_snapshot" or not isinstance(snapshot.get("candidates"), list):
        raise MarketSnapshotReviewError("market snapshot identity is invalid")
    identifiers: set[str] = set()
    for candidate in snapshot["candidates"]:
        if not isinstance(candidate, dict) or set(candidate) != _CANDIDATE_FIELDS:
            raise MarketSnapshotReviewError("market snapshot candidate fields are invalid")
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,80}", candidate_id) or candidate_id in identifiers or not _nonempty(candidate.get("category")) or not _github_url(candidate.get("source_url")) or candidate.get("observed_ref") != "unversioned_public_discovery" or candidate.get("status") != "untrusted_discovery_only":
            raise MarketSnapshotReviewError("market snapshot candidate is invalid")
        identifiers.add(candidate_id)


def validate_market_snapshot_review(review: object) -> None:
    if not isinstance(review, dict) or set(review) != _REVIEW_FIELDS:
        raise MarketSnapshotReviewError("market snapshot review fields are invalid")
    if review.get("schema_version") != "1.0" or review.get("trust_status") != _REVIEW_TRUST or not _sha256(review.get("baseline_snapshot_sha256")) or not _sha256(review.get("current_snapshot_sha256")) or not _date(review.get("reviewed_on")) or not _nonempty(review.get("reviewer")) or not _sha256(review.get("change_fingerprint")):
        raise MarketSnapshotReviewError("market snapshot review identity is invalid")
    for field in ("added_count", "removed_count", "changed_count"):
        if not isinstance(review.get(field), int) or isinstance(review[field], bool) or review[field] < 0:
            raise MarketSnapshotReviewError("market snapshot review counts are invalid")


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 160


def _date(value: object) -> bool:
    try:
        date.fromisoformat(str(value))
    except ValueError:
        return False
    return True


def _sha256(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[a-f0-9]{64}", value))


def _github_url(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value))
