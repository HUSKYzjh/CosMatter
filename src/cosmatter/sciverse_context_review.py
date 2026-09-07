"""Build a private review pool from one confirmed Sciverse content window.

The source text and the resulting candidate pool stay outside the mission run.
Only a count-only event belongs in the run; the pool itself remains unreviewed
and cannot create evidence or a Source Map without a later explicit selection.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .content_access import ContentAccessError, content_access_states
from .operation_parameter_contracts import SCIVERSE_CONTENT_LIMIT_MAX, SCIVERSE_CONTENT_LIMIT_MIN


SCIVERSE_CONTEXT_REVIEW_POOL_SCHEMA_VERSION = "1.0"
SCIVERSE_SOURCE_MAP_REVIEW_SCHEMA_VERSION = "1.0"
_TRUST_STATUS = "private_unreviewed_sciverse_context_candidate_pool_not_source_map"
_BLANK_REVIEW_STATUS = "blank_human_sciverse_source_map_pool_selection_template"
_HUMAN_REVIEW_STATUS = "human_reviewed_sciverse_source_map_pool_selection"
_BLANK_TRIAL_STATUS = "blank_delegated_automated_trial_sciverse_source_map_pool_selection_template"
_TRIAL_REVIEW_STATUS = "delegated_automated_trial_sciverse_source_map_pool_selection"
_MAX_INPUT_BYTES = 32_000
_MAX_CANDIDATES = 48
_MAX_QUOTE_CHARS = 500
_FIELDS = {
    "schema_version", "mission_id", "candidate_fingerprint", "document_id",
    "trust_status", "receipt_id", "content_sha256", "confirmed_at", "offset",
    "limit", "candidate_segments", "review_instructions",
}
_SEGMENT_FIELDS = {"segment_id", "locator", "kind", "quote"}


class SciverseContextReviewError(ValueError):
    """Raised when a local context pool cannot be bound to a confirmed read."""


def prepare_sciverse_context_review_pool(
    *,
    mission_id: str,
    candidate_payload: object,
    content_access: object,
    provider_receipts: object,
    document_id: str,
    offset: int,
    input_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Validate one private context file and write a bounded review pool."""
    confirmation, receipt = _confirmed_receipt(
        mission_id=mission_id,
        candidate_payload=candidate_payload,
        content_access=content_access,
        provider_receipts=provider_receipts,
        document_id=document_id,
        offset=offset,
    )
    content = _read_context(input_path)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if digest != confirmation["content_sha256"] or digest != receipt["content_sha256"]:
        raise SciverseContextReviewError("private Sciverse context does not match the confirmed content hash")
    if len(content) != receipt["content_char_count"]:
        raise SciverseContextReviewError("private Sciverse context character count does not match its receipt")
    segments = _candidate_segments(content, offset)
    if not segments:
        raise SciverseContextReviewError("private Sciverse context contains no reviewable text segments")
    payload = {
        "schema_version": SCIVERSE_CONTEXT_REVIEW_POOL_SCHEMA_VERSION,
        "mission_id": mission_id,
        "candidate_fingerprint": content_access["candidate_fingerprint"],
        "document_id": document_id,
        "trust_status": _TRUST_STATUS,
        "receipt_id": receipt["receipt_id"],
        "content_sha256": digest,
        "confirmed_at": confirmation["confirmed_at"],
        "offset": offset,
        "limit": receipt["limit"],
        "candidate_segments": segments,
        "review_instructions": (
            "This private pool contains unreviewed Sciverse context candidates. Select exact segments in a later "
            "hash-bound review step; the pool is not a Source Map, EvidenceCard, or scientific evidence."
        ),
    }
    _validate_pool(payload)
    _write_new_pool(output_path, payload)
    return payload


