"""Deterministic guardrails for the Evidence Patrol and Route Diagnostics fleets."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .models import AccessPolicy, EvidenceCard, ReviewStatus, Stance
from .verification import VerificationDecision


class FacilityGateError(ValueError):
    """Raised when an evidence or diagnosis facility lacks required inputs."""


_CONDITION_FIELDS = ("sample_form", "strain_percent", "substrate", "thickness_nm", "temperature_k", "method")


@dataclass(frozen=True)
class EvidenceReview:
    evidence_id: str
    status: ReviewStatus
    missing_conditions: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class DiscrepancyRow:
    condition_cluster: str
    supporting_evidence_ids: tuple[str, ...]
    contradicting_evidence_ids: tuple[str, ...]
    differing_fields: tuple[str, ...]
    unknown_fields: tuple[str, ...]


@dataclass(frozen=True)
class DiscrepancyMatrix:
    rows: tuple[DiscrepancyRow, ...]
    counterevidence_queries: tuple[str, ...]


def locate_evidence(card: EvidenceCard) -> EvidenceCard:
    """Reject metadata-only records before they are treated as located evidence."""
    if card.provenance.access_policy is AccessPolicy.METADATA_ONLY:
        raise FacilityGateError("metadata-only records cannot supply a quote-level EvidenceCard")
    if not card.provenance.document_id or not card.provenance.locator or not card.quote:
        raise FacilityGateError("located evidence requires document_id, locator, and quote")
    return card


def record_conditions(card: EvidenceCard) -> dict[str, Any]:
    """Return a complete condition profile, making missing information explicit."""
    locate_evidence(card)
    return {field: card.conditions.get(field, "unknown") for field in _CONDITION_FIELDS}


def review_evidence(card: EvidenceCard) -> EvidenceReview:
    """Accept only located evidence whose material conditions are explicit."""
    conditions = record_conditions(card)
    missing = tuple(field for field, value in conditions.items() if value in (None, "", "unknown"))
    if missing:
        return EvidenceReview(card.evidence_id, ReviewStatus.REJECTED, missing, "conditions incomplete; do not compare as equivalent")
    return EvidenceReview(card.evidence_id, ReviewStatus.ACCEPTED, (), "locator, quote, and required conditions present")


def verification_decision(mission_id: str, card: EvidenceCard) -> VerificationDecision:
    """Turn the deterministic facility review into an immutable release artifact."""
    review = review_evidence(card)
    return VerificationDecision(mission_id, review.evidence_id, review.status, review.reason, review.missing_conditions)

def condition_differential(cards: tuple[EvidenceCard, ...], counterevidence_queries: tuple[str, ...]) -> DiscrepancyMatrix:
    """Compare accepted support/contradiction cards without voting across conditions."""
    if not counterevidence_queries or any(not query.strip() for query in counterevidence_queries):
        raise FacilityGateError("diagnostics requires recorded counterevidence queries")
    if len(cards) < 2:
        raise FacilityGateError("diagnostics requires at least two evidence cards")
    reviews = {card.evidence_id: review_evidence(card) for card in cards}
    rejected = [card.evidence_id for card in cards if reviews[card.evidence_id].status is not ReviewStatus.ACCEPTED]
    if rejected:
        raise FacilityGateError(f"diagnostics requires accepted evidence cards; rejected: {', '.join(rejected)}")
    supports = tuple(card for card in cards if card.stance is Stance.SUPPORT)
    contradicts = tuple(card for card in cards if card.stance is Stance.CONTRADICT)
    if not supports or not contradicts:
        raise FacilityGateError("diagnostics requires both supporting and contradicting evidence")
    profiles = {card.evidence_id: record_conditions(card) for card in cards}
    differing = tuple(field for field in _CONDITION_FIELDS if len({str(profiles[card.evidence_id][field]) for card in cards}) > 1)
    cluster = " / ".join(f"{field}={profiles[cards[0].evidence_id][field]}" for field in _CONDITION_FIELDS if field not in differing)
    return DiscrepancyMatrix(
        rows=(DiscrepancyRow(cluster or "no shared explicit conditions", tuple(card.evidence_id for card in supports), tuple(card.evidence_id for card in contradicts), differing, ()),),
        counterevidence_queries=counterevidence_queries,
    )


def condition_matrix_payload(matrix: DiscrepancyMatrix) -> list[dict[str, object]]:
    """Return the browser-safe portion of a condition-diagnostics result."""
    return [
        {
            "condition_cluster": row.condition_cluster,
            "supporting_evidence_ids": list(row.supporting_evidence_ids),
            "contradicting_evidence_ids": list(row.contradicting_evidence_ids),
            "differing_fields": list(row.differing_fields),
            "unknowns": list(row.unknown_fields),
        }
        for row in matrix.rows
    ]


def write_condition_matrix(run_dir: Path, matrix: DiscrepancyMatrix) -> Path:
    """Persist a condition matrix without quotes, full text, or model reasoning."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "condition_matrix.json"
    path.write_text(json.dumps(condition_matrix_payload(matrix), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path