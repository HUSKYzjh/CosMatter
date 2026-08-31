"""Count-only operational telemetry for one local CosMatter run.

The projection is deliberately narrower than billing or provider observability:
it groups validated receipt and dispatch records, and forwards a cost/latency
record only when a human has already reviewed and recorded that aggregate.
It never exposes request IDs, hashes, queries, URLs, model prompts, documents,
provider payloads, filesystem paths, or credentials.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from .evaluation_operational_disclosure import EvaluationOperationalDisclosureError, load_api_cost_latency
from .external_dispatch import EXTERNAL_DISPATCH_OPERATIONS, ExternalDispatchError, load_external_dispatch_ledger
from .models import MissionBrief
from .provider_receipts import ProviderReceiptError, load_provider_receipts


OPERATIONAL_TELEMETRY_SCHEMA_VERSION = "cosmatter.operational-telemetry/v1"
OPERATIONAL_TELEMETRY_TRUST_STATUS = "loopback_aggregate_operational_telemetry_not_billing_or_scientific_evidence"
_COST_LATENCY_STATUSES = {"not_recorded", "recorded", "invalid"}
# Every ledger operation must remain observable in the count-only projection;
# reuse the dispatch vocabulary rather than maintaining a drift-prone copy.
_DISPATCH_OPERATIONS = EXTERNAL_DISPATCH_OPERATIONS
_TELEMETRY_FIELDS = {"schema_version", "mission_id", "trust_status", "provider_operations", "dispatch_operations", "cost_latency_status", "cost_latency"}


class OperationalTelemetryError(ValueError):
    """Raised when a local telemetry projection cannot be safely derived."""


def operational_telemetry(run_dir: Path, mission: MissionBrief) -> dict[str, Any]:
    """Summarise validated local receipts and human-reviewed cost disclosures."""
    try:
        receipts = load_provider_receipts(run_dir)
        ledger = load_external_dispatch_ledger(run_dir, mission.mission_id)
    except (ProviderReceiptError, ExternalDispatchError) as error:
        raise OperationalTelemetryError("operational telemetry inputs are invalid") from error
    provider_operations = _provider_operations(receipts)
    dispatch_operations = _dispatch_operations(ledger["entries"])
    cost_latency_status, cost_latency = _cost_latency(run_dir, mission.mission_id)
    result = {
        "schema_version": OPERATIONAL_TELEMETRY_SCHEMA_VERSION,
        "mission_id": mission.mission_id,
        "trust_status": OPERATIONAL_TELEMETRY_TRUST_STATUS,
        "provider_operations": provider_operations,
        "dispatch_operations": dispatch_operations,
        "cost_latency_status": cost_latency_status,
        "cost_latency": cost_latency,
    }
    validate_operational_telemetry(result, expected_mission_id=mission.mission_id)
    return result


def _provider_operations(receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"request_count": 0, "successful_response_count": 0, "client_error_count": 0, "server_error_count": 0, "other_status_count": 0})
    for receipt in receipts:
        key = (receipt["provider"], receipt["operation"])
        item = grouped[key]
        item["request_count"] += 1
        status = receipt["status_code"]
        if 200 <= status < 300:
            item["successful_response_count"] += 1
        elif 400 <= status < 500:
            item["client_error_count"] += 1
        elif 500 <= status < 600:
            item["server_error_count"] += 1
        else:
            item["other_status_count"] += 1
    return [
        {"provider": provider, "operation": operation, **counts}
        for (provider, operation), counts in sorted(grouped.items())
    ]


def _dispatch_operations(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, int]] = {operation: {"dispatch_count": 0, "completed_count": 0, "incomplete_count": 0, "unknown_outcome_count": 0} for operation in _DISPATCH_OPERATIONS}
    for entry in entries:
        item = grouped[entry["operation"]]
        item["dispatch_count"] += 1
        state = entry["state"]
        if state == "completed":
            item["completed_count"] += 1
        elif state == "dispatched":
            item["incomplete_count"] += 1
        else:
            item["unknown_outcome_count"] += 1
    return [{"operation": operation, **counts} for operation, counts in grouped.items() if counts["dispatch_count"]]


def _cost_latency(run_dir: Path, mission_id: str) -> tuple[str, list[dict[str, Any]]]:
    path = run_dir / "evaluation_api_cost_latency.json"
    if not path.exists():
        return "not_recorded", []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        corpus_id = raw.get("corpus_id") if isinstance(raw, dict) else None
        if not isinstance(corpus_id, str):
            raise EvaluationOperationalDisclosureError("cost disclosure identity is invalid")
        disclosure = load_api_cost_latency(path, mission_id=mission_id, corpus_id=corpus_id)
    except (OSError, json.JSONDecodeError, EvaluationOperationalDisclosureError):
        return "invalid", []
    return "recorded", [
        {
            "provider_id": item["provider_id"],
            "request_count": item["request_count"],
            "successful_request_count": item["successful_request_count"],
            "failed_request_count": item["failed_request_count"],
            "currency": item["currency"],
            "total_cost": item["total_cost"],
            "median_latency_seconds": item["median_latency_seconds"],
            "p95_latency_seconds": item["p95_latency_seconds"],
        }
        for item in disclosure["providers"]
    ]


def validate_operational_telemetry(payload: object, *, expected_mission_id: str | None = None) -> None:
    if not isinstance(payload, dict) or set(payload) != _TELEMETRY_FIELDS or payload.get("schema_version") != OPERATIONAL_TELEMETRY_SCHEMA_VERSION or payload.get("trust_status") != OPERATIONAL_TELEMETRY_TRUST_STATUS:
        raise OperationalTelemetryError("operational telemetry fields are invalid")
    mission_id = payload.get("mission_id")
    if not isinstance(mission_id, str) or not mission_id.strip() or (expected_mission_id is not None and mission_id != expected_mission_id):
        raise OperationalTelemetryError("operational telemetry mission is invalid")
    provider_operations = payload.get("provider_operations")
    if not isinstance(provider_operations, list) or len(provider_operations) > 20:
        raise OperationalTelemetryError("operational telemetry provider operations are invalid")
    seen_provider_operations: set[tuple[str, str]] = set()
    for item in provider_operations:
        fields = {"provider", "operation", "request_count", "successful_response_count", "client_error_count", "server_error_count", "other_status_count"}
        if not isinstance(item, dict) or set(item) != fields or item.get("provider") not in {"sciverse", "mineru"} or not isinstance(item.get("operation"), str):
            raise OperationalTelemetryError("operational telemetry provider operation is invalid")
        key = (item["provider"], item["operation"])
        if key in seen_provider_operations:
            raise OperationalTelemetryError("operational telemetry provider operation is duplicated")
        seen_provider_operations.add(key)
        counts = [item[name] for name in ("request_count", "successful_response_count", "client_error_count", "server_error_count", "other_status_count")]
        if any(not isinstance(value, int) or value < 0 or value > 10_000_000 for value in counts) or item["request_count"] != sum(counts[1:]):
            raise OperationalTelemetryError("operational telemetry provider counts are invalid")
    dispatch_operations = payload.get("dispatch_operations")
    if not isinstance(dispatch_operations, list) or len(dispatch_operations) > len(_DISPATCH_OPERATIONS):
        raise OperationalTelemetryError("operational telemetry dispatch operations are invalid")
    seen_dispatch: set[str] = set()
    for item in dispatch_operations:
        fields = {"operation", "dispatch_count", "completed_count", "incomplete_count", "unknown_outcome_count"}
        if not isinstance(item, dict) or set(item) != fields or item.get("operation") not in _DISPATCH_OPERATIONS or item["operation"] in seen_dispatch:
            raise OperationalTelemetryError("operational telemetry dispatch operation is invalid")
        seen_dispatch.add(item["operation"])
        counts = [item[name] for name in ("dispatch_count", "completed_count", "incomplete_count", "unknown_outcome_count")]
        if any(not isinstance(value, int) or value < 0 or value > 10_000_000 for value in counts) or counts[0] != sum(counts[1:]):
            raise OperationalTelemetryError("operational telemetry dispatch counts are invalid")
    status = payload.get("cost_latency_status")
    cost_latency = payload.get("cost_latency")
    if status not in _COST_LATENCY_STATUSES or not isinstance(cost_latency, list) or (status != "recorded" and cost_latency):
        raise OperationalTelemetryError("operational telemetry cost disclosure is invalid")
    seen_cost_providers: set[str] = set()
    for item in cost_latency:
        fields = {"provider_id", "request_count", "successful_request_count", "failed_request_count", "currency", "total_cost", "median_latency_seconds", "p95_latency_seconds"}
        if not isinstance(item, dict) or set(item) != fields or not isinstance(item.get("provider_id"), str) or not item["provider_id"] or item["provider_id"] in seen_cost_providers or item.get("currency") not in {"CNY", "USD", "EUR", "not_applicable"}:
            raise OperationalTelemetryError("operational telemetry cost item is invalid")
        seen_cost_providers.add(item["provider_id"])
        if any(not isinstance(item[name], int) or item[name] < 0 for name in ("request_count", "successful_request_count", "failed_request_count")) or item["request_count"] != item["successful_request_count"] + item["failed_request_count"]:
            raise OperationalTelemetryError("operational telemetry cost request counts are invalid")
        if any(not isinstance(item[name], (int, float)) or isinstance(item[name], bool) or not math.isfinite(item[name]) or item[name] < 0 for name in ("total_cost", "median_latency_seconds", "p95_latency_seconds")) or item["p95_latency_seconds"] < item["median_latency_seconds"]:
            raise OperationalTelemetryError("operational telemetry cost values are invalid")
