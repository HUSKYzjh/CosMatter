"""Safe comparison of multiple human-reviewed frozen-corpus retrieval routes.

Each route must already have produced an aggregate retrieval evaluation from
the same human-reviewed gold standard.  This module compares only aggregate
metrics; it deliberately excludes paper IDs, labels, queries, provider payloads
and local paths from the resulting submission-facing artifact.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
_EVALUATION_SCHEMA_VERSION = "1.1"
_EVALUATION_FIELDS = {
    "schema_version", "mission_id", "corpus_id", "trust_status", "identity_resolution_policy", "search_index", "k",
    "raw_retrieved_count", "retrieved_count", "doi_resolved_candidate_count", "duplicate_alias_count",
    "gold_relevant_count", "gold_partially_relevant_count", "precision_at_k", "recall_at_k", "ndcg_at_k",
}


class RetrievalRouteComparisonError(ValueError):
    """Raised when route metrics do not share a valid evaluation boundary."""


def compare_human_retrieval_routes(*, routes: object, baseline_route_id: str) -> dict[str, Any]:
    """Compare reviewed aggregate retrieval metrics from one frozen cohort.

    ``routes`` is a list of objects, each with ``route_id`` and the already
    aggregate ``evaluation`` payload.  The function is intentionally strict:
    comparisons across mission, corpus, K, gold population or identity policy
    are rejected rather than normalized into a misleading ranking.
    """
    if not isinstance(routes, list) or not 2 <= len(routes) <= 8:
        raise RetrievalRouteComparisonError("two to eight retrieval routes are required")
    normalized: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for row in routes:
        if not isinstance(row, dict) or set(row) != {"route_id", "evaluation"}:
            raise RetrievalRouteComparisonError("each route must contain only route_id and evaluation")
        route_id = row.get("route_id")
        if not isinstance(route_id, str) or not route_id.strip() or len(route_id) > 80 or route_id in seen:
            raise RetrievalRouteComparisonError("route identifiers must be unique non-empty text")
        evaluation = row.get("evaluation")
        _validate_evaluation(evaluation)
        seen.add(route_id)
        normalized.append((route_id, evaluation))
    if not isinstance(baseline_route_id, str) or baseline_route_id not in seen:
        raise RetrievalRouteComparisonError("baseline route must identify exactly one supplied route")
    first = normalized[0][1]
    boundary = (first["mission_id"], first["corpus_id"], first["k"], first["gold_relevant_count"], first["gold_partially_relevant_count"], first["identity_resolution_policy"])
    for _route_id, evaluation in normalized[1:]:
        candidate = (evaluation["mission_id"], evaluation["corpus_id"], evaluation["k"], evaluation["gold_relevant_count"], evaluation["gold_partially_relevant_count"], evaluation["identity_resolution_policy"])
        if candidate != boundary:
            raise RetrievalRouteComparisonError("all routes must share mission, frozen corpus, K, gold population, and identity-resolution policy")
    baseline = dict(normalized)[baseline_route_id]
    result_routes = []
    for route_id, evaluation in normalized:
        result_routes.append({
            "route_id": route_id,
            "precision_at_k": evaluation["precision_at_k"],
            "recall_at_k": evaluation["recall_at_k"],
            "ndcg_at_k": evaluation["ndcg_at_k"],
            "retrieved_count": evaluation["retrieved_count"],
            "doi_resolved_candidate_count": evaluation["doi_resolved_candidate_count"],
            "duplicate_alias_count": evaluation["duplicate_alias_count"],
            "relative_to_baseline": {
                "baseline_route_id": baseline_route_id,
                "precision_at_k_delta": round(evaluation["precision_at_k"] - baseline["precision_at_k"], 6),
                "recall_at_k_delta": round(evaluation["recall_at_k"] - baseline["recall_at_k"], 6),
                "ndcg_at_k_delta": round(evaluation["ndcg_at_k"] - baseline["ndcg_at_k"], 6),
            },
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "trust_status": "aggregate_comparison_of_human_reviewed_retrieval_metrics",
        "mission_id": first["mission_id"],
        "corpus_id": first["corpus_id"],
        "k": first["k"],
        "gold_relevant_count": first["gold_relevant_count"],
        "gold_partially_relevant_count": first["gold_partially_relevant_count"],
        "identity_resolution_policy": first["identity_resolution_policy"],
        "baseline_route_id": baseline_route_id,
        "route_metrics": result_routes,
        "interpretation_boundary": (
            "This comparison applies only to the declared frozen corpus, reviewed relevance gold, K, and identity policy. "
            "It does not measure total literature coverage, extraction quality, scientific truth, or general agent capability."
        ),
    }


def write_retrieval_route_comparison(run_dir: Path, payload: dict[str, Any]) -> Path:
    _validate_comparison(payload)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "human_retrieval_route_comparison.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _validate_evaluation(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != _EVALUATION_FIELDS:
        raise RetrievalRouteComparisonError("route evaluation has unsupported or missing fields")
    if payload.get("schema_version") != _EVALUATION_SCHEMA_VERSION or payload.get("trust_status") != "metrics_from_human_reviewed_gold_standard":
        raise RetrievalRouteComparisonError("route evaluation is not a human-reviewed frozen-corpus metric")
    if not all(isinstance(payload.get(key), str) and payload[key].strip() for key in ("mission_id", "corpus_id", "identity_resolution_policy")):
        raise RetrievalRouteComparisonError("route evaluation identity is invalid")
    if not isinstance(payload.get("k"), int) or not 1 <= payload["k"] <= 50:
        raise RetrievalRouteComparisonError("route evaluation K is invalid")
    for key in ("raw_retrieved_count", "retrieved_count", "doi_resolved_candidate_count", "duplicate_alias_count", "gold_relevant_count", "gold_partially_relevant_count"):
        if not isinstance(payload.get(key), int) or payload[key] < 0:
            raise RetrievalRouteComparisonError("route evaluation count is invalid")
    for key in ("precision_at_k", "recall_at_k", "ndcg_at_k"):
        if not isinstance(payload.get(key), (int, float)) or not 0.0 <= float(payload[key]) <= 1.0:
            raise RetrievalRouteComparisonError("route evaluation metric is invalid")


def _validate_comparison(payload: object) -> None:
    if not isinstance(payload, dict):
        raise RetrievalRouteComparisonError("route comparison must be an object")
    expected = {
        "schema_version", "trust_status", "mission_id", "corpus_id", "k", "gold_relevant_count",
        "gold_partially_relevant_count", "identity_resolution_policy", "baseline_route_id", "route_metrics",
        "interpretation_boundary",
    }
    if set(payload) != expected or payload.get("schema_version") != SCHEMA_VERSION:
        raise RetrievalRouteComparisonError("route comparison schema is invalid")
    if payload.get("trust_status") != "aggregate_comparison_of_human_reviewed_retrieval_metrics":
        raise RetrievalRouteComparisonError("route comparison trust status is invalid")
    if not isinstance(payload.get("route_metrics"), list) or len(payload["route_metrics"]) < 2:
        raise RetrievalRouteComparisonError("route comparison lacks metrics")
