"""Aggregate audit for a human-frozen, authorization-bounded corpus.

The audit intentionally reports only counts and a manifest hash.  It neither
returns paper titles/DOIs nor opens local PDFs, so it can be retained as a
submission-facing provenance artifact while the detailed bibliography remains
inside the authorized local review boundary.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .corpus_preparation import CorpusPreparationError, load_corpus_manifest


SCHEMA_VERSION = "1.0"


class CorpusReadinessError(ValueError):
    """Raised when a requested frozen-corpus audit cannot be derived safely."""


def frozen_corpus_readiness(*, run_dir: Path, mission_id: str, expected_document_count: int = 90) -> dict[str, Any]:
    if not isinstance(expected_document_count, int) or not 1 <= expected_document_count <= 250:
        raise CorpusReadinessError("expected document count must be between 1 and 250")
    try:
        manifest = load_corpus_manifest(run_dir / "corpus_manifest.json", mission_id)
    except CorpusPreparationError as error:
        raise CorpusReadinessError(str(error)) from error
    if manifest is None:
        raise CorpusReadinessError("frozen corpus manifest is missing")
    documents = manifest["documents"]
    doi_count = sum(item["doi"] is not None for item in documents)
    identifiers = {item["document_id"] for item in documents}
    access_policies = {item["access_policy"] for item in documents}
    return {
        "schema_version": SCHEMA_VERSION,
        "trust_status": "aggregate_frozen_corpus_readiness_not_evaluation_result",
        "mission_id": mission_id,
        "corpus_id": manifest["corpus_id"],
        "expected_document_count": expected_document_count,
        "frozen_document_count": len(documents),
        "expected_count_matched": len(documents) == expected_document_count,
        "unique_document_id_count": len(identifiers),
        "document_id_uniqueness_valid": len(identifiers) == len(documents),
        "doi_present_count": doi_count,
        "doi_missing_count": len(documents) - doi_count,
        "authorized_access_policy_count": len(access_policies),
        "authorized_access_boundary_valid": access_policies == {"institutional_access_internal_review_only"},
        "manifest_sha256": _sha256(manifest),
        "evaluation_gate": (
            "ready_for_private_human_annotation" if len(documents) == expected_document_count
            else "blocked_until_human_reviewed_manifest_matches_declared_count"
        ),
        "boundary": "Counts only. This audit does not inspect PDFs, full text, annotations, paths, or metric results.",
    }


def write_frozen_corpus_readiness(run_dir: Path, payload: dict[str, Any]) -> Path:
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise CorpusReadinessError("frozen corpus readiness payload is invalid")
    path = run_dir / "frozen_corpus_readiness.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _sha256(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
