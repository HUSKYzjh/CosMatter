"""Guarded conversion of an extracted draft into a reviewed EvidenceCard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifacts import persist_evidence_review
from .models import AccessPolicy, EvidenceCard, Provenance, Stance
from .verification import VerificationDecision


class EvidenceIngestionError(ValueError):
    """Raised when a draft is not traceable to an eligible local candidate."""


_DRAFT_FIELDS = {
    "claim",
    "stance",
    "material",
    "property_name",
    "conditions",
    "quote",
    "provenance",
    "extractor_confidence",
    "evidence_id",
}
_PROVENANCE_FIELDS = {"document_id", "locator", "source", "doi", "content_hash", "access_policy"}


def ingest_evidence_draft(run_dir: Path, draft: dict[str, Any]) -> VerificationDecision:
    """Validate one bounded draft and persist its card plus review decision.

    This function never retrieves text.  It accepts an already extracted short
    quote only after it can be tied to a content-accessible candidate written
    in the same local run directory.
    """
    mission_id = _mission_id(run_dir)
    card = evidence_card_from_draft(draft)
    require_eligible_candidate(run_dir, card.provenance.document_id)
    return persist_evidence_review(run_dir, mission_id, card)


def evidence_card_from_draft(draft: dict[str, Any]) -> EvidenceCard:
    """Parse a narrow evidence-draft schema and reject raw-text side channels."""
    if not isinstance(draft, dict):
        raise EvidenceIngestionError("evidence draft must be a JSON object")
    unknown = set(draft) - _DRAFT_FIELDS
    missing = _DRAFT_FIELDS - set(draft)
    if unknown or missing:
        raise EvidenceIngestionError("evidence draft has unknown or missing fields")
    provenance = draft["provenance"]
    if not isinstance(provenance, dict) or set(provenance) - _PROVENANCE_FIELDS:
        raise EvidenceIngestionError("evidence draft provenance has unsupported fields")
    if not isinstance(draft["conditions"], dict):
        raise EvidenceIngestionError("evidence draft conditions must be an object")
    try:
        return EvidenceCard(
            claim=str(draft["claim"]),
            stance=Stance(str(draft["stance"])),
            material=str(draft["material"]),
            property_name=str(draft["property_name"]),
            conditions=draft["conditions"],
            quote=str(draft["quote"]),
            provenance=Provenance(
                document_id=str(provenance["document_id"]),
                locator=str(provenance["locator"]),
                source=str(provenance["source"]),
                doi=provenance.get("doi"),
                content_hash=provenance.get("content_hash"),
                access_policy=AccessPolicy(str(provenance.get("access_policy", AccessPolicy.AUTHORIZED.value))),
            ),
            extractor_confidence=draft["extractor_confidence"],
            evidence_id=str(draft["evidence_id"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise EvidenceIngestionError("evidence draft does not satisfy EvidenceCard") from error


def _mission_id(run_dir: Path) -> str:
    path = run_dir / "mission.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        mission_id = payload["mission_id"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise EvidenceIngestionError("run must contain a valid mission.json") from error
    if not isinstance(mission_id, str) or not mission_id.strip():
        raise EvidenceIngestionError("mission.json must contain a nonempty mission_id")
    return mission_id


def require_eligible_candidate(run_dir: Path, document_id: str) -> None:
    path = run_dir / "retrieval_candidates.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        candidates = payload["candidates"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise EvidenceIngestionError("run must contain retrieval_candidates.json before evidence ingestion") from error
    if not isinstance(candidates, list):
        raise EvidenceIngestionError("candidate artifact must contain an array")
    candidate = next((item for item in candidates if isinstance(item, dict) and item.get("document_id") == document_id), None)
    if candidate is None:
        raise EvidenceIngestionError("evidence document_id is not a candidate from this run")
    if candidate.get("is_content_accessible") is not True:
        raise EvidenceIngestionError("candidate lacks full-text access authorization")
