"""Batch human approval for automated PotentialScope literature triage.

The LLM performs the repetitive routing of private MinerU candidates. A
researcher then reviews one concise decision row per document rather than
hand-copying every excerpt. Approved rows can be projected into the existing
quote-free reviewed-source registry; no scientific claim or execution request
is created here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .mineru_local_review import source_map_pool_review_template, source_map_selection_from_pool_review
from .potential_scope_auto_triage import PotentialScopeAutoTriageError, load_private_pool
from .potential_scope_review_registry import PotentialScopeReviewRegistryError, build_reviewed_source_registry


BATCH_APPROVAL_SCHEMA_VERSION = "1.0"
_TRIAGE_STATUS = "untrusted_llm_private_potential_scope_source_triage_not_evidence"
_BLANK_STATUS = "blank_human_batch_potential_scope_triage_decision_template"
_APPROVED_STATUS = "human_approved_batch_potential_scope_triage_decision"
_DECISIONS = {"approved", "rejected", "return_for_triangulation"}


class PotentialScopeBatchApprovalError(ValueError):
    """Raised when a batch decision cannot safely become provenance metadata."""


def load_triage_drafts(paths: object, *, mission_id: str) -> list[dict[str, Any]]:
    """Read quote-free automatic drafts; these remain untrusted routing output."""
    if not isinstance(paths, list) or not paths:
        raise PotentialScopeBatchApprovalError("triage draft paths are invalid")
    result: list[dict[str, Any]] = []
    documents: set[str] = set()
    for path in paths:
        if not isinstance(path, Path):
            raise PotentialScopeBatchApprovalError("triage draft path is invalid")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PotentialScopeBatchApprovalError("triage draft cannot be read") from error
        _validate_triage(payload)
        if payload["mission_id"] != mission_id or payload["document_id"] in documents:
            raise PotentialScopeBatchApprovalError("triage drafts have inconsistent document identity")
        documents.add(payload["document_id"])
        result.append(payload)
    return sorted(result, key=lambda item: item["document_id"])


def build_batch_approval_template(*, mission_id: str, drafts: object) -> dict[str, Any]:
    """Create a decision sheet with one blank human decision per document."""
    normalized = _drafts(mission_id=mission_id, drafts=drafts)
    return {
        "schema_version": BATCH_APPROVAL_SCHEMA_VERSION,
        "mission_id": mission_id,
        "trust_status": _BLANK_STATUS,
        "reviewer": "",
        "reviewed_at": "",
        "documents": [
            {"document_id": item["document_id"], "triage_sha256": _sha(item), "decision": "", "note": ""}
            for item in normalized
        ],
        "review_boundary": (
            "A document-level approval accepts the automated routing suggestions only as a private source-map "
            "selection aid. It does not turn them into material facts, a frozen scope, an EvidenceCard, or an "
            "execution authorization."
        ),
    }


def write_batch_approval_template(path: Path, template: object) -> Path:
    _validate_approval(template, blank=True)
    return _write_once(path, template, "batch approval template")


def load_completed_batch_approval(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PotentialScopeBatchApprovalError("batch approval cannot be read") from error
    _validate_approval(payload, blank=False)
    return payload


def build_registry_from_batch_approval(
    *,
    mission_id: str,
    drafts: object,
    approval: object,
    pools_by_document: object,
    source_tasks_by_document: object,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project approved document triages into a registry plus quote-free audit."""
    normalized = _drafts(mission_id=mission_id, drafts=drafts)
    _validate_approval(approval, blank=False)
    if approval["mission_id"] != mission_id:
        raise PotentialScopeBatchApprovalError("approval belongs to another mission")
    decisions = {row["document_id"]: row for row in approval["documents"]}
    if set(decisions) != {draft["document_id"] for draft in normalized}:
        raise PotentialScopeBatchApprovalError("approval documents do not match automated drafts")
    if not isinstance(pools_by_document, dict) or not isinstance(source_tasks_by_document, dict):
        raise PotentialScopeBatchApprovalError("private pool bindings are invalid")
    entries: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    approval_hash = _sha(approval)
    for draft in normalized:
        document_id = draft["document_id"]
        decision = decisions[document_id]
        if decision["triage_sha256"] != _sha(draft):
            raise PotentialScopeBatchApprovalError("approval is stale relative to its automated triage")
        if decision["decision"] != "approved":
            audit_rows.append({"document_id": document_id, "decision": decision["decision"], "selected_segment_count": 0})
            continue
        pool_path = pools_by_document.get(document_id)
        task = source_tasks_by_document.get(document_id)
        if not isinstance(pool_path, Path):
            raise PotentialScopeBatchApprovalError("approved document has no private review pool")
        try:
            pool = load_private_pool(path=pool_path, mission_id=mission_id, document_id=document_id, source_task=task)
        except PotentialScopeAutoTriageError as error:
            raise PotentialScopeBatchApprovalError("approved document pool is invalid") from error
        if any(pool[key] != draft[key] for key in ("document_id", "task_id_sha256", "source_markdown_sha256")):
            raise PotentialScopeBatchApprovalError("approved draft no longer matches its private review pool")
        review = source_map_pool_review_template(pool)
        suggested = {row["segment_id"]: row for row in draft["proposals"]}
        for row in review["segments"]:
            if row["segment_id"] in suggested:
                row["selected"] = True
                row["reason"] = "Batch-approved automated triage: " + suggested[row["segment_id"]]["reason"]
        review["trust_status"] = "human_reviewed_source_map_pool_selection"
        try:
            selection, markdown_sha = source_map_selection_from_pool_review(pool=pool, review=review)
        except Exception as error:
            raise PotentialScopeBatchApprovalError("approved automatic suggestions cannot resolve to private segments") from error
        segment_ids = [row["segment_id"] for row in selection["segments"]]
        entries.append(
            {
                "source_id": f"ps_src_{markdown_sha[:16]}",
                "document_id": document_id,
                "source_markdown_sha256": markdown_sha,
                "task_id_sha256": pool["task_id_sha256"],
                "selection_sha256": _sha({"document_id": document_id, "selected_segment_ids": segment_ids, "batch_approval_sha256": approval_hash}),
                "selected_segment_count": len(segment_ids),
            }
        )
        audit_rows.append({"document_id": document_id, "decision": "approved", "selected_segment_count": len(segment_ids)})
    if not entries:
        raise PotentialScopeBatchApprovalError("no automated triage document was approved")
    try:
        registry = build_reviewed_source_registry(mission_id=mission_id, entries=entries)
    except PotentialScopeReviewRegistryError as error:
        raise PotentialScopeBatchApprovalError("batch-approved registry is invalid") from error
    audit = {
        "schema_version": BATCH_APPROVAL_SCHEMA_VERSION,
        "mission_id": mission_id,
        "trust_status": "human_approved_batch_potential_scope_triage_audit_not_evidence",
        "batch_approval_sha256": approval_hash,
        "reviewer": approval["reviewer"],
        "reviewed_at": approval["reviewed_at"],
        "documents": sorted(audit_rows, key=lambda row: row["document_id"]),
        "review_boundary": (
            "This quote-free audit records document-level human approval of automatic private-source triage. "
            "It contains no excerpt, locator, path, scientific finding, calculation request, or execution authority."
        ),
    }
    return registry, audit


