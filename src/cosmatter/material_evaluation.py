"""Independent human-gold evaluation for review-gated material fact artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MATERIAL_GOLD_SCHEMA_VERSION = "1.0"
MATERIAL_EVALUATION_SCHEMA_VERSION = "1.0"
_GOLD_FIELDS = {"schema_version", "mission_id", "corpus_id", "trust_status", "documents"}
_DOCUMENT_FIELDS = {"document_id", "expected_facts"}
_FACT_FIELDS = {"category", "name", "normalized_value", "normalized_unit", "locator"}
_CATEGORIES = {
    "composition", "structure", "property", "processing",
    "experimental_condition", "simulation_method",
}


class MaterialFactEvaluationError(ValueError):
    """Raised for incomplete human gold or invalid reviewed fact artifacts."""


def load_reviewed_material_fact_gold(
    path: Path,
    *,
    mission_id: str,
    corpus_id: str,
    corpus_document_ids: set[str],
) -> dict[str, tuple[dict[str, Any], ...]]:
    """Load a complete human gold file that contains no source quote text."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise MaterialFactEvaluationError("reviewed material-fact gold file does not exist") from error
    except json.JSONDecodeError as error:
        raise MaterialFactEvaluationError("reviewed material-fact gold file is not valid JSON") from error
    if not isinstance(payload, dict) or set(payload) != _GOLD_FIELDS:
        raise MaterialFactEvaluationError("reviewed material-fact gold has unsupported or missing fields")
    if (
        payload.get("schema_version") != MATERIAL_GOLD_SCHEMA_VERSION
        or payload.get("mission_id") != mission_id
        or payload.get("corpus_id") != corpus_id
        or payload.get("trust_status") != "human_reviewed_material_fact_gold_for_evaluation"
    ):
        raise MaterialFactEvaluationError("reviewed material-fact gold identity or trust status is invalid")
    documents = payload.get("documents")
    if not isinstance(documents, list) or len(documents) != len(corpus_document_ids):
        raise MaterialFactEvaluationError("material-fact gold must cover every frozen corpus document")
    result: dict[str, tuple[dict[str, Any], ...]] = {}
    total = 0
    for item in documents:
        if not isinstance(item, dict) or set(item) != _DOCUMENT_FIELDS:
            raise MaterialFactEvaluationError("material-fact gold document fields are invalid")
        document_id = item.get("document_id")
        if not isinstance(document_id, str) or document_id not in corpus_document_ids or document_id in result:
            raise MaterialFactEvaluationError("material-fact gold document identity is invalid")
        facts = _facts(item.get("expected_facts"))
        result[document_id] = tuple(facts)
        total += len(facts)
    if set(result) != corpus_document_ids:
        raise MaterialFactEvaluationError("material-fact gold document IDs do not match the frozen corpus")
    if total == 0:
        raise MaterialFactEvaluationError("material-fact gold must include at least one expected fact")
    return result


