"""Human-reviewed, bounded source-map artifacts for completed parse tasks.

This module deliberately accepts a reviewer selection, not a MinerU result
archive.  Parser output may be extensive and must be inspected locally before
only the small, locatable excerpts needed for later evidence review are kept.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .audit import FlightRecorder
from .models import MissionState
from .operation_parameter_contracts import SCIVERSE_CONTENT_LIMIT_MAX, SCIVERSE_CONTENT_LIMIT_MIN


SOURCE_MAP_SCHEMA_VERSION = "1.0"
HUMAN_SOURCE_MAP_TRUST_STATUS = "human_reviewed_parser_selection"
AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS = "delegated_automated_trial_source_map_not_scientific_evidence"
_MAX_SEGMENTS = 12
_MAX_QUOTE_CHARS = 500
_INPUT_FIELDS = {"document_id", "segments"}
_INPUT_SEGMENT_FIELDS = {"segment_id", "locator", "kind", "quote"}
_MAP_FIELDS = {"schema_version", "mission_id", "trust_status", "document_id", "provider", "task_id_sha256", "segments"}
_POOL_BOUND_MAP_FIELDS = _MAP_FIELDS | {"source_markdown_sha256"}
_SCIVERSE_CONTEXT_MAP_FIELDS = {
    "schema_version", "mission_id", "trust_status", "document_id", "provider",
    "candidate_fingerprint", "receipt_id", "content_sha256", "content_offset",
    "content_limit", "segments",
}
_MAP_SEGMENT_FIELDS = {"segment_id", "locator", "kind", "quote", "quote_sha256"}
_KINDS = {"paragraph", "table", "formula", "figure_caption"}


class SourceMapError(ValueError):
    """Raised when a proposed reviewer selection exceeds the bounded contract."""


class SourceMapConflictError(SourceMapError):
    """An existing review cannot be replaced by this recording operation."""


class SourceMapAuditError(SourceMapError):
    """A confirmed review could not be verified against the run's audit log."""


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


def source_map_from_sciverse_context_review(
    *,
    mission_id: str,
    document_id: str,
    selection: object,
    candidate_fingerprint: str,
    receipt_id: str,
    content_sha256: str,
    content_offset: int,
    content_limit: int,
    trust_status: str = HUMAN_SOURCE_MAP_TRUST_STATUS,
) -> dict[str, Any]:
    """Create a Source Map from a current hash-bound Sciverse context review."""
    if not isinstance(mission_id, str) or not mission_id.strip() or not isinstance(document_id, str) or not document_id.strip():
        raise SourceMapError("mission_id and document_id must be nonempty")
    if trust_status not in {HUMAN_SOURCE_MAP_TRUST_STATUS, AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS}:
        raise SourceMapError("source map trust status is invalid")
    if not _sha256(candidate_fingerprint) or not _sha256(content_sha256):
        raise SourceMapError("Sciverse Source Map content binding is invalid")
    if not isinstance(receipt_id, str) or not receipt_id.startswith("receipt_") or len(receipt_id) > 200:
        raise SourceMapError("Sciverse Source Map receipt identity is invalid")
    if not isinstance(content_offset, int) or isinstance(content_offset, bool) or content_offset < 0:
        raise SourceMapError("Sciverse Source Map offset is invalid")
    if not isinstance(content_limit, int) or isinstance(content_limit, bool) or not SCIVERSE_CONTENT_LIMIT_MIN <= content_limit <= SCIVERSE_CONTENT_LIMIT_MAX:
        raise SourceMapError("Sciverse Source Map limit is invalid")
    result = {
        "schema_version": "1.2",
        "mission_id": mission_id.strip(),
        "trust_status": trust_status,
        "document_id": document_id.strip(),
        "provider": "sciverse",
        "candidate_fingerprint": candidate_fingerprint,
        "receipt_id": receipt_id,
        "content_sha256": content_sha256,
        "content_offset": content_offset,
        "content_limit": content_limit,
        "segments": _segments_from_selection(selection, document_id),
    }
    _validate_source_map(result)
    return result


def source_map_document_path(run_dir: Path, document_id: str) -> Path:
    if not isinstance(document_id, str) or not document_id.strip():
        raise SourceMapError("document_id must be nonempty")
    return run_dir / "source_maps" / f"{hashlib.sha256(document_id.encode('utf-8')).hexdigest()}.json"


def write_source_map_for_document(run_dir: Path, source_map: dict[str, Any]) -> Path:
    """Return the document-scoped path for an immutable review."""
    path, _ = record_source_map_for_document(run_dir, source_map)
    return path


def record_source_map_for_document(run_dir: Path, source_map: dict[str, Any]) -> tuple[Path, bool]:
    """Return the document path and whether this call first recorded its review."""
    return _store_source_map(run_dir, source_map, legacy_only=False)


