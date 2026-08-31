"""Safe candidate projection and persistence for bounded literature retrieval."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import PaperCandidate, normalized_doi_or_none


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
                is_content_accessible=_sciverse_content_accessible(hit),
                doi=_hit_doi(hit),
            )
        except ValueError:
            continue
        candidates.append(candidate)
        seen_document_ids.add(document_id)
        if len(candidates) == top_k:
            break
    return tuple(candidates)


def _sciverse_content_accessible(hit: dict[str, Any]) -> bool:
    """Map Sciverse's documented full-text identifier without guessing access.

    ``semantic_search`` returns chunks and does not promise the optional
    ``is_content_accessible`` convenience flag.  The official SDK documents a
    nonempty ``doc_id`` as a full-text artifact identifier suitable for
    ``read_content``; metadata-only records lack it.  An explicit provider
    boolean still takes precedence when present.
    """
    explicit = hit.get("is_content_accessible")
    if isinstance(explicit, bool):
        return explicit
    document_id = hit.get("doc_id")
    return isinstance(document_id, str) and bool(document_id.strip())


def _hit_doi(hit: dict[str, Any]) -> str | None:
    for key in ("doi", "DOI"):
        doi = normalized_doi_or_none(hit.get(key))
        if doi is not None:
            return doi
    return None


def _locator_hint(hit: dict[str, Any]) -> str | None:
    page_no = hit.get("page_no")
    offset = hit.get("offset")
    parts = []
    if isinstance(page_no, int) and page_no >= 0:
        parts.append(f"page:{page_no}")
    if isinstance(offset, int) and offset >= 0:
        parts.append(f"offset:{offset}")
    return ";".join(parts) if parts else None


def write_candidate_artifact(
    run_dir: Path,
    query: str,
    candidates: tuple[PaperCandidate, ...],
    *,
    source_provenance: dict[str, dict[str, Any]] | None = None,
) -> Path:
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
    provenance = _validated_source_provenance(query, source_provenance)
    searches = _load_search_history(path)
    searches.append(
        {
            "query": query,
            "candidate_count": len(candidates),
            "candidates": [candidate.to_dict() for candidate in candidates],
            "source_provenance": provenance,
        }
    )
    flattened = _deduplicated_candidates(searches)
    payload = {
        "schema_version": "1.3",
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
        provenance = _validated_source_provenance(search["query"], search.get("source_provenance"))
        safe_searches.append({"query": search["query"], "candidate_count": len(cards), "candidates": cards, "source_provenance": provenance})
    return safe_searches


def _deduplicated_candidates(searches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge only exact document IDs or normalized DOI aliases across searches.

    Titles and years are deliberately not fuzzy-matched: similar material-science
    titles can describe distinct studies. Each retained card records the opaque
    metadata identities that were merged and all query/provider origin links.
    """
    groups: dict[str, dict[str, Any]] = {}
    key_to_group: dict[str, str] = {}
    group_number = 0
    for search_index, search in enumerate(searches):
        provenance_by_source = search["source_provenance"]
        query_digest = hashlib.sha256(search["query"].strip().encode("utf-8")).hexdigest()
        for candidate in search["candidates"]:
            document_id = candidate.get("document_id")
            source = candidate.get("source")
            if not isinstance(document_id, str) or not document_id.strip() or not isinstance(source, str) or not source.strip():
                raise RetrievalArtifactError("candidate history contains a missing document_id or source")
            identity_keys = _candidate_identity_keys(candidate)
            matched = {key_to_group[key] for key in identity_keys if key in key_to_group}
            if not matched:
                group_number += 1
                group_id = f"group:{group_number}"
                groups[group_id] = {"candidate": dict(candidate), "origins": [], "keys": set()}
            else:
                group_id = min(matched, key=lambda value: int(value.split(":", 1)[1]))
                for other_group_id in sorted(matched - {group_id}, key=lambda value: int(value.split(":", 1)[1])):
                    other = groups.pop(other_group_id)
                    groups[group_id]["candidate"] = _preferred_candidate(groups[group_id]["candidate"], other["candidate"])
                    groups[group_id]["origins"].extend(other["origins"])
                    groups[group_id]["keys"].update(other["keys"])
                    for key in other["keys"]:
                        key_to_group[key] = group_id
                groups[group_id]["candidate"] = _preferred_candidate(groups[group_id]["candidate"], candidate)
            origin = {
                "search_index": search_index,
                "source": source,
                "query_sha256": query_digest,
                "retrieved_document_id": document_id,
            }
            provenance = provenance_by_source.get(source)
            if provenance is not None:
                origin["provider"] = provenance["provider"]
                origin["operation"] = provenance["operation"]
                origin["receipt_id"] = provenance["receipt_id"]
            groups[group_id]["origins"].append(origin)
            groups[group_id]["keys"].update(identity_keys)
            for key in identity_keys:
                key_to_group[key] = group_id
    result: list[dict[str, Any]] = []
    for group_id in sorted(groups, key=lambda value: int(value.split(":", 1)[1])):
        group = groups[group_id]
        candidate = dict(group["candidate"])
        origins = group["origins"]
        candidate["retrieval_origins"] = origins
        candidate["deduplication"] = {
            "identity_method": "doi" if any(key.startswith("doi:") for key in group["keys"]) else "document_id",
            "merged_candidate_count": len(origins),
            "merged_document_count": len({origin["retrieved_document_id"] for origin in origins}),
        }
        result.append(candidate)
    return result


