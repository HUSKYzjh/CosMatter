"""Verify that production DSH bundles cannot be selected from a market snapshot."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cosmatter.market_snapshot_review import MarketSnapshotReviewError, verify_market_snapshot_review


class AdmissionError(ValueError):
    pass


def main() -> int:
    try:
        admission = _load(ROOT / "configs" / "dsh_third_party_plugin_admissions.json")
        snapshot = _load(ROOT / "configs" / "dsh_market_snapshot.json")
        baseline = _load(ROOT / "configs" / "dsh_market_snapshot.baseline.json")
        review = _load(ROOT / "configs" / "dsh_market_snapshot_review.json")
        group = _load(ROOT / "plugins" / "dsh-plugin-group.json")
        _validate(admission, snapshot, group)
        review_result = verify_market_snapshot_review(baseline=baseline, current=snapshot, review=review)
    except (AdmissionError, MarketSnapshotReviewError) as error:
        print(json.dumps({"status": "blocked", "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": "ok", "owned_bundle_count": len(group["packages"]), "third_party_admission_count": len(admission["third_party_admissions"]), "market_candidate_count": len(snapshot["candidates"]), "market_snapshot_change_count": review_result["added_count"] + review_result["removed_count"] + review_result["changed_count"], "trust_status": "local_plugin_allowlist_not_market_registry_or_install_instruction"}, ensure_ascii=False))
    return 0


def _validate(admission: dict[str, Any], snapshot: dict[str, Any], group: dict[str, Any]) -> None:
    fields = {"schema_version", "trust_status", "owned_package_prefixes", "third_party_admissions", "policy"}
    if set(admission) != fields or admission.get("schema_version") != "1.0" or admission.get("trust_status") != "local_plugin_allowlist_not_market_registry_or_install_instruction" or admission.get("owned_package_prefixes") != ["@cosmatter/"] or not isinstance(admission.get("third_party_admissions"), list):
        raise AdmissionError("third-party admission allowlist is invalid")
    policy = admission.get("policy")
    expected_policy = {"market_snapshot", "require_pinned_source", "require_package_sha256", "require_human_owner", "require_review_expiry", "block_high_hygiene_risk", "production_profiles_must_not_read_market_snapshot", "require_snapshot_diff_review"}
    if not isinstance(policy, dict) or set(policy) != expected_policy or policy.get("market_snapshot") != "configs/dsh_market_snapshot.json" or any(policy.get(key) is not True for key in expected_policy - {"market_snapshot"}):
        raise AdmissionError("third-party admission policy is invalid")
    _validate_snapshot(snapshot)
    approved: set[str] = set()
    for record in admission["third_party_admissions"]:
        if not isinstance(record, dict) or set(record) != {"package", "source_url", "source_commit", "package_sha256", "license", "permission_review", "hygiene_report_sha256", "owner", "reviewed_on", "expires_on", "rollback"}:
            raise AdmissionError("third-party admission record fields are invalid")
        package = record.get("package")
        if not isinstance(package, str) or not package or package.startswith("@cosmatter/") or package in approved or not _url(record.get("source_url")) or not _hash(record.get("source_commit"), 7, 64) or not _hash(record.get("package_sha256"), 64, 64) or not isinstance(record.get("license"), str) or not record["license"].strip() or not isinstance(record.get("permission_review"), str) or record["permission_review"] not in {"low_risk_manual_review"} or not _hash(record.get("hygiene_report_sha256"), 64, 64) or not isinstance(record.get("owner"), str) or not record["owner"].strip() or not _date(record.get("reviewed_on")) or not _date(record.get("expires_on")) or date.fromisoformat(record["expires_on"]) < date.fromisoformat(record["reviewed_on"]) or not isinstance(record.get("rollback"), str) or not record["rollback"].strip():
            raise AdmissionError("third-party admission record is invalid")
        approved.add(package)
    if not isinstance(group.get("packages"), list) or not all(isinstance(item, dict) and isinstance(item.get("package"), str) for item in group["packages"]):
        raise AdmissionError("DSH group manifest is invalid")
    for item in group["packages"]:
        package = item["package"]
        if package.startswith("@cosmatter/"):
            package_dir = ROOT / "plugins" / str(item.get("path", ""))
            try:
                declared = (package_dir / "package.json").read_text(encoding="utf-8") + (package_dir / "cordis.patch.yml").read_text(encoding="utf-8")
            except OSError as error:
                raise AdmissionError("owned DSH bundle declaration cannot be read") from error
            if "market_snapshot" in declared or "dsh_market_snapshot" in declared:
                raise AdmissionError("production DSH bundle must not read a market snapshot")
        elif package not in approved:
            raise AdmissionError("production DSH group references an unapproved third-party package")


def _validate_snapshot(snapshot: dict[str, Any]) -> None:
    fields = {"schema_version", "snapshot_id", "generated_on", "trust_status", "review_status", "candidates"}
    if set(snapshot) != fields or snapshot.get("schema_version") != "1.0" or not isinstance(snapshot.get("snapshot_id"), str) or not snapshot["snapshot_id"].strip() or not _date(snapshot.get("generated_on")) or snapshot.get("trust_status") != "untrusted_public_plugin_discovery_not_install_authorization_or_scientific_evidence" or snapshot.get("review_status") != "human_reviewed_discovery_snapshot" or not isinstance(snapshot.get("candidates"), list):
        raise AdmissionError("market snapshot is invalid")
    identifiers: set[str] = set()
    for candidate in snapshot["candidates"]:
        if not isinstance(candidate, dict) or set(candidate) != {"candidate_id", "category", "source_url", "observed_ref", "status"} or not isinstance(candidate.get("candidate_id"), str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,80}", candidate["candidate_id"]) or candidate["candidate_id"] in identifiers or not isinstance(candidate.get("category"), str) or not candidate["category"] or not _url(candidate.get("source_url")) or candidate.get("observed_ref") != "unversioned_public_discovery" or candidate.get("status") != "untrusted_discovery_only":
            raise AdmissionError("market snapshot candidate is invalid")
        identifiers.add(candidate["candidate_id"])


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AdmissionError("admission configuration cannot be read") from error
    if not isinstance(value, dict):
        raise AdmissionError("admission configuration is invalid")
    return value


def _url(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value))


def _hash(value: object, low: int, high: int) -> bool:
    return isinstance(value, str) and low <= len(value) <= high and bool(re.fullmatch(r"[a-f0-9]+", value))


def _date(value: object) -> bool:
    try:
        date.fromisoformat(str(value))
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