def record_confirmed_source_map(run_dir: Path, source_map: dict[str, Any], *, access_mode: str | None = None) -> Path:
    """Persist an explicit review and finish its audit event on an identical retry."""
    _validate_source_map(source_map)
    payload = {"document_id": source_map["document_id"], "segment_count": len(source_map["segments"]),
               "trust_status": source_map["trust_status"]}
    delegated = source_map["trust_status"] == AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS
    actor = "delegated_automated_trial_reviewer" if delegated else "source_reviewer"
    if source_map["provider"] == "sciverse":
        event_type = "delegated_automated_trial_sciverse_source_map_recorded" if delegated else "human_reviewed_sciverse_source_map_recorded"
    else:
        event_type = "delegated_automated_trial_source_map_recorded" if delegated else "source_map_reviewed"
    if access_mode is not None:
        if (access_mode not in {"screened_candidate", "human_authorized_private_pdf"} or delegated
                or source_map["provider"] != "mineru"):
            raise SourceMapError("a private Markdown review requires a human-confirmed MinerU selection")
        actor = "human_source_reviewer"
        payload.update(access_mode=access_mode, trust_status="human_reviewed_parser_selection_not_evidence_card")
    event = {"event_type": event_type, "actor": actor, "payload": payload}
    bound = json.dumps([run_dir.name, source_map, event], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["source_map_review_id"] = hashlib.sha256(bound.encode("utf-8")).hexdigest()
    path, _ = _store_source_map(run_dir, source_map, legacy_only=False, event=event)
    return path


@contextmanager
def _source_map_write_lock(run_dir: Path) -> Iterator[None]:
    # Both filenames belong to one review. A stable per-run lock coordinates
    # independent CLI processes, HTTP servers and the legacy writer.
    with (run_dir / ".source-map.lock").open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield


def _publish_json(path: Path, payload: dict[str, Any]) -> None:
    stream = tempfile.NamedTemporaryFile(dir=path.parent, mode="w", encoding="utf-8", delete=False)
    temporary = Path(stream.name)
    try:
        with stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _review_log_state(run_dir: Path, event: dict[str, Any]) -> tuple[bool, bool]:
    """Check all historical rows and whether appending needs a final line separator."""
    try:
        stream = (run_dir / "events.jsonl").open("rb")
    except FileNotFoundError:
        return False, False
    found = False
    needs_newline = False
    with stream:
        for number, raw in enumerate(stream, 1):
            try:
                row = json.loads(raw)
                if (not isinstance(row, dict) or not isinstance(row.get("event_type"), str)
                        or not isinstance(row.get("payload"), dict)):
                    raise ValueError
            except (UnicodeDecodeError, ValueError) as error:
                raise SourceMapAuditError(f"events.jsonl contains an invalid or incomplete event on line {number}") from error
            needs_newline = not raw.endswith(b"\n")
            if row["payload"].get("source_map_review_id") == event["payload"]["source_map_review_id"]:
                if (found or row.get("run_id") != run_dir.name or row.get("state") != MissionState.EXTRACT.value
                        or any(row.get(key) != value for key, value in event.items())):
                    raise SourceMapAuditError("events.jsonl contains conflicting records for this Source Map review")
                found = True
    return found, needs_newline


def _store_source_map(run_dir: Path, source_map: dict[str, Any], *, legacy_only: bool,
                      event: dict[str, Any] | None = None) -> tuple[Path, bool]:
    _validate_source_map(source_map)
    run_dir.mkdir(parents=True, exist_ok=True)
    scoped_path = source_map_document_path(run_dir, source_map["document_id"])
    legacy_path = run_dir / "source_map.json"
    with _source_map_write_lock(run_dir):
        try:
            scoped = _read_source_map(scoped_path)
            legacy = _read_source_map(legacy_path)
        except (SourceMapError, UnicodeDecodeError) as error:
            raise SourceMapConflictError("an existing Source Map could not be validated and was preserved") from error
        same_document = legacy is not None and legacy["document_id"] == source_map["document_id"]
        if legacy is not None and legacy["mission_id"] != source_map["mission_id"]:
            raise SourceMapConflictError("Source Map conflict with the stored mission identity")
        if ((scoped is not None and scoped != source_map)
                or (legacy is not None and (legacy_only or same_document) and legacy != source_map)):
            raise SourceMapConflictError("this document already has a different reviewed Source Map")
        created = scoped is None and not same_document
        pending_path = scoped_path.with_suffix(".audit-pending")
        try:
            pending = json.loads(pending_path.read_bytes())
            if not isinstance(pending, dict) or set(pending) != {"review_id"} or not _sha256(pending["review_id"]):
                raise ValueError
        except FileNotFoundError:
            pending = None
        except (UnicodeDecodeError, ValueError) as error:
            raise SourceMapAuditError("the pending Source Map review record is invalid") from error
        marker = {"review_id": event["payload"]["source_map_review_id"]} if event else None
        if pending is not None and pending != marker:
            raise SourceMapConflictError("a different Source Map confirmation is pending for this document")
        logged, needs_newline = _review_log_state(run_dir, event) if event is not None else (False, False)
        if marker is not None and created and pending is None:
            scoped_path.parent.mkdir(parents=True, exist_ok=True)
            _publish_json(pending_path, marker)
            pending = marker
        if legacy is None:
            _publish_json(legacy_path, source_map)
        if not legacy_only and scoped is None:
            scoped_path.parent.mkdir(parents=True, exist_ok=True)
            _publish_json(scoped_path, source_map)
        if event is not None and pending is not None:
            if not logged:
                try:
                    if needs_newline:
                        with (run_dir / "events.jsonl").open("ab") as stream:
                            stream.write(b"\n")
                    FlightRecorder(run_dir.parent, run_dir.name).record(state=MissionState.EXTRACT, **event)
                except OSError as error:
                    raise SourceMapAuditError("could not write the Source Map review event. Retry the same confirmation.") from error
            pending_path.unlink()
        return (legacy_path if legacy_only else scoped_path), created


def load_source_map_for_document(run_dir: Path, mission_id: str, document_id: str | None) -> dict[str, Any] | None:
    """Load a document-scoped map; keep the legacy single-map path readable."""
    if document_id is None:
        return load_source_map(run_dir / "source_map.json", mission_id)
    path = source_map_document_path(run_dir, document_id)
    if path.exists():
        item = load_source_map(path, mission_id)
        if item is not None and item["document_id"] != document_id:
            raise SourceMapError("stored Source Map document identity does not match its path")
        return item
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
                if path.name != source_map_document_path(run_dir, item["document_id"]).name:
                    raise SourceMapError("stored Source Map document identity does not match its path")
                maps[item["document_id"]] = item
    return tuple(maps[key] for key in sorted(maps))

def write_source_map(run_dir: Path, source_map: dict[str, Any]) -> Path:
    path, _ = _store_source_map(run_dir, source_map, legacy_only=True)
    return path


def load_source_map(path: Path, mission_id: str) -> dict[str, Any] | None:
    payload = _read_source_map(path)
    if payload is None:
        return None
    if payload["mission_id"] != mission_id:
        raise SourceMapError("source map does not belong to mission")
    if path.name == "source_map.json":
        scoped = source_map_document_path(path.parent, payload["document_id"])
    elif path.parent.name == "source_maps":
        scoped = source_map_document_path(path.parent.parent, payload["document_id"])
        if scoped != path:
            raise SourceMapError("stored Source Map document identity does not match its path")
    else:
        return payload
    # The writer publishes this marker before either map and removes it only
    # after the audit event commits. Check it after reading the complete file.
    try:
        scoped.with_suffix(".audit-pending").lstat()
    except FileNotFoundError:
        return payload
    return None


def _read_source_map(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as error:
        raise SourceMapError("source_map.json is invalid JSON") from error
    _validate_source_map(payload)
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
    expected_fields = (
        _MAP_FIELDS if schema_version == SOURCE_MAP_SCHEMA_VERSION
        else _POOL_BOUND_MAP_FIELDS if schema_version == "1.1"
        else _SCIVERSE_CONTEXT_MAP_FIELDS if schema_version == "1.2"
        else None
    )
    if expected_fields is None or set(payload) != expected_fields:
        raise SourceMapError("source map has unsupported or missing fields")
    if payload.get("trust_status") not in {HUMAN_SOURCE_MAP_TRUST_STATUS, AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS}:
        raise SourceMapError("source map schema or trust status is invalid")
    if schema_version == "1.1":
        fingerprint = payload.get("source_markdown_sha256")
        if not _sha256(fingerprint):
            raise SourceMapError("source map private review-pool fingerprint is invalid")
    if schema_version == "1.2":
        if (
            payload.get("provider") != "sciverse"
            or not all(isinstance(payload.get(key), str) and payload[key].strip() for key in ("mission_id", "document_id", "receipt_id"))
            or not payload["receipt_id"].startswith("receipt_")
            or not _sha256(payload.get("candidate_fingerprint"))
            or not _sha256(payload.get("content_sha256"))
            or not isinstance(payload.get("content_offset"), int)
            or isinstance(payload["content_offset"], bool)
            or payload["content_offset"] < 0
            or not isinstance(payload.get("content_limit"), int)
            or isinstance(payload["content_limit"], bool)
            or not SCIVERSE_CONTENT_LIMIT_MIN <= payload["content_limit"] <= SCIVERSE_CONTENT_LIMIT_MAX
        ):
            raise SourceMapError("Sciverse source map identity or content binding is invalid")
    else:
        if payload.get("provider") != "mineru" or not all(isinstance(payload.get(key), str) and payload[key].strip() for key in ("mission_id", "document_id", "task_id_sha256")):
            raise SourceMapError("source map identity is invalid")
        if not _sha256(payload["task_id_sha256"]):
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


def _sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)
