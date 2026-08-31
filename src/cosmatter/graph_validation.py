"""Strict validation for graph snapshots crossing the plugin boundary."""

from __future__ import annotations

import re
from typing import Any

from .graph_contracts import (
    ALLOWED_EDGE_TYPES,
    ALLOWED_NODE_TYPES,
    GRAPH_SCHEMA_VERSION,
    GraphContractError,
    GraphEdge,
    GraphNode,
    GraphSnapshot,
)


_IDENTIFIER = re.compile(r"^[a-z_]+:[a-f0-9]{16,64}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_SENSITIVE_KEY = re.compile(r"(?:quote|excerpt|content|path|token|secret|authorization|password)", re.IGNORECASE)
_PRIVATE_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|/|\\|\.private|case-data)", re.IGNORECASE)


def validate_graph_snapshot(snapshot: GraphSnapshot) -> None:
    """Validate structural, provenance, and data-minimization invariants."""
    if snapshot.schema_version != GRAPH_SCHEMA_VERSION:
        raise GraphContractError("unsupported graph schema version")
    if not snapshot.mission_id.strip() or not _IDENTIFIER.fullmatch(snapshot.graph_id):
        raise GraphContractError("graph identifiers are invalid")
    if snapshot.trust_status != "accepted_evidence_projection_not_scientific_conclusion":
        raise GraphContractError("graph trust status is invalid")
    if not snapshot.source_artifact_hashes or any(not _HASH.fullmatch(item) for item in snapshot.source_artifact_hashes):
        raise GraphContractError("source artifact hashes are invalid")

    node_ids: set[str] = set()
    evidence_count = 0
    for node in snapshot.nodes:
        if node.node_id in node_ids or not _IDENTIFIER.fullmatch(node.node_id):
            raise GraphContractError("graph node identifiers must be unique deterministic identifiers")
        if node.node_type not in ALLOWED_NODE_TYPES or not node.label.strip() or len(node.label) > 300:
            raise GraphContractError("graph node is invalid")
        if not isinstance(node.attributes, dict):
            raise GraphContractError("graph node attributes must be an object")
        _validate_minimized_attributes(node.attributes)
        if node.node_type == "EvidenceCard":
            evidence_count += 1
            if node.attributes.get("review_status") != "accepted":
                raise GraphContractError("only accepted evidence may enter the graph")
            if "claim_digest" not in node.attributes or "provenance_digest" not in node.attributes:
                raise GraphContractError("evidence graph nodes require digested provenance")
        node_ids.add(node.node_id)
    if not snapshot.nodes or not any(node.node_type == "Mission" for node in snapshot.nodes):
        raise GraphContractError("graph requires a mission node")
    if evidence_count == 0:
        raise GraphContractError("graph requires at least one accepted evidence node")

    edge_ids: set[str] = set()
    for edge in snapshot.edges:
        if edge.edge_id in edge_ids or not _IDENTIFIER.fullmatch(edge.edge_id):
            raise GraphContractError("graph edge identifiers must be unique deterministic identifiers")
        if edge.relation not in ALLOWED_EDGE_TYPES:
            raise GraphContractError("graph relation is not allowlisted")
        if edge.source_id not in node_ids or edge.target_id not in node_ids or edge.source_id == edge.target_id:
            raise GraphContractError("graph edge endpoints are invalid")
        edge_ids.add(edge.edge_id)


def validate_graph_payload(payload: object) -> dict[str, Any]:
    """Validate a serialised payload shape before a remote plugin consumes it."""
    if not isinstance(payload, dict):
        raise GraphContractError("graph payload must be an object")
    expected = {"schema_version", "graph_id", "mission_id", "trust_status", "source_artifact_hashes", "nodes", "edges"}
    if set(payload) != expected:
        raise GraphContractError("graph payload fields are invalid")
    if not isinstance(payload["nodes"], list) or not isinstance(payload["edges"], list) or not isinstance(payload["source_artifact_hashes"], list):
        raise GraphContractError("graph payload collections are invalid")
    return graph_snapshot_from_payload(payload).to_dict()


def graph_snapshot_from_payload(payload: dict[str, Any]) -> GraphSnapshot:
    try:
        snapshot = GraphSnapshot(
            schema_version=str(payload["schema_version"]),
            graph_id=str(payload["graph_id"]),
            mission_id=str(payload["mission_id"]),
            trust_status=str(payload["trust_status"]),
            source_artifact_hashes=tuple(str(item) for item in payload["source_artifact_hashes"]),
            nodes=tuple(
                GraphNode(
                    node_id=str(item["node_id"]), node_type=str(item["node_type"]),
                    label=str(item["label"]), attributes=item["attributes"],
                )
                for item in payload["nodes"]
                if isinstance(item, dict) and set(item) == {"node_id", "node_type", "label", "attributes"}
            ),
            edges=tuple(
                GraphEdge(
                    edge_id=str(item["edge_id"]), source_id=str(item["source_id"]),
                    target_id=str(item["target_id"]), relation=str(item["relation"]),
                )
                for item in payload["edges"]
                if isinstance(item, dict) and set(item) == {"edge_id", "source_id", "target_id", "relation"}
            ),
        )
    except (KeyError, TypeError) as error:
        raise GraphContractError("graph payload members are invalid") from error
    if len(snapshot.nodes) != len(payload["nodes"]) or len(snapshot.edges) != len(payload["edges"]):
        raise GraphContractError("graph payload members are invalid")
    validate_graph_snapshot(snapshot)
    return snapshot


def _validate_minimized_attributes(attributes: dict[str, Any]) -> None:
    for key, value in attributes.items():
        if not isinstance(key, str) or _SENSITIVE_KEY.search(key):
            raise GraphContractError("graph attributes may not contain raw content or secrets")
        if isinstance(value, str) and (_PRIVATE_PATH.search(value) or len(value) > 500):
            raise GraphContractError("graph attributes may not contain file paths or oversized text")
        if isinstance(value, dict):
            _validate_minimized_attributes(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, (dict, list)):
                    raise GraphContractError("graph attributes must remain shallow")
