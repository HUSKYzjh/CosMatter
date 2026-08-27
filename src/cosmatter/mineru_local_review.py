"""Prepare a private, bounded review pool from a locally downloaded MinerU Markdown result.

This adapter never contacts MinerU and never writes parser output, Markdown paths,
or excerpts into a mission run. It converts an explicitly supplied local Markdown
file into a small, reviewer-facing JSON pool outside the run. A reviewer must
still create the existing 1-12 segment Source Map selection before any excerpt
becomes a CosMatter artifact.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REVIEW_POOL_SCHEMA_VERSION = "1.0"
SOURCE_MAP_POOL_REVIEW_TEMPLATE_SCHEMA_VERSION = "1.0"
_MAX_INPUT_BYTES = 5_000_000
_MAX_CANDIDATES = 48
_MAX_QUOTE_CHARS = 500
_FIELDS = {
    "schema_version", "mission_id", "document_id", "trust_status",
    "task_id_sha256", "source_markdown_sha256", "candidate_segments",
    "review_instructions",
}
_SEGMENT_FIELDS = {"segment_id", "locator", "kind", "quote"}
_KINDS = {"paragraph", "table", "formula", "figure_caption"}


class MinerULocalReviewError(ValueError):
    """Raised when a local MinerU Markdown review pool is unsafe or invalid."""


def prepare_mineru_markdown_review_pool(
    *,
    mission_id: str,
    document_id: str,
    source_task: object,
    input_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Create one bounded, private candidate pool from a completed task."""
    _validate_completed_task(source_task, document_id)
    if not isinstance(mission_id, str) or not mission_id.strip():
        raise MinerULocalReviewError("mission_id is invalid")
    content = _read_markdown(input_path)
    candidates = _candidate_segments(content)
    if not candidates:
        raise MinerULocalReviewError("local MinerU Markdown contains no reviewable text segments")
    payload = {
        "schema_version": REVIEW_POOL_SCHEMA_VERSION,
        "mission_id": mission_id.strip(),
        "document_id": document_id,
        "trust_status": "private_unreviewed_mineru_markdown_candidate_pool_not_source_map",
        "task_id_sha256": hashlib.sha256(source_task["task_id"].encode("utf-8")).hexdigest(),
        "source_markdown_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "candidate_segments": candidates,
        "review_instructions": (
            "Inspect the local MinerU output and copy only 1-12 accurate candidate segments into a separate "
            "record-source-map selection JSON. This pool is private and unreviewed; it is not evidence."
        ),
    }
    _validate_pool(payload)
    if output_path.suffix.casefold() != ".json":
        raise MinerULocalReviewError("review pool output must use a .json filename")
    if output_path.exists():
        raise MinerULocalReviewError("review pool output already exists and will not be overwritten")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as error:
        raise MinerULocalReviewError("review pool output cannot be written") from error
    return payload


def _read_markdown(path: Path) -> str:
    if path.suffix.casefold() not in {".md", ".markdown"}:
        raise MinerULocalReviewError("local MinerU review input must be UTF-8 Markdown")
    try:
        size = path.stat().st_size
    except OSError as error:
        raise MinerULocalReviewError("local MinerU review input cannot be inspected") from error
    if not 1 <= size <= _MAX_INPUT_BYTES:
        raise MinerULocalReviewError("local MinerU review input is outside the byte safety limit")
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise MinerULocalReviewError("local MinerU review input cannot be read as UTF-8 Markdown") from error
    return content


def _candidate_segments(content: str) -> list[dict[str, str]]:
    lines = content.splitlines()
    groups: list[tuple[int, int, list[str]]] = []
    start = 0
    current: list[str] = []
    for number, line in enumerate(lines, 1):
        if line.strip():
            if not current:
                start = number
            current.append(line.rstrip())
        elif current:
            groups.append((start, number - 1, current))
            current = []
    if current:
        groups.append((start, len(lines), current))
    result: list[dict[str, str]] = []
    for start, end, group in groups:
        kind = _kind(group)
        text = "\n".join(group).strip()
        for part_index, quote in enumerate(_split_quote(text), 1):
            if len(result) >= _MAX_CANDIDATES:
                return result
            suffix = f":part:{part_index}" if len(text) > _MAX_QUOTE_CHARS else ""
            result.append(
                {
                    "segment_id": f"mineru_md_{len(result) + 1:03d}",
                    "locator": f"markdown_line:{start}-{end}{suffix}",
                    "kind": kind,
                    "quote": quote,
                }
            )
    return result