def load_sciverse_context_review_pool(path: Path) -> dict[str, Any]:
    """Load a private pool without treating it as reviewed evidence."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SciverseContextReviewError("private Sciverse context review pool cannot be read") from error
    _validate_pool(payload)
    return payload


def require_current_sciverse_context_review_pool(
    pool: object,
    *,
    mission_id: str,
    candidate_payload: object,
    content_access: object,
    provider_receipts: object,
    document_id: str,
) -> dict[str, Any]:
    """Rebind a private pool to the current candidates and successful receipt."""
    _validate_pool(pool)
    if not isinstance(pool, dict) or pool.get("mission_id") != mission_id or pool.get("document_id") != document_id:
        raise SciverseContextReviewError("Sciverse context review pool belongs to a different mission or document")
    confirmation, receipt = _confirmed_receipt(
        mission_id=mission_id,
        candidate_payload=candidate_payload,
        content_access=content_access,
        provider_receipts=provider_receipts,
        document_id=document_id,
        offset=pool["offset"],
    )
    expected = {
        "candidate_fingerprint": content_access["candidate_fingerprint"],
        "receipt_id": receipt["receipt_id"],
        "content_sha256": confirmation["content_sha256"],
        "confirmed_at": confirmation["confirmed_at"],
        "limit": receipt["limit"],
    }
    if any(pool.get(field) != value for field, value in expected.items()):
        raise SciverseContextReviewError("Sciverse context review pool no longer matches its confirmed content binding")
    return pool


def sciverse_source_map_review_template(pool: object, *, delegated_automated_trial: bool = False) -> dict[str, Any]:
    """Create a quote-free, hash-bound selection template for one private pool."""
    _validate_pool(pool)
    return {
        "schema_version": SCIVERSE_SOURCE_MAP_REVIEW_SCHEMA_VERSION,
        "mission_id": pool["mission_id"],
        "candidate_fingerprint": pool["candidate_fingerprint"],
        "document_id": pool["document_id"],
        "trust_status": _BLANK_TRIAL_STATUS if delegated_automated_trial else _BLANK_REVIEW_STATUS,
        "receipt_id": pool["receipt_id"],
        "content_sha256": pool["content_sha256"],
        "offset": pool["offset"],
        "limit": pool["limit"],
        "segments": [
            {
                "segment_id": item["segment_id"],
                "quote_sha256": hashlib.sha256(item["quote"].encode("utf-8")).hexdigest(),
                "selected": False,
                "reason": "",
            }
            for item in pool["candidate_segments"]
        ],
    }


def write_sciverse_source_map_review(path: Path, review: object, *, allow_blank: bool, delegated_automated_trial: bool = False) -> Path:
    """Write a new quote-free template or completed private selection."""
    _validate_source_map_review(review, allow_blank=allow_blank, delegated_automated_trial=delegated_automated_trial)
    if path.suffix.casefold() != ".json":
        raise SciverseContextReviewError("Sciverse Source Map review must use a .json filename")
    if path.exists():
        raise SciverseContextReviewError("Sciverse Source Map review already exists and will not be overwritten")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(review, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as error:
        raise SciverseContextReviewError("Sciverse Source Map review cannot be written") from error
    return path


def sciverse_source_map_selection_from_review(
    *,
    pool: object,
    review: object,
    delegated_automated_trial: bool = False,
) -> dict[str, Any]:
    """Resolve exact selected IDs back to private excerpts after all hashes match."""
    _validate_pool(pool)
    _validate_source_map_review(review, allow_blank=False, delegated_automated_trial=delegated_automated_trial)
    if not isinstance(pool, dict) or not isinstance(review, dict):
        raise SciverseContextReviewError("Sciverse Source Map pool or review is invalid")
    binding_fields = (
        "mission_id", "candidate_fingerprint", "document_id", "receipt_id",
        "content_sha256", "offset", "limit",
    )
    if any(review[field] != pool[field] for field in binding_fields):
        raise SciverseContextReviewError("Sciverse Source Map review does not match its private pool")
    candidates = {item["segment_id"]: item for item in pool["candidate_segments"]}
    if len(review["segments"]) != len(candidates) or {item["segment_id"] for item in review["segments"]} != set(candidates):
        raise SciverseContextReviewError("Sciverse Source Map review must retain every pool candidate identifier")
    selected = [item for item in review["segments"] if item["selected"]]
    if not 1 <= len(selected) <= 12:
        raise SciverseContextReviewError("Sciverse Source Map review must select 1 to 12 segments")
    for item in review["segments"]:
        candidate = candidates.get(item["segment_id"])
        expected_hash = hashlib.sha256(candidate["quote"].encode("utf-8")).hexdigest() if candidate else None
        if item["quote_sha256"] != expected_hash:
            raise SciverseContextReviewError("Sciverse Source Map candidate quote hash does not match")
        if item["selected"] and not item["reason"].strip():
            raise SciverseContextReviewError("selected Sciverse Source Map segments require a review reason")
    return {
        "document_id": pool["document_id"],
        "segments": [
            {
                "segment_id": candidates[item["segment_id"]]["segment_id"],
                "locator": candidates[item["segment_id"]]["locator"],
                "kind": candidates[item["segment_id"]]["kind"],
                "quote": candidates[item["segment_id"]]["quote"],
            }
            for item in selected
        ],
    }


def sciverse_automated_trial_selection(pool: object, segment_ids: object) -> dict[str, Any]:
    """Create an explicit non-scientific selection for a delegated route test."""
    _validate_pool(pool)
    if (
        not isinstance(segment_ids, list)
        or not 1 <= len(segment_ids) <= 12
        or any(not isinstance(item, str) or not item for item in segment_ids)
        or len(set(segment_ids)) != len(segment_ids)
    ):
        raise SciverseContextReviewError(
            "automated trial Sciverse Source Map selection requires one to twelve unique segment IDs"
        )
    review = sciverse_source_map_review_template(pool, delegated_automated_trial=True)
    known_ids = {item["segment_id"] for item in review["segments"]}
    if any(identifier not in known_ids for identifier in segment_ids):
        raise SciverseContextReviewError(
            "automated trial Sciverse Source Map selection contains an unknown pool segment"
        )
    selected = set(segment_ids)
    for item in review["segments"]:
        if item["segment_id"] in selected:
            item["selected"] = True
            item["reason"] = "selected_for_delegated_pipeline_validation_not_scientific_support"
    review["trust_status"] = _TRIAL_REVIEW_STATUS
    _validate_source_map_review(review, allow_blank=False, delegated_automated_trial=True)
    return review


def _confirmed_receipt(
    *,
    mission_id: str,
    candidate_payload: object,
    content_access: object,
    provider_receipts: object,
    document_id: str,
    offset: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(mission_id, str) or not mission_id.strip() or not isinstance(document_id, str) or not document_id.strip():
        raise SciverseContextReviewError("Sciverse context review identity is invalid")
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise SciverseContextReviewError("Sciverse context review offset is invalid")
    try:
        states = content_access_states(content_access, mission_id, candidate_payload)
    except ContentAccessError as error:
        raise SciverseContextReviewError(str(error)) from error
    if states.get(document_id) != "confirmed" or not isinstance(content_access, dict):
        raise SciverseContextReviewError("Sciverse context review requires a current confirmed content read")
    confirmations = content_access.get("confirmations")
    if not isinstance(confirmations, list):
        raise SciverseContextReviewError("Sciverse content confirmation list is invalid")
    confirmation = next((item for item in confirmations if item.get("document_id") == document_id), None)
    if confirmation is None or not isinstance(provider_receipts, list):
        raise SciverseContextReviewError("Sciverse content confirmation receipt is unavailable")
    matches = [item for item in provider_receipts if isinstance(item, dict) and item.get("receipt_id") == confirmation.get("receipt_id")]
    if len(matches) != 1:
        raise SciverseContextReviewError("Sciverse content confirmation must match exactly one provider receipt")
    receipt = matches[0]
    expected_document_hash = hashlib.sha256(document_id.encode("utf-8")).hexdigest()
    if (
        receipt.get("provider") != "sciverse"
        or receipt.get("operation") != "content"
        or receipt.get("document_id_sha256") != expected_document_hash
        or receipt.get("content_sha256") != confirmation.get("content_sha256")
        or receipt.get("offset") != offset
    ):
        raise SciverseContextReviewError("Sciverse content receipt identity, offset, or hash does not match")
    return confirmation, receipt


def _read_context(path: Path) -> str:
    if path.suffix.casefold() not in {".txt", ".md"}:
        raise SciverseContextReviewError("private Sciverse context input must be UTF-8 .txt or .md")
    try:
        size = path.stat().st_size
    except OSError as error:
        raise SciverseContextReviewError("private Sciverse context input cannot be inspected") from error
    if not 1 <= size <= _MAX_INPUT_BYTES:
        raise SciverseContextReviewError("private Sciverse context input is outside the byte safety limit")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise SciverseContextReviewError("private Sciverse context input cannot be read as UTF-8") from error


def _candidate_segments(content: str, document_offset: int) -> list[dict[str, str]]:
    raw_segments: list[tuple[int, str]] = []
    block_start = 0
    block_parts: list[str] = []
    cursor = 0

    def flush() -> None:
        nonlocal block_parts, block_start
        if not block_parts:
            return
        raw = "".join(block_parts)
        leading = len(raw) - len(raw.lstrip())
        text = raw.strip()
        if text:
            raw_segments.extend(_bounded_parts(text, block_start + leading))
        block_parts = []

    for line in content.splitlines(keepends=True):
        if line.strip():
            if not block_parts:
                block_start = cursor
            block_parts.append(line)
        else:
            flush()
        cursor += len(line)
    flush()
    if content and not content.endswith(("\n", "\r")) and not raw_segments and content.strip():
        leading = len(content) - len(content.lstrip())
        raw_segments.extend(_bounded_parts(content.strip(), leading))
    sampled = _full_document_sample(raw_segments, _MAX_CANDIDATES)
    return [
        {
            "segment_id": f"sciverse_ctx_{index:03d}",
            "locator": f"sciverse_char:{document_offset + start}-{document_offset + start + len(quote)}",
            "kind": "paragraph",
            "quote": quote,
        }
        for index, (start, quote) in enumerate(sampled, 1)
    ]


def _bounded_parts(text: str, start: int) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    remaining = text
    position = start
    while remaining:
        if len(remaining) <= _MAX_QUOTE_CHARS:
            result.append((position, remaining))
            break
        cut = max(remaining.rfind(" ", 0, _MAX_QUOTE_CHARS + 1), remaining.rfind("\n", 0, _MAX_QUOTE_CHARS + 1))
        if cut < _MAX_QUOTE_CHARS // 2:
            cut = _MAX_QUOTE_CHARS
        quote = remaining[:cut].rstrip()
        result.append((position, quote))
        consumed = cut
        tail = remaining[consumed:]
        leading = len(tail) - len(tail.lstrip())
        position += consumed + leading
        remaining = tail.lstrip()
    return result


def _full_document_sample(items: list[tuple[int, str]], limit: int) -> list[tuple[int, str]]:
    if len(items) <= limit:
        return items
    last = len(items) - 1
    return [items[round(position * last / (limit - 1))] for position in range(limit)]


def _write_new_pool(path: Path, payload: dict[str, Any]) -> None:
    if path.suffix.casefold() != ".json":
        raise SciverseContextReviewError("Sciverse context review pool output must use a .json filename")
    if path.exists():
        raise SciverseContextReviewError("Sciverse context review pool output already exists and will not be overwritten")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as error:
        raise SciverseContextReviewError("Sciverse context review pool cannot be written") from error


def _validate_pool(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise SciverseContextReviewError("Sciverse context review pool fields are invalid")
    if payload.get("schema_version") != SCIVERSE_CONTEXT_REVIEW_POOL_SCHEMA_VERSION or payload.get("trust_status") != _TRUST_STATUS:
        raise SciverseContextReviewError("Sciverse context review pool schema or trust status is invalid")
    for field in ("mission_id", "candidate_fingerprint", "document_id", "receipt_id", "content_sha256", "review_instructions"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise SciverseContextReviewError("Sciverse context review pool identity is invalid")
    for field in ("candidate_fingerprint", "content_sha256"):
        if len(payload[field]) != 64 or any(char not in "0123456789abcdef" for char in payload[field]):
            raise SciverseContextReviewError("Sciverse context review pool hashes are invalid")
    if payload.get("confirmed_at") is not None and (not isinstance(payload["confirmed_at"], str) or not payload["confirmed_at"].endswith("Z")):
        raise SciverseContextReviewError("Sciverse context review confirmation time is invalid")
    if not isinstance(payload.get("offset"), int) or payload["offset"] < 0 or not isinstance(payload.get("limit"), int) or not SCIVERSE_CONTENT_LIMIT_MIN <= payload["limit"] <= SCIVERSE_CONTENT_LIMIT_MAX:
        raise SciverseContextReviewError("Sciverse context review range is invalid")
    segments = payload.get("candidate_segments")
    if not isinstance(segments, list) or not 1 <= len(segments) <= _MAX_CANDIDATES:
        raise SciverseContextReviewError("Sciverse context review segments are invalid")
    seen: set[str] = set()
    for item in segments:
        if not isinstance(item, dict) or set(item) != _SEGMENT_FIELDS:
            raise SciverseContextReviewError("Sciverse context review segment fields are invalid")
        if not all(isinstance(item.get(field), str) and item[field].strip() for field in _SEGMENT_FIELDS):
            raise SciverseContextReviewError("Sciverse context review segment values are invalid")
        if item["segment_id"] in seen or item["kind"] != "paragraph" or len(item["quote"]) > _MAX_QUOTE_CHARS or not item["locator"].startswith("sciverse_char:"):
            raise SciverseContextReviewError("Sciverse context review segment boundary is invalid")
        seen.add(item["segment_id"])


def _validate_source_map_review(payload: object, *, allow_blank: bool, delegated_automated_trial: bool) -> None:
    fields = {
        "schema_version", "mission_id", "candidate_fingerprint", "document_id",
        "trust_status", "receipt_id", "content_sha256", "offset", "limit", "segments",
    }
    segment_fields = {"segment_id", "quote_sha256", "selected", "reason"}
    if not isinstance(payload, dict) or set(payload) != fields:
        raise SciverseContextReviewError("Sciverse Source Map review fields are invalid")
    expected_status = (
        _BLANK_TRIAL_STATUS if allow_blank and delegated_automated_trial
        else _TRIAL_REVIEW_STATUS if delegated_automated_trial
        else _BLANK_REVIEW_STATUS if allow_blank
        else _HUMAN_REVIEW_STATUS
    )
    if payload.get("schema_version") != SCIVERSE_SOURCE_MAP_REVIEW_SCHEMA_VERSION or payload.get("trust_status") != expected_status:
        raise SciverseContextReviewError("Sciverse Source Map review schema or trust status is invalid")
    for field in ("mission_id", "candidate_fingerprint", "document_id", "receipt_id", "content_sha256"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise SciverseContextReviewError("Sciverse Source Map review identity is invalid")
    for field in ("candidate_fingerprint", "content_sha256"):
        if len(payload[field]) != 64 or any(char not in "0123456789abcdef" for char in payload[field]):
            raise SciverseContextReviewError("Sciverse Source Map review hashes are invalid")
    if not isinstance(payload.get("offset"), int) or payload["offset"] < 0 or not isinstance(payload.get("limit"), int) or not SCIVERSE_CONTENT_LIMIT_MIN <= payload["limit"] <= SCIVERSE_CONTENT_LIMIT_MAX:
        raise SciverseContextReviewError("Sciverse Source Map review range is invalid")
    rows = payload.get("segments")
    if not isinstance(rows, list) or not 1 <= len(rows) <= _MAX_CANDIDATES:
        raise SciverseContextReviewError("Sciverse Source Map review segments are invalid")
    seen: set[str] = set()
    for item in rows:
        if not isinstance(item, dict) or set(item) != segment_fields:
            raise SciverseContextReviewError("Sciverse Source Map review segment fields are invalid")
        segment_id = item.get("segment_id")
        digest = item.get("quote_sha256")
        if not isinstance(segment_id, str) or not segment_id or segment_id in seen:
            raise SciverseContextReviewError("Sciverse Source Map review segment identity is invalid")
        if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise SciverseContextReviewError("Sciverse Source Map review quote hash is invalid")
        if not isinstance(item.get("selected"), bool) or not isinstance(item.get("reason"), str) or len(item["reason"]) > 500:
            raise SciverseContextReviewError("Sciverse Source Map review decision is invalid")
        if allow_blank and (item["selected"] or item["reason"]):
            raise SciverseContextReviewError("blank Sciverse Source Map review cannot contain decisions")
        seen.add(segment_id)
