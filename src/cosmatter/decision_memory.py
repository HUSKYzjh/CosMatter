"""Project-local, human-editable operational memory (never scientific evidence).

Markdown files are the source of truth and a compact JSON index is rebuilt
from them.  The deliberately small schema permits only operational decisions:
authorizations, environment verification, failure recovery, preferences, and
todo items.  It rejects document/evidence terminology so this store cannot
become an alternate literature database or source for a research report.
"""

from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
import re
from typing import Any


MEMORY_SCHEMA_VERSION = "1.0"
INDEX_FILENAME = "decision_memory_index.json"
_CATEGORIES = {"authorization_decision", "environment_verification", "failure_recovery", "run_preference", "todo"}
_STATUSES = {"active", "resolved", "superseded"}
_SOURCES = {"human", "local_audit", "environment_check"}
_ID = re.compile(r"^[a-z][a-z0-9_-]{2,79}$")
_FORBIDDEN = re.compile(r"(?:evidence|scientific|claim|citation|doi|paper|article|pdf|mineru|source[ _-]?map|full[ _-]?text|quote|abstract|excerpt|literature)", re.IGNORECASE)
_HEADER_FIELDS = ("id", "category", "status", "source", "created_at", "expires_on", "title")
_INDEX_FIELDS = {"schema_version", "trust_status", "entry_count", "entries"}
_ENTRY_FIELDS = {"id", "category", "status", "source", "created_at", "expires_on", "title", "path"}


class DecisionMemoryError(ValueError):
    """Raised when operational memory would become unsafe or inconsistent."""


def write_decision_memory_entry(memory_dir: Path, payload: object) -> Path:
    """Write one validated human-readable operational note and rebuild its index."""
    entry = _validate_entry_payload(payload)
    memory_dir.mkdir(parents=True, exist_ok=True)
    path = memory_dir / f"{entry['id']}.md"
    if path.exists():
        raise DecisionMemoryError("decision memory entry already exists; edit its Markdown then rebuild")
    path.write_text(_render_markdown(entry), encoding="utf-8")
    rebuild_decision_memory_index(memory_dir)
    return path


def rebuild_decision_memory_index(memory_dir: Path) -> dict[str, Any]:
    """Rebuild the index exclusively from editable Markdown source files."""
    if not memory_dir.exists():
        entries: list[dict[str, str | None]] = []
    elif not memory_dir.is_dir():
        raise DecisionMemoryError("decision memory directory is invalid")
    else:
        entries = [_parse_markdown(path) for path in sorted(memory_dir.glob("*.md"))]
    identifiers = [str(item["id"]) for item in entries]
    if len(set(identifiers)) != len(identifiers):
        raise DecisionMemoryError("decision memory identifiers are duplicated")
    index = {
        "schema_version": MEMORY_SCHEMA_VERSION,
        "trust_status": "project_operational_memory_not_scientific_evidence_or_report_source",
        "entry_count": len(entries),
        "entries": entries,
    }
    validate_decision_memory_index(index)
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / INDEX_FILENAME).write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return index


def load_decision_memory_index(memory_dir: Path) -> dict[str, Any]:
    """Read a validated index without accessing operational note bodies."""
    path = memory_dir / INDEX_FILENAME
    if not path.exists():
        return rebuild_decision_memory_index(memory_dir)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DecisionMemoryError("decision memory index is invalid") from error
    validate_decision_memory_index(payload)
    return payload


def validate_decision_memory_index(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != _INDEX_FIELDS:
        raise DecisionMemoryError("decision memory index fields are invalid")
    if payload.get("schema_version") != MEMORY_SCHEMA_VERSION or payload.get("trust_status") != "project_operational_memory_not_scientific_evidence_or_report_source" or not isinstance(payload.get("entry_count"), int) or isinstance(payload["entry_count"], bool) or payload["entry_count"] < 0 or not isinstance(payload.get("entries"), list) or payload["entry_count"] != len(payload["entries"]):
        raise DecisionMemoryError("decision memory index identity is invalid")
    seen: set[str] = set()
    for entry in payload["entries"]:
        if not isinstance(entry, dict) or set(entry) != _ENTRY_FIELDS:
            raise DecisionMemoryError("decision memory index entry fields are invalid")
        _validate_metadata(entry)
        identifier = str(entry["id"])
        if identifier in seen:
            raise DecisionMemoryError("decision memory index identifiers are duplicated")
        seen.add(identifier)
        if entry.get("path") != f"{identifier}.md":
            raise DecisionMemoryError("decision memory index path is invalid")


def _validate_entry_payload(payload: object) -> dict[str, str | None]:
    if not isinstance(payload, dict) or set(payload) != set(_HEADER_FIELDS) | {"body"}:
        raise DecisionMemoryError("decision memory entry fields are invalid")
    entry = {key: payload[key] for key in _HEADER_FIELDS}
    _validate_metadata(entry)
    body = payload.get("body")
    if not isinstance(body, str) or not body.strip() or len(body.strip()) > 2_000 or _FORBIDDEN.search(body):
        raise DecisionMemoryError("decision memory body is invalid or contains scientific-content terminology")
    return {**entry, "body": body.strip()}


def _validate_metadata(entry: dict[str, object]) -> None:
    identifier, category, status, source, created_at, expires_on, title = (entry.get(key) for key in _HEADER_FIELDS)
    if not isinstance(identifier, str) or not _ID.fullmatch(identifier) or not isinstance(category, str) or category not in _CATEGORIES or not isinstance(status, str) or status not in _STATUSES or not isinstance(source, str) or source not in _SOURCES or not isinstance(created_at, str) or not _valid_datetime(created_at) or expires_on is not None and (not isinstance(expires_on, str) or not _valid_date(expires_on)) or not isinstance(title, str) or not title.strip() or len(title.strip()) > 200 or _FORBIDDEN.search(title):
        raise DecisionMemoryError("decision memory metadata is invalid or contains scientific-content terminology")


def _render_markdown(entry: dict[str, str | None]) -> str:
    header = "\n".join(f"{key}: {entry[key] if entry[key] is not None else ''}" for key in _HEADER_FIELDS)
    return f"---\n{header}\n---\n\n{entry['body']}\n"


def _parse_markdown(path: Path) -> dict[str, str | None]:
    if path.name != f"{path.stem}.md" or not _ID.fullmatch(path.stem):
        raise DecisionMemoryError("decision memory Markdown filename is invalid")
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise DecisionMemoryError("decision memory Markdown cannot be read") from error
    match = re.fullmatch(r"---\n(?P<header>(?:[^\n]*\n)+)---\n\n(?P<body>[\s\S]*?)\n?", raw)
    if match is None:
        raise DecisionMemoryError("decision memory Markdown frontmatter is invalid")
    pairs = [line.split(": ", 1) for line in match.group("header").splitlines()]
    if len(pairs) != len(_HEADER_FIELDS) or any(len(pair) != 2 for pair in pairs):
        raise DecisionMemoryError("decision memory Markdown frontmatter is invalid")
    metadata = {key: value for key, value in pairs}
    if tuple(metadata) != _HEADER_FIELDS or metadata["id"] != path.stem:
        raise DecisionMemoryError("decision memory Markdown frontmatter order is invalid")
    metadata["expires_on"] = metadata["expires_on"] or None
    _validate_metadata(metadata)
    body = match.group("body").strip()
    if not body or len(body) > 2_000 or _FORBIDDEN.search(body):
        raise DecisionMemoryError("decision memory Markdown body is invalid or contains scientific-content terminology")
    return {**metadata, "path": path.name}


def _valid_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _valid_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True
