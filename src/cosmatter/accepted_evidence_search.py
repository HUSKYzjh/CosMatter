"""Deterministic search over already accepted evidence cards only.

This is deliberately not full-text RAG: it indexes no PDF, MinerU Markdown,
source-map excerpt, model transcript, or unreviewed card.  A search hit is a
pointer to a previously reviewed evidence card, not a newly verified fact.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

from .models import EvidenceCard, MissionBrief, ReviewStatus
from .verification import VerificationDecision


class AcceptedEvidenceSearchError(ValueError):
    pass


_TOKEN = re.compile(r"[\w]+", re.UNICODE)


def search_accepted_evidence(
    *,
    mission: MissionBrief,
    cards: Iterable[EvidenceCard],
    decisions: Iterable[VerificationDecision],
    query: str,
    limit: int = 8,
) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip() or len(query.strip()) > 300:
        raise AcceptedEvidenceSearchError("accepted-evidence query must be a bounded nonempty string")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 12:
        raise AcceptedEvidenceSearchError("accepted-evidence limit must be between 1 and 12")
    query_terms = _terms(query)
    if not query_terms:
        raise AcceptedEvidenceSearchError("accepted-evidence query must contain searchable terms")
    accepted = {
        decision.evidence_id
        for decision in decisions
        if decision.mission_id == mission.mission_id and decision.status is ReviewStatus.ACCEPTED
    }
    candidates = [card for card in cards if card.evidence_id in accepted]
    if not candidates:
        raise AcceptedEvidenceSearchError("accepted-evidence search requires at least one accepted card")
    scored: list[tuple[int, EvidenceCard]] = []
    for card in candidates:
        if card.provenance.document_id.strip() == "":
            raise AcceptedEvidenceSearchError("accepted evidence provenance is invalid")
        score = len(query_terms & _terms(_searchable_text(card)))
        if score:
            scored.append((score, card))
    scored.sort(key=lambda item: (-item[0], item[1].evidence_id))
    return {
        "schema_version": "1.0",
        "mission_id": mission.mission_id,
        "trust_status": "accepted_evidence_search_not_new_evidence_or_scientific_conclusion",
        "query_sha256": hashlib.sha256(query.strip().encode("utf-8")).hexdigest(),
        "query_char_count": len(query.strip()),
        "accepted_evidence_count": len(candidates),
        "result_count": min(len(scored), limit),
        "results": [_safe_result(card, score) for score, card in scored[:limit]],
    }


def _safe_result(card: EvidenceCard, score: int) -> dict[str, Any]:
    return {
        "evidence_id": card.evidence_id,
        "document_id": card.provenance.document_id,
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
