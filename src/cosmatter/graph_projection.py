"""Read-only serialisation boundary for external graph consumers."""

from __future__ import annotations

from typing import Any

from .graph_contracts import GraphSnapshot
from .graph_contracts import ALLOWED_NODE_TYPES
from .graph_validation import validate_graph_payload, validate_graph_snapshot


MAX_GRAPH_PAGE_SIZE = 100


def external_graph_projection(snapshot: GraphSnapshot) -> dict[str, Any]:
    """Return the exact allowlisted graph contract after re-validating it."""
    validate_graph_snapshot(snapshot)
    payload = snapshot.to_dict()
    validate_graph_payload(payload)
    return payload


def bounded_graph_projection(
    snapshot: GraphSnapshot, *, node_types: tuple[str, ...] = (), offset: int = 0, limit: int = 50
) -> dict[str, Any]:
    """Return one bounded, self-describing node page without mutating a snapshot."""
    validate_graph_snapshot(snapshot)
    if offset < 0 or not 1 <= limit <= MAX_GRAPH_PAGE_SIZE:
        raise ValueError("graph page offset or limit is invalid")
    if any(node_type not in ALLOWED_NODE_TYPES for node_type in node_types):
        raise ValueError("graph node type filter is invalid")
    requested_types = tuple(sorted(set(node_types)))
    matching = tuple(node for node in snapshot.nodes if not requested_types or node.node_type in requested_types)
    page_nodes = matching[offset : offset + limit]
    page_ids = {node.node_id for node in page_nodes}
    page_edges = tuple(edge for edge in snapshot.edges if edge.source_id in page_ids and edge.target_id in page_ids)
    return {
        "schema_version": snapshot.schema_version,
        "graph_id": snapshot.graph_id,
        "mission_id": snapshot.mission_id,
        "trust_status": snapshot.trust_status,
        "source_artifact_hashes": list(snapshot.source_artifact_hashes),
        "nodes": [node.to_dict() for node in page_nodes],
        "edges": [edge.to_dict() for edge in page_edges],
        "page": {
            "node_types": list(requested_types), "offset": offset, "limit": limit,
            "node_total": len(matching), "edge_count": len(page_edges),
            "truncated": offset + len(page_nodes) < len(matching),
            "empty_result_meaning": "No matching nodes in this bounded mission graph page; this does not establish a global absence.",
        },
    }
