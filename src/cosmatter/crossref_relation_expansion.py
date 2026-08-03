"""Review-gated Crossref reference metadata, separate from scientific evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .crossref import CrossrefWork
from .models import EvidenceCard, MissionBrief, ReviewStatus
from .openalex import normalize_doi
from .verification import VerificationDecision


SCHEMA_VERSION = "1.0"
TRUST_STATUS = "public_bibliographic_reference_metadata_not_scientific_evidence"


class CrossrefRelationExpansionError(ValueError):
    pass


def build_crossref_relation_expansion(
    mission: MissionBrief, card: EvidenceCard, decision: VerificationDecision, work: CrossrefWork
) -> dict[str, Any]:
    """Build bounded Crossref reference edges for one accepted DOI-bearing card."""
    if decision.mission_id != mission.mission_id or decision.evidence_id != card.evidence_id or decision.status is not ReviewStatus.ACCEPTED:
        raise CrossrefRelationExpansionError("Crossref expansion requires accepted evidence from this mission")
    if not card.provenance.doi:
        raise CrossrefRelationExpansionError("accepted evidence must have a DOI for Crossref expansion")
    if normalize_doi(card.provenance.doi) != work.doi:
        raise CrossrefRelationExpansionError("Crossref record DOI did not match accepted evidence DOI")
    return {
        "schema_version": SCHEMA_VERSION,
        "mission_id": mission.mission_id,
        "trust_status": TRUST_STATUS,
        "source": {"evidence_id": card.evidence_id, "document_id": card.provenance.document_id, "crossref_doi": work.doi},
        "reference_field_present": work.reference_field_present,
        "edges": [{"edge_type": "crossref_reference", "target_doi": doi} for doi in work.referenced_dois],
    }


def write_crossref_relation_expansion(run_dir: Path, expansion: dict[str, Any]) -> Path:
    _validate(expansion)
    path = run_dir / "crossref_relation_expansion.json"
    path.write_text(json.dumps(expansion, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _validate(payload: Any) -> None:
    required = {"schema_version", "mission_id", "trust_status", "source", "reference_field_present", "edges"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise CrossrefRelationExpansionError("Crossref relation expansion fields are invalid")
    if payload["schema_version"] != SCHEMA_VERSION or payload["trust_status"] != TRUST_STATUS:
        raise CrossrefRelationExpansionError("Crossref relation expansion schema or trust status is invalid")
    source = payload["source"]
    if not isinstance(payload["mission_id"], str) or not payload["mission_id"].strip() or not isinstance(source, dict):
        raise CrossrefRelationExpansionError("Crossref relation expansion identity is invalid")
    if set(source) != {"evidence_id", "document_id", "crossref_doi"} or not all(isinstance(value, str) and value for value in source.values()):
        raise CrossrefRelationExpansionError("Crossref relation expansion source is invalid")
    if normalize_doi(source["crossref_doi"]) != source["crossref_doi"] or not isinstance(payload["reference_field_present"], bool):
        raise CrossrefRelationExpansionError("Crossref relation expansion metadata is invalid")
    if not isinstance(payload["edges"], list) or len(payload["edges"]) > 12:
        raise CrossrefRelationExpansionError("Crossref relation expansion edge list is invalid")
    seen: set[str] = set()
    for edge in payload["edges"]:
        if not isinstance(edge, dict) or set(edge) != {"edge_type", "target_doi"} or edge.get("edge_type") != "crossref_reference":
            raise CrossrefRelationExpansionError("Crossref relation expansion edge type is invalid")
        target = edge.get("target_doi")
        if not isinstance(target, str) or normalize_doi(target) != target or target in seen:
            raise CrossrefRelationExpansionError("Crossref relation expansion target is invalid")
        seen.add(target)
