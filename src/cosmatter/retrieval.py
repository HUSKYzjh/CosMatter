"""Safe candidate projection and persistence for bounded literature retrieval."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import PaperCandidate


class RetrievalArtifactError(ValueError):
    """Raised when upstream candidates cannot form a safe local artifact."""


def candidates_from_sciverse(payload: dict[str, Any], query: str, top_k: int) -> tuple[PaperCandidate, ...]:
    """Reduce upstream results to metadata-only candidate cards.

    A candidate is not a source claim.  Abstracts, full text, request details,
    and arbitrary upstream fields are intentionally excluded.
    """
    if not query.strip() or not 1 <= top_k <= 50:
        raise RetrievalArtifactError("query must be nonempty and top_k must be between 1 and 50")
    hits = payload.get("hits", [])
    if not isinstance(hits, list):
        raise RetrievalArtifactError("Sciverse hits must be an array")
    candidates: list[PaperCandidate] = []
    seen_document_ids: set[str] = set()
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        document_id = str(hit.get("doc_id", "")).strip()
        title = str(hit.get("title", "")).strip()
        if not document_id or not title or document_id in seen_document_ids:
            continue
        year = hit.get("publication_published_year")
        score = hit.get("score")
        try:
            candidate = PaperCandidate(
                document_id=document_id,
                title=title,
                query=query,
                source="Sciverse",
                publication_year=year if isinstance(year, int) else None,
                locator_hint=_locator_hint(hit),
                score=float(score) if isinstance(score, (int, float)) else None,
                is_content_accessible=hit.get("is_content_accessible") is True,
            )
        except ValueError:
            continue
        candidates.append(candidate)
        seen_document_ids.add(document_id)
        if len(candidates) == top_k:
            break
    return tuple(candidates)


def _locator_hint(hit: dict[str, Any]) -> str | None:
    page_no = hit.get("page_no")
    offset = hit.get("offset")
    parts = []
    if isinstance(page_no, int) and page_no >= 0:
        parts.append(f"page:{page_no}")
    if isinstance(offset, int) and offset >= 0:
        parts.append(f"offset:{offset}")
    return ";".join(parts) if parts else None


def write_candidate_artifact(run_dir: Path, query: str, candidates: tuple[PaperCandidate, ...]) -> Path:
    """Append one metadata-only search to the local candidate history.

    ``candidates`` remains a flattened, document-id-deduplicated view for
    source-location gates. ``searches`` preserves which approved query found
    each candidate and prevents later searches from overwriting earlier ones.
    """
    if not query.strip():
        raise RetrievalArtifactError("query must not be empty")
    if any(candidate.query != query for candidate in candidates):
        raise RetrievalArtifactError("candidate query does not match artifact query")
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "retrieval_candidates.json"
    searches = _load_search_history(path)
    searches.append(
        {
            "query": query,
            "candidate_count": len(candidates),
            "candidates": [candidate.to_dict() for candidate in candidates],
        }
    )
    flattened = _deduplicated_candidates(searches)
    payload = {
        "schema_version": "1.1",
        "query": query,
        "candidate_count": len(flattened),
        "search_count": len(searches),
        "candidates": flattened,
        "searches": searches,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _load_search_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RetrievalArtifactError("existing candidate artifact is invalid JSON") from error
    if not isinstance(payload, dict):
        raise RetrievalArtifactError("existing candidate artifact must be an object")
    searches = payload.get("searches")
    if searches is None:
        query = payload.get("query")
        candidates = payload.get("candidates")
        if not isinstance(query, str) or not isinstance(candidates, list):
            raise RetrievalArtifactError("existing candidate artifact has no usable search history")
        searches = [{"query": query, "candidate_count": len(candidates), "candidates": candidates}]
    if not isinstance(searches, list):
        raise RetrievalArtifactError("candidate search history must be an array")
    safe_searches: list[dict[str, Any]] = []
    for search in searches:
        if not isinstance(search, dict) or not isinstance(search.get("query"), str) or not isinstance(search.get("candidates"), list):
            raise RetrievalArtifactError("candidate search history contains an invalid entry")
        cards = search["candidates"]
        if not all(isinstance(card, dict) for card in cards):
            raise RetrievalArtifactError("candidate search contains a non-object candidate")
        safe_searches.append({"query": search["query"], "candidate_count": len(cards), "candidates": cards})
    return safe_searches


def _deduplicated_candidates(searches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduplicated: dict[str, dict[str, Any]] = {}
    for search in searches:
        for candidate in search["candidates"]:
            document_id = candidate.get("document_id")
            if not isinstance(document_id, str) or not document_id.strip():
                raise RetrievalArtifactError("candidate history contains a missing document_id")
            previous = deduplicated.get(document_id)
            if previous is None or (
                candidate.get("is_content_accessible") is True
                and previous.get("is_content_accessible") is not True
            ):
                deduplicated[document_id] = candidate
    return list(deduplicated.values())