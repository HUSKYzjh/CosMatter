"""Safe local task ledger for authorized document-structure extraction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .mineru import MinerUTask
from .private_storage import private_root


SOURCE_PARSE_SCHEMA_VERSION = "1.0"
_TASK_FIELDS = {"document_id", "provider", "source_url_sha256", "task_id", "state", "model_version"}
_ARTIFACT_FIELDS = {"schema_version", "mission_id", "tasks"}


class SourceParseArtifactError(ValueError):
    """Raised when a local source-parse task ledger is invalid."""


def record_source_parse_task(
    run_dir: Path,
    *,
    mission_id: str,
    document_id: str,
    source_url: str,
    task: MinerUTask,
    model_version: str,
) -> Path:
    """Record metadata only; never persist remote URL, result link, or text."""
    if not mission_id.strip() or not document_id.strip() or not model_version.strip():
        raise SourceParseArtifactError("mission, document, and model identities must be nonempty")
    artifact = load_source_parse_tasks(run_dir / "source_parse_tasks.json", mission_id) or {
        "schema_version": SOURCE_PARSE_SCHEMA_VERSION,
        "mission_id": mission_id,
        "tasks": [],
    }
    task_digest = _task_digest(task.task_id)
    _write_private_task_id(run_dir, document_id, task.task_id, task_digest)
    task_item = {
        "document_id": document_id,
        "provider": "mineru",
        "source_url_sha256": hashlib.sha256(source_url.encode("utf-8")).hexdigest(),
        "task_id": task_digest,
        "state": task.state,
        "model_version": model_version,
    }
    artifact["tasks"] = [item for item in artifact["tasks"] if item["document_id"] != document_id]
    artifact["tasks"].append(task_item)
    return _write(run_dir, artifact)


def update_source_parse_task(run_dir: Path, *, mission_id: str, document_id: str, task: MinerUTask) -> Path:
    artifact = load_source_parse_tasks(run_dir / "source_parse_tasks.json", mission_id)
    if artifact is None:
        raise SourceParseArtifactError("source parse task ledger does not exist")
    for item in artifact["tasks"]:
        if item["document_id"] == document_id:
            if item["task_id"] != _task_digest(task.task_id):
                raise SourceParseArtifactError("MinerU task_id does not match the recorded document task")
            item["state"] = task.state
            return _write(run_dir, artifact)
    raise SourceParseArtifactError("document_id has no recorded MinerU task")


def load_source_parse_tasks(path: Path, mission_id: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SourceParseArtifactError("source_parse_tasks.json is invalid JSON") from error
    _validate(payload, mission_id)
    return payload


def task_for_document(run_dir: Path, *, mission_id: str, document_id: str) -> dict[str, Any]:
    artifact = load_source_parse_tasks(run_dir / "source_parse_tasks.json", mission_id)
    if artifact is None:
        raise SourceParseArtifactError("source parse task ledger does not exist")
    for item in artifact["tasks"]:
        if item["document_id"] == document_id:
            return item
    raise SourceParseArtifactError("document_id has no recorded MinerU task")


def private_task_id_for_document(run_dir: Path, *, mission_id: str, document_id: str) -> str:
    """Return one local-only MinerU task ID after checking its run hash."""
    task = task_for_document(run_dir, mission_id=mission_id, document_id=document_id)
    path = _private_task_id_path(run_dir, document_id)
    try:
        task_id = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise SourceParseArtifactError("private MinerU task identifier is unavailable") from error
    if not task_id or _task_digest(task_id) != task["task_id"]:
        raise SourceParseArtifactError("private MinerU task identifier does not match the run hash")
    return task_id


def migrate_legacy_source_parse_task_ids(run_dir: Path, *, mission_id: str) -> int:
    """Move legacy raw task IDs out of a run without making provider calls."""
    path = run_dir / "source_parse_tasks.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SourceParseArtifactError("source parse task ledger is invalid JSON") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != SOURCE_PARSE_SCHEMA_VERSION or payload.get("mission_id") != mission_id or not isinstance(payload.get("tasks"), list):
        raise SourceParseArtifactError("source parse task ledger cannot be migrated")
    migrated = 0
    for item in payload["tasks"]:
        if not isinstance(item, dict) or set(item) != _TASK_FIELDS or item.get("provider") != "mineru" or not isinstance(item.get("document_id"), str) or not item["document_id"].strip() or not isinstance(item.get("task_id"), str) or not item["task_id"].strip():
            raise SourceParseArtifactError("source parse task entry cannot be migrated")
        task_id = item["task_id"].strip()
        if _is_sha256(task_id):
            continue
        digest = _task_digest(task_id)
        _write_private_task_id(run_dir, item["document_id"], task_id, digest)
        item["task_id"] = digest
        migrated += 1
    _write(run_dir, payload)
    return migrated


def _write(run_dir: Path, payload: dict[str, Any]) -> Path:
    _validate(payload, payload["mission_id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "source_parse_tasks.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _task_digest(task_id: str) -> str:
    if not isinstance(task_id, str) or not task_id.strip() or len(task_id.strip()) > 200:
        raise SourceParseArtifactError("MinerU task_id is invalid")
    return hashlib.sha256(task_id.strip().encode("utf-8")).hexdigest()


def _private_task_id_path(run_dir: Path, document_id: str) -> Path:
    if not isinstance(document_id, str) or not document_id.strip():
        raise SourceParseArtifactError("document_id is invalid")
    identity = hashlib.sha256((run_dir.name + "\0" + document_id).encode("utf-8")).hexdigest()
    return private_root() / "mineru_task_ids" / f"{identity}.txt"


def _write_private_task_id(run_dir: Path, document_id: str, task_id: str, digest: str) -> None:
    if _task_digest(task_id) != digest:
        raise SourceParseArtifactError("private MinerU task identifier digest is invalid")
    path = _private_task_id_path(run_dir, document_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(task_id.strip(), encoding="utf-8")
    except OSError as error:
        raise SourceParseArtifactError("private MinerU task identifier cannot be written") from error


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _validate(payload: object, mission_id: str) -> None:
    if not isinstance(payload, dict) or set(payload) != _ARTIFACT_FIELDS:
        raise SourceParseArtifactError("source parse ledger has unsupported or missing fields")
    if payload.get("schema_version") != SOURCE_PARSE_SCHEMA_VERSION or payload.get("mission_id") != mission_id:
        raise SourceParseArtifactError("source parse ledger identity is invalid")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or len(tasks) > 12:
        raise SourceParseArtifactError("source parse task list is invalid")
    documents: set[str] = set()
    for item in tasks:
        if not isinstance(item, dict) or set(item) != _TASK_FIELDS:
            raise SourceParseArtifactError("source parse task fields are invalid")
        if item.get("provider") != "mineru" or item.get("state") not in {"pending", "running", "done", "failed"}:
            raise SourceParseArtifactError("source parse task provider or state is invalid")
        if not all(isinstance(item.get(key), str) and item[key].strip() for key in _TASK_FIELDS - {"provider", "state"}):
            raise SourceParseArtifactError("source parse task values are invalid")
        if not _is_sha256(item["source_url_sha256"]) or not _is_sha256(item["task_id"]):
            raise SourceParseArtifactError("source parse source or task hash is invalid")
        if item["document_id"] in documents:
            raise SourceParseArtifactError("source parse document IDs must be unique")
        documents.add(item["document_id"])
