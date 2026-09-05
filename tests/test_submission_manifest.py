import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.models import MissionBrief
from cosmatter.submission_manifest import (
    SubmissionManifestError,
    build_submission_execution_manifest,
)
from cosmatter.sensitive_artifact_audit import audit_sensitive_artifacts, write_sensitive_artifact_audit
from cosmatter.evidence_maturity_registry import audit_evidence_maturity_registry_against_runs, write_evidence_maturity_registry, write_evidence_maturity_registry_audit
from cosmatter.source_map import AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS, source_map_from_review, write_source_map_for_document
from tests.question_set_helpers import write_synthetic_frozen_question_set


class SubmissionManifestTests(unittest.TestCase):
    def test_manifest_aggregates_execution_without_copying_sensitive_artifact_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            run.mkdir()
            mission = MissionBrief(
                question="Private exact research question",
                material="BiFeO3", property_name="phase stability",
                scope="thin films", mission_id="mission_submission",
            )
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run / "retrieval_candidates.json").write_text(json.dumps({
                "candidates": [{
                    "document_id": "doc_1", "title": "Private paper",
                    "quote": "private source quote should not be projected",
                    "local_path": "D:/private/paper.md",
                }],
                "searches": [{"query": "private query should not be projected", "candidates": []}],
            }), encoding="utf-8")
            (run / "events.jsonl").write_text(json.dumps({
                "event_type": "approved_plan_query_executed",
                "payload": {"query": "private query should not be projected"},
            }) + "\n", encoding="utf-8")
            (run / "provider_receipts.jsonl").write_text(json.dumps({
                "provider": "sciverse", "operation": "agentic_search",
                "request_id": "private-request-id",
            }) + "\n", encoding="utf-8")
            (run / "external_resource_disclosure.json").write_text(json.dumps({"schema_version": "1.0"}), encoding="utf-8")
            (run / "potential_execution_protocol.json").write_text(json.dumps({"schema_version": "1.0"}), encoding="utf-8")
            (run / "material_draft_traceability_audit.json").write_text(json.dumps({"trust_status": "automated_non_scientific_material_draft_traceability_audit"}), encoding="utf-8")
            (run / "test_only_delegated_review.json").write_text(json.dumps({"trust_status": "user_authorized_delegated_test_review_not_scientific_evidence"}), encoding="utf-8")
            write_synthetic_frozen_question_set(run, mission.mission_id)
            write_sensitive_artifact_audit(run, audit_sensitive_artifacts(run, mission.mission_id))
            manifest = build_submission_execution_manifest(run_dir=run, mission=mission)
            serialized = json.dumps(manifest)
            second = build_submission_execution_manifest(run_dir=run, mission=mission)
        self.assertEqual(manifest["event_summary"]["event_type_counts"], {"approved_plan_query_executed": 1})
        self.assertEqual(manifest["provider_receipt_summary"]["provider_operation_counts"], {"sciverse:agentic_search": 1})
        self.assertEqual(manifest["manifest_sha256_input"], second["manifest_sha256_input"])
        self.assertTrue(next(item for item in manifest["artifact_inventory"] if item["name"] == "external_resource_disclosure.json")["exists"])
        self.assertTrue(next(item for item in manifest["artifact_inventory"] if item["name"] == "potential_execution_protocol.json")["exists"])
        self.assertTrue(next(item for item in manifest["artifact_inventory"] if item["name"] == "material_draft_traceability_audit.json")["exists"])
        self.assertTrue(next(item for item in manifest["artifact_inventory"] if item["name"] == "test_only_delegated_review.json")["exists"])
        self.assertTrue(next(item for item in manifest["artifact_inventory"] if item["name"] == "frozen_question_set.json")["exists"])
        self.assertTrue(next(item for item in manifest["artifact_inventory"] if item["name"] == "question_set_review_audit.json")["exists"])
        self.assertEqual(manifest["redaction_audit"], {"present": True, "is_clean": True})
        self.assertNotIn("private source quote", serialized)
        self.assertNotIn("D:/private", serialized)
        self.assertNotIn("private query", serialized)
        self.assertNotIn("private-request-id", serialized)
        self.assertNotIn("synthetic-bfo-question-set", serialized)

    def test_manifest_rejects_an_incomplete_frozen_question_set_pair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            mission = MissionBrief("question", "BiFeO3", "phase", "scope", mission_id="mission_questions")
            write_synthetic_frozen_question_set(run, mission.mission_id)
            (run / "question_set_review_audit.json").unlink()
            with self.assertRaisesRegex(SubmissionManifestError, "question-set"):
                build_submission_execution_manifest(run_dir=run, mission=mission)

    def test_manifest_rechecks_recorded_maturity_registry_links_and_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory) / "runs"
            run = runs / "maturity_manifest"
            run.mkdir(parents=True)
            mission = MissionBrief("question", "BiFeO3", "phase stability", "films", mission_id="mission_maturity_manifest")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run / "retrieval_candidates.json").write_text(json.dumps({"candidates": [{"document_id": "doc_1"}]}), encoding="utf-8")
            source_map = source_map_from_review(mission_id=mission.mission_id, document_id="doc_1", source_task={"document_id": "doc_1", "provider": "mineru", "state": "done", "task_id": "task_1"}, selection={"document_id": "doc_1", "segments": [{"segment_id": "segment_1", "locator": "p. 1", "kind": "paragraph", "quote": "Bounded test excerpt."}]}, trust_status=AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS)
            write_source_map_for_document(run, source_map)
            registry = {"schema_version": "cosmatter.evidence-maturity-registry/v1", "registry_id": "registry_1", "question_id": mission.mission_id, "trust_status": "delegated_automated_trial_evidence_maturity_registry_not_scientific_evidence", "claims": [{"claim_id": "claim_1", "claim_text": "A bounded literature statement.", "maturity_level": "literature_mentioned", "assessment_authority": "delegated_automated_trial", "support_records": [{"run_id": "maturity_manifest", "document_id": "doc_1", "document_version": "preprint", "independence_group": "not_human_verified", "source_map_status": "automated_trial_only", "data_status": "not_checked", "conditions_status": "not_checked", "stance": "supports"}], "reproducibility": {"protocol_status": "not_checked", "materials_status": "not_checked", "measurement_status": "not_checked", "raw_data_status": "not_checked", "assessment": "not_assessed"}, "independent_reproduction": {"status": "not_attempted", "independent_run_id": None, "result_comparison": "not_available", "review_status": "not_reviewed"}, "limitations": ["Not human reviewed."]}]}
            write_evidence_maturity_registry(run / "evidence_maturity_registry.json", registry)
            write_evidence_maturity_registry_audit(run / "evidence_maturity_registry_audit.json", audit_evidence_maturity_registry_against_runs(registry, runs))
            write_sensitive_artifact_audit(run, audit_sensitive_artifacts(run, mission.mission_id))
            manifest = build_submission_execution_manifest(run_dir=run, mission=mission)
            tampered = json.loads((run / "evidence_maturity_registry.json").read_text(encoding="utf-8"))
            tampered["claims"][0]["claim_text"] = "A changed bounded literature statement."
            (run / "evidence_maturity_registry.json").write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaises(SubmissionManifestError):
                build_submission_execution_manifest(run_dir=run, mission=mission)

        self.assertTrue(next(item for item in manifest["artifact_inventory"] if item["name"] == "evidence_maturity_registry.json")["exists"])
        self.assertTrue(next(item for item in manifest["artifact_inventory"] if item["name"] == "evidence_maturity_registry_audit.json")["exists"])

    def test_cli_writes_manifest_and_records_only_aggregate_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "submission_cli"
            run.mkdir(parents=True)
            mission = MissionBrief("question", "BiFeO3", "phase stability", "films", mission_id="mission_cli")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status = main(["build-submission-execution-manifest", "--run-id", "submission_cli"])
            manifest = (run / "submission_execution_manifest.json").read_text(encoding="utf-8")
            event_log = (run / "events.jsonl").read_text(encoding="utf-8")
        self.assertEqual(status, 0, output.getvalue())
        self.assertIn("derived_submission_execution_index", manifest)
        self.assertIn("submission_execution_manifest_built", event_log)
        self.assertNotIn("question", json.loads(manifest))

    def test_rejects_malformed_event_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            run.mkdir()
            mission = MissionBrief("q", "BiFeO3", "phase", "films", mission_id="mission_invalid")
            (run / "events.jsonl").write_text("{bad json}\n", encoding="utf-8")
            with self.assertRaises(SubmissionManifestError):
                build_submission_execution_manifest(run_dir=run, mission=mission)


if __name__ == "__main__":
    unittest.main()