def _kind(lines: list[str]) -> str:
    stripped = [line.strip() for line in lines if line.strip()]
    if stripped and all(line.startswith("|") for line in stripped):
        return "table"
    if stripped and all(line.startswith("$") or line.startswith("$$") for line in stripped):
        return "formula"
    if stripped and stripped[0].casefold().startswith(("figure", "fig.", "figure caption")):
        return "figure_caption"
    return "paragraph"


def _split_quote(value: str) -> list[str]:
    result: list[str] = []
    remaining = value.strip()
    while remaining:
        if len(remaining) <= _MAX_QUOTE_CHARS:
            result.append(remaining)
            break
        cut = remaining.rfind(" ", 0, _MAX_QUOTE_CHARS + 1)
        if cut < _MAX_QUOTE_CHARS // 2:
            cut = _MAX_QUOTE_CHARS
        result.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    return result


def _validate_completed_task(source_task: object, document_id: str) -> None:
    if not isinstance(source_task, dict) or source_task.get("document_id") != document_id or source_task.get("provider") != "mineru" or source_task.get("state") != "done":
        raise MinerULocalReviewError("local MinerU review requires a completed recorded MinerU task for this document")
    task_id = source_task.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip() or len(task_id) > 200:
        raise MinerULocalReviewError("local MinerU review task identity is invalid")


