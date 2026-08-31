"""Human-reviewed, bounded source-map artifacts for completed parse tasks.

This module deliberately accepts a reviewer selection, not a MinerU result
archive.  Parser output may be extensive and must be inspected locally before
only the small, locatable excerpts needed for later evidence review are kept.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SOURCE_MAP_SCHEMA_VERSION = "1.0"
HUMAN_SOURCE_MAP_TRUST_STATUS = "human_reviewed_parser_selection"
AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS = "delegated_automated_trial_source_map_not_scientific_evidence"
_MAX_SEGMENTS = 12
_MAX_QUOTE_CHARS = 500
_INPUT_FIELDS = {"document_id", "segments"}
_INPUT_SEGMENT_FIELDS = {"segment_id", "locator", "kind", "quote"}
_MAP_FIELDS = {"schema_version", "mission_id", "trust_status", "document_id", "provider", "task_id_sha256", "segments"}
_POOL_BOUND_MAP_FIELDS = _MAP_FIELDS | {"source_markdown_sha256"}
_MAP_SEGMENT_FIELDS = {"segment_id", "locator", "kind", "quote", "quote_sha256"}
_KINDS = {"paragraph", "table", "formula", "figure_caption"}


class SourceMapError(ValueError):
    """Raised when a proposed reviewer selection exceeds the bounded contract."""


def source_map_from_review(
    *,
    mission_id: str,
    document_id: str,
    source_task: dict[str, Any],
    selection: object,
    trust_status: str = HUMAN_SOURCE_MAP_TRUST_STATUS,
) -> dict[str, Any]:
    """Create a review-only source map after a completed recorded task.

    The caller must separately prove candidate authorization.  This function
    requires the parse ledger task to be done, then keeps at most twelve short
    reviewer-selected snippets with stable locators.
    """
    if not isinstance(mission_id, str) or not mission_id.strip() or not isinstance(document_id, str) or not document_id.strip():
        raise SourceMapError("mission_id and document_id must be nonempty")
    _validate_completed_task(source_task, document_id)
    if trust_status not in {HUMAN_SOURCE_MAP_TRUST_STATUS, AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS}:
        raise SourceMapError("source map trust status is invalid")
    selected_segments = _segments_from_selection(selection, document_id)
    return {
        "schema_version": SOURCE_MAP_SCHEMA_VERSION,
        "mission_id": mission_id,
        "trust_status": trust_status,
        "document_id": document_id,
        "provider": "mineru",
        "task_id_sha256": _task_digest(source_task["task_id"]),
        "segments": selected_segments,
    }



def source_map_from_pool_review(
    *,
    mission_id: str,
    document_id: str,
    source_task: dict[str, Any],
    selection: object,
    source_markdown_sha256: str,
    trust_status: str = HUMAN_SOURCE_MAP_TRUST_STATUS,
) -> dict[str, Any]:
    """Create a Source Map whose selected snippets were resolved from a private pool."""
    if not isinstance(source_markdown_sha256, str) or len(source_markdown_sha256) != 64 or any(char not in "0123456789abcdef" for char in source_markdown_sha256):
        raise SourceMapError("private review-pool Markdown fingerprint is invalid")
    result = source_map_from_review(
        mission_id=mission_id,
        document_id=document_id,
        source_task=source_task,
        selection=selection,
        trust_status=trust_status,
    )
    result["schema_version"] = "1.1"
    result["source_markdown_sha256"] = source_markdown_sha256
    _validate_source_map(result)
    return result


def source_map_document_path(run_dir: Path, document_id: str) -> Path:
    if not isinstance(document_id, str) or not document_id.strip():
        raise SourceMapError("document_id must be nonempty")
    return run_dir / "source_maps" / f"{hashlib.sha256(document_id.encode('utf-8')).hexdigest()}.json"


def write_source_map_for_document(run_dir: Path, source_map: dict[str, Any]) -> Path:
    """Persist a document-scoped map without replacing maps for earlier papers."""
    _validate_source_map(source_map)
    path = source_map_document_path(run_dir, source_map["document_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(source_map, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    legacy = run_dir / "source_map.json"
    if not legacy.exists():
        legacy.write_text(json.dumps(source_map, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_source_map_for_document(run_dir: Path, mission_id: str, document_id: str | None) -> dict[str, Any] | None:
    """Load a document-scoped map; keep the legacy single-map path readable."""
    if document_id is None:
        return load_source_map(run_dir / "source_map.json", mission_id)
    path = source_map_document_path(run_dir, document_id)
    if path.exists():
        return load_source_map(path, mission_id)
    legacy = load_source_map(run_dir / "source_map.json", mission_id)
    if legacy is not None and legacy["document_id"] == document_id:
        return legacy
    return None


def iter_source_maps(run_dir: Path, mission_id: str) -> tuple[dict[str, Any], ...]:
    """Return all document-scoped maps, deduplicated with any legacy artifact."""
    maps: dict[str, dict[str, Any]] = {}
    legacy = load_source_map(run_dir / "source_map.json", mission_id)
    if legacy is not None:
        maps[legacy["document_id"]] = legacy
    directory = run_dir / "source_maps"
    if directory.exists():
        for path in sorted(directory.glob("*.json")):
            item = load_source_map(path, mission_id)
            if item is not None:
                maps[item["document_id"]] = item
    return tuple(maps[key] for key in sorted(maps))

def write_source_map(run_dir: Path, source_map: dict[str, Any]) -> Path:
    _validate_source_map(source_map)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "source_map.json"
    path.write_text(json.dumps(source_map, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_source_map(path: Path, mission_id: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SourceMapError("source_map.json is invalid JSON") from error
    _validate_source_map(payload)
    if payload["mission_id"] != mission_id:
        raise SourceMapError("source map does not belong to mission")
    return payload


def _validate_completed_task(source_task: object, document_id: str) -> None:
    if not isinstance(source_task, dict):
        raise SourceMapError("source parse task must be an object")
    if source_task.get("document_id") != document_id or source_task.get("provider") != "mineru" or source_task.get("state") != "done":
        raise SourceMapError("source map requires a completed MinerU task for the same document")
    task_id = source_task.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip() or len(task_id) > 200:
        raise SourceMapError("source parse task identity is invalid")


def _task_digest(task_id: str) -> str:
    if len(task_id) == 64 and all(character in "0123456789abcdef" for character in task_id):
        return task_id
    return hashlib.sha256(task_id.encode("utf-8")).hexdigest()


def _segments_from_selection(selection: object, document_id: str) -> list[dict[str, str]]:
    if not isinstance(selection, dict) or set(selection) != _INPUT_FIELDS or selection.get("document_id") != document_id:
        raise SourceMapError("review selection fields or document identity are invalid")
    raw_segments = selection.get("segments")
    if not isinstance(raw_segments, list) or not 1 <= len(raw_segments) <= _MAX_SEGMENTS:
        raise SourceMapError("review selection must contain 1 to 12 segments")
    result: list[dict[str, str]] = []
    identifiers: set[str] = set()
    for raw in raw_segments:
        if not isinstance(raw, dict) or set(raw) != _INPUT_SEGMENT_FIELDS:
            raise SourceMapError("review segment has unsupported or missing fields")
        segment_id = raw.get("segment_id")
        locator = raw.get("locator")
        kind = raw.get("kind")
        quote = raw.get("quote")
        if not all(isinstance(value, str) and value.strip() for value in (segment_id, locator, kind, quote)):
            raise SourceMapError("review segment values must be nonempty strings")
        if segment_id in identifiers or len(segment_id) > 120 or len(locator) > 240 or len(quote) > _MAX_QUOTE_CHARS or kind not in _KINDS:
            raise SourceMapError("review segment identifier, locator, kind, or quote is invalid")
        identifiers.add(segment_id)
        result.append(
            {
                "segment_id": segment_id,
                "locator": locator,
                "kind": kind,
                "quote": quote,
                "quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
            }
        )
    return result


def _validate_source_map(payload: object) -> None:
    if not isinstance(payload, dict):
        raise SourceMapError("source map has unsupported or missing fields")
    schema_version = payload.get("schema_version")
    expected_fields = _MAP_FIELDS if schema_version == SOURCE_MAP_SCHEMA_VERSION else _POOL_BOUND_MAP_FIELDS if schema_version == "1.1" else None
    if expected_fields is None or set(payload) != expected_fields:
        raise SourceMapError("source map has unsupported or missing fields")
    if payload.get("trust_status") not in {HUMAN_SOURCE_MAP_TRUST_STATUS, AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS}:
        raise SourceMapError("source map schema or trust status is invalid")
    if schema_version == "1.1":
        fingerprint = payload.get("source_markdown_sha256")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
            raise SourceMapError("source map private review-pool fingerprint is invalid")
    if payload.get("provider") != "mineru" or not all(isinstance(payload.get(key), str) and payload[key].strip() for key in ("mission_id", "document_id", "task_id_sha256")):
        raise SourceMapError("source map identity is invalid")
    if len(payload["task_id_sha256"]) != 64 or any(character not in "0123456789abcdef" for character in payload["task_id_sha256"]):
        raise SourceMapError("source map task fingerprint is invalid")
    segments = payload.get("segments")
    if not isinstance(segments, list) or not 1 <= len(segments) <= _MAX_SEGMENTS:
        raise SourceMapError("source map segments are invalid")
    identifiers: set[str] = set()
    for segment in segments:
        if not isinstance(segment, dict) or set(segment) != _MAP_SEGMENT_FIELDS:
            raise SourceMapError("source map segment fields are invalid")
        if not all(isinstance(segment.get(key), str) and segment[key].strip() for key in _MAP_SEGMENT_FIELDS):
            raise SourceMapError("source map segment values are invalid")
        if segment["segment_id"] in identifiers or segment["kind"] not in _KINDS or len(segment["quote"]) > _MAX_QUOTE_CHARS:
            raise SourceMapError("source map segment identity, kind, or quote is invalid")
        if hashlib.sha256(segment["quote"].encode("utf-8")).hexdigest() != segment["quote_sha256"]:
            raise SourceMapError("source map quote fingerprint does not match")
        identifiers.add(segment["segment_id"])
