"""Independent human review of evidence locators, conditions, and contradiction labels."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import EvidenceCard, Stance


EVIDENCE_QUALITY_SCHEMA_VERSION = "1.0"
_TEMPLATE_FIELDS = {"schema_version", "mission_id", "trust_status", "assessments"}
_ASSESSMENT_FIELDS = {
    "evidence_id", "document_id", "locator", "predicted_stance",
    "citation_locator_correct", "conditions_complete", "predicted_contradiction_correct",
}


class EvidenceQualityEvaluationError(ValueError):
    """Raised when an evidence-quality review is incomplete or stale."""


def evidence_quality_review_template(*, mission_id: str, cards: tuple[EvidenceCard, ...]) -> dict[str, Any]:
    """Create narrow review slots without copying claims, quotes, or provider data."""
    if not isinstance(mission_id, str) or not mission_id.strip() or not cards:
        raise EvidenceQualityEvaluationError("evidence-quality review requires a mission and accepted evidence")
    identifiers = [card.evidence_id for card in cards]
    if len(set(identifiers)) != len(identifiers):
        raise EvidenceQualityEvaluationError("evidence-quality review cards must have unique identifiers")
    return {
        "schema_version": EVIDENCE_QUALITY_SCHEMA_VERSION,
        "mission_id": mission_id,
        "trust_status": "blank_human_evidence_quality_review_template_not_evaluation_result",
        "assessments": [
            {
                "evidence_id": card.evidence_id,
                "document_id": card.provenance.document_id,
                "locator": card.provenance.locator,
                "predicted_stance": card.stance.value,
                "citation_locator_correct": None,
                "conditions_complete": None,
                "predicted_contradiction_correct": None,
            }
            for card in cards
        ],
    }


def write_evidence_quality_review_template(run_dir: Path, template: dict[str, Any]) -> Path:
    _validate_template(template, reviewed=False)
    path = run_dir / "human_evidence_quality_review_template.json"
    path.write_text(json.dumps(template, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_reviewed_evidence_quality_assessment(
    path: Path,
    *,
    mission_id: str,
    cards: tuple[EvidenceCard, ...],
) -> tuple[dict[str, Any], ...]:
    """Load an exact review of the current accepted evidence set."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise EvidenceQualityEvaluationError("reviewed evidence-quality assessment file does not exist") from error
    except json.JSONDecodeError as error:
        raise EvidenceQualityEvaluationError("reviewed evidence-quality assessment file is not valid JSON") from error
    _validate_template(payload, reviewed=True)
    if payload["mission_id"] != mission_id:
        raise EvidenceQualityEvaluationError("reviewed evidence-quality assessment does not belong to this mission")
    expected = {
        card.evidence_id: (card.provenance.document_id, card.provenance.locator, card.stance.value)
        for card in cards
    }
    if len(expected) != len(cards):
        raise EvidenceQualityEvaluationError("current evidence IDs are not unique")
    observed: dict[str, tuple[str, str, str]] = {}
    for item in payload["assessments"]:
        evidence_id = item["evidence_id"]
        if evidence_id in observed:
            raise EvidenceQualityEvaluationError("reviewed evidence-quality assessment contains duplicate evidence IDs")
        observed[evidence_id] = (item["document_id"], item["locator"], item["predicted_stance"])
    if observed != expected:
        raise EvidenceQualityEvaluationError("reviewed evidence-quality assessment is stale or does not cover the current accepted evidence")
    return tuple(payload["assessments"])


