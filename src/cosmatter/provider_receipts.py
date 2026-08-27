"""Secret-safe receipts proving bounded external-provider execution.

Receipts intentionally retain a query digest rather than query text and never
retain headers, request bodies, response payloads, abstracts, or full text.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import new_id, utc_now


RECEIPT_SCHEMA_VERSION = "1.0"
_PROVIDERS = {"sciverse", "mineru"}
_OPERATIONS = {"agentic_search", "content", "source_parse_submit", "source_parse_poll"}
_AGENTIC_RECEIPT_FIELDS = {
    "schema_version", "receipt_id", "provider", "operation", "request_id",
    "status_code", "query_sha256", "query_char_count", "requested_top_k",
    "candidate_count", "recorded_at",
}

_CONTENT_RECEIPT_FIELDS = {
    "schema_version", "receipt_id", "provider", "operation", "request_id", "status_code",
    "document_id_sha256", "offset", "limit", "content_sha256", "content_char_count",
    "next_offset", "more", "recorded_at",
}

_MINERU_RECEIPT_FIELDS = {
    "schema_version", "receipt_id", "provider", "operation", "request_id", "status_code",
    "document_id_sha256", "source_url_sha256", "task_id_sha256", "task_state",
    "model_version", "recorded_at",
}
_MINERU_OPERATIONS = {"source_parse_submit", "source_parse_poll"}
_TASK_STATES = {"pending", "running", "done", "failed"}


class ProviderReceiptError(ValueError):
    """Raised when a receipt could be unsafe or internally inconsistent."""


def sciverse_search_receipt(
    *,
    query: str,
    top_k: int,
    status_code: int,
    request_id: str | None,
    candidate_count: int,
) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip() or len(query) > 2_000:
        raise ProviderReceiptError("receipt query must be a bounded nonempty string")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 50:
        raise ProviderReceiptError("receipt top_k must be between 1 and 50")
    if not isinstance(status_code, int) or isinstance(status_code, bool) or not 100 <= status_code <= 599:
        raise ProviderReceiptError("receipt status_code must be an HTTP status")
    if request_id is not None and (not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 256):
        raise ProviderReceiptError("receipt request_id is invalid")
    if not isinstance(candidate_count, int) or isinstance(candidate_count, bool) or candidate_count < 0:
        raise ProviderReceiptError("receipt candidate_count is invalid")
    normalized_query = query.strip()
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "receipt_id": new_id("receipt"),
        "provider": "sciverse",
        "operation": "agentic_search",
        "request_id": request_id,
        "status_code": status_code,
        "query_sha256": hashlib.sha256(normalized_query.encode("utf-8")).hexdigest(),
        "query_char_count": len(normalized_query),
        "requested_top_k": top_k,
        "candidate_count": candidate_count,
        "recorded_at": utc_now(),
    }


def sciverse_content_receipt(
    *,
    document_id: str,
    offset: int,
    limit: int,
    content: str,
    next_offset: int | None,
    more: bool,
    status_code: int,
    request_id: str | None,
) -> dict[str, Any]:
    if not isinstance(document_id, str) or not document_id.strip() or len(document_id) > 255:
        raise ProviderReceiptError("content receipt document_id is invalid")
    if not isinstance(offset, int) or offset < 0 or not isinstance(limit, int) or not 200 <= limit <= 4_000:
        raise ProviderReceiptError("content receipt range is invalid")
    if not isinstance(content, str) or not content or len(content) > limit or not isinstance(more, bool):
        raise ProviderReceiptError("content receipt body metadata is invalid")
    if next_offset is not None and (not isinstance(next_offset, int) or next_offset < 0):
        raise ProviderReceiptError("content receipt continuation is invalid")
    if not isinstance(status_code, int) or not 100 <= status_code <= 599:
        raise ProviderReceiptError("content receipt status_code is invalid")
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION, "receipt_id": new_id("receipt"), "provider": "sciverse",
        "operation": "content", "request_id": request_id, "status_code": status_code,
        "document_id_sha256": hashlib.sha256(document_id.strip().encode("utf-8")).hexdigest(),
        "offset": offset, "limit": limit, "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "content_char_count": len(content), "next_offset": next_offset, "more": more, "recorded_at": utc_now(),
    }


def mineru_task_receipt(
    *,
    operation: str,
    document_id: str,
    source_url_sha256: str,
    task_id: str,
    task_state: str,
    model_version: str,
    status_code: int,
    request_id: str | None,
) -> dict[str, Any]:
    """Record a MinerU task operation without retaining its URL or task ID."""
    if operation not in _MINERU_OPERATIONS:
        raise ProviderReceiptError("MinerU receipt operation is invalid")
    if not isinstance(document_id, str) or not document_id.strip() or len(document_id) > 255:
        raise ProviderReceiptError("MinerU receipt document_id is invalid")
    if not _is_sha256(source_url_sha256):
        raise ProviderReceiptError("MinerU receipt source URL digest is invalid")
    if not isinstance(task_id, str) or not task_id.strip() or len(task_id) > 200:
        raise ProviderReceiptError("MinerU receipt task_id is invalid")
    if task_state not in _TASK_STATES:
        raise ProviderReceiptError("MinerU receipt task_state is invalid")
    if not isinstance(model_version, str) or not model_version.strip() or len(model_version) > 160:
        raise ProviderReceiptError("MinerU receipt model_version is invalid")
    if not isinstance(status_code, int) or isinstance(status_code, bool) or not 100 <= status_code <= 599:
        raise ProviderReceiptError("MinerU receipt status_code is invalid")
    if request_id is not None and (not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 256):
        raise ProviderReceiptError("MinerU receipt request_id is invalid")
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "receipt_id": new_id("receipt"),
        "provider": "mineru",
        "operation": operation,
        "request_id": request_id,
        "status_code": status_code,
        "document_id_sha256": hashlib.sha256(document_id.strip().encode("utf-8")).hexdigest(),
        "source_url_sha256": source_url_sha256,
        "task_id_sha256": hashlib.sha256(task_id.strip().encode("utf-8")).hexdigest(),
        "task_state": task_state,
        "model_version": model_version.strip(),
        "recorded_at": utc_now(),
    }


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def append_provider_receipt(run_dir: Path, receipt: dict[str, Any]) -> Path:
    _validate_receipt(receipt)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "provider_receipts.jsonl"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
        handle.write("\n")
    return path


def _validate_receipt(receipt: object) -> None:
    if not isinstance(receipt, dict):
        raise ProviderReceiptError("provider receipt schema is invalid")
    operation = receipt.get("operation")
    if operation == "agentic_search":
        fields, provider = _AGENTIC_RECEIPT_FIELDS, "sciverse"
    elif operation == "content":
        fields, provider = _CONTENT_RECEIPT_FIELDS, "sciverse"
    elif operation in _MINERU_OPERATIONS:
        fields, provider = _MINERU_RECEIPT_FIELDS, "mineru"
    else:
        raise ProviderReceiptError("provider receipt schema version or operation is invalid")
    if set(receipt) != fields or receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise ProviderReceiptError("provider receipt schema version or fields are invalid")
    if receipt.get("provider") != provider or not isinstance(receipt.get("receipt_id"), str) or not receipt["receipt_id"].startswith("receipt_"):
        raise ProviderReceiptError("provider receipt identity is invalid")
    if receipt.get("request_id") is not None and (not isinstance(receipt["request_id"], str) or not receipt["request_id"].strip()):
        raise ProviderReceiptError("provider receipt request_id is invalid")
    if not isinstance(receipt.get("status_code"), int) or isinstance(receipt["status_code"], bool) or not 100 <= receipt["status_code"] <= 599 or not isinstance(receipt.get("recorded_at"), str) or not receipt["recorded_at"].strip():
        raise ProviderReceiptError("provider receipt status or timestamp is invalid")
    if operation == "agentic_search":
        if not _is_sha256(receipt.get("query_sha256")):
            raise ProviderReceiptError("provider receipt query digest is invalid")
        for field in ("query_char_count", "requested_top_k", "candidate_count"):
            if not isinstance(receipt.get(field), int) or isinstance(receipt[field], bool) or receipt[field] < 0:
                raise ProviderReceiptError(f"provider receipt {field} is invalid")
        if not 1 <= receipt["requested_top_k"] <= 50:
            raise ProviderReceiptError("provider receipt requested_top_k is invalid")
    elif operation == "content":
        for field in ("document_id_sha256", "content_sha256"):
            if not _is_sha256(receipt.get(field)):
                raise ProviderReceiptError("content receipt digest is invalid")
        if not isinstance(receipt.get("offset"), int) or receipt["offset"] < 0 or not isinstance(receipt.get("limit"), int) or not 200 <= receipt["limit"] <= 4_000 or not isinstance(receipt.get("content_char_count"), int) or not 1 <= receipt["content_char_count"] <= receipt["limit"] or not isinstance(receipt.get("more"), bool):
            raise ProviderReceiptError("content receipt metadata is invalid")
        if receipt.get("next_offset") is not None and (not isinstance(receipt["next_offset"], int) or receipt["next_offset"] < 0):
            raise ProviderReceiptError("content receipt continuation is invalid")
    else:
        for field in ("document_id_sha256", "source_url_sha256", "task_id_sha256"):
            if not _is_sha256(receipt.get(field)):
                raise ProviderReceiptError("MinerU receipt digest is invalid")
        if receipt.get("task_state") not in _TASK_STATES or not isinstance(receipt.get("model_version"), str) or not receipt["model_version"].strip():
            raise ProviderReceiptError("MinerU receipt task metadata is invalid")

def audit_source_parse_receipt_links(source_parse_payload: object, receipts_path: Path) -> dict[str, Any]:
    """Check MinerU task-ledger entries against hash-only provider receipts."""
    if not isinstance(source_parse_payload, dict) or not isinstance(source_parse_payload.get("tasks"), list):
        raise ProviderReceiptError("source parse task ledger is invalid")
    receipts = _load_receipts(receipts_path)
    tasks = source_parse_payload["tasks"]
    matched = stale = 0
    for task in tasks:
        if not isinstance(task, dict):
            raise ProviderReceiptError("source parse task entry is invalid")
        document_id, source_digest, task_id = task.get("document_id"), task.get("source_url_sha256"), task.get("task_id")
        if not isinstance(document_id, str) or not document_id.strip() or not _is_sha256(source_digest) or not isinstance(task_id, str) or not task_id.strip() or task.get("state") not in _TASK_STATES:
            raise ProviderReceiptError("source parse task identity is invalid")
        document_digest = hashlib.sha256(document_id.encode("utf-8")).hexdigest()
        task_digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()
        links = [
            receipt for receipt in receipts
            if receipt.get("provider") == "mineru"
            and receipt.get("document_id_sha256") == document_digest
            and receipt.get("source_url_sha256") == source_digest
            and receipt.get("task_id_sha256") == task_digest
        ]
        if not links:
            continue
        if links[-1]["task_state"] != task["state"]:
            stale += 1
            continue
        matched += 1
    task_count = len(tasks)
    return {
        "schema_version": "1.0",
        "trust_status": "source_parse_receipt_link_audit_not_parser_quality_assessment",
        "source_parse_task_count": task_count,
        "receipt_linked_task_count": matched,
        "stale_task_state_count": stale,
        "unlinked_task_count": task_count - matched - stale,
        "mineru_receipt_count": sum(receipt.get("provider") == "mineru" for receipt in receipts),
        "receipt_link_coverage": 1.0 if not task_count else matched / task_count,
    }


def write_source_parse_receipt_audit(run_dir: Path, result: dict[str, Any]) -> Path:
    fields = {
        "schema_version", "trust_status", "source_parse_task_count", "receipt_linked_task_count",
        "stale_task_state_count", "unlinked_task_count", "mineru_receipt_count", "receipt_link_coverage",
    }
    if not isinstance(result, dict) or set(result) != fields or result.get("schema_version") != "1.0":
        raise ProviderReceiptError("source parse receipt audit result is invalid")
    path = run_dir / "source_parse_receipt_audit.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def audit_candidate_receipt_links(candidate_payload: object, receipts_path: Path) -> dict[str, Any]:
    """Verify only opaque Sciverse receipt links retained in candidate origins."""
    receipts = _load_receipts(receipts_path)
    by_id = {receipt["receipt_id"]: receipt for receipt in receipts}
    if len(by_id) != len(receipts):
        raise ProviderReceiptError("provider receipts contain duplicate receipt identifiers")
    if not isinstance(candidate_payload, dict) or not isinstance(candidate_payload.get("candidates"), list):
        raise ProviderReceiptError("retrieval candidate artifact is invalid")
    candidate_count = origin_count = linked_origin_count = 0
    for candidate in candidate_payload["candidates"]:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("document_id"), str) or not candidate["document_id"]:
            raise ProviderReceiptError("retrieval candidate identity is invalid")
        candidate_count += 1
        origins = candidate.get("retrieval_origins", [])
        if not isinstance(origins, list):
            raise ProviderReceiptError("retrieval candidate origins are invalid")
        for origin in origins:
            if not isinstance(origin, dict):
                raise ProviderReceiptError("retrieval candidate origin is invalid")
            origin_count += 1
            receipt_id = origin.get("receipt_id")
            if receipt_id is None:
                continue
            provider, operation, query_digest = origin.get("provider"), origin.get("operation"), origin.get("query_sha256")
            if not all(isinstance(value, str) and value for value in (receipt_id, provider, operation, query_digest)):
                raise ProviderReceiptError("provider-linked candidate origin is invalid")
            receipt = by_id.get(receipt_id)
            if receipt is None or receipt.get("operation") != "agentic_search":
                raise ProviderReceiptError("candidate origin refers to a missing search receipt")
            if (provider, operation, query_digest) != (receipt["provider"], receipt["operation"], receipt["query_sha256"]):
                raise ProviderReceiptError("candidate origin does not match its provider receipt")
            linked_origin_count += 1
    return {"schema_version": "1.0", "trust_status": "candidate_origin_receipt_link_audit_not_relevance_assessment", "candidate_count": candidate_count, "candidate_origin_count": origin_count, "provider_linked_origin_count": linked_origin_count, "provider_receipt_count": len(receipts), "provider_origin_receipt_coverage": 1.0}


def write_candidate_receipt_audit(run_dir: Path, result: dict[str, Any]) -> Path:
    fields = {"schema_version", "trust_status", "candidate_count", "candidate_origin_count", "provider_linked_origin_count", "provider_receipt_count", "provider_origin_receipt_coverage"}
    if not isinstance(result, dict) or set(result) != fields or result.get("schema_version") != "1.0":
        raise ProviderReceiptError("candidate receipt audit result is invalid")
    path = run_dir / "candidate_receipt_audit.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _load_receipts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ProviderReceiptError("provider receipt log cannot be read") from error
    result: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            receipt = json.loads(line)
        except json.JSONDecodeError as error:
            raise ProviderReceiptError("provider receipt log contains invalid JSON") from error
        _validate_receipt(receipt)
        result.append(receipt)
    return result
