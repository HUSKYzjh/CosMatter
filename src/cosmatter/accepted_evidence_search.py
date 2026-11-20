"""Deterministic search over already accepted evidence cards only.

This is deliberately not full-text RAG: it indexes no PDF, MinerU Markdown,
source-map excerpt, model transcript, or unreviewed card.  A search hit is a
pointer to a previously reviewed evidence card, not a newly verified fact.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any, Iterable

from .models import EvidenceCard, MissionBrief, ReviewStatus
from .verification import VerificationDecision


class AcceptedEvidenceSearchError(ValueError):
    pass


_TOKEN = re.compile(r"[\w]+", re.UNICODE)
_DOI_PREFIX = re.compile(r"^(?:https?://doi\.org/|doi:) *", re.IGNORECASE | re.ASCII)
_DOI_NAME = re.compile(r"10\.[0-9]+(?:\.[0-9]+)*/\S+")
_DOI_CASE = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def canonical_evidence_doi(value: object) -> str | None:
    if not isinstance(value, str) or not _valid_selector(value, 300):
        return None
    # DOI names compare without ASCII case distinctions. Preserve non-ASCII
    # suffix characters identically in Python and in the JavaScript client.
    doi = _DOI_PREFIX.sub("", value).translate(_DOI_CASE)
    return doi if len(doi) <= 255 and _DOI_NAME.fullmatch(doi) else None


def search_accepted_evidence(
    *,
    mission: MissionBrief,
    cards: Iterable[EvidenceCard],
    decisions: Iterable[VerificationDecision],
    query: str | None = None,
    evidence_id: str | None = None,
    document_id: str | None = None,
    doi: str | None = None,
    locator: str | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    by_location = document_id is not None
    if (sum((query is not None, evidence_id is not None, by_location, doi is not None)) != 1
            or (locator is not None and not by_location and doi is None)):
        raise AcceptedEvidenceSearchError("provide a query or one exact evidence ID, a document ID and locator together, or a DOI with optional locator")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 12:
        raise AcceptedEvidenceSearchError("accepted-evidence limit must be between 1 and 12")
    query_terms: set[str] = set()
    requested_doi = canonical_evidence_doi(doi)
    if doi is not None:
        if not requested_doi or (locator is not None and not _valid_selector(locator, 240)):
            raise AcceptedEvidenceSearchError("provide a valid DOI and an optional exact locator")
        query_value = json.dumps({"doi": requested_doi, "locator": locator}, ensure_ascii=False, separators=(",", ":"))
    elif by_location:
        if not _valid_selector(document_id, 255) or not _valid_selector(locator, 240):
            raise AcceptedEvidenceSearchError("exact document ID and locator must both be valid")
        query_value = json.dumps([document_id, locator], ensure_ascii=False, separators=(",", ":"))
    elif evidence_id is not None:
        if not _valid_selector(evidence_id, 200):
            raise AcceptedEvidenceSearchError("exact evidence ID is invalid")
        query_value = evidence_id
    else:
        if not isinstance(query, str) or not query.strip() or len(query.strip()) > 300:
            raise AcceptedEvidenceSearchError("accepted-evidence query must be a bounded nonempty string")
        query_value = query.strip()
        query_terms = _terms(query_value)
        if not query_terms:
            raise AcceptedEvidenceSearchError("accepted-evidence query must contain searchable terms")
    mission_decisions = [decision for decision in decisions if decision.mission_id == mission.mission_id]
    if evidence_id is not None and sum(decision.evidence_id == evidence_id for decision in mission_decisions) > 1:
        raise AcceptedEvidenceSearchError("accepted evidence ID has ambiguous verification decisions")
    accepted = {
        decision.evidence_id
        for decision in mission_decisions
        if decision.status is ReviewStatus.ACCEPTED
    }
    candidates = [card for card in cards if card.evidence_id in accepted]
    if not candidates and requested_doi is None:
        raise AcceptedEvidenceSearchError("accepted-evidence search requires at least one accepted card")
    if by_location or requested_doi:
        card_counts = Counter(card.evidence_id for card in candidates)
        decision_counts = Counter(decision.evidence_id for decision in mission_decisions)
    scored: list[tuple[int, EvidenceCard]] = []
    for card in candidates:
        if evidence_id is not None and card.evidence_id != evidence_id:
            continue
        if requested_doi and canonical_evidence_doi(card.provenance.doi) != requested_doi:
            continue
        if by_location and card.provenance.document_id != document_id:
            continue
        if locator is not None and card.provenance.locator != locator:
            continue
        if by_location or requested_doi:
            if card_counts[card.evidence_id] != 1 or decision_counts[card.evidence_id] != 1:
                raise AcceptedEvidenceSearchError("accepted evidence at this location has an ambiguous evidence ID or verification decision")
        if card.provenance.document_id.strip() == "":
            raise AcceptedEvidenceSearchError("accepted evidence provenance is invalid")
        score = len(query_terms & _terms(_searchable_text(card))) if query is not None else 1
        if score:
            scored.append((score, card))
    scored.sort(key=lambda item: (-item[0], item[1].evidence_id))
    if evidence_id is not None and len(scored) > 1:
        raise AcceptedEvidenceSearchError("accepted evidence ID is ambiguous")
    return {
        "schema_version": "1.0",
        "mission_id": mission.mission_id,
        "trust_status": "accepted_evidence_search_not_new_evidence_or_scientific_conclusion",
        "query_sha256": hashlib.sha256(query_value.encode("utf-8")).hexdigest(),
        "query_char_count": len(query_value),
        "accepted_evidence_count": len(candidates),
        "result_count": min(len(scored), limit),
        "results": [_safe_result(card, score, requested_doi) for score, card in scored[:limit]],
        **({"match_mode": "exact_id"} if evidence_id is not None else {}),
        **({"match_mode": "exact_locator", "matched_count": len(scored)} if by_location else {}),
        **({"match_mode": "exact_doi", "matched_count": len(scored)} if requested_doi else {}),
    }


def _valid_selector(value: object, maximum: int) -> bool:
    return isinstance(value, str) and 0 < len(value) <= maximum and value == value.strip() and not re.search(r"[\x00-\x1f\x7f]", value)


def _safe_result(card: EvidenceCard, score: int, requested_doi: str | None) -> dict[str, Any]:
    return {
        "evidence_id": card.evidence_id,
        "document_id": card.provenance.document_id,
        **({"doi": requested_doi, "review_status": ReviewStatus.ACCEPTED.value} if requested_doi else {}),
        "claim": card.claim,
        "stance": card.stance.value,
        "material": card.material,
        "property_name": card.property_name,
        "conditions": _safe_conditions(card.conditions),
        "locator": card.provenance.locator,
        "source": card.provenance.source,
        "score": score,
    }


def _safe_conditions(value: object) -> dict[str, str | int | float | bool | None]:
    if not isinstance(value, dict) or len(value) > 20:
        raise AcceptedEvidenceSearchError("accepted evidence conditions are invalid")
    result: dict[str, str | int | float | bool | None] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip() or len(key) > 80:
            raise AcceptedEvidenceSearchError("accepted evidence condition key is invalid")
        if isinstance(item, str):
            if not item.strip() or len(item) > 200:
                raise AcceptedEvidenceSearchError("accepted evidence condition is invalid")
            result[key] = item.strip()
        elif item is None or isinstance(item, bool) or isinstance(item, int) and not isinstance(item, bool) or isinstance(item, float):
            result[key] = item
        else:
            raise AcceptedEvidenceSearchError("accepted evidence condition is invalid")
    return result


def _searchable_text(card: EvidenceCard) -> str:
    conditions = _safe_conditions(card.conditions)
    return " ".join([card.claim, card.material, card.property_name, card.stance.value, *conditions.keys(), *(str(value) for value in conditions.values())])


def _terms(value: str) -> set[str]:
    return {term.casefold() for term in _TOKEN.findall(value) if len(term) >= 2}
