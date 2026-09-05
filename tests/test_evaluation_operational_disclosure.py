import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from cosmatter.evaluation_operational_disclosure import (
    API_COST_LATENCY_TRUST_STATUS,
    FAILURE_CASE_TRUST_STATUS,
    EvaluationOperationalDisclosureError,
    api_cost_latency_from_review,
    failure_case_log_from_review,
    write_api_cost_latency,
    write_failure_case_log,
)
from cosmatter.evaluation_run_record import (
    EvaluationRunRecordError,
    evaluation_run_record_template,
    reviewed_evaluation_run_record,
)
from tests.question_set_helpers import write_synthetic_frozen_question_set


def manifest():
    return {
        "mission_id": "mission_1",
        "corpus_id": "bfo_90_v1",
        "documents": [{"document_id": "d1"}, {"document_id": "d2"}],
    }


def failure_payload():
    return {
        "schema_version": "1.0",
        "mission_id": "mission_1",
        "corpus_id": "bfo_90_v1",
        "trust_status": FAILURE_CASE_TRUST_STATUS,
        "categories": [
            {
                "category": "parser_or_conversion_failure",
                "occurrence_count": 2,
                "resolution_status": "excluded_from_evaluation",
            }
        ],
    }


def cost_payload():
    return {
        "schema_version": "1.0",
        "mission_id": "mission_1",
        "corpus_id": "bfo_90_v1",
        "trust_status": API_COST_LATENCY_TRUST_STATUS,
        "measurement_scope": "reviewed metadata retrieval calls for frozen corpus evaluation",
        "providers": [
            {
                "provider_id": "openalex",
                "request_count": 10,
                "successful_request_count": 9,
                "failed_request_count": 1,
                "currency": "not_applicable",
                "total_cost": 0,
                "median_latency_seconds": 0.2,
                "p95_latency_seconds": 0.8,
            }
        ],
    }


def completed_metric_payloads():
    return {
        "human_retrieval_evaluation.json": {"schema_version": "1.1", "mission_id": "mission_1", "corpus_id": "bfo_90_v1", "trust_status": "metrics_from_human_reviewed_gold_standard", "identity_resolution_policy": "exact_document_id", "search_index": 0, "k": 10, "raw_retrieved_count": 10, "retrieved_count": 10, "doi_resolved_candidate_count": 0, "duplicate_alias_count": 0, "gold_relevant_count": 1, "gold_partially_relevant_count": 0, "precision_at_k": 0.1, "recall_at_k": 1.0, "ndcg_at_k": 1.0},
        "human_material_fact_evaluation.json": {"schema_version": "1.0", "mission_id": "mission_1", "corpus_id": "bfo_90_v1", "trust_status": "metrics_for_review_gated_material_fact_pipeline_not_raw_llm_accuracy", "gold_fact_count": 1, "reviewed_fact_count": 1, "exact_match_count": 1, "precision": 1.0, "recall": 1.0, "f1": 1.0, "unit_match_denominator": 1, "unit_match_accuracy": 1.0},
        "human_evidence_quality_evaluation.json": {"schema_version": "1.0", "mission_id": "mission_1", "trust_status": "metrics_from_human_reviewed_evidence_locator_condition_and_contradiction_audit", "evidence_count": 1, "predicted_contradiction_count": 0, "citation_precision": 1.0, "condition_completeness": 1.0, "contradiction_precision": 0.0},
        "human_gap_evaluation.json": {"schema_version": "1.1", "mission_id": "mission_1", "trust_status": "metrics_from_human_expert_review_of_evidence_bound_gap_candidates", "candidate_count": 1, "expert_approval_rate": 1.0, "mean_novelty_rating": 4.0, "mean_actionability_rating": 4.0, "evidence_completeness_rate": 1.0, "counterevidence_review_rate": 1.0, "bounded_no_direct_match_rate": 0.0, "related_prior_work_found_rate": 1.0, "inconclusive_novelty_search_rate": 0.0},
    }


def write_completed_upstream_audits(run: Path) -> None:
    frozen_manifest = manifest()
    digest = hashlib.sha256(
        json.dumps(frozen_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    (run / "frozen_corpus_readiness.json").write_text(json.dumps({
        "schema_version": "1.0", "trust_status": "aggregate_frozen_corpus_readiness_not_evaluation_result",
        "mission_id": "mission_1", "corpus_id": "bfo_90_v1", "expected_document_count": 2,
        "frozen_document_count": 2, "expected_count_matched": True, "unique_document_id_count": 2,
        "document_id_uniqueness_valid": True, "doi_present_count": 0, "doi_missing_count": 2,
        "authorized_access_policy_count": 1, "authorized_access_boundary_valid": True,
        "manifest_sha256": digest, "evaluation_gate": "ready_for_private_human_annotation", "boundary": "fixture",
    }), encoding="utf-8")
    (run / "human_annotation_coverage.json").write_text(json.dumps({
        "schema_version": "1.0", "trust_status": "aggregate_human_annotation_coverage_not_evaluation_result",
        "mission_id": "mission_1", "corpus_id": "bfo_90_v1", "frozen_document_count": 2,
        "annotation_file_status": "human_reviewed_gold_standard_for_evaluation",
        "relevance_counts": {"unreviewed": 0, "relevant": 1, "partially_relevant": 0, "not_relevant": 1},
        "documents_with_evidence_annotations": 1, "documents_with_material_fact_annotations": 1,
        "documents_with_comparison_annotations": 1, "documents_with_gap_annotations": 1,
        "relevance_evaluation_gate": "ready_for_human_retrieval_evaluation", "annotation_file_sha256": "sha256:fixture", "boundary": "fixture",
    }), encoding="utf-8")
    (run / "bibliographic_source_coverage.json").write_text(json.dumps({
        "schema_version": "1.0", "trust_status": "aggregate_bibliographic_source_coverage_not_evaluation_result",
        "mission_id": "mission_1", "corpus_id": "bfo_90_v1", "frozen_document_count": 2,
        "documents_with_reviewed_bibliographic_source": 2, "distinct_bibliographic_source_count": 1,
        "bibliographic_source_coverage_gate": "ready_for_source_traceable_evaluation",
        "registry_sha256": "a" * 64, "boundary": "fixture",
    }), encoding="utf-8")


class EvaluationOperationalDisclosureTests(unittest.TestCase):
    def test_safe_aggregate_payloads_and_writers(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            write_synthetic_frozen_question_set(run)
            failure = failure_case_log_from_review(mission_id="mission_1", corpus_id="bfo_90_v1", payload=failure_payload())
            cost = api_cost_latency_from_review(mission_id="mission_1", corpus_id="bfo_90_v1", payload=cost_payload())
            self.assertTrue(write_failure_case_log(run, failure).is_file())
            self.assertTrue(write_api_cost_latency(run, cost).is_file())

    def test_rejects_disallowed_free_text_and_inconsistent_latency(self):
        bad_failure = failure_payload()
        bad_failure["categories"][0]["private_path"] = "C:/private/paper.pdf"
        with self.assertRaises(EvaluationOperationalDisclosureError):
            failure_case_log_from_review(mission_id="mission_1", corpus_id="bfo_90_v1", payload=bad_failure)
        bad_cost = cost_payload()
        bad_cost["providers"][0]["p95_latency_seconds"] = 0.1
        with self.assertRaises(EvaluationOperationalDisclosureError):
            api_cost_latency_from_review(mission_id="mission_1", corpus_id="bfo_90_v1", payload=bad_cost)

    def test_completed_record_requires_real_operational_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            write_synthetic_frozen_question_set(run)
            for filename in (
                "human_retrieval_evaluation.json",
                "human_material_fact_evaluation.json",
                "human_evidence_quality_evaluation.json",
                "human_gap_evaluation.json",
            ):
                (run / filename).write_text("{}", encoding="utf-8")
            record = evaluation_run_record_template(run_dir=run, manifest=manifest(), mission_id="mission_1")
            record["trust_status"] = "human_reviewed_real_corpus_evaluation_run_record"
            record["execution_completed_on"] = "2026-08-14"
            record["code_revision"] = "test-snapshot"
            record["metric_artifacts"] = {key: "generated" for key in record["metric_artifacts"]}
            record["failure_case_log_status"] = "recorded"
            record["api_cost_and_latency_status"] = "recorded"
            record["submission_truth_check"] = "completed"
            record["human_review_disclosure"] = {key: "completed" for key in record["human_review_disclosure"]}
            with self.assertRaises(EvaluationRunRecordError):
                reviewed_evaluation_run_record(run_dir=run, manifest=manifest(), mission_id="mission_1", payload=record)
            write_failure_case_log(run, failure_payload())
            write_api_cost_latency(run, cost_payload())
            write_completed_upstream_audits(run)
            for filename, payload in completed_metric_payloads().items():
                (run / filename).write_text(json.dumps(payload), encoding="utf-8")
            saved = reviewed_evaluation_run_record(run_dir=run, manifest=manifest(), mission_id="mission_1", payload=record)
        self.assertEqual(saved["submission_truth_check"], "completed")


if __name__ == "__main__":
    unittest.main()
