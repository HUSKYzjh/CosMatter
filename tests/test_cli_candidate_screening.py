import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.mineru import MinerUTask
from cosmatter.models import MissionBrief
from cosmatter.source_parse import record_source_parse_task


class CliCandidateScreeningTests(unittest.TestCase):
    def _seed(self, run_dir: Path) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_cli_screen")
        (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
        (run_dir / "retrieval_candidates.json").write_text(
            json.dumps({"candidates": [
                {"document_id": "doc_keep", "title": "BiFeO3 films", "is_content_accessible": True},
                {"document_id": "doc_drop", "title": "Other material", "is_content_accessible": True},
            ]}),
            encoding="utf-8",
        )

    def test_template_then_complete_review_records_only_safe_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "screen_cli"
            run.mkdir(parents=True)
            self._seed(run)
            review = root / "review.json"
            review.write_text(json.dumps({"decisions": [
                {"document_id": "doc_keep", "decision": "include_for_fulltext", "reason_codes": ["material_match", "scope_match"]},
                {"document_id": "doc_drop", "decision": "exclude", "reason_codes": ["out_of_scope_material"]},
            ]}), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                self.assertEqual(main(["create-candidate-screening-template", "--run-id", "screen_cli"]), 0)
                self.assertEqual(main(["record-candidate-screening", "--run-id", "screen_cli", "--input", str(review)]), 0)
            template = json.loads((run / "candidate_screening_template.json").read_text(encoding="utf-8"))
            artifact = (run / "candidate_screening.json").read_text(encoding="utf-8")

        self.assertEqual(template["decisions"][0]["decision"], "unreviewed")
        self.assertNotIn("BiFeO3 films", artifact)
        self.assertNotIn("Other material", artifact)

    def test_source_map_recording_stops_without_screening(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory)
            run = runs / "screen_map_gate"
            run.mkdir()
            self._seed(run)
            record_source_parse_task(
                run, mission_id="mission_cli_screen", document_id="doc_keep",
                source_url="https://example.org/paper.pdf",
                task=MinerUTask("task_1", "done", "request_1"), model_version="fixture",
            )
            selection = runs / "selection.json"
            selection.write_text(json.dumps({"document_id": "doc_keep", "segments": [{"segment_id": "s1", "locator": "page:1", "kind": "paragraph", "quote": "short excerpt"}]}), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status = main(["record-source-map", "--run-id", "screen_map_gate", "--document-id", "doc_keep", "--input", str(selection)])
            result = json.loads(output.getvalue())

        self.assertEqual(status, 2)
        self.assertIn("completed human candidate screening", result["error"])

    def test_mineru_submission_stops_before_provider_without_screening(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory)
            run = runs / "screen_gate"
            run.mkdir()
            self._seed(run)
            output = io.StringIO()
            with (
                patch("cosmatter.cli._runs_dir", return_value=runs),
                patch("cosmatter.cli.MinerUAdapter.submit_remote_source") as submit,
                contextlib.redirect_stdout(output),
            ):
                status = main(["mineru-submit-url", "--run-id", "screen_gate", "--document-id", "doc_keep", "--source-url", "https://example.org/paper.pdf"])
            result = json.loads(output.getvalue())

        self.assertEqual(status, 2)
        self.assertIn("completed human candidate screening", result["error"])
        submit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
