"""Build a compact, secret-safe execution manifest for a CosMatter mission run.

The manifest is an audit index, not a scientific result. It proves which local
artifacts and provider receipts exist by filename, size and SHA-256, while
deliberately excluding paper text, source-map excerpts, local paths, query text
and digests, request identifiers, URLs, prompts and credentials.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .models import MissionBrief
from .sensitive_artifact_audit import SensitiveArtifactAuditError, load_sensitive_artifact_audit
from .evidence_maturity_registry import EvidenceMaturityRegistryError, audit_evidence_maturity_registry_against_runs, load_evidence_maturity_registry, validate_evidence_maturity_registry_audit
from .workflow_readiness import workflow_readiness
from .question_set import QuestionSetError, load_frozen_question_set_binding


SUBMISSION_MANIFEST_SCHEMA_VERSION = "1.0"
_MANIFEST_NAME = "submission_execution_manifest.json"
_ARTIFACT_NAMES = (
    "mission.json",
    "approved_flight_plan.json",
    "retrieval_candidates.json",
    "candidate_screening.json",
    "source_parse_tasks.json",
    "provider_receipts.jsonl",
    "verification_decisions.json",
    "condition_matrix.json",
    "research_gap_candidates.json",
    "evidence_provenance_audit.json",
    "report_evidence_audit.json",
    "mission_report.json",
    "research_report.md",
    "workflow_readiness.json",
    "sensitive_artifact_audit.json",
    "material_draft_traceability_audit.json",
    "test_only_delegated_review.json",
    "evidence_maturity_registry.json",
    "evidence_maturity_registry_audit.json",
    "human_retrieval_evaluation.json",
    "human_retrieval_route_comparison.json",
    "human_material_fact_evaluation.json",
    "human_evidence_quality_evaluation.json",
    "human_gap_evaluation.json",
    "frozen_question_set.json",
    "question_set_review_audit.json",
    "frozen_corpus_readiness.json",
    "human_annotation_coverage.json",
    "bibliographic_source_coverage.json",
    "real_corpus_evaluation_run_record.json",
    "evaluation_failure_case_log.json",
    "evaluation_api_cost_latency.json",
    "external_resource_disclosure.json",
    "potential_benchmark_plan.json",
    "potential_execution_protocol.json",
    "potential_benchmark_evaluation.json",
    "potential_benchmark_followups.json",
    "ising_benchmark_plan.json",
    "ising_benchmark_result.json",
    "ising_benchmark_followups.json",
    "ising_benchmark_summary.json",
)
_FIELDS = {
    "schema_version", "mission_id", "material", "property_name", "scope",
    "trust_status", "workflow", "redaction_audit", "artifact_inventory", "event_summary",
    "provider_receipt_summary", "manifest_sha256_input", "disclosure",
}


class SubmissionManifestError(ValueError):
    """Raised when a submission execution manifest cannot be safely built."""


def build_submission_execution_manifest(*, run_dir: Path, mission: MissionBrief) -> dict[str, Any]:
    """Summarize a bounded run without reading or projecting sensitive content."""
    readiness = workflow_readiness(run_dir, mission)
    _validate_evidence_maturity_registry_artifacts(run_dir, mission)
    _validate_question_set_artifacts(run_dir, mission)
    artifacts = [_artifact_entry(run_dir / name, name) for name in _ARTIFACT_NAMES]
    try:
        redaction = load_sensitive_artifact_audit(run_dir / "sensitive_artifact_audit.json", mission.mission_id)
    except SensitiveArtifactAuditError as error:
        raise SubmissionManifestError(str(error)) from error
    events = _event_summary(run_dir / "events.jsonl")
    receipts = _provider_receipt_summary(run_dir / "provider_receipts.jsonl")
    digest_input = json.dumps(
        {
            "mission_id": mission.mission_id,
            "artifacts": [{"name": item["name"], "sha256": item["sha256"]} for item in artifacts if item["exists"]],
            "event_summary": events,
            "provider_receipt_summary": receipts,
            "redaction_audit": {"present": redaction is not None, "is_clean": bool(redaction and redaction["is_clean"])},
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    result = {
        "schema_version": SUBMISSION_MANIFEST_SCHEMA_VERSION,
        "mission_id": mission.mission_id,
        "material": mission.material,
        "property_name": mission.property_name,
        "scope": mission.scope,
        "trust_status": "derived_submission_execution_index_not_scientific_evidence",
        "workflow": {
            "next_stage": readiness["next_stage"],
            "stages": [
                {
                    "stage": item["stage"],
                    "status": item["status"],
                    "counts": item["counts"],
                }
                for item in readiness["stages"]
            ],
        },
        "redaction_audit": {"present": redaction is not None, "is_clean": bool(redaction and redaction["is_clean"])},
        "artifact_inventory": artifacts,
        "event_summary": events,
        "provider_receipt_summary": receipts,
        "manifest_sha256_input": hashlib.sha256(digest_input).hexdigest(),
        "disclosure": (
            "This is a derived execution index. It proves only bounded local artifact presence and "
            "receipt/event counts; it does not prove scientific truth, retrieval coverage, source "
            "authenticity, novelty, extraction accuracy, or human approval."
        ),
    }
    _validate_manifest(result)
    return result


def _validate_evidence_maturity_registry_artifacts(run_dir: Path, mission: MissionBrief) -> None:
    """Reject a manifest that would inventory a stale or mismatched maturity claim ledger."""
    registry_path = run_dir / "evidence_maturity_registry.json"
    audit_path = run_dir / "evidence_maturity_registry_audit.json"
    if not registry_path.exists() and not audit_path.exists():
        return
    if not registry_path.is_file() or not audit_path.is_file():
        raise SubmissionManifestError("evidence maturity registry artifacts are incomplete")
    try:
        registry = load_evidence_maturity_registry(registry_path)
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        if registry["question_id"] != mission.mission_id:
            raise EvidenceMaturityRegistryError("evidence maturity registry question does not match this mission")
        validate_evidence_maturity_registry_audit(audit, registry)
        if audit["passed"] is not True:
            raise EvidenceMaturityRegistryError("evidence maturity registry source links did not pass audit")
        if audit_evidence_maturity_registry_against_runs(registry, run_dir.parent) != audit:
            raise EvidenceMaturityRegistryError("evidence maturity registry source links changed after audit")
    except (OSError, json.JSONDecodeError, EvidenceMaturityRegistryError) as error:
        raise SubmissionManifestError("evidence maturity registry artifacts are invalid") from error


def _validate_question_set_artifacts(run_dir: Path, mission: MissionBrief) -> None:
    """Inventory a frozen question set only when its paired audit still matches."""
    try:
        load_frozen_question_set_binding(run_dir, mission_id=mission.mission_id)
    except QuestionSetError as error:
        raise SubmissionManifestError("frozen question-set artifacts are invalid") from error


def write_submission_execution_manifest(run_dir: Path, manifest: dict[str, Any]) -> Path:
    _validate_manifest(manifest)
    path = run_dir / _MANIFEST_NAME
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _artifact_entry(path: Path, name: str) -> dict[str, Any]:
    if not path.exists():
        return {"name": name, "exists": False, "byte_count": 0, "sha256": None}
    if not path.is_file():
        raise SubmissionManifestError(f"run artifact {name} is not a regular file")
    hasher = hashlib.sha256()
    byte_count = 0
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                hasher.update(chunk)
                byte_count += len(chunk)
    except OSError as error:
        raise SubmissionManifestError(f"run artifact {name} cannot be read") from error
    return {"name": name, "exists": True, "byte_count": byte_count, "sha256": hasher.hexdigest()}


def _event_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"event_count": 0, "event_type_counts": {}, "event_log_sha256": None}
    event_types: Counter[str] = Counter()
    hasher = hashlib.sha256()
    count = 0
    try:
        with path.open("rb") as handle:
            for line in handle:
                hasher.update(line)
                if not line.strip():
                    continue
                try:
                    item = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise SubmissionManifestError("event log is invalid") from error
                event_type = item.get("event_type") if isinstance(item, dict) else None
                if not isinstance(event_type, str) or not event_type.strip() or len(event_type) > 160:
                    raise SubmissionManifestError("event log event type is invalid")
                event_types[event_type] += 1
                count += 1
                if count > 10_000:
                    raise SubmissionManifestError("event log exceeds submission-manifest safety limit")
    except OSError as error:
        raise SubmissionManifestError("event log cannot be read") from error
    return {"event_count": count, "event_type_counts": dict(sorted(event_types.items())), "event_log_sha256": hasher.hexdigest()}


def _provider_receipt_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"receipt_count": 0, "provider_operation_counts": {}, "receipt_log_sha256": None}
    counts: Counter[str] = Counter()
    hasher = hashlib.sha256()
    count = 0
    try:
        with path.open("rb") as handle:
            for line in handle:
                hasher.update(line)
                if not line.strip():
                    continue
                try:
                    item = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise SubmissionManifestError("provider receipt log is invalid") from error
                provider = item.get("provider") if isinstance(item, dict) else None
                operation = item.get("operation") if isinstance(item, dict) else None
                if not isinstance(provider, str) or not provider.strip() or not isinstance(operation, str) or not operation.strip():
                    raise SubmissionManifestError("provider receipt log entry is invalid")
                counts[f"{provider.strip()}:{operation.strip()}"] += 1
                count += 1
                if count > 10_000:
                    raise SubmissionManifestError("provider receipt log exceeds submission-manifest safety limit")
    except OSError as error:
        raise SubmissionManifestError("provider receipt log cannot be read") from error
    return {"receipt_count": count, "provider_operation_counts": dict(sorted(counts.items())), "receipt_log_sha256": hasher.hexdigest()}


def _validate_manifest(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise SubmissionManifestError("submission execution manifest has unsupported or missing fields")
    if payload.get("schema_version") != SUBMISSION_MANIFEST_SCHEMA_VERSION or payload.get("trust_status") != "derived_submission_execution_index_not_scientific_evidence":
        raise SubmissionManifestError("submission execution manifest schema or trust status is invalid")
    if not all(isinstance(payload.get(key), str) and payload[key].strip() for key in ("mission_id", "material", "property_name", "scope", "manifest_sha256_input", "disclosure")):
        raise SubmissionManifestError("submission execution manifest identity is invalid")
    if not isinstance(payload.get("workflow"), dict) or not isinstance(payload["workflow"].get("stages"), list):
        raise SubmissionManifestError("submission execution manifest workflow is invalid")
    if not isinstance(payload.get("redaction_audit"), dict) or set(payload["redaction_audit"]) != {"present", "is_clean"} or not all(isinstance(payload["redaction_audit"].get(key), bool) for key in ("present", "is_clean")):
        raise SubmissionManifestError("submission execution manifest redaction audit is invalid")
    if not payload["redaction_audit"]["present"] and payload["redaction_audit"]["is_clean"]:
        raise SubmissionManifestError("submission execution manifest redaction audit state is invalid")
    if not isinstance(payload.get("artifact_inventory"), list) or len(payload["artifact_inventory"]) != len(_ARTIFACT_NAMES):
        raise SubmissionManifestError("submission execution manifest artifact inventory is invalid")
    for item in payload["artifact_inventory"]:
        if not isinstance(item, dict) or set(item) != {"name", "exists", "byte_count", "sha256"} or item.get("name") not in _ARTIFACT_NAMES:
            raise SubmissionManifestError("submission execution manifest artifact entry is invalid")
        if not isinstance(item["exists"], bool) or not isinstance(item["byte_count"], int) or item["byte_count"] < 0:
            raise SubmissionManifestError("submission execution manifest artifact entry values are invalid")
        if item["exists"] != isinstance(item["sha256"], str):
            raise SubmissionManifestError("submission execution manifest artifact hash state is invalid")
    for key in ("event_summary", "provider_receipt_summary"):
        if not isinstance(payload.get(key), dict):
            raise SubmissionManifestError("submission execution manifest summary is invalid")
