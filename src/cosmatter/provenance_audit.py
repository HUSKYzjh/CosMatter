"""Audit accepted evidence cards against reviewer-selected source-map segments."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import EvidenceCard, MissionBrief, ReviewStatus
from .verification import VerificationDecision


PROVENANCE_AUDIT_SCHEMA_VERSION = "1.0"


class ProvenanceAuditError(ValueError):
    """Raised when accepted evidence cannot satisfy the provenance audit schema."""


def audit_accepted_evidence_provenance(
    *,
    mission: MissionBrief,
    cards: tuple[EvidenceCard, ...],
    decisions: tuple[VerificationDecision, ...],
    source_maps: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Return a quote-free audit of exact source-map linkage for accepted cards.

    A source-map absence is recorded as a manual locator boundary. A source-map
    present for the same document must match exactly, otherwise the audit fails.
    """
    accepted_ids = _accepted_ids(mission.mission_id, cards, decisions)
    if not accepted_ids:
        raise ProvenanceAuditError("provenance audit requires at least one accepted evidence card")
    maps = _source_maps_by_document(mission.mission_id, source_maps)
    items: list[dict[str, str]] = []
    exact_count = 0
    for card in cards:
        if card.evidence_id not in accepted_ids:
            continue
        source_map = maps.get(card.provenance.document_id)
        if source_map is None:
            raise ProvenanceAuditError("accepted evidence requires a reviewed source map for its document")
        quote_digest = hashlib.sha256(card.quote.encode("utf-8")).hexdigest()
        matched = any(
            segment["locator"] == card.provenance.locator
            and segment["quote_sha256"] == quote_digest
            for segment in source_map["segments"]
        )
        if not matched:
            raise ProvenanceAuditError("accepted evidence does not exactly match the reviewed source map for its document")
        status = "exact_reviewed_source_map_match"
        exact_count += 1
        items.append({
            "evidence_id": card.evidence_id,
            "document_id": card.provenance.document_id,
            "locator": card.provenance.locator,
            "provenance_status": status,
        })
    return {
        "schema_version": PROVENANCE_AUDIT_SCHEMA_VERSION,
        "mission_id": mission.mission_id,
        "trust_status": "accepted_evidence_provenance_coverage_not_source_authenticity_assessment",
        "accepted_evidence_count": len(items),
        "exact_reviewed_source_map_match_count": exact_count,
        "manual_locator_only_count": len(items) - exact_count,
        "exact_source_map_match_rate": round(exact_count / len(items), 6),
        "items": items,
    }


def write_evidence_provenance_audit(run_dir: Path, result: dict[str, Any]) -> Path:
    required = {
        "schema_version", "mission_id", "trust_status", "accepted_evidence_count",
        "exact_reviewed_source_map_match_count", "manual_locator_only_count",
        "exact_source_map_match_rate", "items",
    }
    if not isinstance(result, dict) or set(result) != required:
        raise ProvenanceAuditError("provenance audit result has an invalid schema")
    path = run_dir / "evidence_provenance_audit.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _accepted_ids(
    mission_id: str, cards: tuple[EvidenceCard, ...], decisions: tuple[VerificationDecision, ...],
) -> set[str]:
    card_ids = {card.evidence_id for card in cards}
    if len(card_ids) != len(cards):
        raise ProvenanceAuditError("evidence cards have duplicate identifiers")
    result: set[str] = set()
    seen: set[str] = set()
    for decision in decisions:
        if decision.mission_id != mission_id:
            continue
        if decision.evidence_id in seen:
            raise ProvenanceAuditError("evidence has multiple verification decisions")
        seen.add(decision.evidence_id)
        if decision.status is ReviewStatus.ACCEPTED:
            if decision.evidence_id not in card_ids:
                raise ProvenanceAuditError("accepted decision refers to a missing evidence card")
            result.add(decision.evidence_id)
    return result


def _source_maps_by_document(mission_id: str, source_maps: tuple[dict[str, Any], ...]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for source_map in source_maps:
        if not isinstance(source_map, dict) or source_map.get("mission_id") != mission_id or source_map.get("trust_status") != "human_reviewed_parser_selection":
            raise ProvenanceAuditError("source map is outside this reviewed mission")
        document_id = source_map.get("document_id")
        segments = source_map.get("segments")
        if not isinstance(document_id, str) or not document_id or not isinstance(segments, list) or not segments or document_id in result:
            raise ProvenanceAuditError("source map identity is invalid or duplicated")
        for segment in segments:
            if not isinstance(segment, dict) or not all(isinstance(segment.get(key), str) and segment[key] for key in ("locator", "quote_sha256")):
                raise ProvenanceAuditError("source map segment is invalid")
        result[document_id] = source_map
    return result
