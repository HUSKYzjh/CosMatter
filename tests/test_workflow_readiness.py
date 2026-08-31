import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.candidate_screening import candidate_screening_from_review, write_candidate_screening
from cosmatter.counterevidence import CounterevidenceExecution
from cosmatter.facilities import condition_differential
from cosmatter.gap_analysis import candidates_from_discrepancies, write_gap_candidates
from cosmatter.models import AccessPolicy, EvidenceCard, Provenance, ReviewStatus, Stance
from cosmatter.verification import VerificationDecision
from cosmatter.provider_receipts import append_provider_receipt, mineru_task_receipt
from cosmatter.cli import main
from cosmatter.models import FlightPlan, MissionBrief
from cosmatter.workflow_readiness import workflow_readiness, write_workflow_readiness


class WorkflowReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mission = MissionBrief("private question", "BiFeO3", "phase stability", "films", mission_id="mission_readiness")
        self.plan = FlightPlan(self.mission.mission_id, ("primary query",), ("search primary",), ("search counter",))
        self.history = {
            "candidates": [{"document_id": "doc_1", "title": "private title"}],
            "searches": [{"query": "search primary"}, {"query": "search counter"}],
        }

    def test_distinguishes_completed_execution_from_pending_parse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / "flight_plan.json").write_text(json.dumps(self.plan.to_dict()), encoding="utf-8")
            (run / "retrieval_candidates.json").write_text(json.dumps(self.history), encoding="utf-8")
            screening = candidate_screening_from_review(
                self.mission.mission_id, self.history,
                {"decisions": [{"document_id": "doc_1", "decision": "include_for_fulltext", "reason_codes": ["material_match"]}]},
            )
            write_candidate_screening(run, screening)
            artifact = workflow_readiness(run, self.mission)
            path = write_workflow_readiness(run, artifact)
            stored = json.loads(path.read_text(encoding="utf-8"))

        stages = {item["stage"]: item for item in stored["stages"]}
        self.assertEqual(stages["plan"]["status"], "completed")
        self.assertEqual(stages["retrieval"]["status"], "completed")
        self.assertEqual(stages["screening"]["status"], "completed")
        self.assertEqual(stages["parse"]["status"], "waiting_human_review")
        self.assertEqual(stages["screening"]["counts"]["fulltext_eligible_count"], 0)
        self.assertEqual(stored["next_stage"], "parse")
        self.assertNotIn("private question", json.dumps(stored))
        self.assertNotIn("private title", json.dumps(stored))


    def test_detects_stale_screening_when_same_candidate_id_metadata_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / "flight_plan.json").write_text(json.dumps(self.plan.to_dict()), encoding="utf-8")
            screening = candidate_screening_from_review(
                self.mission.mission_id, self.history,
                {"decisions": [{"document_id": "doc_1", "decision": "include_for_fulltext", "reason_codes": ["material_match"]}]},
            )
            write_candidate_screening(run, screening)
            changed = {**self.history, "candidates": [{"document_id": "doc_1", "title": "changed title", "is_content_accessible": True}], "searches": self.history["searches"]}
            (run / "retrieval_candidates.json").write_text(json.dumps(changed), encoding="utf-8")
            stages = {item["stage"]: item for item in workflow_readiness(run, self.mission)["stages"]}
        self.assertEqual(stages["screening"]["status"], "waiting_human_review")
        self.assertEqual(stages["screening"]["counts"]["candidate_fingerprint_current"], 0)

    def test_blocks_retrieval_with_unverifiable_provider_origin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / "flight_plan.json").write_text(json.dumps(self.plan.to_dict()), encoding="utf-8")
            history = {
                "candidates": [{"document_id": "doc_1", "title": "paper", "retrieval_origins": [{"source": "Sciverse", "query_sha256": "0" * 64, "provider": "sciverse", "operation": "agentic_search", "receipt_id": "receipt_missing"}]}],
                "searches": [{"query": "search primary"}, {"query": "search counter"}],
            }
            (run / "retrieval_candidates.json").write_text(json.dumps(history), encoding="utf-8")
            stages = {item["stage"]: item for item in workflow_readiness(run, self.mission)["stages"]}
        self.assertEqual(stages["retrieval"]["status"], "blocked")
        self.assertEqual(stages["retrieval"]["counts"]["provider_receipt_link_valid"], 0)


    def test_parse_stage_distinguishes_pending_done_and_failed_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / "flight_plan.json").write_text(json.dumps(self.plan.to_dict()), encoding="utf-8")
            (run / "retrieval_candidates.json").write_text(json.dumps(self.history), encoding="utf-8")
            screening = candidate_screening_from_review(self.mission.mission_id, self.history, {"decisions": [{"document_id": "doc_1", "decision": "include_for_fulltext", "reason_codes": ["material_match"]}]})
            write_candidate_screening(run, screening)
            ledger = {"schema_version": "1.0", "mission_id": self.mission.mission_id, "tasks": [{"document_id": "doc_1", "provider": "mineru", "source_url_sha256": "0" * 64, "task_id": hashlib.sha256(b"task_1").hexdigest(), "state": "pending", "model_version": "configured"}]}
            (run / "source_parse_tasks.json").write_text(json.dumps(ledger), encoding="utf-8")
            def receipt(state: str) -> None:
                append_provider_receipt(run, mineru_task_receipt(
                    operation="source_parse_poll", document_id="doc_1", source_url_sha256="0" * 64,
                    task_id="task_1", task_state=state, model_version="configured", status_code=200, request_id=None,
                ))
            receipt("pending")
            pending = {item["stage"]: item for item in workflow_readiness(run, self.mission)["stages"]}["parse"]
            ledger["tasks"][0]["state"] = "done"
            (run / "source_parse_tasks.json").write_text(json.dumps(ledger), encoding="utf-8")
            receipt("done")
            done = {item["stage"]: item for item in workflow_readiness(run, self.mission)["stages"]}["parse"]
            ledger["tasks"][0]["state"] = "failed"
            (run / "source_parse_tasks.json").write_text(json.dumps(ledger), encoding="utf-8")
            receipt("failed")
            failed = {item["stage"]: item for item in workflow_readiness(run, self.mission)["stages"]}["parse"]
        self.assertEqual(pending["status"], "ready")
        self.assertEqual(done["status"], "completed")
        self.assertEqual(failed["status"], "blocked")



    def test_report_stage_requires_a_current_valid_evidence_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / "mission_report.json").write_text("{}", encoding="utf-8")
            (run / "research_report.md").write_text("# local report\n", encoding="utf-8")
            waiting = {item["stage"]: item for item in workflow_readiness(run, self.mission)["stages"]}["report"]
            (run / "report_evidence_audit.json").write_text(json.dumps({"schema_version": "1.2"}), encoding="utf-8")
            blocked = {item["stage"]: item for item in workflow_readiness(run, self.mission)["stages"]}["report"]
        self.assertEqual(waiting["status"], "blocked")
        self.assertEqual(waiting["counts"]["report_evidence_audit_valid"], 0)
        self.assertEqual(blocked["status"], "blocked")


    def test_gap_stage_requires_a_semantically_valid_executed_counterevidence_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            invalid = [{
                "schema_version": "1.1", "gap_id": "gap_001", "material": "BiFeO3", "property_name": "phase stability",
                "problem_description": "disagreement", "evidence_ids": ["e1", "e2"],
                "conflict_or_missing_evidence": ["conflicting_condition:strain"],
                "novelty_status": "unverified_requires_bounded_literature_review", "actionability": "test",
                "falsifiable_hypothesis": "strain matters", "suggested_validation": ["review"],
                "evidence_completeness": 1.0, "review_status": "candidate_requires_human_review",
                "counterevidence_boundary": {"status": "not_attested", "approved_query_count": 1, "executed_query_count": 0, "query_sha256": ["a" * 64], "candidate_history_sha256": None},
            }]
            (run / "research_gap_candidates.json").write_text(json.dumps(invalid), encoding="utf-8")
            blocked = {item["stage"]: item for item in workflow_readiness(run, self.mission)["stages"]}["gap"]
            self.assertEqual(blocked["status"], "blocked")
            self.assertEqual(blocked["counts"]["gap_artifact_valid"], 0)

            cards = (
                EvidenceCard("support", Stance.SUPPORT, "BiFeO3", "phase stability", {"sample_form": "film", "strain_percent": 1, "substrate": "STO", "thickness_nm": 20, "temperature_k": 300, "method": "XRD"}, "short", Provenance("doc1", "p1", "fixture", access_policy=AccessPolicy.OA), review_status=ReviewStatus.ACCEPTED, evidence_id="e1"),
                EvidenceCard("contradict", Stance.CONTRADICT, "BiFeO3", "phase stability", {"sample_form": "film", "strain_percent": 2, "substrate": "STO", "thickness_nm": 20, "temperature_k": 300, "method": "XRD"}, "short", Provenance("doc2", "p2", "fixture", access_policy=AccessPolicy.OA), review_status=ReviewStatus.ACCEPTED, evidence_id="e2"),
            )
            decisions = tuple(VerificationDecision(self.mission.mission_id, card.evidence_id, ReviewStatus.ACCEPTED, "complete") for card in cards)
            candidates = candidates_from_discrepancies(
                self.mission.mission_id, "BiFeO3", "phase stability", cards, decisions,
                condition_differential(cards, ("counter",)), CounterevidenceExecution(1, 1, 1, "a" * 64),
            )
            write_gap_candidates(run, candidates)
            completed = {item["stage"]: item for item in workflow_readiness(run, self.mission)["stages"]}["gap"]
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["counts"]["executed_counterevidence_boundary_count"], 1)
        self.assertEqual(completed["counts"]["gap_artifact_valid"], 1)


    def test_exposes_missing_or_invalid_human_evaluation_after_accepted_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / "verification_decisions.json").write_text(json.dumps([
                {"mission_id": self.mission.mission_id, "evidence_id": "e_1", "status": "accepted"},
            ]), encoding="utf-8")
            pending = {item["stage"]: item for item in workflow_readiness(run, self.mission)["stages"]}["evaluation"]
            result = {
                "schema_version": "1.0", "mission_id": self.mission.mission_id,
                "trust_status": "metrics_from_human_reviewed_evidence_locator_condition_and_contradiction_audit",
                "evidence_count": 1, "predicted_contradiction_count": 0,
                "citation_precision": 1.0, "condition_completeness": 1.0, "contradiction_precision": 0.0,
            }
            (run / "human_evidence_quality_evaluation.json").write_text(json.dumps(result), encoding="utf-8")
            complete = {item["stage"]: item for item in workflow_readiness(run, self.mission)["stages"]}["evaluation"]
            result["trust_status"] = "untrusted"
            (run / "human_evidence_quality_evaluation.json").write_text(json.dumps(result), encoding="utf-8")
            invalid = {item["stage"]: item for item in workflow_readiness(run, self.mission)["stages"]}["evaluation"]
        self.assertEqual(pending["status"], "waiting_human_review")
        self.assertEqual(pending["counts"]["required_metric_family_count"], 1)
        self.assertEqual(complete["status"], "completed")
        self.assertEqual(invalid["status"], "blocked")
        self.assertEqual(invalid["counts"]["invalid_metric_artifact_count"], 1)


    def test_cli_handles_empty_run_without_provider_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory)
            run = runs / "readiness_cli"
            run.mkdir()
            (run / "mission.json").write_text(json.dumps(self.mission.to_dict()), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status = main(["audit-workflow-readiness", "--run-id", "readiness_cli"])
            result = json.loads(output.getvalue())
            artifact = json.loads((run / "workflow_readiness.json").read_text(encoding="utf-8"))

        self.assertEqual(status, 0)
        self.assertEqual(result["next_stage"], "plan")
        self.assertEqual(artifact["next_stage"], "plan")


if __name__ == "__main__":
    unittest.main()
