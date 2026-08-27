"""Deterministic BM25 retrieval over explicitly selected parsed Markdown sources.

The caller supplies a path-bearing index for one invocation. Paths and document
content remain process-local: persisted candidate and audit artifacts contain
only ordinary bibliographic cards. This is a baseline retriever, not a claim
that the selected corpus represents all of the literature.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .corpus_preparation import CorpusPreparationError
from .models import PaperCandidate


class LocalCorpusSearchError(ValueError):
    """Raised when a local source index is unsafe or cannot be searched."""


_TOKEN = re.compile(r"[a-z0-9][a-z0-9+._-]*", re.IGNORECASE)
_INDEX_FIELDS = {"documents"}
_DOCUMENT_FIELDS = {"document_id", "title", "path", "parser_provenance"}
_ALLOWED_PROVENANCE = {"mineru_reviewed_local_output", "reviewed_local_markdown_output", "scibase_parquet_oa_subset"}
_MAX_DOCUMENT_BYTES = 5_000_000
_MAX_TOTAL_CORPUS_BYTES = 100_000_000
_BM25_K1 = 1.2
_BM25_B = 0.75
_TITLE_WEIGHT = 3.0


@dataclass(frozen=True)
class _LocalRecord:
    document_id: str
    title: str
    weighted_length: float
    query_counts: Counter[str]


def candidates_from_local_source_index(
    *,
    manifest: dict[str, Any],
    index_path: Path,
    query: str,
    top_k: int,
) -> tuple[PaperCandidate, ...]:
    """Rank a reviewer-selected local parsed corpus without persisting its text.

    Scoring is field-weighted BM25: title occurrences receive a fixed boost, and
    all tokenization, document frequency, and ranking occur in process memory.
    """
    if not isinstance(query, str) or not query.strip() or not 1 <= top_k <= 50:
        raise LocalCorpusSearchError("query must be nonempty and top_k must be between 1 and 50")
    manifest_documents = _manifest_documents(manifest)
    index = _load_index(index_path)
    terms = tuple(dict.fromkeys(term.casefold() for term in _TOKEN.findall(query)))
    if not terms:
        raise LocalCorpusSearchError("query does not contain searchable tokens")

    records: list[_LocalRecord] = []
    seen: set[str] = set()
    total_bytes = 0
    for item in index["documents"]:
        document_id = item["document_id"]
        if document_id in seen:
            raise LocalCorpusSearchError("local source index contains duplicate document_id")
        seen.add(document_id)
        metadata = manifest_documents.get(document_id)
        if metadata is None:
            raise LocalCorpusSearchError("local source index document_id is missing from the authorized corpus manifest")
        if item["title"] != metadata["title"]:
            raise LocalCorpusSearchError("local source index title must match the authorized corpus manifest")
        source_path = Path(item["path"])
        content = _read_local_markdown(source_path)
        total_bytes += len(content.encode("utf-8"))
        if total_bytes > _MAX_TOTAL_CORPUS_BYTES:
            raise LocalCorpusSearchError("local parsed corpus exceeds the total byte safety limit")
        records.append(_record(terms, document_id, item["title"], content))
    return _rank_bm25(terms, query, records, top_k)


def _record(terms: tuple[str, ...], document_id: str, title: str, content: str) -> _LocalRecord:
    title_tokens = tuple(term.casefold() for term in _TOKEN.findall(title))
    content_tokens = tuple(term.casefold() for term in _TOKEN.findall(content))
    title_counts = Counter(title_tokens)
    content_counts = Counter(content_tokens)
    query_counts = Counter({term: content_counts[term] + _TITLE_WEIGHT * title_counts[term] for term in terms})
    return _LocalRecord(document_id, title, len(content_tokens) + _TITLE_WEIGHT * len(title_tokens), query_counts)


def _rank_bm25(
    terms: tuple[str, ...], query: str, records: list[_LocalRecord], top_k: int,
) -> tuple[PaperCandidate, ...]:
    if not records:
        return ()
    document_frequency = {term: sum(record.query_counts[term] > 0 for record in records) for term in terms}
    average_length = sum(record.weighted_length for record in records) / len(records)
    ranked: list[tuple[float, str, PaperCandidate]] = []
    for record in records:
        score = _bm25_score(terms, record, document_frequency, len(records), average_length)
        if score <= 0:
            continue
        ranked.append((
            score,
            record.document_id,
            PaperCandidate(
                document_id=record.document_id,
                title=record.title,
                query=query,
                source="Authorized local parsed corpus (BM25)",
                publication_year=None,
                locator_hint="local-reviewed-parsed-source",
                score=score,
                is_content_accessible=True,
            ),
        ))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return tuple(item[2] for item in ranked[:top_k])


def _manifest_documents(manifest: object) -> dict[str, dict[str, Any]]:
    if not isinstance(manifest, dict) or manifest.get("trust_status") != "human_reviewed_authorized_corpus_manifest_not_evaluation_result":
        raise CorpusPreparationError("local corpus search requires a reviewed authorized corpus manifest")
    documents = manifest.get("documents")
    if not isinstance(documents, list):
        raise CorpusPreparationError("authorized corpus manifest documents are invalid")
    result: dict[str, dict[str, Any]] = {}
    for item in documents:
        if not isinstance(item, dict) or item.get("access_policy") != "institutional_access_internal_review_only":
            raise CorpusPreparationError("local corpus search requires institutionally authorized document metadata")
        document_id = item.get("document_id")
        title = item.get("title")
        if not isinstance(document_id, str) or not document_id or not isinstance(title, str) or not title:
            raise CorpusPreparationError("authorized corpus metadata is invalid")
        result[document_id] = item
    return result


def _load_index(path: Path) -> dict[str, list[dict[str, str]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise LocalCorpusSearchError("local source index does not exist") from error
    except json.JSONDecodeError as error:
        raise LocalCorpusSearchError("local source index is not valid JSON") from error
    if not isinstance(payload, dict) or set(payload) != _INDEX_FIELDS or not isinstance(payload.get("documents"), list):
        raise LocalCorpusSearchError("local source index must contain only a documents array")
    result: list[dict[str, str]] = []
    for item in payload["documents"]:
        if not isinstance(item, dict) or set(item) != _DOCUMENT_FIELDS:
            raise LocalCorpusSearchError("local source index document fields are invalid")
        if not all(isinstance(item.get(key), str) and item[key].strip() for key in _DOCUMENT_FIELDS):
            raise LocalCorpusSearchError("local source index document values are invalid")
        if item["parser_provenance"] not in _ALLOWED_PROVENANCE:
            raise LocalCorpusSearchError("local source index parser provenance is not approved")
        result.append({key: item[key].strip() for key in _DOCUMENT_FIELDS})
    if not result or len(result) > 250:
        raise LocalCorpusSearchError("local source index must contain between 1 and 250 documents")
    return {"documents": result}


def _read_local_markdown(path: Path) -> str:
    if path.suffix.casefold() not in {".md", ".markdown"}:
        raise LocalCorpusSearchError("local source index accepts reviewed Markdown only")
    try:
        size = path.stat().st_size
    except OSError as error:
        raise LocalCorpusSearchError("local parsed source cannot be inspected") from error
    if size < 1 or size > _MAX_DOCUMENT_BYTES:
        raise LocalCorpusSearchError("local parsed source byte size is outside the allowed range")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise LocalCorpusSearchError("local parsed source must be UTF-8 Markdown") from error
    except OSError as error:
        raise LocalCorpusSearchError("local parsed source cannot be read") from error


def _bm25_score(
    terms: tuple[str, ...], record: _LocalRecord, document_frequency: dict[str, int],
    document_count: int, average_length: float,
) -> float:
    score = 0.0
    normalizer = _BM25_K1 * (1 - _BM25_B + _BM25_B * record.weighted_length / max(average_length, 1.0))
    for term in terms:
        frequency = record.query_counts[term]
        if frequency <= 0:
            continue
        inverse_frequency = math.log(1 + (document_count - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
        score += inverse_frequency * (frequency * (_BM25_K1 + 1)) / (frequency + normalizer)
    return round(score, 6)
