"""Bounded, DOI-rooted bibliographic navigation graph.

The output is deliberately not evidence: it contains only public identifiers,
directions and depth, never claims, abstracts, full text or provider payloads.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Callable, Iterable, Mapping, Any

from .openalex import normalize_doi


SCHEMA_VERSION = "1.0"
TRUST_STATUS = "public_bibliographic_metadata_not_scientific_evidence"
MAX_NODES = 160
MAX_EDGES_PER_NODE = 25


class CitationExpansionError(ValueError):
    pass


def build_citation_expansion(
    mission_id: str,
    root_doi: str,
    relations: Callable[[str], Mapping[str, Iterable[str]]],
    *,
    max_nodes: int = MAX_NODES,
    max_edges_per_node: int = MAX_EDGES_PER_NODE,
) -> dict[str, Any]:
    """Build two hops using a provider-agnostic relation callback.

    ``relations`` returns optional ``references`` and ``cited_by`` DOI lists.
    Per-node failures are represented safely instead of aborting usable graph
    data gathered before the error.
    """
    if not isinstance(mission_id, str) or not mission_id.strip():
        raise CitationExpansionError("mission_id is invalid")
    root = normalize_doi(root_doi)
    if not 1 <= max_nodes <= MAX_NODES or not 1 <= max_edges_per_node <= MAX_EDGES_PER_NODE:
        raise CitationExpansionError("citation expansion limits are invalid")
    nodes: dict[str, int] = {root: 0}
    edges: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    queue: deque[str] = deque([root])
    while queue and len(nodes) < max_nodes:
        source = queue.popleft()
        depth = nodes[source]
        if depth >= 2:
            continue
        try:
            raw = relations(source)
        except Exception as error:  # provider adapters are allowed to fail independently
            failures.append({"doi": source, "reason": str(error)[:240] or "provider lookup failed"})
            continue
        emitted = 0
        for direction, edge_type in (("references", "citation_reference"), ("cited_by", "citation_cited_by")):
            values = raw.get(direction, ()) if isinstance(raw, Mapping) else ()
            for target_raw in values:
                if emitted >= max_edges_per_node or len(nodes) >= max_nodes:
                    break
                try:
                    target = normalize_doi(target_raw)
                except (TypeError, ValueError):
                    continue
                if target == source:
                    continue
                edge = {"source_doi": source, "target_doi": target, "edge_type": edge_type, "depth": depth + 1}
                if edge not in edges:
                    edges.append(edge)
                    emitted += 1
                if target not in nodes:
                    nodes[target] = depth + 1
                    queue.append(target)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "mission_id": mission_id,
        "trust_status": TRUST_STATUS,
        "root_doi": root,
        "nodes": [{"doi": doi, "depth": depth} for doi, depth in sorted(nodes.items(), key=lambda item: (item[1], item[0]))],
        "edges": edges,
        "failures": failures,
    }
    validate_citation_expansion(payload)
    return payload


def write_citation_expansion(run_dir: Path, payload: dict[str, Any]) -> Path:
    validate_citation_expansion(payload)
    path = run_dir / "citation_expansion.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def validate_citation_expansion(payload: object) -> None:
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION or payload.get("trust_status") != TRUST_STATUS:
        raise CitationExpansionError("citation expansion schema is invalid")
    if not isinstance(payload.get("mission_id"), str) or not isinstance(payload.get("root_doi"), str):
        raise CitationExpansionError("citation expansion identity is invalid")
    if not isinstance(payload.get("nodes"), list) or not 1 <= len(payload["nodes"]) <= MAX_NODES or not isinstance(payload.get("edges"), list):
        raise CitationExpansionError("citation expansion shape is invalid")
    node_ids: set[str] = set()
    for node in payload["nodes"]:
        if not isinstance(node, dict) or set(node) != {"doi", "depth"} or not isinstance(node["depth"], int) or node["depth"] not in {0, 1, 2}:
            raise CitationExpansionError("citation expansion node is invalid")
        node_ids.add(normalize_doi(node["doi"]))
    if normalize_doi(payload["root_doi"]) not in node_ids:
        raise CitationExpansionError("citation expansion root is missing")
    if len(payload["edges"]) > MAX_NODES * MAX_EDGES_PER_NODE:
        raise CitationExpansionError("citation expansion edge count is invalid")
    for edge in payload["edges"]:
        if not isinstance(edge, dict) or set(edge) != {"source_doi", "target_doi", "edge_type", "depth"} or edge["edge_type"] not in {"citation_reference", "citation_cited_by"}:
            raise CitationExpansionError("citation expansion edge is invalid")
        if normalize_doi(edge["source_doi"]) not in node_ids or normalize_doi(edge["target_doi"]) not in node_ids:
            raise CitationExpansionError("citation expansion edge endpoint is invalid")
