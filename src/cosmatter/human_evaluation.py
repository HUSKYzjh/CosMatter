"""Evaluation of a reviewed real-corpus retrieval run against a human gold file."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .models import normalized_doi_or_none


HUMAN_GOLD_SCHEMA_VERSION = "1.0"
_EVALUATION_SCHEMA_VERSION = "1.1"
_GOLD_FIELDS = {"schema_version", "mission_id", "corpus_id", "trust_status", "annotation_instructions", "documents"}
_GOLD_INSTRUCTION_FIELDS = {
    "retrieval_relevance",
    "evidence_annotations",
    "material_fact_annotations",
    "comparison_annotations",
    "gap_annotations",
}
_GOLD_DOCUMENT_FIELDS = {
    "document_id",
    "retrieval_relevance",
    "evidence_annotations",
    "material_fact_annotations",
    "comparison_annotations",
    "gap_annotations",
}
_ALLOWED_RELEVANCE = {"relevant", "partially_relevant", "not_relevant"}


class HumanEvaluationError(ValueError):
    """Raised when a purported gold standard is incomplete or not human reviewed."""


def load_reviewed_retrieval_gold(
    path: Path,
    *,
    mission_id: str,
    corpus_id: str,
    corpus_document_ids: set[str],
) -> dict[str, str]:
    """Load only a fully reviewed relevance layer from a human gold file."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise HumanEvaluationError("reviewed human gold file does not exist") from error
    except json.JSONDecodeError as error:
        raise HumanEvaluationError("reviewed human gold file is not valid JSON") from error
    if not isinstance(payload, dict) or set(payload) != _GOLD_FIELDS:
        raise HumanEvaluationError("reviewed human gold has unsupported or missing fields")
    if (
        payload.get("schema_version") != HUMAN_GOLD_SCHEMA_VERSION
        or payload.get("mission_id") != mission_id
        or payload.get("corpus_id") != corpus_id
        or payload.get("trust_status") != "human_reviewed_gold_standard_for_evaluation"
    ):
        raise HumanEvaluationError("reviewed human gold identity or trust status is invalid")
    instructions = payload.get("annotation_instructions")
    if (
        not isinstance(instructions, dict)
        or set(instructions) != _GOLD_INSTRUCTION_FIELDS
        or not all(isinstance(value, str) and value.strip() and len(value) <= 1_000 for value in instructions.values())
    ):
        raise HumanEvaluationError("reviewed human gold annotation instructions are invalid")
    documents = payload.get("documents")
    if not isinstance(documents, list) or len(documents) != len(corpus_document_ids):
        raise HumanEvaluationError("reviewed human gold must annotate every frozen corpus document")
    result: dict[str, str] = {}
    for item in documents:
        if not isinstance(item, dict) or set(item) != _GOLD_DOCUMENT_FIELDS:
            raise HumanEvaluationError("reviewed human gold document fields are invalid")
        document_id = item.get("document_id")
        relevance = item.get("retrieval_relevance")
        if (
            not isinstance(document_id, str)
            or document_id not in corpus_document_ids
            or document_id in result
            or relevance not in _ALLOWED_RELEVANCE
        ):
            raise HumanEvaluationError("reviewed human gold document identity or relevance is invalid")
        if not all(isinstance(item[key], list) for key in _GOLD_DOCUMENT_FIELDS - {"document_id", "retrieval_relevance"}):
            raise HumanEvaluationError("reviewed human gold annotation fields must be arrays")
        result[document_id] = relevance
    if set(result) != corpus_document_ids:
        raise HumanEvaluationError("reviewed human gold document IDs do not match the frozen corpus")
    if not any(value == "relevant" for value in result.values()):
        raise HumanEvaluationError("reviewed human gold must identify at least one relevant document")
    return result


