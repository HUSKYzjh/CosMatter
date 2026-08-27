"""Private human-review registry for PotentialScope literature source IDs.

PotentialScope freezes use short, stable source identifiers, while the selected
MinerU excerpts must remain in the private reviewer pool.  This module accepts
only completed human-selection templates that still validate against their
private pools and writes a quote-free registry.  The registry is a provenance
bridge, not a Source Map, EvidenceCard, material fact, or scientific claim.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .mineru_local_review import (
    MinerULocalReviewError,
    load_mineru_markdown_review_pool,
    source_map_selection_from_pool_review,
)


POTENTIAL_SCOPE_REVIEW_REGISTRY_SCHEMA_VERSION = "1.0"


class PotentialScopeReviewRegistryError(ValueError):
    """Raised when a private selection cannot produce a safe source registry."""


def build_reviewed_source_registry(*, mission_id: str, entries: object) -> dict[str, Any]:
    """Return a quote-free registry after validating selected private pools.

    ``entries`` must be internally constructed by :func:`load_reviewed_source`
    so callers cannot forge review counts or Markdown fingerprints.
    """
    if not isinstance(mission_id, str) or not mission_id.strip():
        raise PotentialScopeReviewRegistryError("mission_id is invalid")
    if not isinstance(entries, list) or not (1 <= len(entries) <= 200):
        raise PotentialScopeReviewRegistryError("registry requires one through two hundred reviewed entries")
    expected = {
        "source_id",
        "document_id",
        "source_markdown_sha256",
        "task_id_sha256",
        "selection_sha256",
        "selected_segment_count",
    }
    normalized: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    documents: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != expected:
            raise PotentialScopeReviewRegistryError("registry entry has unsupported or missing fields")
        source_id = entry.get("source_id")
        document_id = entry.get("document_id")
        if not _identifier(source_id) or not _identifier(document_id):
            raise PotentialScopeReviewRegistryError("registry identifier is invalid")
        if source_id in identifiers or document_id in documents:
            raise PotentialScopeReviewRegistryError("registry source and document identifiers must be unique")
        identifiers.add(source_id)
        documents.add(document_id)
        for field in ("source_markdown_sha256", "task_id_sha256", "selection_sha256"):
            if not _sha256(entry.get(field)):
                raise PotentialScopeReviewRegistryError(f"registry {field} is invalid")
        count = entry.get("selected_segment_count")
        if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 12:
            raise PotentialScopeReviewRegistryError("registry selected segment count is invalid")
        normalized.append(dict(entry))
    return {
        "schema_version": POTENTIAL_SCOPE_REVIEW_REGISTRY_SCHEMA_VERSION,
        "mission_id": mission_id.strip(),
        "trust_status": "human_reviewed_private_source_registry_not_evidence",
        "sources": sorted(normalized, key=lambda item: item["source_id"]),
        "review_boundary": (
            "This quote-free registry proves only that a human-reviewed private selection exists. "
            "It is not a Source Map, EvidenceCard, material fact, calculation result, or scientific conclusion."
        ),
    }


def load_reviewed_source(
    *,
    mission_id: str,
    document_id: str,
    source_task: object,
    pool_path: Path,
    review_path: Path,
) -> dict[str, Any]:
    """Validate one selected review and project only its safe provenance fields."""
    try:
        pool = load_mineru_markdown_review_pool(
            path=pool_path,
            mission_id=mission_id,
            document_id=document_id,
            source_task=source_task,
        )
        review = json.loads(review_path.read_text(encoding="utf-8"))
        selection, source_markdown_sha256 = source_map_selection_from_pool_review(pool=pool, review=review)
    except (OSError, json.JSONDecodeError, MinerULocalReviewError) as error:
        raise PotentialScopeReviewRegistryError("private reviewed source cannot be loaded or validated") from error
    selected_ids = [item["segment_id"] for item in selection["segments"]]
    selection_sha256 = _canonical_sha256(
        {
            "document_id": document_id,
            "source_markdown_sha256": source_markdown_sha256,
            "task_id_sha256": pool["task_id_sha256"],
            "selected_segment_ids": selected_ids,
            "reviewed_reasons": [
                item["reason"] for item in review["segments"] if item["selected"]
            ],
        }
    )
    return {
        "source_id": f"ps_src_{source_markdown_sha256[:16]}",
        "document_id": document_id,
        "source_markdown_sha256": source_markdown_sha256,
        "task_id_sha256": pool["task_id_sha256"],
        "selection_sha256": selection_sha256,
        "selected_segment_count": len(selected_ids),
    }


def write_reviewed_source_registry(path: Path, registry: object) -> Path:
    """Persist the quote-free registry once; never overwrite review history."""
    _validate_registry(registry)
    if path.suffix.casefold() != ".json":
        raise PotentialScopeReviewRegistryError("registry output must use a .json filename")
    if path.exists():
        raise PotentialScopeReviewRegistryError("registry output already exists and will not be overwritten")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as error:
        raise PotentialScopeReviewRegistryError("registry output cannot be written") from error
    return path


def _validate_registry(payload: object) -> None:
    expected = {"schema_version", "mission_id", "trust_status", "sources", "review_boundary"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise PotentialScopeReviewRegistryError("registry has unsupported or missing fields")
    if payload.get("schema_version") != POTENTIAL_SCOPE_REVIEW_REGISTRY_SCHEMA_VERSION:
        raise PotentialScopeReviewRegistryError("registry schema version is invalid")
    if payload.get("trust_status") != "human_reviewed_private_source_registry_not_evidence":
        raise PotentialScopeReviewRegistryError("registry trust status is invalid")
    if not isinstance(payload.get("review_boundary"), str) or not payload["review_boundary"].strip():
        raise PotentialScopeReviewRegistryError("registry review boundary is invalid")
    build_reviewed_source_registry(mission_id=payload.get("mission_id"), entries=payload.get("sources"))


def _identifier(value: object) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= 128 and all(
        char in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in value
    )


def _sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