def write_batch_outputs(*, registry_path: Path, audit_path: Path, registry: object, audit: object) -> tuple[Path, Path]:
    if registry_path.exists() or audit_path.exists():
        raise PotentialScopeBatchApprovalError("batch output already exists and will not be overwritten")
    return _write_once(registry_path, registry, "reviewed source registry"), _write_once(audit_path, audit, "batch approval audit")


def _drafts(*, mission_id: str, drafts: object) -> list[dict[str, Any]]:
    if not isinstance(mission_id, str) or not mission_id.strip() or not isinstance(drafts, list) or not drafts:
        raise PotentialScopeBatchApprovalError("automatic triage batch is invalid")
    documents: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for draft in drafts:
        _validate_triage(draft)
        if draft["mission_id"] != mission_id or draft["document_id"] in documents:
            raise PotentialScopeBatchApprovalError("automatic triage document identity is invalid")
        documents.add(draft["document_id"])
        normalized.append(draft)
    return sorted(normalized, key=lambda row: row["document_id"])


def _validate_triage(payload: object) -> None:
    if not isinstance(payload, dict) or payload.get("trust_status") != _TRIAGE_STATUS:
        raise PotentialScopeBatchApprovalError("automatic triage draft trust status is invalid")
    required = {"schema_version", "mission_id", "document_id", "trust_status", "source_markdown_sha256", "task_id_sha256", "model", "request_id", "proposals", "review_boundary"}
    if set(payload) != required or not all(isinstance(payload.get(key), str) and payload[key].strip() for key in ("mission_id", "document_id", "source_markdown_sha256", "task_id_sha256", "model", "review_boundary")):
        raise PotentialScopeBatchApprovalError("automatic triage draft fields are invalid")
    proposals = payload.get("proposals")
    if not isinstance(proposals, list) or not 1 <= len(proposals) <= 12:
        raise PotentialScopeBatchApprovalError("automatic triage proposals are invalid")
    seen: set[str] = set()
    for row in proposals:
        if not isinstance(row, dict) or set(row) != {"segment_id", "roles", "reason", "confidence"}:
            raise PotentialScopeBatchApprovalError("automatic triage proposal fields are invalid")
        if not isinstance(row.get("segment_id"), str) or not row["segment_id"] or row["segment_id"] in seen:
            raise PotentialScopeBatchApprovalError("automatic triage proposal segment is invalid")
        if not isinstance(row.get("roles"), list) or not row["roles"] or not isinstance(row.get("reason"), str) or not row["reason"].strip() or len(row["reason"]) > 300:
            raise PotentialScopeBatchApprovalError("automatic triage proposal content is invalid")
        if not isinstance(row.get("confidence"), (int, float)) or isinstance(row["confidence"], bool) or not 0 <= float(row["confidence"]) <= 1:
            raise PotentialScopeBatchApprovalError("automatic triage proposal confidence is invalid")
        seen.add(row["segment_id"])