def _candidate_identity_keys(candidate: dict[str, Any]) -> set[str]:
    document_id = candidate.get("document_id")
    if not isinstance(document_id, str) or not document_id.strip():
        raise RetrievalArtifactError("candidate history contains an invalid document_id")
    normalized_document_id = document_id.strip().casefold()
    result = {f"document:{normalized_document_id}"}
    doi = candidate.get("doi")
    if not isinstance(doi, str) or not doi.strip():
        doi = normalized_document_id[4:] if normalized_document_id.startswith("doi:") else None
    if isinstance(doi, str) and doi.strip():
        normalized_doi = _normalize_doi_alias(doi)
        if normalized_doi is not None:
            result.add(f"doi:{normalized_doi}")
    return result


def _normalize_doi_alias(value: str) -> str | None:
    doi = value.strip().casefold()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):].strip()
            break
    if not doi or len(doi) > 255 or any(character.isspace() for character in doi) or not doi.startswith("10.") or "/" not in doi:
        return None
    return doi


def _preferred_candidate(current: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Prefer an authorized full-text route without comparing provider scores."""
    use_incoming = incoming.get("is_content_accessible") is True and current.get("is_content_accessible") is not True
    selected = dict(incoming if use_incoming else current)
    alternate = current if use_incoming else incoming
    if not selected.get("doi") and isinstance(alternate.get("doi"), str) and alternate["doi"].strip():
        selected["doi"] = alternate["doi"]
    return selected


def _validated_source_provenance(query: str, provenance: object) -> dict[str, dict[str, str]]:
    """Keep only source-specific receipt links and query digests, never payloads."""
    if provenance is None:
        return {}
    if not isinstance(provenance, dict):
        raise RetrievalArtifactError("source provenance must be a source mapping")
    if not provenance:
        return {}
    result: dict[str, dict[str, str]] = {}
    for source, receipt in provenance.items():
        if not isinstance(source, str) or not source.strip() or len(source) > 160:
            raise RetrievalArtifactError("source provenance source is invalid")
        if not isinstance(receipt, dict) or set(receipt) != {"provider", "operation", "receipt_id", "query_sha256"}:
            raise RetrievalArtifactError("source provenance must contain only receipt references")
        provider, operation, receipt_id, query_sha256 = (
            receipt.get("provider"), receipt.get("operation"), receipt.get("receipt_id"), receipt.get("query_sha256"),
        )
        if not all(isinstance(value, str) and value.strip() for value in (provider, operation, receipt_id, query_sha256)):
            raise RetrievalArtifactError("source provenance values are invalid")
        expected = hashlib.sha256(query.strip().encode("utf-8")).hexdigest()
        if query_sha256 != expected or len(query_sha256) != 64:
            raise RetrievalArtifactError("source provenance query digest does not match the search")
        if len(provider) > 64 or len(operation) > 120 or len(receipt_id) > 160:
            raise RetrievalArtifactError("source provenance values exceed safe bounds")
        result[source] = {"provider": provider, "operation": operation, "receipt_id": receipt_id, "query_sha256": query_sha256}
    return result
