"""Secret-safe scan summaries for persisted mission-run artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class SensitiveArtifactAuditError(ValueError):
    """Raised when a sensitive-artifact audit cannot be safely written."""


_SCHEMA_VERSION = "1.0"
_TRUST_STATUS = "artifact_redaction_audit_not_scientific_evidence"
_TEXT_SUFFIXES = {".json", ".jsonl", ".md", ".txt"}
_MAX_SCANNED_BYTES = 2_000_000
_PATTERNS = {
    "complete_url": re.compile(r"https?://", re.IGNORECASE),
    "credential_token": re.compile(r"(?<![A-Za-z0-9_-])(?:sk|sv|gho)[_-][A-Za-z0-9_-]{8,}", re.IGNORECASE),
    "authorization_header": re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{8,}", re.IGNORECASE),
    "named_secret_value": re.compile(
        r"\b(?:api[_-]?(?:key|token)|token|secret|password)\b\s*[\"']?\s*[:=]\s*[\"']?(?!\[REDACTED\])[^\s\",}\]]{4,}",
        re.IGNORECASE,
    ),
    "private_absolute_path": re.compile(
        r"(?:[A-Za-z]:[\\/]|/)(?:[^\r\n\"']{0,500}?)(?:case-data[\\/]runtime[\\/]private|\.sciverse[\\/]|\.mineru[\\/])",
        re.IGNORECASE,
    ),
}


def audit_sensitive_artifacts(run_dir: Path, mission_id: str) -> dict[str, Any]:
    """Count forbidden persisted patterns without retaining values or paths."""
    if not isinstance(mission_id, str) or not mission_id.strip() or len(mission_id.strip()) > 255:
        raise SensitiveArtifactAuditError("mission_id is invalid")
    if not run_dir.is_dir():
        raise SensitiveArtifactAuditError("run directory does not exist")

    counts = {name: 0 for name in _PATTERNS}
    oversized_count = 0
    scanned_count = 0
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in _TEXT_SUFFIXES:
            continue
        if path.name == "sensitive_artifact_audit.json":
            continue
        if path.stat().st_size > _MAX_SCANNED_BYTES:
            oversized_count += 1
            continue
        scanned_count += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in _PATTERNS.items():
            counts[name] += len(pattern.findall(text))

    findings = [
        {"category": name, "match_count": count}
        for name, count in counts.items()
        if count
    ]
    if oversized_count:
        findings.append({"category": "oversized_text_artifact", "match_count": oversized_count})
    return {
        "schema_version": _SCHEMA_VERSION,
        "mission_id": mission_id.strip(),
        "trust_status": _TRUST_STATUS,
        "scanned_text_artifact_count": scanned_count,
        "is_clean": not findings,
        "findings": findings,
    }


def write_sensitive_artifact_audit(run_dir: Path, artifact: dict[str, Any]) -> Path:
    """Persist a schema-validated count-only audit result in the run."""
    _validate(artifact)
    path = run_dir / "sensitive_artifact_audit.json"
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_sensitive_artifact_audit(path: Path, mission_id: str) -> dict[str, Any] | None:
    """Load one count-only audit after validating its mission binding."""
    if not path.exists():
        return None
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SensitiveArtifactAuditError("sensitive artifact audit is invalid JSON") from error
    _validate(artifact)
    if artifact["mission_id"] != mission_id:
        raise SensitiveArtifactAuditError("sensitive artifact audit does not belong to this mission")
    return artifact


def _validate(artifact: object) -> None:
    expected = {"schema_version", "mission_id", "trust_status", "scanned_text_artifact_count", "is_clean", "findings"}
    if not isinstance(artifact, dict) or set(artifact) != expected:
        raise SensitiveArtifactAuditError("sensitive artifact audit fields are invalid")
    if artifact.get("schema_version") != _SCHEMA_VERSION or artifact.get("trust_status") != _TRUST_STATUS:
        raise SensitiveArtifactAuditError("sensitive artifact audit identity is invalid")
    if not isinstance(artifact.get("mission_id"), str) or not artifact["mission_id"].strip() or len(artifact["mission_id"]) > 255:
        raise SensitiveArtifactAuditError("sensitive artifact audit mission_id is invalid")
    if not isinstance(artifact.get("scanned_text_artifact_count"), int) or artifact["scanned_text_artifact_count"] < 0 or not isinstance(artifact.get("is_clean"), bool):
        raise SensitiveArtifactAuditError("sensitive artifact audit counters are invalid")
    findings = artifact.get("findings")
    allowed = set(_PATTERNS) | {"oversized_text_artifact"}
    if not isinstance(findings, list) or any(
        not isinstance(item, dict)
        or set(item) != {"category", "match_count"}
        or item.get("category") not in allowed
        or not isinstance(item.get("match_count"), int)
        or item["match_count"] <= 0
        for item in findings
    ):
        raise SensitiveArtifactAuditError("sensitive artifact audit findings are invalid")
    if artifact["is_clean"] != (not findings):
        raise SensitiveArtifactAuditError("sensitive artifact audit cleanliness is inconsistent")
