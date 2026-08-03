import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.dispatch import MissionDispatcher
from cosmatter.models import AccessPolicy, EvidenceCard, MissionBrief, Provenance, ReviewStatus, Stance
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
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(output):
                self.assertEqual(main(["build-report", "--run-id", "report_cli"]), 0)
                self.assertEqual(main(["export-ui", "--run-id", "report_cli"]), 0)
            ui_bundle = json.loads((run_dir / "ui.json").read_text(encoding="utf-8"))
            audit = (run_dir / "events.jsonl").read_text(encoding="utf-8")

        self.assertEqual(ui_bundle["mission_report"]["evidence_ids"], ["evidence_report_cli"])
        self.assertNotIn("synthetic short quote", json.dumps(ui_bundle["mission_report"]))
        self.assertIn("mission_report_built", audit)


if __name__ == "__main__":
    unittest.main()
