"""Safe local task ledger for authorized document-structure extraction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .mineru import MinerUTask


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
    task_item = {
        "document_id": document_id,
        "provider": "mineru",
        "source_url_sha256": hashlib.sha256(source_url.encode("utf-8")).hexdigest(),
        "task_id": task.task_id,
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
            if item["task_id"] != task.task_id:
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


def _write(run_dir: Path, payload: dict[str, Any]) -> Path:
    _validate(payload, payload["mission_id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "source_parse_tasks.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


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
        if len(item["source_url_sha256"]) != 64 or any(character not in "0123456789abcdef" for character in item["source_url_sha256"]):
            raise SourceParseArtifactError("source parse source hash is invalid")
        if item["document_id"] in documents:
            raise SourceParseArtifactError("source parse document IDs must be unique")
        documents.add(item["document_id"])