def material_fact_evaluation_from_gold(
    *,
    mission_id: str,
    corpus_id: str,
    gold: dict[str, tuple[dict[str, Any], ...]],
    reviewed_artifacts: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Score final review-gated fact records; this is not raw-LLM accuracy."""
    expected = {
        _fact_key(document_id, fact)
        for document_id, facts in gold.items()
        for fact in facts
    }
    observed: set[tuple[str, str, str, str, str, str]] = set()
    base_pairs: list[tuple[tuple[str, str, str, str, str], str]] = []
    for artifact in reviewed_artifacts:
        if not isinstance(artifact, dict) or artifact.get("mission_id") != mission_id:
            raise MaterialFactEvaluationError("reviewed material fact artifact belongs to a different mission")
        document_id = artifact.get("document_id")
        facts = artifact.get("facts")
        if not isinstance(document_id, str) or document_id not in gold or not isinstance(facts, list):
            raise MaterialFactEvaluationError("reviewed material fact artifact identity is invalid")
        for fact in facts:
            normalized = _fact_from_reviewed_artifact(fact)
            observed.add(_fact_key(document_id, normalized))
            base_pairs.append((_fact_base_key(document_id, normalized), _unit_key(normalized["normalized_unit"])))
    hits = observed & expected
    precision = len(hits) / len(observed) if observed else 0.0
    recall = len(hits) / len(expected) if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    expected_units = {_fact_base_key(document_id, fact): _unit_key(fact["normalized_unit"]) for document_id, facts in gold.items() for fact in facts}
    eligible_unit_pairs = [(base, unit) for base, unit in base_pairs if base in expected_units]
    unit_correct = sum(expected_units[base] == unit for base, unit in eligible_unit_pairs)
    return {
        "schema_version": MATERIAL_EVALUATION_SCHEMA_VERSION,
        "mission_id": mission_id,
        "corpus_id": corpus_id,
        "trust_status": "metrics_for_review_gated_material_fact_pipeline_not_raw_llm_accuracy",
        "gold_fact_count": len(expected),
        "reviewed_fact_count": len(observed),
        "exact_match_count": len(hits),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "unit_match_denominator": len(eligible_unit_pairs),
        "unit_match_accuracy": round(unit_correct / len(eligible_unit_pairs), 6) if eligible_unit_pairs else 0.0,
    }


def write_material_fact_evaluation(run_dir: Path, result: dict[str, Any]) -> Path:
    fields = {
        "schema_version", "mission_id", "corpus_id", "trust_status",
        "gold_fact_count", "reviewed_fact_count", "exact_match_count",
        "precision", "recall", "f1", "unit_match_denominator", "unit_match_accuracy",
    }
    if not isinstance(result, dict) or set(result) != fields:
        raise MaterialFactEvaluationError("material-fact evaluation result is invalid")
    path = run_dir / "human_material_fact_evaluation.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _facts(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or len(raw) > 500:
        raise MaterialFactEvaluationError("material-fact gold expected_facts is invalid")
    facts: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for item in raw:
        if not isinstance(item, dict) or set(item) != _FACT_FIELDS:
            raise MaterialFactEvaluationError("material-fact gold fact fields are invalid")
        if item.get("category") not in _CATEGORIES or not isinstance(item.get("name"), str) or not item["name"].strip() or not isinstance(item.get("locator"), str) or not item["locator"].strip():
            raise MaterialFactEvaluationError("material-fact gold fact category, name, or locator is invalid")
        if item.get("normalized_value") is not None and not isinstance(item["normalized_value"], (str, int, float)):
            raise MaterialFactEvaluationError("material-fact gold normalized_value is invalid")
        if item.get("normalized_unit") is not None and (not isinstance(item["normalized_unit"], str) or not item["normalized_unit"].strip()):
            raise MaterialFactEvaluationError("material-fact gold normalized_unit is invalid")
        normalized = {
            "category": item["category"],
            "name": item["name"].strip(),
            "normalized_value": item["normalized_value"],
            "normalized_unit": item["normalized_unit"].strip() if isinstance(item["normalized_unit"], str) else None,
            "locator": item["locator"].strip(),
        }
        identity = _fact_base_key("", normalized)
        if identity in seen:
            raise MaterialFactEvaluationError("material-fact gold contains duplicate expected facts")
        seen.add(identity)
        facts.append(normalized)
    return facts


def _fact_from_reviewed_artifact(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise MaterialFactEvaluationError("reviewed material fact is invalid")
    subset = {key: raw.get(key) for key in _FACT_FIELDS}
    return _facts([subset])[0]


def _fact_key(document_id: str, fact: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    return (
        document_id,
        str(fact["category"]).casefold(),
        str(fact["name"]).strip().casefold(),
        _value_key(fact["normalized_value"]),
        str(fact["locator"]).strip().casefold(),
        _unit_key(fact["normalized_unit"]),
    )


def _fact_base_key(document_id: str, fact: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        document_id,
        str(fact["category"]).casefold(),
        str(fact["name"]).strip().casefold(),
        _value_key(fact["normalized_value"]),
        str(fact["locator"]).strip().casefold(),
    )


def _unit_key(value: object) -> str:
    return value.strip().casefold() if isinstance(value, str) else "<none>"


def _value_key(value: object) -> str:
    if value is None:
        return "<none>"
    if isinstance(value, float):
        return format(value, ".12g")
    return str(value).strip().casefold()
