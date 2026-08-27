"""Human expert assessment of evidence-bound Research Gap candidates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


GAP_REVIEW_SCHEMA_VERSION = "1.1"
GAP_EVALUATION_SCHEMA_VERSION = "1.1"
_TEMPLATE_FIELDS = {"schema_version", "mission_id", "trust_status", "assessments"}
_ASSESSMENT_FIELDS = {
    "gap_id", "expert_approved", "novelty_rating",
    "actionability_rating", "evidence_complete", "counterevidence_reviewed",
    "bounded_novelty_search_outcome",
}
_NOVELTY_OUTCOMES = {
    "no_direct_match_in_bounded_search",
    "related_prior_work_found",
    "inconclusive",
}


class GapReviewEvaluationError(ValueError):
    """Raised when a Gap review is incomplete, mismatched, or self-attested."""


def gap_review_template(*, mission_id: str, gap_ids: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(mission_id, str) or not mission_id.strip() or not gap_ids or len(set(gap_ids)) != len(gap_ids):
        raise GapReviewEvaluationError("Gap review template identity is invalid")
    return {
        "schema_version": GAP_REVIEW_SCHEMA_VERSION,
        "mission_id": mission_id,
        "trust_status": "blank_human_gap_review_template_not_evaluation_result",
        "assessment_instructions": {
            "counterevidence_reviewed": "Confirm that the candidate was checked against the executed approved counterevidence search history and its evidence boundary.",
            "bounded_novelty_search_outcome": "Use no_direct_match_in_bounded_search only for the reviewed bounded search. It is not a claim of global novelty or literature absence.",
        },
        "assessments": [
            {
                "gap_id": gap_id,
                "expert_approved": None,
                "novelty_rating": None,
                "actionability_rating": None,
                "evidence_complete": None,
                "counterevidence_reviewed": None,
                "bounded_novelty_search_outcome": None,
            }
            for gap_id in gap_ids
        ],
    }


def write_gap_review_template(run_dir: Path, template: dict[str, Any]) -> Path:
    _validate_template(template, reviewed=False)
    path = run_dir / "human_gap_review_template.json"
    path.write_text(json.dumps(template, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_reviewed_gap_assessment(
    path: Path,
    *,
    mission_id: str,
    gap_ids: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise GapReviewEvaluationError("reviewed Gap assessment file does not exist") from error
    except json.JSONDecodeError as error:
        raise GapReviewEvaluationError("reviewed Gap assessment file is not valid JSON") from error
    _validate_template(payload, reviewed=True)
    if payload["mission_id"] != mission_id:
        raise GapReviewEvaluationError("reviewed Gap assessment does not belong to this mission")
    assessments = payload["assessments"]
    observed = tuple(item["gap_id"] for item in assessments)
    if set(observed) != set(gap_ids) or len(observed) != len(gap_ids):
        raise GapReviewEvaluationError("reviewed Gap assessment must cover every current candidate exactly once")
    return tuple(assessments)


def gap_evaluation_from_assessments(
    *,
    mission_id: str,
    assessments: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    if not assessments:
        raise GapReviewEvaluationError("Gap evaluation requires at least one reviewed assessment")
    approved = sum(item["expert_approved"] is True for item in assessments)
    evidence_complete = sum(item["evidence_complete"] is True for item in assessments)
    counterevidence_reviewed = sum(item["counterevidence_reviewed"] is True for item in assessments)
    no_direct_match = sum(item["bounded_novelty_search_outcome"] == "no_direct_match_in_bounded_search" for item in assessments)
    related_work = sum(item["bounded_novelty_search_outcome"] == "related_prior_work_found" for item in assessments)
    inconclusive = sum(item["bounded_novelty_search_outcome"] == "inconclusive" for item in assessments)
    return {
        "schema_version": GAP_EVALUATION_SCHEMA_VERSION,
        "mission_id": mission_id,
        "trust_status": "metrics_from_human_expert_review_of_evidence_bound_gap_candidates",
        "candidate_count": len(assessments),
        "expert_approval_rate": round(approved / len(assessments), 6),
        "mean_novelty_rating": round(sum(item["novelty_rating"] for item in assessments) / len(assessments), 6),
        "mean_actionability_rating": round(sum(item["actionability_rating"] for item in assessments) / len(assessments), 6),
        "evidence_completeness_rate": round(evidence_complete / len(assessments), 6),
        "counterevidence_review_rate": round(counterevidence_reviewed / len(assessments), 6),
        "bounded_no_direct_match_rate": round(no_direct_match / len(assessments), 6),
        "related_prior_work_found_rate": round(related_work / len(assessments), 6),
        "inconclusive_novelty_search_rate": round(inconclusive / len(assessments), 6),
    }


def write_gap_evaluation(run_dir: Path, result: dict[str, Any]) -> Path:
    fields = {
        "schema_version", "mission_id", "trust_status", "candidate_count",
        "expert_approval_rate", "mean_novelty_rating",
        "mean_actionability_rating", "evidence_completeness_rate",
        "counterevidence_review_rate", "bounded_no_direct_match_rate",
        "related_prior_work_found_rate", "inconclusive_novelty_search_rate",
    }
    if not isinstance(result, dict) or set(result) != fields:
        raise GapReviewEvaluationError("Gap evaluation result is invalid")
    path = run_dir / "human_gap_evaluation.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _validate_template(payload: object, *, reviewed: bool) -> None:
    expected_fields = _TEMPLATE_FIELDS | {"assessment_instructions"}
    if not isinstance(payload, dict) or set(payload) != expected_fields:
        raise GapReviewEvaluationError("Gap assessment has unsupported or missing fields")
    expected_status = (
        "human_expert_reviewed_gap_assessment_for_evaluation"
        if reviewed
        else "blank_human_gap_review_template_not_evaluation_result"
    )
    if payload.get("schema_version") != GAP_REVIEW_SCHEMA_VERSION or payload.get("trust_status") != expected_status:
        raise GapReviewEvaluationError("Gap assessment schema or trust status is invalid")
    if not isinstance(payload.get("mission_id"), str) or not payload["mission_id"].strip():
        raise GapReviewEvaluationError("Gap assessment mission identity is invalid")
    instructions = payload.get("assessment_instructions")
    if not isinstance(instructions, dict) or set(instructions) != {"counterevidence_reviewed", "bounded_novelty_search_outcome"} or not all(isinstance(value, str) and value.strip() for value in instructions.values()):
        raise GapReviewEvaluationError("Gap assessment instructions are invalid")
    assessments = payload.get("assessments")
    if not isinstance(assessments, list) or not assessments:
        raise GapReviewEvaluationError("Gap assessment must contain at least one candidate")
    seen: set[str] = set()
    for item in assessments:
        if not isinstance(item, dict) or set(item) != _ASSESSMENT_FIELDS:
            raise GapReviewEvaluationError("Gap assessment fields are invalid")
        gap_id = item.get("gap_id")
        if not isinstance(gap_id, str) or not gap_id or gap_id in seen:
            raise GapReviewEvaluationError("Gap assessment gap_id is invalid or duplicated")
        seen.add(gap_id)
        if reviewed:
            if not isinstance(item.get("expert_approved"), bool) or not isinstance(item.get("evidence_complete"), bool) or not isinstance(item.get("counterevidence_reviewed"), bool):
                raise GapReviewEvaluationError("reviewed Gap booleans are invalid")
            if not all(isinstance(item.get(key), int) and 1 <= item[key] <= 5 for key in ("novelty_rating", "actionability_rating")):
                raise GapReviewEvaluationError("reviewed Gap ratings must be integers from 1 to 5")
            if item.get("bounded_novelty_search_outcome") not in _NOVELTY_OUTCOMES:
                raise GapReviewEvaluationError("reviewed Gap novelty search outcome is invalid")
            if item["expert_approved"] and not item["counterevidence_reviewed"]:
                raise GapReviewEvaluationError("an expert cannot approve a Gap before reviewing its bounded counterevidence search")
        elif any(item.get(key) is not None for key in _ASSESSMENT_FIELDS - {"gap_id"}):
            raise GapReviewEvaluationError("blank Gap review template must not contain assessment values")
