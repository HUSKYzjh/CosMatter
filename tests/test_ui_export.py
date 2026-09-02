import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.audit import FlightRecorder
from cosmatter.cli import main
from cosmatter.dispatch import MissionDispatcher
from cosmatter.models import MissionBrief, MissionState
from cosmatter.simulation_campaign import (
    SIMULATION_CAMPAIGN_BOUNDARY,
    SIMULATION_CAMPAIGN_SCHEMA_VERSION,
    SIMULATION_CAMPAIGN_TRUST_STATUS,
    build_approved_simulation_campaign,
)
from cosmatter.source_map import AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS, source_map_from_review, write_source_map_for_document
from cosmatter.ui_export import UiExportError, export_run_to_ui


class UiExportTests(unittest.TestCase):
    def _write_run(self, runs_dir: Path, run_id: str) -> None:
        run_dir = runs_dir / run_id
        run_dir.mkdir()
        brief = MissionBrief(
            mission_id="mission_ui_export_001",
            question="为什么两篇论文对 BiFeO3 应变相变有不同结论？",
            material="BiFeO3",
            property_name="phase stability",
            scope="epitaxial thin films",
        )
        assignment = MissionDispatcher.from_project().assign(brief)
        (run_dir / "mission.json").write_text(json.dumps(brief.to_dict()), encoding="utf-8")
        (run_dir / "fleet_assignment.json").write_text(json.dumps(assignment.to_dict()), encoding="utf-8")
        FlightRecorder(runs_dir, run_id).record(
            event_type="state_transition",
            actor="orchestrator",
            state=MissionState.RETRIEVE,
            payload={"token": "must never appear in UI JSON"},
        )

    def test_cli_exports_a_redacted_ui_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            self._write_run(runs_dir, "ui_export_test")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(output):
                status = main(["export-ui", "--run-id", "ui_export_test"])
            result = json.loads(output.getvalue())
            bundle_path = runs_dir / "ui_export_test" / "ui.json"
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

        self.assertEqual(status, 0)
        self.assertEqual(result["schema_version"], "1.0")
        self.assertEqual(bundle["mission"]["material"], "BiFeO3")
        self.assertEqual(bundle["fleet_assignment"]["fleet_type"], "route_diagnostics")
        self.assertEqual(bundle["status"]["mission_state"], "RETRIEVE")
        self.assertEqual(bundle["evidence_cards"], [])
        serialised = json.dumps(bundle).lower()
        self.assertNotIn("must never appear", serialised)
        self.assertNotIn("api_key", serialised)
        self.assertNotIn("authorization", serialised)

    def test_export_projects_only_safe_plan_only_campaign_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            self._write_run(runs_dir, "simulation_campaign_export")
            run_dir = runs_dir / "simulation_campaign_export"
            mission = MissionBrief(
                mission_id="mission_ui_export_001", question="为什么两篇论文对 BiFeO3 应变相变有不同结论？",
                material="BiFeO3", property_name="phase stability", scope="epitaxial thin films",
            )
            campaign = build_approved_simulation_campaign(
                mission=mission, accepted_evidence_ids={"evidence_accepted"}, payload={
                    "schema_version": SIMULATION_CAMPAIGN_SCHEMA_VERSION, "trust_status": SIMULATION_CAMPAIGN_TRUST_STATUS,
                    "campaign_id": "campaign_ui_001", "mission_id": mission.mission_id, "simulation_kind": "dft",
                    "evidence_ids": ["evidence_accepted"],
                    "hypothesis": {"statement": "bounded hypothesis", "variables": "strain", "control": "composition", "observable": "aggregate value", "falsifier": "no difference"},
                    "protocol": {"engine": "external engine", "recipe_id": "recipe_001", "method_boundary": "reviewed method", "convergence_or_sampling_boundary": "reviewed convergence", "result_summary_boundary": "aggregate results only"},
                    "input_manifest": {"input_count": 1, "inputs": [{"input_id": "input_001", "sha256": "c" * 64, "source_kind": "reviewed manifest", "license_status": "reviewed license clearance"}]},
                    "execution_profile": {"mode": "disabled", "adapter_kind": "none", "allowed_engines": [], "allowed_recipe_ids": [], "max_jobs": 0, "max_gpu_jobs": 0, "max_dft_jobs": 0, "scheduler_submission_enabled": False, "polling_enabled": False},
                    "approval": {"status": "approved_plan_only", "reviewer": "private reviewer", "approved_on": "2026-09-02", "rationale": "bounded evidence"},
                    "execution_permitted": False, "execution_boundary": SIMULATION_CAMPAIGN_BOUNDARY,
                },
            )
            (run_dir / "simulation_campaign.json").write_text(json.dumps(campaign), encoding="utf-8")
            export_run_to_ui(runs_dir, "simulation_campaign_export")
            bundle = json.loads((run_dir / "ui.json").read_text(encoding="utf-8"))

        self.assertEqual(bundle["simulation_campaign_delivery_status"], "approved")
        self.assertEqual(bundle["simulation_campaign"], {"delivery_status": "approved_plan_only", "simulation_kind": "dft", "evidence_count": 1, "input_count": 1, "execution_permitted": False, "execution_state": "not_started"})
        serialised = json.dumps(bundle)
        self.assertNotIn("evidence_accepted", serialised)
        self.assertNotIn("private reviewer", serialised)
        self.assertNotIn("c" * 64, serialised)

    def test_maturity_registry_reaches_ui_only_after_a_bound_link_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            self._write_run(runs_dir, "maturity_registry_run")
            run_dir = runs_dir / "maturity_registry_run"
            (run_dir / "retrieval_candidates.json").write_text(json.dumps({"candidates": [{"document_id": "doc_1", "title": "Bounded registry test paper", "source": "Sciverse", "publication_year": 2024}]}), encoding="utf-8")
            source_map = source_map_from_review(mission_id="mission_ui_export_001", document_id="doc_1", source_task={"document_id": "doc_1", "provider": "mineru", "state": "done", "task_id": "task_1"}, selection={"document_id": "doc_1", "segments": [{"segment_id": "segment_1", "locator": "p. 1", "kind": "paragraph", "quote": "Bounded test excerpt."}]})
            write_source_map_for_document(run_dir, source_map)
            input_path = runs_dir / "reviewed_registry.json"
            input_path.write_text(json.dumps({"schema_version": "cosmatter.evidence-maturity-registry/v1", "registry_id": "registry_1", "question_id": "mission_ui_export_001", "trust_status": "human_reviewed_evidence_maturity_registry_not_scientific_conclusion", "claims": [{"claim_id": "claim_1", "claim_text": "A bounded literature statement.", "maturity_level": "literature_mentioned", "assessment_authority": "human_source_review", "support_records": [{"run_id": "maturity_registry_run", "document_id": "doc_1", "document_version": "preprint", "independence_group": "not_human_verified", "source_map_status": "human_reviewed", "data_status": "not_checked", "conditions_status": "not_checked", "stance": "supports"}], "reproducibility": {"protocol_status": "not_checked", "materials_status": "not_checked", "measurement_status": "not_checked", "raw_data_status": "not_checked", "assessment": "not_assessed"}, "independent_reproduction": {"status": "not_attempted", "independent_run_id": None, "result_comparison": "not_available", "review_status": "not_reviewed"}, "limitations": ["Not human reviewed data."]}]}), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(output):
                self.assertEqual(main(["record-evidence-maturity-registry", "--run-id", "maturity_registry_run", "--input", str(input_path)]), 0)
                self.assertEqual(main(["export-ui", "--run-id", "maturity_registry_run"]), 0, output.getvalue())
            bundle = json.loads((run_dir / "ui.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle["evidence_maturity_registry_delivery_status"], "accepted")
            self.assertEqual(bundle["evidence_maturity_registry"]["registry_id"], "registry_1")
            self.assertTrue((run_dir / "sensitive_artifact_audit.json").exists())
            registry_path = run_dir / "evidence_maturity_registry.json"
            tampered = json.loads(registry_path.read_text(encoding="utf-8"))
            tampered["claims"][0]["claim_text"] = "A changed bounded literature statement."
            registry_path.write_text(json.dumps(tampered), encoding="utf-8")
            export_run_to_ui(runs_dir, "maturity_registry_run")
            rejected = json.loads((run_dir / "ui.json").read_text(encoding="utf-8"))

        self.assertEqual(rejected["evidence_maturity_registry_delivery_status"], "rejected")
        self.assertIsNone(rejected["evidence_maturity_registry"])

    def test_export_projects_an_allowlisted_timeline_without_raw_audit_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            self._write_run(runs_dir, "timeline_export")
            recorder = FlightRecorder(runs_dir, "timeline_export")
            recorder.record(
                event_type="mission_created",
                actor="mission_control_private",
                state=MissionState.INTAKE,
                payload={"question": "do not export this question", "token": "do-not-export"},
            )
            recorder.record(
                event_type="approved_plan_query_executed",
                actor="search_selection_private",
                state=MissionState.RETRIEVE,
                payload={"query_kind": "counter", "query": "do not export this query", "request_id": "private-request"},
            )
            recorder.record(
                event_type="source_parse_submitted",
                actor="document_parser_private",
                state=MissionState.EXTRACT,
                payload={"document_id": "private-document", "provider": "mineru", "task_id": "private-task"},
            )
            recorder.record(
                event_type="source_map_reviewed",
                actor="source_reviewer_private",
                state=MissionState.EXTRACT,
                payload={"document_id": "private-document", "segment_count": 1, "quote": "do not export this excerpt"},
            )
            recorder.record(
                event_type="condition_normalization_reviewed",
                actor="source_reviewer_private",
                state=MissionState.MAP,
                payload={"mapping_count": 1, "raw_field": "do not export this field", "unit": "do not export this unit"},
            )
            export_run_to_ui(runs_dir, "timeline_export")
            bundle = json.loads((runs_dir / "timeline_export" / "ui.json").read_text(encoding="utf-8"))

        self.assertEqual(
            [(item["station_type"], item["action"]) for item in bundle["timeline"]],
            [("question_intake", "任务已创建"), ("search_selection", "反例检索已完成"), ("evidence_extraction", "授权结构解析任务已提交"), ("evidence_extraction", "定位片段已人工复核"), ("cross_check_review", "条件字段名称与单位已人工规范化（未换算）")],
        )
        serialised = json.dumps(bundle, ensure_ascii=False)
        for forbidden in ("do not export", "private-request", "mission_control_private", "search_selection_private", "document_parser_private", "source_reviewer_private", "private-document", "private-task", "do not export this excerpt", "token"):
            self.assertNotIn(forbidden, serialised)

    def test_export_rejects_candidate_title_containing_a_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            self._write_run(runs_dir, "unsafe_candidate_title")
            (runs_dir / "unsafe_candidate_title" / "retrieval_candidates.json").write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "document_id": "doc_unsafe",
                                "title": "https://example.invalid/not-a-paper-title",
                                "source": "Sciverse",
                                "publication_year": 2024,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(UiExportError):
                export_run_to_ui(runs_dir, "unsafe_candidate_title")

    def test_export_projects_only_accepted_evidence_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "approved_evidence_run"
            self._write_run(runs_dir, "approved_evidence_run")
            evidence = [
                {
                    "evidence_id": "evidence_accepted",
                    "claim": "short synthetic claim",
                    "stance": "support",
                    "material": "BiFeO3",
                    "property_name": "phase stability",
                    "conditions": {"sample_form": "film"},
                    "quote": "short synthetic quote",
                    "provenance": {
                        "document_id": "doc_fixture",
                        "locator": "page:1",
                        "source": "fixture",
                        "access_policy": "oa",
                    },
                },
                {
                    "evidence_id": "evidence_rejected",
                    "claim": "withheld synthetic claim",
                    "stance": "contradict",
                    "material": "BiFeO3",
                    "property_name": "phase stability",
                    "conditions": {"sample_form": "film"},
                    "quote": "withheld synthetic quote",
                    "provenance": {
                        "document_id": "doc_fixture_2",
                        "locator": "page:2",
                        "source": "fixture",
                        "access_policy": "oa",
                    },
                },
            ]
            decisions = [
                {
                    "mission_id": "mission_ui_export_001",
                    "evidence_id": "evidence_accepted",
                    "status": "accepted",
                    "reason": "complete",
                },
                {
                    "mission_id": "mission_ui_export_001",
                    "evidence_id": "evidence_rejected",
                    "status": "rejected",
                    "reason": "missing conditions",
                },
            ]
            (run_dir / "evidence_cards.json").write_text(json.dumps(evidence), encoding="utf-8")
            (run_dir / "verification_decisions.json").write_text(json.dumps(decisions), encoding="utf-8")
            write_source_map_for_document(run_dir, source_map_from_review(
                mission_id="mission_ui_export_001", document_id="doc_fixture",
                source_task={"provider": "mineru", "task_id": "task_fixture", "state": "done", "document_id": "doc_fixture"},
                selection={"document_id": "doc_fixture", "segments": [{"segment_id": "s1", "locator": "page:1", "kind": "paragraph", "quote": "short synthetic quote"}]},
            ))
            export_run_to_ui(runs_dir, "approved_evidence_run")
            bundle = json.loads((run_dir / "ui.json").read_text(encoding="utf-8"))

        self.assertEqual([card["evidence_id"] for card in bundle["evidence_cards"]], ["evidence_accepted"])
        self.assertEqual(bundle["status"]["verification_summary"]["rejected_count"], 1)
        self.assertEqual(bundle["verification_decisions"], [])
    def test_export_includes_valid_condition_matrix_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            self._write_run(runs_dir, "matrix_export")
            matrix = [
                {
                    "condition_cluster": "synthetic cluster",
                    "supporting_evidence_ids": ["support"],
                    "contradicting_evidence_ids": ["contradict"],
                    "differing_fields": ["strain_percent"],
                    "unknowns": [],
                }
            ]
            (runs_dir / "matrix_export" / "condition_matrix.json").write_text(json.dumps(matrix), encoding="utf-8")
            export_run_to_ui(runs_dir, "matrix_export")
            bundle = json.loads((runs_dir / "matrix_export" / "ui.json").read_text(encoding="utf-8"))

        self.assertEqual(bundle["condition_matrix"], matrix)

    def test_export_projects_human_condition_field_normalization_without_values_or_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_id = "normalization_export"
            self._write_run(runs_dir, run_id)
            run_dir = runs_dir / run_id
            evidence = [{
                "evidence_id": "evidence_normalized",
                "claim": "short synthetic claim",
                "stance": "support",
                "material": "BiFeO3",
                "property_name": "phase stability",
                "conditions": {"thickness_nm": 30},
                "quote": "short synthetic quote",
                "provenance": {"document_id": "doc_normalized", "locator": "page:1", "source": "fixture", "access_policy": "oa"},
            }]
            decisions = [{"mission_id": "mission_ui_export_001", "evidence_id": "evidence_normalized", "status": "accepted", "reason": "complete"}]
            (run_dir / "evidence_cards.json").write_text(json.dumps(evidence), encoding="utf-8")
            (run_dir / "verification_decisions.json").write_text(json.dumps(decisions), encoding="utf-8")
            write_source_map_for_document(run_dir, source_map_from_review(
                mission_id="mission_ui_export_001", document_id="doc_normalized",
                source_task={"provider": "mineru", "task_id": "task_normalized", "state": "done", "document_id": "doc_normalized"},
                selection={"document_id": "doc_normalized", "segments": [{"segment_id": "s1", "locator": "page:1", "kind": "paragraph", "quote": "short synthetic quote"}]},
            ))
            (run_dir / "condition_normalization.json").write_text(json.dumps({
                "schema_version": "1.0",
                "mission_id": "mission_ui_export_001",
                "trust_status": "human_reviewed_condition_normalization_no_conversion",
                "mappings": [{"evidence_id": "evidence_normalized", "raw_field": "thickness_nm", "canonical_field": "thickness", "unit": "nm"}],
            }), encoding="utf-8")
            export_run_to_ui(runs_dir, run_id)
            bundle = json.loads((run_dir / "ui.json").read_text(encoding="utf-8"))

        self.assertEqual(bundle["condition_normalization"], {
            "trust_status": "human_reviewed_condition_normalization_no_conversion",
            "mappings": [{"evidence_id": "evidence_normalized", "raw_field": "thickness_nm", "canonical_field": "thickness", "unit": "nm"}],
        })
        self.assertNotIn("normalized_value", bundle["condition_normalization"])
        self.assertNotIn("converted_value", bundle["condition_normalization"])

    def test_export_rejects_path_traversal_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(UiExportError):
                export_run_to_ui(Path(directory), "../outside")

    def test_cli_returns_safe_error_for_missing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=Path(directory)), contextlib.redirect_stdout(output):
                status = main(["export-ui", "--run-id", "missing_run"])
            payload = json.loads(output.getvalue())

        self.assertEqual(status, 2)
        self.assertIn("missing mission artifact", payload["error"])


    def test_cli_pipeline_can_link_artifacts_with_a_stable_mission_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            common = [
                "--question", "为什么两篇论文对 BiFeO3 应变相变有不同结论？",
                "--material", "BiFeO3",
                "--property", "phase stability",
                "--scope", "epitaxial thin films",
                "--run-id", "linked_run",
                "--mission-id", "mission_linked_001",
            ]
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["create-mission", *common]), 0)
                self.assertEqual(main(["assign-fleet", *common]), 0)
                self.assertEqual(main(["export-ui", "--run-id", "linked_run"]), 0)
            bundle = json.loads((runs_dir / "linked_run" / "ui.json").read_text(encoding="utf-8"))

        self.assertEqual(bundle["mission"]["mission_id"], "mission_linked_001")
        self.assertEqual(bundle["fleet_assignment"]["fleet_type"], "route_diagnostics")
if __name__ == "__main__":
    unittest.main()