def retrieval_evaluation_from_gold(
    *,
    mission_id: str,
    corpus_id: str,
    gold: dict[str, str],
    candidate_artifact: object,
    search_index: int,
    k: int,
    corpus_document_dois: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Calculate P/R/nDCG for one search against a frozen reviewed corpus.

    Candidate identity is deliberately conservative.  A result can match a
    gold document by the same document ID, or by an exact normalized DOI mapped
    from the frozen manifest.  Title/year similarity is never used.  This makes
    Sciverse, Sci-Base, and local-library routes comparable without pretending
    that differently named provider records are the same paper.
    """
    if not 1 <= k <= 50:
        raise HumanEvaluationError("k must be between 1 and 50")
    if not isinstance(candidate_artifact, dict) or not isinstance(candidate_artifact.get("searches"), list):
        raise HumanEvaluationError("candidate artifact must retain a search history")
    searches = candidate_artifact["searches"]
    if not isinstance(search_index, int) or not 0 <= search_index < len(searches):
        raise HumanEvaluationError("search_index is outside the recorded search history")
    search = searches[search_index]
    if not isinstance(search, dict) or not isinstance(search.get("candidates"), list):
        raise HumanEvaluationError("selected retrieval search is invalid")
    doi_to_document = _frozen_doi_index(gold, corpus_document_dois)
    candidate_ids: list[str] = []
    seen: set[str] = set()
    raw_retrieved_count = 0
    doi_resolved_count = 0
    duplicate_alias_count = 0
    for item in search["candidates"]:
        if not isinstance(item, dict) or not isinstance(item.get("document_id"), str):
            raise HumanEvaluationError("selected retrieval candidate is invalid")
        raw_retrieved_count += 1
        document_id, resolved_by_doi = _resolve_frozen_document_id(item, gold, doi_to_document)
        if resolved_by_doi:
            doi_resolved_count += 1
        if document_id in seen:
            duplicate_alias_count += 1
            continue
        seen.add(document_id)
        candidate_ids.append(document_id)
    top = candidate_ids[:k]
    strict_relevant = {document_id for document_id, label in gold.items() if label == "relevant"}
    strict_hits = sum(document_id in strict_relevant for document_id in top)
    gains = {"relevant": 2, "partially_relevant": 1, "not_relevant": 0}
    dcg = sum(gains[gold[document_id]] / math.log2(rank + 2) for rank, document_id in enumerate(top))
    ideal_gains = sorted((gains[label] for label in gold.values()), reverse=True)[:k]
    ideal_dcg = sum(gain / math.log2(rank + 2) for rank, gain in enumerate(ideal_gains))
    return {
        "schema_version": _EVALUATION_SCHEMA_VERSION,
        "mission_id": mission_id,
        "corpus_id": corpus_id,
        "trust_status": "metrics_from_human_reviewed_gold_standard",
        "identity_resolution_policy": "exact_document_id_or_normalized_doi_to_frozen_manifest",
        "search_index": search_index,
        "k": k,
        "raw_retrieved_count": raw_retrieved_count,
        "retrieved_count": len(candidate_ids),
        "doi_resolved_candidate_count": doi_resolved_count,
        "duplicate_alias_count": duplicate_alias_count,
        "gold_relevant_count": len(strict_relevant),
        "gold_partially_relevant_count": sum(label == "partially_relevant" for label in gold.values()),
        "precision_at_k": round(strict_hits / k, 6),
        "recall_at_k": round(strict_hits / len(strict_relevant), 6),
        "ndcg_at_k": round(dcg / ideal_dcg, 6) if ideal_dcg else 0.0,
    }


def _frozen_doi_index(
    gold: dict[str, str], corpus_document_dois: dict[str, str | None] | None,
) -> dict[str, str]:
    if corpus_document_dois is None:
        return {}
    if set(corpus_document_dois) != set(gold):
        raise HumanEvaluationError("frozen corpus DOI map must cover exactly the reviewed gold document IDs")
    result: dict[str, str] = {}
    for document_id, raw_doi in corpus_document_dois.items():
        doi = normalized_doi_or_none(raw_doi)
        if doi is None:
            continue
        if doi in result:
            raise HumanEvaluationError("frozen corpus has duplicate normalized DOI values; resolve identity before evaluation")
        result[doi] = document_id
    return result


def _resolve_frozen_document_id(
    candidate: dict[str, Any], gold: dict[str, str], doi_to_document: dict[str, str],
) -> tuple[str, bool]:
    document_id = candidate["document_id"].strip()
    if document_id in gold:
        return document_id, False
    doi = normalized_doi_or_none(candidate.get("doi"))
    if doi is not None and doi in doi_to_document:
        return doi_to_document[doi], True
    raise HumanEvaluationError("selected retrieval candidate cannot be matched exactly to the frozen corpus")


def write_human_retrieval_evaluation(run_dir: Path, result: dict[str, Any]) -> Path:
    expected = {
        "schema_version", "mission_id", "corpus_id", "trust_status", "identity_resolution_policy", "search_index", "k",
        "raw_retrieved_count", "retrieved_count", "doi_resolved_candidate_count", "duplicate_alias_count",
        "gold_relevant_count", "gold_partially_relevant_count", "precision_at_k", "recall_at_k", "ndcg_at_k",
    }
    if not isinstance(result, dict) or set(result) != expected:
        raise HumanEvaluationError("human retrieval evaluation result is invalid")
    path = run_dir / "human_retrieval_evaluation.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
