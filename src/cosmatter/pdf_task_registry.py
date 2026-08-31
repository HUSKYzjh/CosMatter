"""Mission-scoped registry for private PDF parsing tasks.

The registry stores hashes and task metadata only.  Raw PDFs, Markdown, signed
URLs, credentials, and provider responses remain in private storage and never
enter the mission run directory.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REGISTRY_FILENAME = "pdf_intake_tasks.json"
LEGACY_FILENAME = "pdf_intake.json"
SCHEMA_VERSION = "1.0"
MAX_TASKS = 12
_TASK_STATES = {"waiting-file", "uploading", "pending", "converting", "running", "done", "failed"}
_DOI_STATUSES = {"pending", "resolved", "needs_human_doi", "human_confirmed"}
_REQUIRED_TASK_FIELDS = {"schema_version", "mission_id", "document_id", "file_name", "pdf_sha256", "byte_count", "consent", "batch_id", "state", "markdown_sha256", "doi", "doi_status"}
_OPTIONAL_TASK_FIELDS = {"candidate_document_id", "error"}


class PdfTaskRegistryError(ValueError):
    pass


def load_pdf_tasks(run_dir: Path, mission_id: str) -> list[dict[str, Any]]:
    """Load a registry, transparently projecting one legacy task when needed."""
    registry_path = run_dir / REGISTRY_FILENAME
    if registry_path.exists():
        try:
            payload = json.loads(registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PdfTaskRegistryError("private PDF task registry is invalid") from error
        _validate_registry(payload, mission_id)
        return [dict(item) for item in payload["tasks"]]
    legacy_path = run_dir / LEGACY_FILENAME
    if not legacy_path.exists():
        raise PdfTaskRegistryError("private PDF task is not available")
    try:
        legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PdfTaskRegistryError("legacy private PDF task is invalid") from error
    _validate_task(legacy, mission_id)
    return [legacy]


def task_for_pdf_document(run_dir: Path, mission_id: str, document_id: str | None = None) -> dict[str, Any]:
    tasks = load_pdf_tasks(run_dir, mission_id)
    if document_id is None:
        if len(tasks) != 1:
            raise PdfTaskRegistryError("document_id is required when multiple private PDF tasks exist")
        return dict(tasks[0])
    if not isinstance(document_id, str) or not document_id.strip():
        raise PdfTaskRegistryError("private PDF document_id is invalid")
    normalized = document_id.strip()
    for task in tasks:
        if task["document_id"] == normalized:
            return dict(task)
    raise PdfTaskRegistryError("private PDF task is not available for document_id")


def assert_pdf_task_slot(run_dir: Path, mission_id: str, candidate_document_id: str | None = None) -> None:
    """Reject a non-retry duplicate before any PDF is sent to a provider."""
    tasks = load_pdf_tasks(run_dir, mission_id) if (run_dir / REGISTRY_FILENAME).exists() or (run_dir / LEGACY_FILENAME).exists() else []
    if candidate_document_id:
        for task in tasks:
            if task.get("candidate_document_id") == candidate_document_id and task.get("state") != "failed":
                raise PdfTaskRegistryError("a non-failed private PDF task already exists for this screened candidate")
    elif len(tasks) >= MAX_TASKS:
        raise PdfTaskRegistryError(f"at most {MAX_TASKS} private PDF tasks may be registered for one mission")

def write_pdf_task(run_dir: Path, mission_id: str, task: dict[str, Any]) -> Path:
    """Insert or update exactly one private task without overwriting others."""
    _validate_task(task, mission_id)
    try:
        current = load_pdf_tasks(run_dir, mission_id)
    except PdfTaskRegistryError as error:
        if "not available" not in str(error):
            raise
        current = []
    document_id = task["document_id"]
    candidate_document_id = task.get("candidate_document_id")
    replacement = False
    next_tasks: list[dict[str, Any]] = []
    for existing in current:
        if existing["document_id"] == document_id:
            next_tasks.append(dict(task)); replacement = True; continue
        if candidate_document_id and existing.get("candidate_document_id") == candidate_document_id:
            if existing.get("state") != "failed":
                raise PdfTaskRegistryError("a non-failed private PDF task already exists for this screened candidate")
            # A new, explicitly authorised upload may replace only a failed parse.
            # The prior failure remains in the append-only run audit; raw content is
            # never retained in this registry.
            next_tasks.append(dict(task)); replacement = True; continue
        next_tasks.append(existing)
    if not replacement:
        next_tasks.append(dict(task))
    if len(next_tasks) > MAX_TASKS:
        raise PdfTaskRegistryError(f"at most {MAX_TASKS} private PDF tasks may be registered for one mission")
    payload = {"schema_version": SCHEMA_VERSION, "mission_id": mission_id, "tasks": next_tasks}
    _validate_registry(payload, mission_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / REGISTRY_FILENAME
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _validate_registry(payload: object, mission_id: str) -> None:
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "mission_id", "tasks"}:
        raise PdfTaskRegistryError("private PDF task registry fields are invalid")
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("mission_id") != mission_id:
        raise PdfTaskRegistryError("private PDF task registry identity is invalid")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= MAX_TASKS:
        raise PdfTaskRegistryError("private PDF task registry task list is invalid")
    seen_documents: set[str] = set(); seen_candidates: set[str] = set()
    for task in tasks:
        _validate_task(task, mission_id)
        document_id = task["document_id"]
        if document_id in seen_documents:
            raise PdfTaskRegistryError("private PDF document IDs must be unique")
        seen_documents.add(document_id)
        candidate = task.get("candidate_document_id")
        if candidate:
            if candidate in seen_candidates:
                raise PdfTaskRegistryError("screened candidate IDs must have at most one private PDF task")
            seen_candidates.add(candidate)


def _validate_task(task: object, mission_id: str) -> None:
    if not isinstance(task, dict) or not _REQUIRED_TASK_FIELDS.issubset(task) or set(task) - _REQUIRED_TASK_FIELDS - _OPTIONAL_TASK_FIELDS or task.get("schema_version") != SCHEMA_VERSION or task.get("mission_id") != mission_id:
        raise PdfTaskRegistryError("private PDF task is invalid")
    if not all(isinstance(task.get(key), str) and task[key].strip() for key in ("document_id", "file_name", "pdf_sha256", "batch_id")) or task.get("state") not in _TASK_STATES or task.get("doi_status") not in _DOI_STATUSES:
        raise PdfTaskRegistryError("private PDF task identity is invalid")
    if not isinstance(task.get("byte_count"), int) or task["byte_count"] <= 0 or task.get("consent") is not True:
        raise PdfTaskRegistryError("private PDF task metadata is invalid")
    candidate = task.get("candidate_document_id")
    if candidate is not None and (not isinstance(candidate, str) or not candidate.strip()):
        raise PdfTaskRegistryError("private PDF candidate identity is invalid")
    if task.get("markdown_sha256") is not None and not isinstance(task.get("markdown_sha256"), str):
        raise PdfTaskRegistryError("private PDF Markdown hash is invalid")
    if task.get("doi") is not None and not isinstance(task.get("doi"), str):
        raise PdfTaskRegistryError("private PDF DOI is invalid")
    if task.get("error") is not None and (not isinstance(task.get("error"), str) or len(task["error"]) > 300):
        raise PdfTaskRegistryError("private PDF task error is invalid")