def evidence_quality_evaluation_from_assessments(*, mission_id: str, assessments: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    """Summarize human verification; no assessment-level data leaves the review file."""
    if not isinstance(mission_id, str) or not mission_id.strip() or not assessments:
        raise EvidenceQualityEvaluationError("evidence-quality evaluation requires reviewed assessments")
    predicted_contradictions = [item for item in assessments if item["predicted_stance"] == Stance.CONTRADICT.value]
    correct_citations = sum(item["citation_locator_correct"] is True for item in assessments)
    complete_conditions = sum(item["conditions_complete"] is True for item in assessments)
    correct_contradictions = sum(item["predicted_contradiction_correct"] is True for item in predicted_contradictions)
    return {
        "schema_version": EVIDENCE_QUALITY_SCHEMA_VERSION,
        "mission_id": mission_id,
        "trust_status": "metrics_from_human_reviewed_evidence_locator_condition_and_contradiction_audit",
        "evidence_count": len(assessments),
        "predicted_contradiction_count": len(predicted_contradictions),
        "citation_precision": round(correct_citations / len(assessments), 6),
        "condition_completeness": round(complete_conditions / len(assessments), 6),
        "contradiction_precision": round(correct_contradictions / len(predicted_contradictions), 6) if predicted_contradictions else 0.0,
    }


def write_evidence_quality_evaluation(run_dir: Path, result: dict[str, Any]) -> Path:
    expected = {
        "schema_version", "mission_id", "trust_status", "evidence_count", "predicted_contradiction_count",
        "citation_precision", "condition_completeness", "contradiction_precision",
    }
    if not isinstance(result, dict) or set(result) != expected:
        raise EvidenceQualityEvaluationError("evidence-quality evaluation result is invalid")
    path = run_dir / "human_evidence_quality_evaluation.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _validate_template(payload: object, *, reviewed: bool) -> None:
    if not isinstance(payload, dict) or set(payload) != _TEMPLATE_FIELDS:
        raise EvidenceQualityEvaluationError("evidence-quality assessment has unsupported or missing fields")
    expected_status = (
        "human_reviewed_evidence_quality_assessment_for_evaluation"
        if reviewed else "blank_human_evidence_quality_review_template_not_evaluation_result"
    )
    if payload.get("schema_version") != EVIDENCE_QUALITY_SCHEMA_VERSION or payload.get("trust_status") != expected_status:
        raise EvidenceQualityEvaluationError("evidence-quality assessment schema or trust status is invalid")
    if not isinstance(payload.get("mission_id"), str) or not payload["mission_id"].strip():
        raise EvidenceQualityEvaluationError("evidence-quality assessment mission identity is invalid")
    assessments = payload.get("assessments")
    if not isinstance(assessments, list) or not assessments:
        raise EvidenceQualityEvaluationError("evidence-quality assessment must contain at least one item")
    seen: set[str] = set()
    for item in assessments:
        if not isinstance(item, dict) or set(item) != _ASSESSMENT_FIELDS:
            raise EvidenceQualityEvaluationError("evidence-quality assessment fields are invalid")
        evidence_id = item.get("evidence_id")
        document_id = item.get("document_id")
        locator = item.get("locator")
        stance = item.get("predicted_stance")
        if not all(isinstance(value, str) and value.strip() for value in (evidence_id, document_id, locator)) or evidence_id in seen:
            raise EvidenceQualityEvaluationError("evidence-quality assessment identity is invalid")
        if stance not in {item.value for item in Stance}:
            raise EvidenceQualityEvaluationError("evidence-quality assessment stance is invalid")
        seen.add(evidence_id)
        if reviewed:
            if not isinstance(item.get("citation_locator_correct"), bool) or not isinstance(item.get("conditions_complete"), bool):
                raise EvidenceQualityEvaluationError("reviewed evidence-quality citation or condition status is invalid")
            expected_contradiction = stance == Stance.CONTRADICT.value
            if expected_contradiction and not isinstance(item.get("predicted_contradiction_correct"), bool):
                raise EvidenceQualityEvaluationError("reviewed contradiction status is required for predicted contradictions")
            if not expected_contradiction and item.get("predicted_contradiction_correct") is not None:
                raise EvidenceQualityEvaluationError("non-contradiction assessments cannot carry a contradiction judgment")
        elif any(item.get(key) is not None for key in ("citation_locator_correct", "conditions_complete", "predicted_contradiction_correct")):
            raise EvidenceQualityEvaluationError("blank evidence-quality template must not contain review judgments")
