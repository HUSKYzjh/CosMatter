import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.config import Settings
from cosmatter.mineru import MinerUTask
from cosmatter.models import MissionBrief
from cosmatter.source_parse import record_source_parse_task


class CliMinerUTests(unittest.TestCase):
    def test_submit_records_no_plain_source_url_in_output_or_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "mineru_cli"
            run_dir.mkdir()
            (run_dir / "mission.json").write_text(json.dumps(MissionBrief(question="test question", material="BiFeO3", property_name="phase stability", scope="test scope", mission_id="mission_cli").to_dict()), encoding="utf-8")
            (run_dir / "retrieval_candidates.json").write_text(
                json.dumps({"candidates": [{"document_id": "doc_1", "is_content_accessible": True}]}), encoding="utf-8"
            )
            settings = Settings.load({"MINERU_API_TOKEN": "test-token", "API_MAX_RETRIES": "1"})
            output = io.StringIO()
            source_url = "https://publisher.example/paper.pdf?opaque=temporary"
            with (
                patch("cosmatter.cli._runs_dir", return_value=runs_dir),
                patch("cosmatter.cli.Settings.load", return_value=settings),
                patch("cosmatter.cli.MinerUAdapter.submit_remote_source", return_value=MinerUTask("task_1", "pending", "request_1")),
                contextlib.redirect_stdout(output),
            ):
                status = main(["mineru-submit-url", "--run-id", "mineru_cli", "--document-id", "doc_1", "--source-url", source_url])
            self.assertEqual(status, 0, output.getvalue())
            audit = (run_dir / "events.jsonl").read_text(encoding="utf-8")
            ledger = (run_dir / "source_parse_tasks.json").read_text(encoding="utf-8")


        self.assertNotIn(source_url, output.getvalue())
        self.assertNotIn(source_url, audit)
        self.assertNotIn(source_url, ledger)
        self.assertNotIn("task_1", output.getvalue())
    def test_source_map_requires_completed_task_and_keeps_quote_out_of_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "source_map_cli"
            run_dir.mkdir()
            mission = MissionBrief(question="test question", material="BiFeO3", property_name="phase stability", scope="test scope", mission_id="mission_map")
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run_dir / "retrieval_candidates.json").write_text(
                json.dumps({"candidates": [{"document_id": "doc_1", "is_content_accessible": True}]}), encoding="utf-8"
            )
            record_source_parse_task(
                run_dir,
                mission_id="mission_map",
                document_id="doc_1",
                source_url="https://publisher.example/paper.pdf",
                task=MinerUTask("task_1", "done", "request_1"),
                model_version="vlm",
            )
            quote = "Reviewer-selected short excerpt."
            selection_path = runs_dir / "selection.json"
            selection_path.write_text(
                json.dumps({"document_id": "doc_1", "segments": [{"segment_id": "p1", "locator": "p. 2", "kind": "paragraph", "quote": quote}]}),
                encoding="utf-8",
            )
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(output):
                status = main(["record-source-map", "--run-id", "source_map_cli", "--document-id", "doc_1", "--input", str(selection_path)])
            audit = (run_dir / "events.jsonl").read_text(encoding="utf-8")
            source_map = (run_dir / "source_map.json").read_text(encoding="utf-8")

        self.assertEqual(status, 0, output.getvalue())
        self.assertNotIn(quote, output.getvalue())
        self.assertNotIn(quote, audit)
        self.assertIn(quote, source_map)
