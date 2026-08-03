"""Bounded, non-claim relation edges derived from one OpenAlex work lookup."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import EvidenceCard, MissionBrief, ReviewStatus
from .openalex import OpenAlexWork
from .verification import VerificationDecision


RELATION_SCHEMA_VERSION = "1.0"
_EDGE_TYPES = {"citation_reference", "algorithmic_related"}


class RelationExpansionError(ValueError):
    pass


def build_relation_expansion(
    mission: MissionBrief, card: EvidenceCard, decision: VerificationDecision, work: OpenAlexWork
) -> dict[str, Any]:
    """Produce graph edges only from one accepted, DOI-bearing evidence source."""
    if decision.mission_id != mission.mission_id or decision.evidence_id != card.evidence_id or decision.status is not ReviewStatus.ACCEPTED:
        raise RelationExpansionError("relation expansion requires accepted evidence from this mission")
    if not card.provenance.doi:
        raise RelationExpansionError("accepted evidence must have a DOI for OpenAlex relation expansion")
    edges = [
        {"edge_type": "citation_reference", "target_openalex_id": target}
        for target in work.referenced_work_ids
    ] + [
        {"edge_type": "algorithmic_related", "target_openalex_id": target}
        for target in work.related_work_ids
    ]
    return {
        "schema_version": RELATION_SCHEMA_VERSION,
        "mission_id": mission.mission_id,
        "trust_status": "public_relation_metadata_not_scientific_evidence",
        "source": {"evidence_id": card.evidence_id, "document_id": card.provenance.document_id, "openalex_work_id": work.work_id},
        "edges": edges,
    }


def write_relation_expansion(run_dir: Path, expansion: dict[str, Any]) -> Path:
    _validate(expansion)
    path = run_dir / "relation_expansion.json"
    path.write_text(json.dumps(expansion, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _validate(payload: Any) -> None:
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "mission_id", "trust_status", "source", "edges"}:
        raise RelationExpansionError("relation expansion fields are invalid")
    if payload["schema_version"] != RELATION_SCHEMA_VERSION or payload["trust_status"] != "public_relation_metadata_not_scientific_evidence":
        raise RelationExpansionError("relation expansion schema or trust status is invalid")
    if not isinstance(payload["mission_id"], str) or not payload["mission_id"].strip() or not isinstance(payload["source"], dict):
        raise RelationExpansionError("relation expansion identity is invalid")
    if set(payload["source"]) != {"evidence_id", "document_id", "openalex_work_id"} or not all(isinstance(value, str) and value for value in payload["source"].values()):
        raise RelationExpansionError("relation expansion source is invalid")
    if not isinstance(payload["edges"], list) or len(payload["edges"]) > 24:
        raise RelationExpansionError("relation expansion edge list is invalid")
    seen: set[tuple[str, str]] = set()
    for edge in payload["edges"]:
        if not isinstance(edge, dict) or set(edge) != {"edge_type", "target_openalex_id"} or edge.get("edge_type") not in _EDGE_TYPES:
            raise RelationExpansionError("relation expansion edge type is invalid")
        target = edge.get("target_openalex_id")
        if not isinstance(target, str) or not target.startswith("https://openalex.org/W"):
            raise RelationExpansionError("relation expansion target is invalid")
        identity = (edge["edge_type"], target)
        if identity in seen:
            raise RelationExpansionError("relation expansion edges must be unique")
        seen.add(identity)