def _validate_pool(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise MinerULocalReviewError("local MinerU review pool has unsupported or missing fields")
    if payload.get("schema_version") != REVIEW_POOL_SCHEMA_VERSION or payload.get("trust_status") != "private_unreviewed_mineru_markdown_candidate_pool_not_source_map":
        raise MinerULocalReviewError("local MinerU review pool schema or trust status is invalid")
    if not all(isinstance(payload.get(key), str) and payload[key].strip() for key in ("mission_id", "document_id", "task_id_sha256", "source_markdown_sha256", "review_instructions")):
        raise MinerULocalReviewError("local MinerU review pool identity is invalid")
    if len(payload["task_id_sha256"]) != 64 or len(payload["source_markdown_sha256"]) != 64:
        raise MinerULocalReviewError("local MinerU review pool hashes are invalid")
    segments = payload.get("candidate_segments")
    if not isinstance(segments, list) or not 1 <= len(segments) <= _MAX_CANDIDATES:
        raise MinerULocalReviewError("local MinerU review pool candidates are invalid")
    identifiers: set[str] = set()
    for item in segments:
        if not isinstance(item, dict) or set(item) != _SEGMENT_FIELDS:
            raise MinerULocalReviewError("local MinerU review segment fields are invalid")
        if not all(isinstance(item.get(key), str) and item[key].strip() for key in _SEGMENT_FIELDS):
            raise MinerULocalReviewError("local MinerU review segment values are invalid")
        if item["segment_id"] in identifiers or item["kind"] not in _KINDS or len(item["quote"]) > _MAX_QUOTE_CHARS:
            raise MinerULocalReviewError("local MinerU review segment identity or boundary is invalid")
        identifiers.add(item["segment_id"])


def load_mineru_markdown_review_pool(
    *,
    path: Path,
    mission_id: str,
    document_id: str,
    source_task: object,
) -> dict[str, Any]:
    """Load a private candidate pool and bind it to this completed parse task."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MinerULocalReviewError("private MinerU review pool cannot be read") from error
    _validate_pool(payload)
    _validate_completed_task(source_task, document_id)
    if payload["mission_id"] != mission_id or payload["document_id"] != document_id:
        raise MinerULocalReviewError("private MinerU review pool belongs to a different mission or document")
    task_digest = hashlib.sha256(source_task["task_id"].encode("utf-8")).hexdigest()
    if payload["task_id_sha256"] != task_digest:
        raise MinerULocalReviewError("private MinerU review pool does not match the recorded parse task")
    return payload


def source_map_pool_review_template(pool: object) -> dict[str, Any]:
    """Create an excerpt-free selection template tied to every pool candidate."""
    _validate_pool(pool)
    return {
        "schema_version": SOURCE_MAP_POOL_REVIEW_TEMPLATE_SCHEMA_VERSION,
        "mission_id": pool["mission_id"],
        "document_id": pool["document_id"],
        "trust_status": "blank_human_source_map_pool_selection_template",
        "source_markdown_sha256": pool["source_markdown_sha256"],
        "task_id_sha256": pool["task_id_sha256"],
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


def write_source_map_pool_review_template(path: Path, template: object) -> Path:
    _validate_pool_review_template(template, allow_blank=True)
    if path.suffix.casefold() != ".json":
        raise MinerULocalReviewError("source-map pool review template must use a .json filename")
    if path.exists():
        raise MinerULocalReviewError("source-map pool review template already exists and will not be overwritten")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(template, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as error:
        raise MinerULocalReviewError("source-map pool review template cannot be written") from error
    return path


def source_map_selection_from_pool_review(*, pool: object, review: object) -> tuple[dict[str, Any], str]:
    """Resolve selected reviewer IDs to exact pool snippets after all hashes match."""
    _validate_pool(pool)
    _validate_pool_review_template(review, allow_blank=False)
    if any(review[key] != pool[key] for key in ("mission_id", "document_id", "source_markdown_sha256", "task_id_sha256")):
        raise MinerULocalReviewError("source-map pool review does not match the private candidate pool")
    candidates = {item["segment_id"]: item for item in pool["candidate_segments"]}
    selected = [item for item in review["segments"] if item["selected"]]
    if not 1 <= len(selected) <= 12:
        raise MinerULocalReviewError("source-map pool review must select 1 to 12 candidate segments")
    if {item["segment_id"] for item in review["segments"]} != set(candidates) or len(review["segments"]) != len(candidates):
        raise MinerULocalReviewError("source-map pool review must retain every candidate identifier")
    expected_hashes = {identifier: hashlib.sha256(item["quote"].encode("utf-8")).hexdigest() for identifier, item in candidates.items()}
    for item in review["segments"]:
        if item["quote_sha256"] != expected_hashes.get(item["segment_id"]):
            raise MinerULocalReviewError("source-map pool review candidate fingerprint does not match")
        if item["selected"] and not item["reason"].strip():
            raise MinerULocalReviewError("selected source-map pool segments require a human review reason")
    return (
        {
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
        },
        pool["source_markdown_sha256"],
    )


def _validate_pool_review_template(payload: object, *, allow_blank: bool) -> None:
    expected = {"schema_version", "mission_id", "document_id", "trust_status", "source_markdown_sha256", "task_id_sha256", "segments"}
    fields = {"segment_id", "quote_sha256", "selected", "reason"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise MinerULocalReviewError("source-map pool review has unsupported or missing fields")
    status = "blank_human_source_map_pool_selection_template" if allow_blank else "human_reviewed_source_map_pool_selection"
    if payload.get("schema_version") != SOURCE_MAP_POOL_REVIEW_TEMPLATE_SCHEMA_VERSION or payload.get("trust_status") != status:
        raise MinerULocalReviewError("source-map pool review schema or trust status is invalid")
    if not all(isinstance(payload.get(key), str) and payload[key].strip() for key in ("mission_id", "document_id", "source_markdown_sha256", "task_id_sha256")):
        raise MinerULocalReviewError("source-map pool review identity is invalid")
    if any(len(payload[key]) != 64 or any(char not in "0123456789abcdef" for char in payload[key]) for key in ("source_markdown_sha256", "task_id_sha256")):
        raise MinerULocalReviewError("source-map pool review fingerprints are invalid")
    rows = payload.get("segments")
    if not isinstance(rows, list) or not 1 <= len(rows) <= _MAX_CANDIDATES:
        raise MinerULocalReviewError("source-map pool review segments are invalid")
    seen: set[str] = set()
    for item in rows:
        if not isinstance(item, dict) or set(item) != fields:
            raise MinerULocalReviewError("source-map pool review segment fields are invalid")
        if not isinstance(item.get("segment_id"), str) or not item["segment_id"] or item["segment_id"] in seen:
            raise MinerULocalReviewError("source-map pool review segment identifiers are invalid")
        if not isinstance(item.get("quote_sha256"), str) or len(item["quote_sha256"]) != 64 or any(char not in "0123456789abcdef" for char in item["quote_sha256"]):
            raise MinerULocalReviewError("source-map pool review quote fingerprints are invalid")
        if not isinstance(item.get("selected"), bool) or not isinstance(item.get("reason"), str) or len(item["reason"]) > 500:
            raise MinerULocalReviewError("source-map pool review selection values are invalid")
        if allow_blank and (item["selected"] or item["reason"]):
            raise MinerULocalReviewError("blank source-map pool review template must not contain decisions")
        seen.add(item["segment_id"])
