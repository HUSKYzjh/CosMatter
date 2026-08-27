"""Private per-document bibliographic-source review with a safe aggregate audit.

The frozen manifest establishes an authorized document boundary but intentionally
does not expose the original metadata-provider route.  This module keeps that
route in a reviewer-maintained private file and writes only aggregate coverage
facts to a run artifact.  It never opens PDFs or records titles, DOI values,
paths, full text, URLs, credentials, or reviewer identity.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .corpus_preparation import CorpusPreparationError, load_corpus_manifest


SCHEMA_VERSION = "1.0"
_FIELDS = {"schema_version", "mission_id", "corpus_id", "trust_status", "documents"}
_DOCUMENT_FIELDS = {"document_id", "bibliographic_source"}
_BLANK_STATUS = "blank_human_bibliographic_source_template_not_evaluation_result"
_REVIEWED_STATUS = "human_reviewed_bibliographic_source_registry"
_SOURCE_SAFE = re.compile(r"^[^\r\n]{1,180}$")


class BibliographicSourceCoverageError(ValueError):
    """Raised for a registry that cannot be tied to one frozen corpus."""


def bibliographic_source_template_from_manifest(manifest: object) -> dict[str, Any]:
    """Create blank private reviewer slots; no bibliographic metadata is copied."""
    mission_id, corpus_id, document_ids = _manifest_identity(manifest)
    return {
        "schema_version": SCHEMA_VERSION,
        "mission_id": mission_id,
        "corpus_id": corpus_id,
        "trust_status": _BLANK_STATUS,
        "documents": [
            {"document_id": document_id, "bibliographic_source": "unreviewed"}
            for document_id in sorted(document_ids)
        ],
    }


def bibliographic_source_coverage_audit(*, run_dir: Path, mission_id: str, registry_path: Path) -> dict[str, Any]:
    """Validate a private source registry and emit a count-only coverage audit."""
    try:
        manifest = load_corpus_manifest(run_dir / "corpus_manifest.json", mission_id)
    except CorpusPreparationError as error:
        raise BibliographicSourceCoverageError(str(error)) from error
    if manifest is None:
        raise BibliographicSourceCoverageError("bibliographic source coverage requires a frozen corpus manifest")
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise BibliographicSourceCoverageError("bibliographic source registry does not exist") from error
    except json.JSONDecodeError as error:
        raise BibliographicSourceCoverageError("bibliographic source registry is not valid JSON") from error
    document_ids = {item["document_id"] for item in manifest["documents"]}
    _validate_registry(payload, mission_id=mission_id, corpus_id=manifest["corpus_id"], document_ids=document_ids)
    assert isinstance(payload, dict)
    reviewed = payload["trust_status"] == _REVIEWED_STATUS
    sources = [item["bibliographic_source"] for item in payload["documents"]]
    reviewed_count = sum(source != "unreviewed" for source in sources)
    return {
        "schema_version": SCHEMA_VERSION,
        "trust_status": "aggregate_bibliographic_source_coverage_not_evaluation_result",
        "mission_id": mission_id,
        "corpus_id": manifest["corpus_id"],
        "frozen_document_count": len(document_ids),
        "documents_with_reviewed_bibliographic_source": reviewed_count,
        "distinct_bibliographic_source_count": len(set(sources) - {"unreviewed"}),
        "bibliographic_source_coverage_gate": (
            "ready_for_source_traceable_evaluation"
            if reviewed and reviewed_count == len(document_ids)
            else "blocked_until_every_frozen_document_has_human_reviewed_bibliographic_source"
        ),
        "registry_sha256": _sha256(payload),
        "boundary": "Counts and hashes only. This audit does not expose document metadata, bibliographic-source labels, PDFs, full text, paths, URLs, credentials, or reviewer identity.",
    }


def write_bibliographic_source_template(run_dir: Path, payload: object) -> Path:
    _validate_registry_template(payload)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "bibliographic_source_registry_template.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_bibliographic_source_coverage_audit(run_dir: Path, payload: object) -> Path:
    expected = {
        "schema_version", "trust_status", "mission_id", "corpus_id", "frozen_document_count",
        "documents_with_reviewed_bibliographic_source", "distinct_bibliographic_source_count",
        "bibliographic_source_coverage_gate", "registry_sha256", "boundary",
    }
    if not isinstance(payload, dict) or set(payload) != expected or payload.get("schema_version") != SCHEMA_VERSION:
        raise BibliographicSourceCoverageError("bibliographic source coverage audit payload is invalid")
    path = run_dir / "bibliographic_source_coverage.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_bibliographic_source_coverage(path: Path, *, mission_id: str, corpus_id: str, document_count: int) -> dict[str, Any]:
    """Load only a completed aggregate source-coverage audit."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BibliographicSourceCoverageError("bibliographic source coverage audit is missing or invalid") from error
    expected = {
        "schema_version", "trust_status", "mission_id", "corpus_id", "frozen_document_count",
        "documents_with_reviewed_bibliographic_source", "distinct_bibliographic_source_count",
        "bibliographic_source_coverage_gate", "registry_sha256", "boundary",
    }
    if (
        not isinstance(payload, dict) or set(payload) != expected
        or payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("trust_status") != "aggregate_bibliographic_source_coverage_not_evaluation_result"
        or payload.get("mission_id") != mission_id or payload.get("corpus_id") != corpus_id
        or payload.get("frozen_document_count") != document_count
        or payload.get("documents_with_reviewed_bibliographic_source") != document_count
        or not isinstance(payload.get("distinct_bibliographic_source_count"), int)
        or payload["distinct_bibliographic_source_count"] < 1
        or payload.get("bibliographic_source_coverage_gate") != "ready_for_source_traceable_evaluation"
        or not isinstance(payload.get("registry_sha256"), str) or len(payload["registry_sha256"]) != 64
    ):
        raise BibliographicSourceCoverageError("bibliographic source coverage audit is incomplete or mismatched")
    return payload


