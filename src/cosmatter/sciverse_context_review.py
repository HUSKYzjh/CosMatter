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


SCIVERSE_CONTEXT_REVIEW_POOL_SCHEMA_VERSION = "1.0"
_TRUST_STATUS = "private_unreviewed_sciverse_context_candidate_pool_not_source_map"
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
    if not isinstance(payload.get("offset"), int) or payload["offset"] < 0 or not isinstance(payload.get("limit"), int) or not 200 <= payload["limit"] <= 4_000:
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
