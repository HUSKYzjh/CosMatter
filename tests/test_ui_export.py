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
