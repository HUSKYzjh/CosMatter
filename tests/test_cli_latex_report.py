import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.models import AccessPolicy, EvidenceCard, MissionBrief, Provenance, ReviewStatus, Stance
from cosmatter.verification import VerificationDecision


class LatexReportCliTests(unittest.TestCase):
    def test_cli_exports_and_compiles_reviewed_latex_submission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, run = Path(directory), Path(directory) / "runs" / "latex_cli"
            run.mkdir(parents=True)
            mission = MissionBrief("question", "BiFeO3", "phase stability", "films", mission_id="mission_latex_cli")
            card = EvidenceCard(
                "Reviewed claim", Stance.SUPPORT, "BiFeO3", "phase stability", {"form": "film"},
                "bounded quote", Provenance("doc_latex", "page:1", "fixture", access_policy=AccessPolicy.LOCAL_ONLY), evidence_id="card_latex",
            )
            decision = VerificationDecision("mission_latex_cli", "card_latex", ReviewStatus.ACCEPTED, "reviewed")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run / "evidence_cards.json").write_text(json.dumps([card.to_dict()]), encoding="utf-8")
            (run / "verification_decisions.json").write_text(json.dumps([decision.to_dict()]), encoding="utf-8")
            (run / "retrieval_candidates.json").write_text(json.dumps({"candidates": [{"document_id": "doc_latex", "title": "A reference record", "source": "Fixture", "publication_year": 2026, "doi": "10.1000/latex"}]}), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=root / "runs"), contextlib.redirect_stdout(output):
                status = main(["export-latex-report", "--run-id", "latex_cli", "--compile"])
            self.assertEqual(status, 0, output.getvalue())
            package = run / "latex_submission"
            tex = (package / "main.tex").read_text(encoding="utf-8")
            audit = json.loads((package / "citation_audit.json").read_text(encoding="utf-8"))
            self.assertTrue((package / "main.pdf").is_file())
        self.assertIn("\\cite{", tex)
        self.assertNotIn("bounded quote", tex)
        self.assertTrue(audit["citation_bibliography_bijection"])


if __name__ == "__main__":
    unittest.main()
