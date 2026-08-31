"""Versioned, mission-scoped graph contracts for CosMatter.

The graph is a derived review surface, not a global knowledge graph and not a
new evidence store.  It intentionally excludes source excerpts, private paths,
provider payloads, and unreviewed claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


GRAPH_SCHEMA_VERSION = "1.0"
ALLOWED_NODE_TYPES = frozenset({"Mission", "Paper", "Entity", "Condition", "EvidenceCard"})
ALLOWED_EDGE_TYPES = frozenset({"supports", "contradicts", "conditions", "mentions", "derived_from"})


class GraphContractError(ValueError):
    """Raised when a graph payload violates the bounded graph contract."""


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    node_type: str
    label: str
    attributes: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "label": self.label,
            "attributes": self.attributes,
        }


@dataclass(frozen=True)
class GraphEdge:
    edge_id: str
    source_id: str
    target_id: str
    relation: str

    def to_dict(self) -> dict[str, str]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
        }


@dataclass(frozen=True)
class GraphSnapshot:
    """A deterministic, review-gated graph projection for one mission."""

    mission_id: str
    graph_id: str
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    source_artifact_hashes: tuple[str, ...]
    schema_version: str = GRAPH_SCHEMA_VERSION
    trust_status: str = "accepted_evidence_projection_not_scientific_conclusion"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "graph_id": self.graph_id,
            "mission_id": self.mission_id,
            "trust_status": self.trust_status,
            "source_artifact_hashes": list(self.source_artifact_hashes),
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }
