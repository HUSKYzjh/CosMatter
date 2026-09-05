"""Human-reviewed disclosure record for a real frozen-corpus evaluation run."""

from __future__ import annotations

import json
import math
import hashlib
from pathlib import Path
from typing import Any

from .evaluation_operational_disclosure import (
    EvaluationOperationalDisclosureError,
    load_api_cost_latency,
    load_failure_case_log,
)
from .bibliographic_source_coverage import (
    BibliographicSourceCoverageError,
    load_bibliographic_source_coverage,
)
from .question_set import QuestionSetError, load_frozen_question_set_binding


EVALUATION_RUN_RECORD_SCHEMA_VERSION = "1.1"
_TEMPLATE_STATUS = "blank_human_real_corpus_evaluation_run_record_not_a_result"
_REVIEWED_STATUS = "human_reviewed_real_corpus_evaluation_run_record"
_FIELDS = {
    "schema_version", "mission_id", "corpus_id", "question_set_id", "trust_status",
    "frozen_question_count", "frozen_question_set_sha256",
    "frozen_corpus_document_count", "execution_completed_on", "code_revision",
    "service_and_model_disclosure", "human_review_disclosure", "metric_artifacts",
    "failure_case_log_status", "api_cost_and_latency_status", "submission_truth_check",
}
_SERVICES = {"llm", "embedding", "reranker", "sciverse", "mineru", "local_corpus"}
_METRICS = {
    "human_retrieval_evaluation": "human_retrieval_evaluation.json",
    "human_material_fact_evaluation": "human_material_fact_evaluation.json",
    "human_evidence_quality_evaluation": "human_evidence_quality_evaluation.json",
    "human_gap_evaluation": "human_gap_evaluation.json",
}
_ALLOWED_METRIC_STATUS = {"not_generated", "generated"}
_ALLOWED_LOG_STATUS = {"not_recorded", "recorded"}
_ALLOWED_TRUTH_STATUS = {"not_completed", "completed"}


class EvaluationRunRecordError(ValueError):
    """Raised when a real-corpus disclosure is incomplete or mismatched."""


def evaluation_run_record_template(*, run_dir: Path, manifest: object, mission_id: str) -> dict[str, Any]:
    corpus_id, document_count = _manifest_identity(manifest, mission_id)
    question_set = _required_question_set_binding(run_dir, mission_id)
    return {
        "schema_version": EVALUATION_RUN_RECORD_SCHEMA_VERSION,
        "mission_id": mission_id,
        "corpus_id": corpus_id,
        **question_set,
        "trust_status": _TEMPLATE_STATUS,
        "frozen_corpus_document_count": document_count,
        "execution_completed_on": "",
        "code_revision": "",
        "service_and_model_disclosure": {key: "not_recorded" for key in sorted(_SERVICES)},
        "human_review_disclosure": {
            "relevance_gold": "not_started",
            "material_fact_gold": "not_started",
            "evidence_quality": "not_started",
            "gap_expert_review": "not_started",
        },
        "metric_artifacts": {key: "not_generated" for key in sorted(_METRICS)},
        "failure_case_log_status": "not_recorded",
        "api_cost_and_latency_status": "not_recorded",
        "submission_truth_check": "not_completed",
    }


def reviewed_evaluation_run_record(*, run_dir: Path, manifest: object, mission_id: str, payload: object) -> dict[str, Any]:
    corpus_id, document_count = _manifest_identity(manifest, mission_id)
    question_set = _required_question_set_binding(run_dir, mission_id)
    _validate(payload, reviewed=True)
    assert isinstance(payload, dict)
    if (
        payload["mission_id"] != mission_id
        or payload["corpus_id"] != corpus_id
        or payload["frozen_corpus_document_count"] != document_count
        or payload["question_set_id"] != question_set["question_set_id"]
        or payload["frozen_question_count"] != question_set["frozen_question_count"]
        or payload["frozen_question_set_sha256"] != question_set["frozen_question_set_sha256"]
    ):
        raise EvaluationRunRecordError("evaluation run record does not match the frozen manifest and question set")
    metric_status = payload["metric_artifacts"]
    for key, filename in _METRICS.items():
        exists = (run_dir / filename).is_file()
        if (metric_status[key] == "generated") != exists:
            raise EvaluationRunRecordError("evaluation run record metric status does not match generated artifacts")
    generated_all = all(metric_status[key] == "generated" for key in _METRICS)
    failure_recorded = payload["failure_case_log_status"] == "recorded"
    cost_recorded = payload["api_cost_and_latency_status"] == "recorded"
    try:
        if failure_recorded:
            load_failure_case_log(run_dir / "evaluation_failure_case_log.json", mission_id=mission_id, corpus_id=corpus_id)
        if cost_recorded:
            load_api_cost_latency(run_dir / "evaluation_api_cost_latency.json", mission_id=mission_id, corpus_id=corpus_id)
    except EvaluationOperationalDisclosureError as error:
        raise EvaluationRunRecordError(str(error)) from error
    if payload["submission_truth_check"] == "completed":
        if not generated_all or not failure_recorded or not cost_recorded:
            raise EvaluationRunRecordError("completed truth check requires all metric artifacts plus failure-case and cost records")
        _validate_completed_upstream_gates(
            run_dir=run_dir,
            manifest=manifest,
            mission_id=mission_id,
            corpus_id=corpus_id,
            document_count=document_count,
            human_review_disclosure=payload["human_review_disclosure"],
        )
        for key, filename in _METRICS.items():
            _validate_completed_metric_artifact(
                run_dir / filename,
                metric_name=key,
                mission_id=mission_id,
                corpus_id=corpus_id,
            )
    return payload


def write_evaluation_run_record_template(run_dir: Path, template: object) -> Path:
    _validate(template, reviewed=False)
    path = run_dir / "real_corpus_evaluation_run_record_template.json"
    path.write_text(json.dumps(template, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_reviewed_evaluation_run_record(run_dir: Path, record: object) -> Path:
    _validate(record, reviewed=True)
    path = run_dir / "real_corpus_evaluation_run_record.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _manifest_identity(manifest: object, mission_id: str) -> tuple[str, int]:
    if not isinstance(manifest, dict) or manifest.get("mission_id") != mission_id:
        raise EvaluationRunRecordError("evaluation run record requires this mission's reviewed corpus manifest")
    corpus_id = manifest.get("corpus_id")
    documents = manifest.get("documents")
    if not isinstance(corpus_id, str) or not corpus_id or not isinstance(documents, list) or not documents:
        raise EvaluationRunRecordError("evaluation run record corpus manifest identity is invalid")
    return corpus_id, len(documents)


def _required_question_set_binding(run_dir: Path, mission_id: str) -> dict[str, Any]:
    try:
        binding = load_frozen_question_set_binding(run_dir, mission_id=mission_id)
    except QuestionSetError as error:
        raise EvaluationRunRecordError(str(error)) from error
    if binding is None:
        raise EvaluationRunRecordError("evaluation run record requires a human-reviewed frozen question set")
    return binding


def _validate(payload: object, *, reviewed: bool) -> None:
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise EvaluationRunRecordError("evaluation run record has unsupported or missing fields")
    expected_status = _REVIEWED_STATUS if reviewed else _TEMPLATE_STATUS
    if payload.get("schema_version") != EVALUATION_RUN_RECORD_SCHEMA_VERSION or payload.get("trust_status") != expected_status:
        raise EvaluationRunRecordError("evaluation run record schema or trust status is invalid")
    if not all(isinstance(payload.get(key), str) and payload[key].strip() for key in ("mission_id", "corpus_id", "question_set_id")):
        raise EvaluationRunRecordError("evaluation run record identity is invalid")
    if not isinstance(payload.get("frozen_question_count"), int) or isinstance(payload["frozen_question_count"], bool) or payload["frozen_question_count"] < 3:
        raise EvaluationRunRecordError("evaluation run record question count is invalid")
    question_hash = payload.get("frozen_question_set_sha256")
    if not isinstance(question_hash, str) or len(question_hash) != 71 or not question_hash.startswith("sha256:") or any(character not in "0123456789abcdef" for character in question_hash[7:]):
        raise EvaluationRunRecordError("evaluation run record question-set hash is invalid")
    if not isinstance(payload.get("frozen_corpus_document_count"), int) or payload["frozen_corpus_document_count"] < 1:
        raise EvaluationRunRecordError("evaluation run record corpus count is invalid")
    if not isinstance(payload.get("service_and_model_disclosure"), dict) or set(payload["service_and_model_disclosure"]) != _SERVICES or not all(isinstance(value, str) and value.strip() and len(value) <= 240 for value in payload["service_and_model_disclosure"].values()):
        raise EvaluationRunRecordError("evaluation run record service disclosure is invalid")
    reviews = payload.get("human_review_disclosure")
    if not isinstance(reviews, dict) or set(reviews) != {"relevance_gold", "material_fact_gold", "evidence_quality", "gap_expert_review"} or not all(isinstance(value, str) and value.strip() and len(value) <= 80 for value in reviews.values()):
        raise EvaluationRunRecordError("evaluation run record human-review disclosure is invalid")
    metrics = payload.get("metric_artifacts")
    if not isinstance(metrics, dict) or set(metrics) != set(_METRICS) or any(value not in _ALLOWED_METRIC_STATUS for value in metrics.values()):
        raise EvaluationRunRecordError("evaluation run record metric disclosure is invalid")
    for key in ("failure_case_log_status", "api_cost_and_latency_status"):
        if payload.get(key) not in _ALLOWED_LOG_STATUS:
            raise EvaluationRunRecordError("evaluation run record operational disclosure is invalid")
    if payload.get("submission_truth_check") not in _ALLOWED_TRUTH_STATUS:
        raise EvaluationRunRecordError("evaluation run record truth-check status is invalid")
    if reviewed:
        if not all(isinstance(payload.get(key), str) and payload[key].strip() and len(payload[key]) <= 240 for key in ("execution_completed_on", "code_revision")):
            raise EvaluationRunRecordError("reviewed evaluation run record requires execution date and code revision")
    elif payload.get("execution_completed_on") != "" or payload.get("code_revision") != "":
        raise EvaluationRunRecordError("blank evaluation run record cannot declare execution details")


def _validate_completed_metric_artifact(
    path: Path, *, metric_name: str, mission_id: str, corpus_id: str,
) -> None:
    """Reject placeholder or cross-mission metrics before a final truth claim.

    Individual metric writers own their rich schemas.  This compact gate repeats
    only the public identity, schema, trust-status, field-set and finite-number
    invariants needed to ensure a completed run cannot be backed by ``{}`` or a
    synthetic file from another task.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationRunRecordError(f"completed evaluation metric cannot be read: {metric_name}") from error
    specifications: dict[str, tuple[str, str, set[str], set[str], set[str]]] = {
        "human_retrieval_evaluation": (
            "1.1", "metrics_from_human_reviewed_gold_standard",
            {"schema_version", "mission_id", "corpus_id", "trust_status", "identity_resolution_policy", "search_index", "k", "raw_retrieved_count", "retrieved_count", "doi_resolved_candidate_count", "duplicate_alias_count", "gold_relevant_count", "gold_partially_relevant_count", "precision_at_k", "recall_at_k", "ndcg_at_k"},
            {"raw_retrieved_count", "retrieved_count", "doi_resolved_candidate_count", "duplicate_alias_count", "gold_relevant_count", "gold_partially_relevant_count", "search_index", "k"},
            {"precision_at_k", "recall_at_k", "ndcg_at_k"},
        ),
        "human_material_fact_evaluation": (
            "1.0", "metrics_for_review_gated_material_fact_pipeline_not_raw_llm_accuracy",
            {"schema_version", "mission_id", "corpus_id", "trust_status", "gold_fact_count", "reviewed_fact_count", "exact_match_count", "precision", "recall", "f1", "unit_match_denominator", "unit_match_accuracy"},
            {"gold_fact_count", "reviewed_fact_count", "exact_match_count", "unit_match_denominator"},
            {"precision", "recall", "f1", "unit_match_accuracy"},
        ),
        "human_evidence_quality_evaluation": (
            "1.0", "metrics_from_human_reviewed_evidence_locator_condition_and_contradiction_audit",
            {"schema_version", "mission_id", "trust_status", "evidence_count", "predicted_contradiction_count", "citation_precision", "condition_completeness", "contradiction_precision"},
            {"evidence_count", "predicted_contradiction_count"},
            {"citation_precision", "condition_completeness", "contradiction_precision"},
        ),
        "human_gap_evaluation": (
            "1.1", "metrics_from_human_expert_review_of_evidence_bound_gap_candidates",
            {"schema_version", "mission_id", "trust_status", "candidate_count", "expert_approval_rate", "mean_novelty_rating", "mean_actionability_rating", "evidence_completeness_rate", "counterevidence_review_rate", "bounded_no_direct_match_rate", "related_prior_work_found_rate", "inconclusive_novelty_search_rate"},
            {"candidate_count"},
            {"expert_approval_rate", "mean_novelty_rating", "mean_actionability_rating", "evidence_completeness_rate", "counterevidence_review_rate", "bounded_no_direct_match_rate", "related_prior_work_found_rate", "inconclusive_novelty_search_rate"},
        ),
    }
    schema, trust_status, fields, integer_fields, numeric_fields = specifications[metric_name]
    if not isinstance(payload, dict) or set(payload) != fields:
        raise EvaluationRunRecordError(f"completed evaluation metric schema is invalid: {metric_name}")
    if payload.get("schema_version") != schema or payload.get("trust_status") != trust_status or payload.get("mission_id") != mission_id:
        raise EvaluationRunRecordError(f"completed evaluation metric identity is invalid: {metric_name}")
    if "corpus_id" in fields and payload.get("corpus_id") != corpus_id:
        raise EvaluationRunRecordError(f"completed evaluation metric corpus is invalid: {metric_name}")
    if not all(isinstance(payload.get(key), int) and not isinstance(payload[key], bool) and payload[key] >= 0 for key in integer_fields):
        raise EvaluationRunRecordError(f"completed evaluation metric counts are invalid: {metric_name}")
    if not all(isinstance(payload.get(key), (int, float)) and not isinstance(payload[key], bool) and math.isfinite(float(payload[key])) for key in numeric_fields):
        raise EvaluationRunRecordError(f"completed evaluation metric numeric fields are invalid: {metric_name}")
    if metric_name in {"human_retrieval_evaluation", "human_material_fact_evaluation", "human_evidence_quality_evaluation"}:
        bounded = numeric_fields
        if not all(0.0 <= float(payload[key]) <= 1.0 for key in bounded):
            raise EvaluationRunRecordError(f"completed evaluation metric rates are invalid: {metric_name}")
    if metric_name == "human_gap_evaluation":
        if not all(0.0 <= float(payload[key]) <= 1.0 for key in numeric_fields if key.endswith("rate")):
            raise EvaluationRunRecordError("completed Gap evaluation rates are invalid")
        if not all(1.0 <= float(payload[key]) <= 5.0 for key in ("mean_novelty_rating", "mean_actionability_rating")):
            raise EvaluationRunRecordError("completed Gap evaluation ratings are invalid")


def _validate_completed_upstream_gates(
    *, run_dir: Path, manifest: object, mission_id: str, corpus_id: str,
    document_count: int, human_review_disclosure: object,
) -> None:
    """Require completed metrics to retain a verified, frozen human-gold boundary.

    A completed result must be linked to the same manifest used for the run and
    to an aggregate audit showing every frozen document received a relevance
    review.  The checks intentionally read only safe aggregate artifacts; the
    detailed bibliography and annotations remain in the authorized review
    boundary.
    """
    if not isinstance(human_review_disclosure, dict) or any(
        human_review_disclosure.get(key) != "completed"
        for key in ("relevance_gold", "material_fact_gold", "evidence_quality", "gap_expert_review")
    ):
        raise EvaluationRunRecordError("completed truth check requires all human-review disclosures to be completed")
    frozen = _load_json_artifact(run_dir / "frozen_corpus_readiness.json", "frozen corpus readiness")
    expected_frozen_fields = {
        "schema_version", "trust_status", "mission_id", "corpus_id", "expected_document_count",
        "frozen_document_count", "expected_count_matched", "unique_document_id_count",
        "document_id_uniqueness_valid", "doi_present_count", "doi_missing_count",
        "authorized_access_policy_count", "authorized_access_boundary_valid", "manifest_sha256",
        "evaluation_gate", "boundary",
    }
    if not isinstance(frozen, dict) or set(frozen) != expected_frozen_fields:
        raise EvaluationRunRecordError("completed truth check frozen-corpus readiness schema is invalid")
    manifest_hash = _sha256(manifest)
    if not (
        frozen.get("schema_version") == "1.0"
        and frozen.get("trust_status") == "aggregate_frozen_corpus_readiness_not_evaluation_result"
        and frozen.get("mission_id") == mission_id
        and frozen.get("corpus_id") == corpus_id
        and frozen.get("frozen_document_count") == document_count
        and frozen.get("unique_document_id_count") == document_count
        and frozen.get("expected_count_matched") is True
        and frozen.get("document_id_uniqueness_valid") is True
        and frozen.get("authorized_access_boundary_valid") is True
        and frozen.get("manifest_sha256") == manifest_hash
        and frozen.get("evaluation_gate") == "ready_for_private_human_annotation"
    ):
        raise EvaluationRunRecordError("completed truth check is not bound to a ready frozen corpus audit")
    annotations = _load_json_artifact(run_dir / "human_annotation_coverage.json", "human annotation coverage")
    expected_annotation_fields = {
        "schema_version", "trust_status", "mission_id", "corpus_id", "frozen_document_count",
        "annotation_file_status", "relevance_counts", "documents_with_evidence_annotations",
        "documents_with_material_fact_annotations", "documents_with_comparison_annotations",
        "documents_with_gap_annotations", "relevance_evaluation_gate", "annotation_file_sha256", "boundary",
    }
    relevance = annotations.get("relevance_counts") if isinstance(annotations, dict) else None
    if (
        not isinstance(annotations, dict)
        or set(annotations) != expected_annotation_fields
        or annotations.get("schema_version") != "1.0"
        or annotations.get("trust_status") != "aggregate_human_annotation_coverage_not_evaluation_result"
        or annotations.get("mission_id") != mission_id
        or annotations.get("corpus_id") != corpus_id
        or annotations.get("frozen_document_count") != document_count
        or annotations.get("annotation_file_status") != "human_reviewed_gold_standard_for_evaluation"
        or annotations.get("relevance_evaluation_gate") != "ready_for_human_retrieval_evaluation"
        or not isinstance(relevance, dict)
        or relevance.get("unreviewed") != 0
    ):
        raise EvaluationRunRecordError("completed truth check requires a fully reviewed human-annotation coverage audit")
    try:
        load_bibliographic_source_coverage(
            run_dir / "bibliographic_source_coverage.json",
            mission_id=mission_id,
            corpus_id=corpus_id,
            document_count=document_count,
        )
    except BibliographicSourceCoverageError as error:
        raise EvaluationRunRecordError(str(error)) from error


def _load_json_artifact(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationRunRecordError(f"completed truth check requires {label} artifact") from error


def _sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
