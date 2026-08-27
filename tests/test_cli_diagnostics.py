import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.models import AccessPolicy, EvidenceCard, FlightPlan, MissionBrief, Provenance, ReviewStatus, Stance
from cosmatter.verification import VerificationDecision


def card(evidence_id: str, stance: Stance, strain: float) -> EvidenceCard:
    return EvidenceCard(
        "synthetic claim",
        stance,
        "BiFeO3",
        "phase stability",
        {
            "sample_form": "film",
            "strain_percent": strain,
            "substrate": "synthetic",
            "thickness_nm": 30,
            "temperature_k": 300,
            "method": "synthetic method",
        },
        "synthetic short quote",
        Provenance("doc_" + evidence_id, "page:1", "fixture", access_policy=AccessPolicy.OA),
        evidence_id=evidence_id,
    )


class CliDiagnosticsTests(unittest.TestCase):
    def test_diagnostics_writes_matrix_from_accepted_cards_and_export_ui_reads_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "diagnostics_cli"
            run_dir.mkdir()
            mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_diagnostics_cli")
            plan = FlightPlan(mission.mission_id, ("Which conditions?",), ("query",), ("counter query",))
            support = card("support", Stance.SUPPORT, -2.0)
            contradict = card("contradict", Stance.CONTRADICT, -1.0)
            decisions = [
                VerificationDecision(mission.mission_id, support.evidence_id, ReviewStatus.ACCEPTED, "complete"),
                VerificationDecision(mission.mission_id, contradict.evidence_id, ReviewStatus.ACCEPTED, "complete"),
            ]
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run_dir / "flight_plan.json").write_text(json.dumps(plan.to_dict()), encoding="utf-8")
            retrieval = {"schema_version": "1.1", "query": "counter query", "candidate_count": 0, "search_count": 1, "candidates": [], "searches": [{"query": "counter query", "candidate_count": 0, "candidates": []}]}
            (run_dir / "retrieval_candidates.json").write_text(json.dumps(retrieval), encoding="utf-8")
            (run_dir / "evidence_cards.json").write_text(json.dumps([support.to_dict(), contradict.to_dict()]), encoding="utf-8")
            (run_dir / "verification_decisions.json").write_text(json.dumps([item.to_dict() for item in decisions]), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(output):
                status = main(["diagnose-conditions", "--run-id", "diagnostics_cli"])
            result = json.loads(output.getvalue())
            matrix = json.loads((run_dir / "condition_matrix.json").read_text(encoding="utf-8"))

        self.assertEqual(status, 0)
        self.assertEqual(result["matrix_row_count"], 1)
        self.assertIn("strain_percent", matrix[0]["differing_fields"])
        self.assertNotIn("synthetic short quote", json.dumps(matrix))


if __name__ == "__main__":
    unittest.main()
