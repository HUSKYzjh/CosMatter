"""Fixed, secret-safe download contract for approved CosMatter artifacts.

This is intentionally *not* a file browser.  It exposes a very small set of
reviewed/public-safe run products by symbolic identifier, never accepts a
path, and never includes PDFs, MinerU Markdown, provider receipts, source
URLs, tokens, source maps, or raw evidence-card stores.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ARTIFACT_SCHEMA_VERSION = "cosmatter.artifact/v1"
_TRUST_STATUS = "allowlisted_artifact_index_not_scientific_evidence"
_ITEM_FIELDS = {"artifact_id", "title", "media_type", "sha256", "generated_at", "trust_status", "download_path"}
_MANIFEST_FIELDS = {"schema_version", "run_id", "mission_id", "trust_status", "artifact_count", "artifacts"}
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_FORBIDDEN_KEY = re.compile(r"(?:token|secret|api[_-]?key|password|source_url|private_path|full_text|markdown)", re.IGNORECASE)
_FORBIDDEN_TEXT = re.compile(r"(?:https?://|(?:[A-Za-z]:[\\/])|private-upload:|bearer\s+)", re.IGNORECASE)


class ArtifactContractError(ValueError):
    """Raised for an unavailable or unsafe artifact-contract request."""


@dataclass(frozen=True)
class ArtifactDownload:
    data: bytes
    media_type: str
    filename: str


@dataclass(frozen=True)
class _ArtifactSpec:
    artifact_id: str
    filename: str
    title: str
    media_type: str
    trust_status: str
    requires_report_audit: bool = False


# This immutable list is the entire downloadable surface.  In particular,
# nothing under ``source_maps/``, private storage, or provider logs can become
# downloadable by merely creating a same-named file.
_SPECS = (
    _ArtifactSpec("ui_bundle", "ui.json", "浏览器安全工作台导出", "application/json; charset=utf-8", "browser_safe_export_from_reviewed_artifacts"),
    _ArtifactSpec("graph_snapshot", "graph_snapshot.json", "已接受证据图投影", "application/json; charset=utf-8", "accepted_evidence_projection_not_scientific_conclusion"),
    _ArtifactSpec("workflow_readiness", "workflow_readiness.json", "工作流就绪度摘要", "application/json; charset=utf-8", "derived_workflow_readiness_not_scientific_evidence"),
    _ArtifactSpec("runtime_invariants", "runtime_invariant_audit.json", "运行时关系审计", "application/json; charset=utf-8", "runtime_relationship_audit_not_scientific_evidence_or_provider_status_verification"),
    _ArtifactSpec("mission_report", "mission_report.json", "已审核证据报告清单", "application/json; charset=utf-8", "review_gated_evidence_manifest", True),
    _ArtifactSpec("research_report", "research_report.md", "可追溯研究报告", "text/markdown; charset=utf-8", "review_gated_structured_report", True),
)
_BY_ID = {spec.artifact_id: spec for spec in _SPECS}


def artifact_manifest(*, run_dir: Path, run_id: str, mission_id: str) -> dict[str, Any]:
    """Build a count-only, fixed-route manifest of available approved outputs."""
    _validate_identity(run_id, mission_id)
    artifacts = [_item(spec, run_dir, run_id, mission_id) for spec in _SPECS if _available(spec, run_dir, mission_id)]
    manifest = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "run_id": run_id,
        "mission_id": mission_id,
        "trust_status": _TRUST_STATUS,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }
    validate_artifact_manifest(manifest, expected_run_id=run_id, expected_mission_id=mission_id)
    return manifest


def approved_artifact_download(*, run_dir: Path, run_id: str, mission_id: str, artifact_id: str) -> ArtifactDownload:
    """Return exactly one allowlisted generated artifact by opaque ID."""
    manifest = artifact_manifest(run_dir=run_dir, run_id=run_id, mission_id=mission_id)
    if not isinstance(artifact_id, str) or artifact_id not in _BY_ID:
        raise ArtifactContractError("artifact identifier is not allowlisted")
    if artifact_id not in {item["artifact_id"] for item in manifest["artifacts"]}:
        raise ArtifactContractError("artifact is not currently approved for download")
    spec = _BY_ID[artifact_id]
    path = run_dir / spec.filename
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ArtifactContractError("approved artifact cannot be read") from error
    # Detect replacement after manifest construction, including a symlink/race.
    if hashlib.sha256(data).hexdigest() != next(item["sha256"] for item in manifest["artifacts"] if item["artifact_id"] == artifact_id):
        raise ArtifactContractError("approved artifact changed during download")
    return ArtifactDownload(data=data, media_type=spec.media_type, filename=spec.filename)


def validate_artifact_manifest(payload: object, *, expected_run_id: str, expected_mission_id: str) -> None:
    """Strict schema validation for DSH/Web artifact-card consumers."""
    if not isinstance(payload, dict) or set(payload) != _MANIFEST_FIELDS:
        raise ArtifactContractError("artifact manifest fields are invalid")
    if payload.get("schema_version") != ARTIFACT_SCHEMA_VERSION or payload.get("run_id") != expected_run_id or payload.get("mission_id") != expected_mission_id or payload.get("trust_status") != _TRUST_STATUS:
        raise ArtifactContractError("artifact manifest identity is invalid")
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or payload.get("artifact_count") != len(artifacts):
        raise ArtifactContractError("artifact manifest count is invalid")
    seen: set[str] = set()
    for item in artifacts:
        if not isinstance(item, dict) or set(item) != _ITEM_FIELDS:
            raise ArtifactContractError("artifact manifest item fields are invalid")
        artifact_id = item.get("artifact_id")
        spec = _BY_ID.get(artifact_id) if isinstance(artifact_id, str) else None
        if spec is None or artifact_id in seen:
            raise ArtifactContractError("artifact manifest identifier is invalid")
        seen.add(artifact_id)
        if (
            item.get("title") != spec.title or item.get("media_type") != spec.media_type
            or item.get("trust_status") != spec.trust_status
            or not isinstance(item.get("sha256"), str) or not _SHA256.fullmatch(item["sha256"])
            or not isinstance(item.get("generated_at"), str) or not item["generated_at"].strip()
            or item.get("download_path") != f"/api/runs/{expected_run_id}/artifacts/{artifact_id}"
        ):
            raise ArtifactContractError("artifact manifest item is invalid")


def _available(spec: _ArtifactSpec, run_dir: Path, mission_id: str) -> bool:
    path = run_dir / spec.filename
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 5 * 1024 * 1024:
        return False
    if spec.requires_report_audit and not _report_is_audited(run_dir, mission_id):
        return False
    return _matches_safe_contract(spec, path, mission_id)


def _matches_safe_contract(spec: _ArtifactSpec, path: Path, mission_id: str) -> bool:
    try:
        if spec.artifact_id == "research_report":
            text = path.read_text(encoding="utf-8")
            return bool(text.strip()) and len(text) <= 5 * 1024 * 1024 and "\x00" not in text and not _FORBIDDEN_TEXT.search(text)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict) or _unsafe_json(payload) or payload.get("mission_id") != mission_id:
        return False
    if spec.artifact_id == "ui_bundle":
        return payload.get("schema_version") == "1.0" and isinstance(payload.get("mission"), dict)
    if spec.artifact_id == "graph_snapshot":
        return payload.get("schema_version") == "1.0" and payload.get("trust_status") == spec.trust_status and isinstance(payload.get("nodes"), list) and isinstance(payload.get("edges"), list)
    if spec.artifact_id == "workflow_readiness":
        return payload.get("schema_version") == "1.0" and payload.get("trust_status") == spec.trust_status and isinstance(payload.get("stages"), list)
    if spec.artifact_id == "runtime_invariants":
        return payload.get("schema_version") == "1.0" and payload.get("trust_status") == spec.trust_status and isinstance(payload.get("passed"), bool)
    if spec.artifact_id == "mission_report":
        return payload.get("schema_version") is None and isinstance(payload.get("report_id"), str) and isinstance(payload.get("evidence_ids"), list)
    return False


def _unsafe_json(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            not isinstance(key, str) or _FORBIDDEN_KEY.search(key) is not None or _unsafe_json(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_unsafe_json(item) for item in value)
    return isinstance(value, str) and _FORBIDDEN_TEXT.search(value) is not None


def _report_is_audited(run_dir: Path, mission_id: str) -> bool:
    try:
        payload = json.loads((run_dir / "report_evidence_audit.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(payload, dict)
        and payload.get("schema_version") == "1.3"
        and payload.get("mission_id") == mission_id
        and payload.get("trust_status") == "artifact_level_identifier_audit_not_scientific_validity_assessment"
    )


def _item(spec: _ArtifactSpec, run_dir: Path, run_id: str, mission_id: str) -> dict[str, str]:
    path = run_dir / spec.filename
    timestamp = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
    return {
        "artifact_id": spec.artifact_id,
        "title": spec.title,
        "media_type": spec.media_type,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "generated_at": timestamp,
        "trust_status": spec.trust_status,
        "download_path": f"/api/runs/{run_id}/artifacts/{spec.artifact_id}",
    }


def _validate_identity(run_id: str, mission_id: str) -> None:
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id) or not isinstance(mission_id, str) or not mission_id.strip() or len(mission_id) > 255:
        raise ArtifactContractError("artifact manifest identity is invalid")
