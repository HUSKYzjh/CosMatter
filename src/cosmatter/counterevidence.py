"""Gate discrepancy analysis on actually executed counterevidence searches."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .models import FlightPlan


class CounterevidenceGateError(ValueError):
    """Raised when a planned counterevidence search was not actually executed."""


@dataclass(frozen=True)
class CounterevidenceExecution:
    planned_query_count: int
    executed_query_count: int
    search_count: int
    candidate_history_sha256: str


def require_executed_counterevidence(
    plan: FlightPlan,
    candidate_history: dict[str, Any],
) -> CounterevidenceExecution:
    """Require every approved counter query to appear in local search history.

    Presence in history proves the bounded retrieval step ran even if a given
    query returned zero candidates.  It does not prove relevance or validate a
    scientific claim; those remain separate human-review steps.
    """
    if not plan.counter_queries:
        raise CounterevidenceGateError("discrepancy analysis requires approved counterevidence queries")
    searches = _searches(candidate_history)
    executed = {entry["query"] for entry in searches}
    missing = tuple(query for query in plan.counter_queries if query not in executed)
    if missing:
        raise CounterevidenceGateError(
            "counterevidence retrieval must execute every approved counter query before discrepancy or Gap analysis"
        )
    fingerprint_payload = [
        {
            "query_sha256": hashlib.sha256(entry["query"].encode("utf-8")).hexdigest(),
            "candidate_document_ids": [
                item.get("document_id") for item in entry["candidates"]
                if isinstance(item, dict) and isinstance(item.get("document_id"), str)
            ],
        }
        for entry in searches
    ]
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return CounterevidenceExecution(
        planned_query_count=len(plan.counter_queries),
        executed_query_count=len(plan.counter_queries),
        search_count=len(searches),
        candidate_history_sha256=fingerprint,
    )


def _searches(payload: object) -> tuple[dict[str, Any], ...]:
    if not isinstance(payload, dict):
        raise CounterevidenceGateError("retrieval candidate history must be an object")
    searches = payload.get("searches")
    if searches is None:
        query = payload.get("query")
        candidates = payload.get("candidates")
        if isinstance(query, str) and query.strip() and isinstance(candidates, list):
            searches = [{"query": query, "candidates": candidates}]
    if not isinstance(searches, list) or not searches:
        raise CounterevidenceGateError("retrieval candidate history has no executed searches")
    normalized: list[dict[str, Any]] = []
    for entry in searches:
        if not isinstance(entry, dict) or not isinstance(entry.get("query"), str) or not entry["query"].strip():
            raise CounterevidenceGateError("retrieval search history entry is invalid")
        candidates = entry.get("candidates")
        if not isinstance(candidates, list):
            raise CounterevidenceGateError("retrieval search history candidate list is invalid")
        normalized.append({"query": entry["query"].strip(), "candidates": candidates})
    return tuple(normalized)
