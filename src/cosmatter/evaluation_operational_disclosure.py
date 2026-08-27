"""Safe, aggregate operational disclosures for a reviewed corpus evaluation.

These records deliberately capture only the *kind* and count of operational
failures plus aggregate provider cost/latency.  They must never become a
backdoor for paper titles, full text, locators, local paths, credentials,
provider request identifiers, or raw provider responses.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any


OPERATIONAL_DISCLOSURE_SCHEMA_VERSION = "1.0"
FAILURE_CASE_LOG_FILENAME = "evaluation_failure_case_log.json"
API_COST_LATENCY_FILENAME = "evaluation_api_cost_latency.json"
FAILURE_CASE_TRUST_STATUS = "human_reviewed_aggregate_evaluation_failure_case_log"
API_COST_LATENCY_TRUST_STATUS = "human_reviewed_aggregate_evaluation_api_cost_latency"

_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
_FAILURE_CATEGORIES = {
    "retrieval_identity_mismatch",
    "metadata_missing_or_ambiguous",
    "parser_or_conversion_failure",
    "source_locator_missing_or_invalid",
    "fact_normalization_or_unit_error",
    "citation_or_evidence_review_failure",
    "condition_comparability_incomplete",
    "gap_evidence_or_counterevidence_incomplete",
    "provider_rate_limit_or_timeout",
    "provider_schema_or_content_access_failure",
    "other_reviewed_operational_failure",
}
_RESOLUTION_STATUSES = {"open", "mitigated", "excluded_from_evaluation", "accepted_with_limit"}
_CURRENCIES = {"CNY", "USD", "EUR", "not_applicable"}


class EvaluationOperationalDisclosureError(ValueError):
    """Raised when an operational disclosure exceeds its safe schema."""


def failure_case_log_from_review(*, mission_id: str, corpus_id: str, payload: object) -> dict[str, Any]:
    _validate_failure_case_log(payload)
    assert isinstance(payload, dict)
    _require_identity(payload, mission_id=mission_id, corpus_id=corpus_id)
    return payload


def api_cost_latency_from_review(*, mission_id: str, corpus_id: str, payload: object) -> dict[str, Any]:
    _validate_api_cost_latency(payload)
    assert isinstance(payload, dict)
    _require_identity(payload, mission_id=mission_id, corpus_id=corpus_id)
    return payload


def load_failure_case_log(path: Path, *, mission_id: str, corpus_id: str) -> dict[str, Any]:
    return failure_case_log_from_review(
        mission_id=mission_id, corpus_id=corpus_id, payload=_read_json(path, "evaluation failure-case log")
    )


def load_api_cost_latency(path: Path, *, mission_id: str, corpus_id: str) -> dict[str, Any]:
    return api_cost_latency_from_review(
        mission_id=mission_id, corpus_id=corpus_id, payload=_read_json(path, "evaluation API cost/latency disclosure")
    )


def write_failure_case_log(run_dir: Path, payload: object) -> Path:
    _validate_failure_case_log(payload)
    return _write(run_dir / FAILURE_CASE_LOG_FILENAME, payload)


def write_api_cost_latency(run_dir: Path, payload: object) -> Path:
    _validate_api_cost_latency(payload)
    return _write(run_dir / API_COST_LATENCY_FILENAME, payload)


def _read_json(path: Path, name: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationOperationalDisclosureError(f"{name} is missing or invalid") from error


def _write(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _require_identity(payload: dict[str, Any], *, mission_id: str, corpus_id: str) -> None:
    if payload["mission_id"] != mission_id or payload["corpus_id"] != corpus_id:
        raise EvaluationOperationalDisclosureError("operational disclosure does not match this frozen evaluation")


def _validate_identity(payload: dict[str, Any], *, trust_status: str) -> None:
    if payload.get("schema_version") != OPERATIONAL_DISCLOSURE_SCHEMA_VERSION or payload.get("trust_status") != trust_status:
        raise EvaluationOperationalDisclosureError("operational disclosure schema or trust status is invalid")
    for key in ("mission_id", "corpus_id"):
        if not isinstance(payload.get(key), str) or not _IDENTIFIER.fullmatch(payload[key]):
            raise EvaluationOperationalDisclosureError("operational disclosure identity is invalid")


def _validate_failure_case_log(payload: object) -> None:
    expected = {"schema_version", "mission_id", "corpus_id", "trust_status", "categories"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise EvaluationOperationalDisclosureError("evaluation failure-case log has unsupported or missing fields")
    _validate_identity(payload, trust_status=FAILURE_CASE_TRUST_STATUS)
    categories = payload.get("categories")
    if not isinstance(categories, list) or len(categories) > len(_FAILURE_CATEGORIES):
        raise EvaluationOperationalDisclosureError("evaluation failure-case categories are invalid")
    seen: set[str] = set()
    for item in categories:
        if not isinstance(item, dict) or set(item) != {"category", "occurrence_count", "resolution_status"}:
            raise EvaluationOperationalDisclosureError("evaluation failure-case item is invalid")
        category = item.get("category")
        if category not in _FAILURE_CATEGORIES or category in seen:
            raise EvaluationOperationalDisclosureError("evaluation failure-case category is invalid or duplicated")
        seen.add(category)
        if not isinstance(item.get("occurrence_count"), int) or not 0 <= item["occurrence_count"] <= 100_000:
            raise EvaluationOperationalDisclosureError("evaluation failure-case count is invalid")
        if item.get("resolution_status") not in _RESOLUTION_STATUSES:
            raise EvaluationOperationalDisclosureError("evaluation failure-case resolution status is invalid")


def _validate_api_cost_latency(payload: object) -> None:
    expected = {"schema_version", "mission_id", "corpus_id", "trust_status", "measurement_scope", "providers"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise EvaluationOperationalDisclosureError("evaluation API cost/latency disclosure has unsupported or missing fields")
    _validate_identity(payload, trust_status=API_COST_LATENCY_TRUST_STATUS)
    scope = payload.get("measurement_scope")
    if not isinstance(scope, str) or not scope.strip() or len(scope) > 160:
        raise EvaluationOperationalDisclosureError("evaluation API cost/latency measurement scope is invalid")
    providers = payload.get("providers")
    if not isinstance(providers, list) or len(providers) > 20:
        raise EvaluationOperationalDisclosureError("evaluation API cost/latency provider list is invalid")
    seen: set[str] = set()
    expected_provider = {
        "provider_id", "request_count", "successful_request_count", "failed_request_count",
        "currency", "total_cost", "median_latency_seconds", "p95_latency_seconds",
    }
    for item in providers:
        if not isinstance(item, dict) or set(item) != expected_provider:
            raise EvaluationOperationalDisclosureError("evaluation API cost/latency provider item is invalid")
        provider_id = item.get("provider_id")
        if not isinstance(provider_id, str) or not _IDENTIFIER.fullmatch(provider_id) or provider_id in seen:
            raise EvaluationOperationalDisclosureError("evaluation API cost/latency provider identity is invalid or duplicated")
        seen.add(provider_id)
        if item.get("currency") not in _CURRENCIES:
            raise EvaluationOperationalDisclosureError("evaluation API cost/latency currency is invalid")
        for key in ("request_count", "successful_request_count", "failed_request_count"):
            if not isinstance(item.get(key), int) or not 0 <= item[key] <= 10_000_000:
                raise EvaluationOperationalDisclosureError("evaluation API cost/latency request count is invalid")
        if item["successful_request_count"] + item["failed_request_count"] != item["request_count"]:
            raise EvaluationOperationalDisclosureError("evaluation API cost/latency request totals are inconsistent")
        for key in ("total_cost", "median_latency_seconds", "p95_latency_seconds"):
            value = item.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise EvaluationOperationalDisclosureError("evaluation API cost/latency numeric value is invalid")
        if item["p95_latency_seconds"] < item["median_latency_seconds"]:
            raise EvaluationOperationalDisclosureError("evaluation API cost/latency quantiles are inconsistent")
        if item["currency"] == "not_applicable" and item["total_cost"] != 0:
            raise EvaluationOperationalDisclosureError("not_applicable cost currency requires zero total cost")
