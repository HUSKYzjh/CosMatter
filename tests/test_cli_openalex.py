import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.config import Settings
from cosmatter.models import AccessPolicy, EvidenceCard, MissionBrief, Provenance, ReviewStatus, Stance
from cosmatter.openalex import OpenAlexWork
from cosmatter.verification import VerificationDecision


class CliOpenAlexTests(unittest.TestCase):
    def test_expansion_requires_accepted_evidence_and_hides_relation_ids_from_audit_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "openalex_cli"
            run_dir.mkdir()
            mission = MissionBrief(question="q", material="BiFeO3", property_name="phase", scope="scope", mission_id="mission_1")
            card = EvidenceCard(claim="claim", stance=Stance.SUPPORT, material="BiFeO3", property_name="phase", conditions={}, quote="short", provenance=Provenance(document_id="doc_1", locator="p.1", source="fixture", doi="10.1000/test", access_policy=AccessPolicy.AUTHORIZED), evidence_id="evidence_1")
            decision = VerificationDecision(mission_id="mission_1", evidence_id="evidence_1", status=ReviewStatus.ACCEPTED, reason="accepted")
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run_dir / "evidence_cards.json").write_text(json.dumps([card.to_dict()]), encoding="utf-8")
            (run_dir / "verification_decisions.json").write_text(json.dumps([decision.to_dict()]), encoding="utf-8")
            output = io.StringIO()
            settings = Settings.load({"OPENALEX_API_KEY": "test-key"})
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), patch("cosmatter.cli.Settings.load", return_value=settings), patch("cosmatter.cli.OpenAlexAdapter.work_relations_by_doi", return_value=OpenAlexWork("https://openalex.org/W1", ("https://openalex.org/W2",), (), "private")), contextlib.redirect_stdout(output):
                status = main(["expand-openalex-relations", "--run-id", "openalex_cli", "--evidence-id", "evidence_1"])
            audit = (run_dir / "events.jsonl").read_text(encoding="utf-8")
            relation = (run_dir / "relation_expansion.json").read_text(encoding="utf-8")

        self.assertEqual(status, 0, output.getvalue())
        self.assertNotIn("https://openalex.org/W2", output.getvalue())
        self.assertNotIn("https://openalex.org/W2", audit)
        self.assertIn("https://openalex.org/W2", relation)
