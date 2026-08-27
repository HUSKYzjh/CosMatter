"""Count-only audit for a frozen-corpus human annotation file.

The audit accepts either the blank gold template or a fully reviewed relevance
gold file.  It never projects titles, DOI values, source text, locators, fact
content, annotations, or reviewer information into the output.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .corpus_preparation import CorpusPreparationError, load_corpus_manifest


SCHEMA_VERSION = "1.0"
_FIELDS = {"schema_version", "mission_id", "corpus_id", "trust_status", "annotation_instructions", "documents"}
_DOCUMENT_FIELDS = {
    "document_id", "retrieval_relevance", "evidence_annotations", "material_fact_annotations",
    "comparison_annotations", "gap_annotations",
}
_REVIEWED_STATUS = "human_reviewed_gold_standard_for_evaluation"
_BLANK_STATUS = "blank_human_annotation_template_not_evaluation_result"
_RELEVANCE = {"unreviewed", "relevant", "partially_relevant", "not_relevant"}


class AnnotationCoverageError(ValueError):
    """Raised when an annotation file cannot be safely audited."""


def annotation_coverage_audit(*, run_dir: Path, mission_id: str, annotation_path: Path) -> dict[str, Any]:
    """Return aggregate annotation coverage bound to the frozen manifest."""
    try:
        manifest = load_corpus_manifest(run_dir / "corpus_manifest.json", mission_id)
    except CorpusPreparationError as error:
        raise AnnotationCoverageError(str(error)) from error
    if manifest is None:
        raise AnnotationCoverageError("annotation coverage audit requires a frozen corpus manifest")
    try:
        payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise AnnotationCoverageError("annotation file does not exist") from error
    except json.JSONDecodeError as error:
        raise AnnotationCoverageError("annotation file is not valid JSON") from error
    _validate_annotation(payload, mission_id=mission_id, corpus_id=manifest["corpus_id"], document_ids={item["document_id"] for item in manifest["documents"]})
    assert isinstance(payload, dict)
    documents = payload["documents"]
    relevance_counts = {label: sum(item["retrieval_relevance"] == label for item in documents) for label in sorted(_RELEVANCE)}
    nonempty = {
        field: sum(bool(item[field]) for item in documents)
        for field in ("evidence_annotations", "material_fact_annotations", "comparison_annotations", "gap_annotations")
    }
    fully_reviewed = payload["trust_status"] == _REVIEWED_STATUS and relevance_counts["unreviewed"] == 0
    return {
        "schema_version": SCHEMA_VERSION,
        "trust_status": "aggregate_human_annotation_coverage_not_evaluation_result",
        "mission_id": mission_id,
        "corpus_id": manifest["corpus_id"],
        "frozen_document_count": len(documents),
        "annotation_file_status": payload["trust_status"],
        "relevance_counts": relevance_counts,
        "documents_with_evidence_annotations": nonempty["evidence_annotations"],
        "documents_with_material_fact_annotations": nonempty["material_fact_annotations"],
        "documents_with_comparison_annotations": nonempty["comparison_annotations"],
        "documents_with_gap_annotations": nonempty["gap_annotations"],
        "relevance_evaluation_gate": "ready_for_human_retrieval_evaluation" if fully_reviewed else "blocked_until_every_frozen_document_has_reviewed_relevance",
        "annotation_file_sha256": _sha256(payload),
        "boundary": "Counts only. This audit does not expose document metadata, labels by document, facts, source locators, quotations, or reviewer identity.",
    }


def write_annotation_coverage_audit(run_dir: Path, payload: dict[str, Any]) -> Path:
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise AnnotationCoverageError("annotation coverage payload is invalid")
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "human_annotation_coverage.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _validate_annotation(payload: object, *, mission_id: str, corpus_id: str, document_ids: set[str]) -> None:
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise AnnotationCoverageError("annotation file has unsupported or missing fields")
    if payload.get("schema_version") != "1.0" or payload.get("mission_id") != mission_id or payload.get("corpus_id") != corpus_id:
        raise AnnotationCoverageError("annotation file identity is invalid")
    if payload.get("trust_status") not in {_BLANK_STATUS, _REVIEWED_STATUS}:
        raise AnnotationCoverageError("annotation file trust status is invalid")
    if not isinstance(payload.get("annotation_instructions"), dict):
        raise AnnotationCoverageError("annotation instructions are invalid")
    documents = payload.get("documents")
    if not isinstance(documents, list) or len(documents) != len(document_ids):
        raise AnnotationCoverageError("annotation file must cover exactly the frozen corpus")
    observed: set[str] = set()
    reviewed = payload["trust_status"] == _REVIEWED_STATUS
    for item in documents:
        if not isinstance(item, dict) or set(item) != _DOCUMENT_FIELDS:
            raise AnnotationCoverageError("annotation document fields are invalid")
        document_id = item.get("document_id")
        relevance = item.get("retrieval_relevance")
        if not isinstance(document_id, str) or document_id not in document_ids or document_id in observed or relevance not in _RELEVANCE:
            raise AnnotationCoverageError("annotation document identity or relevance is invalid")
        if not all(isinstance(item[field], list) for field in _DOCUMENT_FIELDS - {"document_id", "retrieval_relevance"}):
            raise AnnotationCoverageError("annotation document entries must use arrays")
        if reviewed and relevance == "unreviewed":
            raise AnnotationCoverageError("reviewed annotation file cannot retain unreviewed relevance")
        if not reviewed and relevance != "unreviewed":
            raise AnnotationCoverageError("blank annotation template cannot contain relevance judgments")
        observed.add(document_id)
    if observed != document_ids:
        raise AnnotationCoverageError("annotation document IDs do not match frozen corpus")


def _sha256(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
