import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.ui_export import _audit_summary_from_run
from cosmatter.question_set import REVIEWED_STATUS, bfo_question_set_review_template, freeze_reviewed_question_set, write_frozen_question_set
from cosmatter.models import MissionBrief
from cosmatter.planning import approved_flight_plan_from_payload, write_approved_flight_plan


class UiAuditSummaryTests(unittest.TestCase):
    def test_projects_only_aggregate_audit_and_receipt_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            mission_id = "mission_ui_audit"
            report = {
                "schema_version": "1.0", "mission_id": mission_id, "report_id": "report_1",
                "trust_status": "artifact_level_identifier_audit_not_scientific_validity_assessment",
                "accepted_evidence_count": 2, "manifest_evidence_count": 2,
                "accepted_evidence_manifest_coverage": 1.0, "research_gap_candidate_count": 1,
                "gap_evidence_reference_count": 2, "gap_evidence_accepted_coverage": 1.0,
                "structured_report_identifier_coverage": 1.0,
                "accepted_evidence_locator_rendered_coverage": 1.0,
                "reviewed_material_fact_count": 0, "reviewed_material_fact_rendered_coverage": 1.0,
                "cross_document_comparison_count": 0, "comparison_observation_reference_count": 0,
                "comparison_observation_rendered_coverage": 1.0,
                "executed_gap_counterevidence_boundary_count": 1,
                "gap_counterevidence_boundary_rendered_coverage": 1.0,
                "human_source_locator_review_required": True,
            }
            provenance = {
                "schema_version": "1.0", "mission_id": mission_id,
                "trust_status": "accepted_evidence_provenance_coverage_not_source_authenticity_assessment",
                "accepted_evidence_count": 2, "exact_reviewed_source_map_match_count": 1,
                "manual_locator_only_count": 1, "exact_source_map_match_rate": 0.5,
                "items": [{"evidence_id": "hidden", "document_id": "hidden", "locator": "hidden", "provenance_status": "hidden"}],
            }
            receipt = {"provider": "sciverse", "operation": "agentic_search", "query_sha256": "private-query-digest"}
            mineru_receipt = {
                "provider": "mineru", "operation": "source_parse_poll",
                "source_url_sha256": "private-source-digest", "task_id_sha256": "private-task-digest",
            }
            (run / "report_evidence_audit.json").write_text(json.dumps(report), encoding="utf-8")
            (run / "evidence_provenance_audit.json").write_text(json.dumps(provenance), encoding="utf-8")
            (run / "provider_receipts.jsonl").write_text(
                json.dumps(receipt) + "\n" + json.dumps(mineru_receipt) + "\n", encoding="utf-8"
            )
            summary = _audit_summary_from_run(run, mission_id)
        self.assertEqual(summary["report_evidence"]["accepted_evidence_count"], 2)
        self.assertEqual(summary["evidence_provenance"]["manual_locator_only_count"], 1)
        self.assertEqual(summary["external_retrieval"]["sciverse_agentic_search_count"], 1)
        self.assertNotIn("private-query-digest", json.dumps(summary))
        self.assertNotIn("private-source-digest", json.dumps(summary))
        self.assertNotIn("private-task-digest", json.dumps(summary))
        self.assertNotIn("hidden", json.dumps(summary))


    def test_projects_aggregate_counterevidence_gate_without_query_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            mission = MissionBrief("compare conditions", "BiFeO3", "phase stability", "films", mission_id="mission_counter_gate")
            counter_query = "private counterevidence query that must not reach the browser"
            plan = approved_flight_plan_from_payload(mission, {
                "subquestions": ["Which conditions differ?"],
                "queries": ["primary private query"],
                "counter_queries": [counter_query],
            })
            write_approved_flight_plan(run, plan)
            waiting = _audit_summary_from_run(run, mission.mission_id)["counterevidence"]
            (run / "retrieval_candidates.json").write_text(json.dumps({
                "searches": [{"query": counter_query, "candidates": []}],
            }), encoding="utf-8")
            ready = _audit_summary_from_run(run, mission.mission_id)["counterevidence"]
        self.assertEqual(waiting, {
            "state": "awaiting_counterevidence_execution",
            "planned_query_count": 1,
            "executed_query_count": 0,
        })
        self.assertEqual(ready, {
            "state": "ready",
            "planned_query_count": 1,
            "executed_query_count": 1,
        })
        self.assertNotIn(counter_query, json.dumps({"waiting": waiting, "ready": ready}))
    def test_projects_only_human_reviewed_evaluation_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            mission_id = "mission_eval"
            evidence_quality = {
                "schema_version": "1.0", "mission_id": mission_id,
                "trust_status": "metrics_from_human_reviewed_evidence_locator_condition_and_contradiction_audit",
                "evidence_count": 8, "predicted_contradiction_count": 3,
                "citation_precision": 0.875, "condition_completeness": 0.75,
                "contradiction_precision": 0.666667,
            }
            retrieval = {
                "schema_version": "1.0", "mission_id": mission_id, "corpus_id": "private-corpus",
                "trust_status": "metrics_from_human_reviewed_gold_standard", "search_index": 0, "k": 10,
                "retrieved_count": 10, "gold_relevant_count": 3, "gold_partially_relevant_count": 2,
                "precision_at_k": 0.3, "recall_at_k": 1.0, "ndcg_at_k": 0.8,
            }
            facts = {
                "schema_version": "1.0", "mission_id": mission_id, "corpus_id": "private-corpus",
                "trust_status": "metrics_for_review_gated_material_fact_pipeline_not_raw_llm_accuracy",
                "gold_fact_count": 12, "reviewed_fact_count": 11, "exact_match_count": 9,
                "precision": 0.818182, "recall": 0.75, "f1": 0.782609,
                "unit_match_denominator": 9, "unit_match_accuracy": 1.0,
            }
            gaps = {
                "schema_version": "1.1", "mission_id": mission_id,
                "trust_status": "metrics_from_human_expert_review_of_evidence_bound_gap_candidates",
                "candidate_count": 2, "expert_approval_rate": 0.5, "mean_novelty_rating": 3.5,
                "mean_actionability_rating": 4.0, "evidence_completeness_rate": 1.0,
                "counterevidence_review_rate": 1.0, "bounded_no_direct_match_rate": 0.5,
                "related_prior_work_found_rate": 0.25, "inconclusive_novelty_search_rate": 0.25,
            }
            (run / "human_evidence_quality_evaluation.json").write_text(json.dumps(evidence_quality), encoding="utf-8")
            (run / "human_retrieval_evaluation.json").write_text(json.dumps(retrieval), encoding="utf-8")
            (run / "human_material_fact_evaluation.json").write_text(json.dumps(facts), encoding="utf-8")
            (run / "human_gap_evaluation.json").write_text(json.dumps(gaps), encoding="utf-8")
            summary = _audit_summary_from_run(run, mission_id)
        self.assertEqual(summary["evaluation"]["evidence_quality"]["citation_precision"], 0.875)
        self.assertEqual(summary["evaluation"]["evidence_quality"]["trust_status"], "metrics_from_human_reviewed_evidence_locator_condition_and_contradiction_audit")
        self.assertEqual(summary["evaluation"]["retrieval"]["ndcg_at_k"], 0.8)
        self.assertEqual(summary["evaluation"]["material_facts"]["f1"], 0.782609)
        self.assertEqual(summary["evaluation"]["research_gaps"]["mean_actionability_rating"], 4.0)
        self.assertNotIn("private-corpus", json.dumps(summary))

    def test_projects_submission_readiness_without_private_corpus_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            mission_id = "mission_submission_readiness"
            corpus_id = "private-corpus-do-not-project"
            frozen = {
                "schema_version": "1.0", "trust_status": "aggregate_frozen_corpus_readiness_not_evaluation_result",
                "mission_id": mission_id, "corpus_id": corpus_id, "expected_document_count": 90,
                "frozen_document_count": 90, "expected_count_matched": True,
                "unique_document_id_count": 90, "document_id_uniqueness_valid": True,
                "doi_present_count": 88, "doi_missing_count": 2, "authorized_access_policy_count": 1,
                "authorized_access_boundary_valid": True, "manifest_sha256": "a" * 64,
                "evaluation_gate": "ready_for_private_human_annotation",
                "boundary": "private aggregate boundary",
            }
            annotations = {
                "schema_version": "1.0", "trust_status": "aggregate_human_annotation_coverage_not_evaluation_result",
                "mission_id": mission_id, "corpus_id": corpus_id, "frozen_document_count": 90,
                "annotation_file_status": "human_reviewed_gold_standard_for_evaluation",
                "relevance_counts": {"unreviewed": 0, "relevant": 50, "partially_relevant": 20, "not_relevant": 20},
                "documents_with_evidence_annotations": 30, "documents_with_material_fact_annotations": 25,
                "documents_with_comparison_annotations": 18, "documents_with_gap_annotations": 5,
                "relevance_evaluation_gate": "ready_for_human_retrieval_evaluation",
                "annotation_file_sha256": "b" * 64, "boundary": "private annotation boundary",
            }
            sources = {
                "schema_version": "1.0", "trust_status": "aggregate_bibliographic_source_coverage_not_evaluation_result",
                "mission_id": mission_id, "corpus_id": corpus_id, "frozen_document_count": 90,
                "documents_with_reviewed_bibliographic_source": 90, "distinct_bibliographic_source_count": 3,
                "bibliographic_source_coverage_gate": "ready_for_source_traceable_evaluation",
                "registry_sha256": "c" * 64, "boundary": "private bibliographic boundary",
            }
            for name, payload in (
                ("frozen_corpus_readiness.json", frozen),
                ("human_annotation_coverage.json", annotations),
                ("bibliographic_source_coverage.json", sources),
            ):
                (run / name).write_text(json.dumps(payload), encoding="utf-8")
            review = bfo_question_set_review_template(question_set_id="private-question-set-do-not-project")
            review["trust_status"] = REVIEWED_STATUS
            for item in review["questions"]:
                item["review_decision"] = "include"
                item["review_checks"] = {name: True for name in item["review_checks"]}
                item["review_note"] = "Private human review note that must not reach the UI."
            question_set, question_audit = freeze_reviewed_question_set(
                mission_id=mission_id, mission_material="BiFeO3", review=review
            )
            write_frozen_question_set(run, question_set, question_audit)
            summary = _audit_summary_from_run(run, mission_id)

        readiness = summary["submission_readiness"]
        self.assertEqual(readiness["question_set"]["included_question_count"], 8)
        self.assertEqual(readiness["frozen_corpus"]["frozen_document_count"], 90)
        self.assertEqual(readiness["human_annotation"]["relevance_counts"]["unreviewed"], 0)
        self.assertEqual(readiness["bibliographic_source"]["distinct_bibliographic_source_count"], 3)
        serialised = json.dumps(summary)
        self.assertNotIn(corpus_id, serialised)
        self.assertNotIn("private aggregate boundary", serialised)
        self.assertNotIn("private annotation boundary", serialised)
        self.assertNotIn("private bibliographic boundary", serialised)
        self.assertNotIn("private-question-set-do-not-project", serialised)
        self.assertNotIn("Private human review note", serialised)
        self.assertNotIn("sha256", json.dumps(readiness["question_set"]))


if __name__ == "__main__":
    unittest.main()
