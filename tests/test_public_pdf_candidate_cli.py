import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.models import MissionBrief
from cosmatter.planning import FlightPlan, write_approved_flight_plan


class PublicPdfCandidateCliTests(unittest.TestCase):
    def test_registers_only_metadata_and_probe_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "public_pdf"
            run.mkdir(parents=True)
            mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_public_pdf")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            plan = FlightPlan(mission_id=mission.mission_id, subquestions=("q",), queries=("BiFeO3 phase",), counter_queries=("BiFeO3 phase disagreement",), max_papers=5)
            write_approved_flight_plan(run, plan)
            output = io.StringIO()
            probe = {"schema_version": "cosmatter.public-pdf-probe-receipt/v1", "trust_status": "public_pdf_route_confirmed_not_content_review_or_evidence", "source_url_sha256": "a" * 64, "redirect_count": 0, "final_host": "arxiv.org", "status_class": "2xx", "pdf_signature_confirmed": True, "cookies_or_credentials_used": False, "remote_body_persisted": False}
            source_url = "https://arxiv.org/pdf/0909.4979"
            with patch("cosmatter.cli._runs_dir", return_value=runs), patch("cosmatter.cli.probe_public_pdf", return_value=probe), contextlib.redirect_stdout(output):
                status = main(["register-public-pdf-candidate", "--run-id", "public_pdf", "--query-index", "0", "--document-id", "arxiv:0909.4979", "--title", "Strain-induced isosymmetric phase transition", "--publication-year", "2010", "--source-url", source_url])
            artifact = (run / "retrieval_candidates.json").read_text(encoding="utf-8")
            receipt = (run / "public_pdf_probe_receipts.jsonl").read_text(encoding="utf-8")
            events = (run / "events.jsonl").read_text(encoding="utf-8")
        self.assertEqual(status, 0, output.getvalue())
        self.assertIn("arxiv:0909.4979", artifact)
        self.assertIn("PublicOpenAccess", artifact)
        self.assertNotIn(source_url, artifact + receipt + events + output.getvalue())

    def test_probe_refusal_does_not_write_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "public_pdf_fail"
            run.mkdir(parents=True)
            mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_public_pdf_fail")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            write_approved_flight_plan(run, FlightPlan(mission_id=mission.mission_id, subquestions=("q",), queries=("BiFeO3 phase",), counter_queries=("BiFeO3 counter",), max_papers=5))
            with patch("cosmatter.cli._runs_dir", return_value=runs), patch("cosmatter.cli.probe_public_pdf", side_effect=ValueError("unsafe source")):
                status = main(["register-public-pdf-candidate", "--run-id", "public_pdf_fail", "--query-index", "0", "--document-id", "public:1", "--title", "Paper", "--source-url", "https://arxiv.org/pdf/1"])
        self.assertEqual(status, 2)
        self.assertFalse((run / "retrieval_candidates.json").exists())

    def test_approved_plan_arxiv_discovery_writes_metadata_without_urls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "public_arxiv"
            run.mkdir(parents=True)
            mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_public_arxiv")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            write_approved_flight_plan(run, FlightPlan(mission_id=mission.mission_id, subquestions=("q",), queries=("BiFeO3 phase",), counter_queries=("BiFeO3 counter",), max_papers=5))
            discovery = ([{"document_id": "arxiv:0909.4979", "title": "Public BFO paper", "query": "BiFeO3 phase", "source": "PublicArXiv", "publication_year": 2010, "is_content_accessible": False}], {"schema_version": "cosmatter.public-discovery-receipt/v1", "trust_status": "untrusted_public_candidate_discovery_not_download_or_evidence", "query_length": 13, "redirect_count": 0, "final_host": "export.arxiv.org", "status_class": "2xx", "candidate_count": 1, "cookies_or_credentials_used": False, "download_or_import_performed": False})
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), patch("cosmatter.cli.discover_arxiv_candidates", return_value=discovery), contextlib.redirect_stdout(output):
                status = main(["execute-plan-public-arxiv-discovery", "--run-id", "public_arxiv", "--query-index", "0"])
            artifact = (run / "retrieval_candidates.json").read_text(encoding="utf-8")
            receipt = (run / "public_candidate_discovery_receipts.jsonl").read_text(encoding="utf-8")
            events = (run / "events.jsonl").read_text(encoding="utf-8")
        self.assertEqual(status, 0, output.getvalue())
        self.assertIn("PublicArXiv", artifact)
        self.assertIn('"is_content_accessible": false', artifact)
        self.assertNotIn("https://", artifact + receipt + events + output.getvalue())