def _manifest_identity(manifest: object) -> tuple[str, str, set[str]]:
    if not isinstance(manifest, dict):
        raise BibliographicSourceCoverageError("frozen corpus manifest is invalid")
    mission_id, corpus_id, documents = manifest.get("mission_id"), manifest.get("corpus_id"), manifest.get("documents")
    if not isinstance(mission_id, str) or not mission_id or not isinstance(corpus_id, str) or not corpus_id or not isinstance(documents, list):
        raise BibliographicSourceCoverageError("frozen corpus manifest identity is invalid")
    ids = {item.get("document_id") for item in documents if isinstance(item, dict)}
    if not ids or not all(isinstance(value, str) and value for value in ids) or len(ids) != len(documents):
        raise BibliographicSourceCoverageError("frozen corpus manifest document identities are invalid")
    return mission_id, corpus_id, ids


def _validate_registry_template(payload: object) -> None:
    if not isinstance(payload, dict):
        raise BibliographicSourceCoverageError("bibliographic source template is invalid")
    document_ids = {item.get("document_id") for item in payload.get("documents", []) if isinstance(item, dict)}
    _validate_registry(payload, mission_id=payload.get("mission_id"), corpus_id=payload.get("corpus_id"), document_ids=document_ids)
    if payload["trust_status"] != _BLANK_STATUS:
        raise BibliographicSourceCoverageError("bibliographic source template must be blank")


def _validate_registry(payload: object, *, mission_id: object, corpus_id: object, document_ids: set[str]) -> None:
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise BibliographicSourceCoverageError("bibliographic source registry has unsupported or missing fields")
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("mission_id") != mission_id or payload.get("corpus_id") != corpus_id:
        raise BibliographicSourceCoverageError("bibliographic source registry identity is invalid")
    status = payload.get("trust_status")
    if status not in {_BLANK_STATUS, _REVIEWED_STATUS}:
        raise BibliographicSourceCoverageError("bibliographic source registry trust status is invalid")
    documents = payload.get("documents")
    if not isinstance(documents, list) or len(documents) != len(document_ids):
        raise BibliographicSourceCoverageError("bibliographic source registry must cover exactly the frozen corpus")
    seen: set[str] = set()
    for item in documents:
        if not isinstance(item, dict) or set(item) != _DOCUMENT_FIELDS:
            raise BibliographicSourceCoverageError("bibliographic source registry document fields are invalid")
        document_id, source = item.get("document_id"), item.get("bibliographic_source")
        if not isinstance(document_id, str) or document_id not in document_ids or document_id in seen:
            raise BibliographicSourceCoverageError("bibliographic source registry document identity is invalid")
        if not isinstance(source, str) or not _SOURCE_SAFE.fullmatch(source) or any(marker in source.casefold() for marker in ("api_key", "authorization", "bearer ", "c:\\users\\", "/home/")):
            raise BibliographicSourceCoverageError("bibliographic source registry source label is invalid")
        if status == _BLANK_STATUS and source != "unreviewed":
            raise BibliographicSourceCoverageError("blank bibliographic source registry must keep every source unreviewed")
        if status == _REVIEWED_STATUS and source == "unreviewed":
            raise BibliographicSourceCoverageError("reviewed bibliographic source registry cannot retain unreviewed entries")
        seen.add(document_id)
    if seen != document_ids:
        raise BibliographicSourceCoverageError("bibliographic source registry document IDs do not match frozen corpus")


def _sha256(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
