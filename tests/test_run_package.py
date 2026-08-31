import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.run_package import RunPackageError, export_run_package, restore_run_package, validate_run_package
from cosmatter.workflow_readiness import WorkflowReadinessError, continuation_next_stage
from cosmatter.evidence_maturity_registry import audit_evidence_maturity_registry_against_runs, write_evidence_maturity_registry, write_evidence_maturity_registry_audit
from cosmatter.source_map import AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS, source_map_from_review, write_source_map_for_document
from cosmatter.dispatch import MissionDispatcher
from cosmatter.models import MissionBrief
from cosmatter.ui_export import export_run_to_ui


class RunPackageTests(unittest.TestCase):
    def test_allowlisted_package_detects_tampering_and_omits_private_values(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run_a"; run.mkdir()
            mission = {"mission_id": "mission_a", "question": "Map material reports", "material": "BiFeO3", "property_name": "phase stability", "scope": "films"}
            (run / "mission.json").write_text(json.dumps(mission), encoding="utf-8")
            package = export_run_package(run)
            validate_run_package(package)
            altered = copy.deepcopy(package); altered["mission"]["question"] = "changed"
            with self.assertRaises(RunPackageError):
                validate_run_package(altered)
            restored = restore_run_package(Path(directory) / "runs", "resume_a", package)
            self.assertTrue((restored / "mission.json").is_file())

    def test_workflow_readiness_keeps_the_audited_continuation_stage(self):
        readiness = {
            "schema_version": "1.0",
            "mission_id": "mission_a",
            "trust_status": "derived_workflow_readiness_not_scientific_evidence",
            "stages": [
                {"stage": stage, "status": "completed" if index < 3 else ("waiting_human_review" if index == 3 else "blocked"), "counts": {}}
                for index, stage in enumerate(("intake", "plan", "retrieval", "screening", "parse", "extraction", "gap", "report", "evaluation"))
            ],
            "next_stage": "screening",
        }
        self.assertEqual(continuation_next_stage(readiness, "mission_a"), "screening")
        with self.assertRaises(WorkflowReadinessError):
            continuation_next_stage(readiness, "other_mission")
        inconsistent = copy.deepcopy(readiness)
        inconsistent["next_stage"] = "gap"
        with self.assertRaises(WorkflowReadinessError):
            continuation_next_stage(inconsistent, "mission_a")

    def test_restore_failure_never_publishes_a_partial_run_or_staging_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            mission = {"mission_id": "mission_a", "question": "Map material reports", "material": "BiFeO3", "property_name": "phase stability", "scope": "films"}
            artifacts = {"mission.json": mission, "retrieval_candidates.json": {"candidates": []}}
            package = {"package_type": "cosmatter_run", "schema_version": "1.0", "mission": mission, "artifacts": artifacts, "artifact_sha256": {name: hashlib.sha256((json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")).hexdigest() for name, artifact in artifacts.items()}}
            original_write_text = Path.write_text

            def fail_second_artifact(path: Path, content: str, *args, **kwargs):
                if path.name == "retrieval_candidates.json" and path.parent.name.startswith(".resume_a.restore-"):
                    raise OSError("simulated write failure")
                return original_write_text(path, content, *args, **kwargs)

            with patch.object(Path, "write_text", new=fail_second_artifact):
                with self.assertRaises(RunPackageError):
                    restore_run_package(runs, "resume_a", package)
            self.assertFalse((runs / "resume_a").exists())
            self.assertEqual(list(runs.glob(".resume_a.restore-*")), [])

    def test_rejects_rehashed_package_with_url_local_path_or_cookie_field(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run_a"; run.mkdir()
            mission = {"mission_id": "mission_a", "question": "Map material reports", "material": "BiFeO3", "property_name": "phase stability", "scope": "films"}
            (run / "mission.json").write_text(json.dumps(mission), encoding="utf-8")
            package = export_run_package(run)
            for artifact in (
                {"candidates": [], "source_url": "opaque"},
                {"candidates": [], "note": "https://example.invalid/private.pdf"},
                {"candidates": [], "note": r"C:\\Users\\Researcher\\private.pdf"},
                {"candidates": [], "cookie": "session-value"},
            ):
                forged = copy.deepcopy(package)
                forged["artifacts"]["retrieval_candidates.json"] = artifact
                forged["artifact_sha256"]["retrieval_candidates.json"] = hashlib.sha256((json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")).hexdigest()
                with self.assertRaises(RunPackageError):
                    validate_run_package(forged)

    def test_package_preserves_only_hash_bound_maturity_registry_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "original"; run.mkdir(parents=True)
            brief = MissionBrief("Map material reports", "BiFeO3", "phase stability", "films", mission_id="mission_original")
            mission = brief.to_dict()
            (run / "mission.json").write_text(json.dumps(mission), encoding="utf-8")
            (run / "fleet_assignment.json").write_text(json.dumps(MissionDispatcher.from_project().assign(brief).to_dict()), encoding="utf-8")
            (run / "retrieval_candidates.json").write_text(json.dumps({"candidates": [{"document_id": "doc_1", "title": "Bounded package test paper", "source": "Sciverse", "publication_year": 2024}]}), encoding="utf-8")
            source_map = source_map_from_review(mission_id="mission_original", document_id="doc_1", source_task={"document_id": "doc_1", "provider": "mineru", "state": "done", "task_id": "task_1"}, selection={"document_id": "doc_1", "segments": [{"segment_id": "segment_1", "locator": "p. 1", "kind": "paragraph", "quote": "Bounded test excerpt."}]}, trust_status=AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS)
            write_source_map_for_document(run, source_map)
            registry = {"schema_version": "cosmatter.evidence-maturity-registry/v1", "registry_id": "registry_1", "question_id": "mission_original", "trust_status": "delegated_automated_trial_evidence_maturity_registry_not_scientific_evidence", "claims": [{"claim_id": "claim_1", "claim_text": "A bounded literature statement.", "maturity_level": "literature_mentioned", "assessment_authority": "delegated_automated_trial", "support_records": [{"run_id": "original", "document_id": "doc_1", "document_version": "preprint", "independence_group": "not_human_verified", "source_map_status": "automated_trial_only", "data_status": "not_checked", "conditions_status": "not_checked", "stance": "supports"}], "reproducibility": {"protocol_status": "not_checked", "materials_status": "not_checked", "measurement_status": "not_checked", "raw_data_status": "not_checked", "assessment": "not_assessed"}, "independent_reproduction": {"status": "not_attempted", "independent_run_id": None, "result_comparison": "not_available", "review_status": "not_reviewed"}, "limitations": ["Not human reviewed."]}]}
            write_evidence_maturity_registry(run / "evidence_maturity_registry.json", registry)
            write_evidence_maturity_registry_audit(run / "evidence_maturity_registry_audit.json", audit_evidence_maturity_registry_against_runs(registry, runs))
            package = export_run_package(run)
            self.assertIn("evidence_maturity_registry.json", package["artifacts"])
            self.assertIn("fleet_assignment.json", package["artifacts"])
            restored = restore_run_package(runs, "resume_original", package)
            self.assertTrue((restored / "evidence_maturity_registry.json").is_file())
            export_run_to_ui(runs, "resume_original")
            bundle = json.loads((restored / "ui.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle["evidence_maturity_registry_delivery_status"], "accepted")
            tampered = copy.deepcopy(package)
            tampered["artifacts"]["evidence_maturity_registry.json"]["claims"][0]["claim_text"] = "Changed statement."
            tampered["artifact_sha256"]["evidence_maturity_registry.json"] = hashlib.sha256((json.dumps(tampered["artifacts"]["evidence_maturity_registry.json"], ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")).hexdigest()
            with self.assertRaises(RunPackageError):
                validate_run_package(tampered)
            bad_assignment = copy.deepcopy(package)
            bad_assignment["artifacts"]["fleet_assignment.json"]["mission_id"] = "another_mission"
            bad_assignment["artifact_sha256"]["fleet_assignment.json"] = hashlib.sha256((json.dumps(bad_assignment["artifacts"]["fleet_assignment.json"], ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")).hexdigest()
            with self.assertRaises(RunPackageError):
                validate_run_package(bad_assignment)

