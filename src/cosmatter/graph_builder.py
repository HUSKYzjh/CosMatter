"""Build deterministic graph projections from accepted CosMatter evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from .graph_contracts import GraphEdge, GraphNode, GraphSnapshot
from .graph_validation import validate_graph_snapshot
from .models import EvidenceCard, MissionBrief, ReviewStatus
from .verification import VerificationDecision


def build_accepted_evidence_graph(
    mission: MissionBrief,
    cards: Iterable[EvidenceCard],
    decisions: Iterable[VerificationDecision],
) -> GraphSnapshot:
    """Project accepted cards into a bounded graph without copying their text.

    Verification decisions, rather than a card's embedded status, are the
    authority.  Per-paper entities are deliberately scoped to this mission so
    that no implicit cross-paper entity resolution occurs.
    """
    decisions_by_evidence: dict[str, VerificationDecision] = {}
    for decision in decisions:
        if decision.mission_id != mission.mission_id:
            continue
        if decision.evidence_id in decisions_by_evidence:
            raise ValueError("multiple verification decisions for one evidence card")
        decisions_by_evidence[decision.evidence_id] = decision

    accepted = sorted(
        (
            card for card in cards
            if (decision := decisions_by_evidence.get(card.evidence_id)) is not None
            and decision.status is ReviewStatus.ACCEPTED
        ),
        key=lambda card: card.evidence_id,
    )
    if not accepted:
        raise ValueError("graph projection requires at least one accepted evidence card")

    mission_node = _node("mission", mission.mission_id, "Mission", mission.material, {
        "property_name": mission.property_name,
        "scope_digest": _digest(mission.scope),
    })
    nodes: dict[str, GraphNode] = {mission_node.node_id: mission_node}
    edges: dict[str, GraphEdge] = {}
    artifact_hashes: set[str] = set()

    for card in accepted:
        document_node = _node("paper", card.provenance.document_id, "Paper", _bounded_label(card.provenance.document_id), {
            "source": _bounded_label(card.provenance.source),
            "doi_digest": _digest(card.provenance.doi or "none"),
        })
        entity_node = _node("entity", f"{card.provenance.document_id}|{card.material}|{card.property_name}", "Entity", _bounded_label(f"{card.material} / {card.property_name}"), {
            "entity_scope": "paper_scoped",
            "material_digest": _digest(card.material),
            "property_digest": _digest(card.property_name),
        })
        condition_node = _node("condition", _canonical_conditions(card.conditions), "Condition", "reported conditions", {
            "field_names": sorted(str(key) for key in card.conditions),
            "condition_digest": _digest(_canonical_conditions(card.conditions)),
        })
        evidence_node = _node("evidence", card.evidence_id, "EvidenceCard", _bounded_label(card.evidence_id), {
            "review_status": ReviewStatus.ACCEPTED.value,
            "stance": card.stance.value,
            "claim_digest": _digest(card.claim),
            "provenance_digest": _digest(f"{card.provenance.document_id}|{card.provenance.locator}|{card.provenance.content_hash or ''}"),
        })
        for node in (document_node, entity_node, condition_node, evidence_node):
            nodes[node.node_id] = node
        _edge(edges, evidence_node.node_id, document_node.node_id, "derived_from")
        _edge(
            edges,
            evidence_node.node_id,
            entity_node.node_id,
            {"support": "supports", "contradict": "contradicts"}[card.stance.value],
        )
        _edge(edges, evidence_node.node_id, condition_node.node_id, "conditions")
        _edge(edges, mission_node.node_id, entity_node.node_id, "mentions")
        artifact_hashes.add(_digest(json.dumps({"evidence_id": card.evidence_id, "decision_id": decisions_by_evidence[card.evidence_id].decision_id}, sort_keys=True)))

    snapshot = GraphSnapshot(
        mission_id=mission.mission_id,
        graph_id=_identifier("graph", mission.mission_id),
        nodes=tuple(sorted(nodes.values(), key=lambda node: node.node_id)),
        edges=tuple(sorted(edges.values(), key=lambda edge: edge.edge_id)),
        source_artifact_hashes=tuple(sorted(artifact_hashes)),
    )
    validate_graph_snapshot(snapshot)
    return snapshot


def _node(prefix: str, material: str, node_type: str, label: str, attributes: dict[str, object]) -> GraphNode:
    return GraphNode(_identifier(prefix, material), node_type, label, attributes)


def _edge(edges: dict[str, GraphEdge], source_id: str, target_id: str, relation: str) -> None:
    edge = GraphEdge(_identifier("edge", f"{source_id}|{relation}|{target_id}"), source_id, target_id, relation)
    edges[edge.edge_id] = edge


def _identifier(prefix: str, value: str) -> str:
    return f"{prefix}:{_digest(value)[:32]}"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_conditions(conditions: dict[str, object]) -> str:
    return json.dumps(conditions, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _bounded_label(value: str) -> str:
    return " ".join(value.split())[:300]