def _validate_approval(payload: object, *, blank: bool) -> None:
    required = {"schema_version", "mission_id", "trust_status", "reviewer", "reviewed_at", "documents", "review_boundary"}
    status = _BLANK_STATUS if blank else _APPROVED_STATUS
    if not isinstance(payload, dict) or set(payload) != required or payload.get("schema_version") != BATCH_APPROVAL_SCHEMA_VERSION or payload.get("trust_status") != status:
        raise PotentialScopeBatchApprovalError("batch approval schema is invalid")
    if not isinstance(payload.get("mission_id"), str) or not payload["mission_id"].strip() or not isinstance(payload.get("review_boundary"), str) or not payload["review_boundary"].strip():
        raise PotentialScopeBatchApprovalError("batch approval identity is invalid")
    if not isinstance(payload.get("reviewer"), str) or not isinstance(payload.get("reviewed_at"), str):
        raise PotentialScopeBatchApprovalError("batch approval reviewer is invalid")
    if blank:
        if payload["reviewer"] or payload["reviewed_at"]:
            raise PotentialScopeBatchApprovalError("blank batch approval includes reviewer data")
    elif not payload["reviewer"].strip() or not payload["reviewed_at"].strip():
        raise PotentialScopeBatchApprovalError("completed batch approval requires reviewer and date")
    rows = payload.get("documents")
    if not isinstance(rows, list) or not rows:
        raise PotentialScopeBatchApprovalError("batch approval documents are invalid")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"document_id", "triage_sha256", "decision", "note"}:
            raise PotentialScopeBatchApprovalError("batch approval document fields are invalid")
        if not isinstance(row.get("document_id"), str) or not row["document_id"] or row["document_id"] in seen or not isinstance(row.get("triage_sha256"), str) or len(row["triage_sha256"]) != 64 or not isinstance(row.get("note"), str) or len(row["note"]) > 500:
            raise PotentialScopeBatchApprovalError("batch approval document identity is invalid")
        if blank:
            if row["decision"] or row["note"]:
                raise PotentialScopeBatchApprovalError("blank batch approval includes a decision")
        elif row.get("decision") not in _DECISIONS:
            raise PotentialScopeBatchApprovalError("completed batch approval decision is invalid")
        seen.add(row["document_id"])


def _write_once(path: Path, payload: object, label: str) -> Path:
    if path.suffix.casefold() != ".json" or "runs" in {part.casefold() for part in path.parts}:
        raise PotentialScopeBatchApprovalError(f"{label} must be a JSON file outside CosMatter/runs")
    if path.exists():
        raise PotentialScopeBatchApprovalError(f"{label} already exists and will not be overwritten")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as error:
        raise PotentialScopeBatchApprovalError(f"{label} cannot be written") from error
    return path


def _sha(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
