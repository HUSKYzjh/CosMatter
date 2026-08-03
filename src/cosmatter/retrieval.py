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
    """Write a compact metadata-only retrieval work product for one query."""
    if not query.strip():
        raise RetrievalArtifactError("query must not be empty")
    if any(candidate.query != query for candidate in candidates):
        raise RetrievalArtifactError("candidate query does not match artifact query")
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "retrieval_candidates.json"
    payload = {
        "schema_version": "1.0",
        "query": query,
        "candidate_count": len(candidates),
        "candidates": [candidate.to_dict() for candidate in candidates],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
