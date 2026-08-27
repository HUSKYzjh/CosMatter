import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.dispatch import MissionDispatcher
from cosmatter.models import AccessPolicy, EvidenceCard, FlightPlan, MissionBrief, Provenance, ReviewStatus, Stance
from cosmatter.source_map import source_map_from_review, write_source_map_for_document
from cosmatter.verification import VerificationDecision


class CliReportTests(unittest.TestCase):
    def test_build_report_then_export_ui_keeps_a_safe_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "report_cli"
            run_dir.mkdir()
            mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_report_cli")
            assignment = MissionDispatcher.from_project().assign(mission)
            card = EvidenceCard(
                "synthetic claim",
                Stance.SUPPORT,
                "BiFeO3",
                "phase stability",
                {"sample_form": "film"},
                "synthetic short quote",
                Provenance("doc_1", "page:1", "fixture", access_policy=AccessPolicy.OA),
                evidence_id="evidence_report_cli",
            )
            decision = VerificationDecision(mission.mission_id, card.evidence_id, ReviewStatus.ACCEPTED, "complete")
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run_dir / "fleet_assignment.json").write_text(json.dumps(assignment.to_dict()), encoding="utf-8")
            (run_dir / "evidence_cards.json").write_text(json.dumps([card.to_dict()]), encoding="utf-8")
            (run_dir / "verification_decisions.json").write_text(json.dumps([decision.to_dict()]), encoding="utf-8")
            write_source_map_for_document(run_dir, source_map_from_review(
                mission_id=mission.mission_id, document_id="doc_1",
                source_task={"provider": "mineru", "task_id": "task_1", "state": "done", "document_id": "doc_1"},
                selection={"document_id": "doc_1", "segments": [{"segment_id": "s1", "locator": "page:1", "kind": "paragraph", "quote": "synthetic short quote"}]},
            ))
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(output):
                self.assertEqual(main(["build-report", "--run-id", "report_cli"]), 0)
                self.assertEqual(main(["export-ui", "--run-id", "report_cli"]), 0)
            ui_bundle = json.loads((run_dir / "ui.json").read_text(encoding="utf-8"))
            audit = (run_dir / "events.jsonl").read_text(encoding="utf-8")
            structured_report_exists = (run_dir / "research_report.md").exists()

        self.assertEqual(ui_bundle["mission_report"]["evidence_ids"], ["evidence_report_cli"])
        self.assertNotIn("synthetic short quote", json.dumps(ui_bundle["mission_report"]))
        self.assertIn("mission_report_built", audit)
        self.assertTrue(structured_report_exists)


    def test_gap_candidates_flow_from_condition_matrix_to_report_and_ui(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "gap_report_cli"
            run_dir.mkdir()
            mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_gap_report_cli")
            assignment = MissionDispatcher.from_project().assign(mission)
            support = EvidenceCard("support", Stance.SUPPORT, "BiFeO3", "phase stability", {"sample_form": "film", "strain_percent": 1}, "located support", Provenance("doc_support", "page:1", "fixture", access_policy=AccessPolicy.OA), evidence_id="evidence_support")
            contradict = EvidenceCard("contradict", Stance.CONTRADICT, "BiFeO3", "phase stability", {"sample_form": "film", "strain_percent": 2}, "located contradict", Provenance("doc_contradict", "page:2", "fixture", access_policy=AccessPolicy.OA), evidence_id="evidence_contradict")
            decisions = (
                VerificationDecision(mission.mission_id, support.evidence_id, ReviewStatus.ACCEPTED, "complete"),
                VerificationDecision(mission.mission_id, contradict.evidence_id, ReviewStatus.ACCEPTED, "complete"),
            )
            matrix = [{"condition_cluster": "film", "supporting_evidence_ids": [support.evidence_id], "contradicting_evidence_ids": [contradict.evidence_id], "differing_fields": ["strain_percent"], "unknowns": []}]
            plan = FlightPlan(mission.mission_id, ("Which condition differs?",), ("primary",), ("counter",))
            search_history = {"schema_version": "1.1", "query": "counter", "candidate_count": 0, "search_count": 1, "candidates": [], "searches": [{"query": "counter", "candidate_count": 0, "candidates": []}]}
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run_dir / "fleet_assignment.json").write_text(json.dumps(assignment.to_dict()), encoding="utf-8")
            (run_dir / "flight_plan.json").write_text(json.dumps(plan.to_dict()), encoding="utf-8")
            (run_dir / "retrieval_candidates.json").write_text(json.dumps(search_history), encoding="utf-8")
            (run_dir / "evidence_cards.json").write_text(json.dumps([support.to_dict(), contradict.to_dict()]), encoding="utf-8")
            (run_dir / "verification_decisions.json").write_text(json.dumps([item.to_dict() for item in decisions]), encoding="utf-8")
            for document_id, locator, quote in (("doc_support", "page:1", "located support"), ("doc_contradict", "page:2", "located contradict")):
                write_source_map_for_document(run_dir, source_map_from_review(
                    mission_id=mission.mission_id, document_id=document_id,
                    source_task={"provider": "mineru", "task_id": f"task_{document_id}", "state": "done", "document_id": document_id},
                    selection={"document_id": document_id, "segments": [{"segment_id": f"seg_{document_id}", "locator": locator, "kind": "paragraph", "quote": quote}]},
                ))
            (run_dir / "condition_matrix.json").write_text(json.dumps(matrix), encoding="utf-8")
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["generate-gap-candidates", "--run-id", "gap_report_cli"]), 0)
                self.assertEqual(main(["build-report", "--run-id", "gap_report_cli"]), 0)
                self.assertEqual(main(["export-ui", "--run-id", "gap_report_cli"]), 0)
            report = json.loads((run_dir / "mission_report.json").read_text(encoding="utf-8"))
            bundle = json.loads((run_dir / "ui.json").read_text(encoding="utf-8"))

        self.assertEqual(report["research_gap_candidate_ids"], ["gap_001"])
        self.assertEqual(bundle["research_gap_candidates"][0]["evidence_ids"], ["evidence_support", "evidence_contradict"])
        self.assertEqual(bundle["research_gap_candidates"][0]["review_status"], "candidate_requires_human_review")
        self.assertIn("gap:gap_001", [node["node_id"] for node in bundle["literature_graph"]["nodes"]])
        self.assertIn("gap_evidence_basis", [edge["edge_type"] for edge in bundle["literature_graph"]["edges"]])


if __name__ == "__main__":
    unittest.main()
