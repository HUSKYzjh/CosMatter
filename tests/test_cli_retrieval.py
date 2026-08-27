import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.sciverse import SciverseContentResponse, SciverseResponse
from cosmatter.candidate_screening import candidate_screening_from_review, write_candidate_screening
from cosmatter.models import MissionBrief


class CliRetrievalTests(unittest.TestCase):
    def test_local_zotero_search_writes_metadata_only_candidates(self) -> None:
        export = [{"key": "BFO1", "title": "BiFeO3 ferroelectric thin film", "date": "2023", "tags": ["ferroelectric"], "abstractNote": "not persisted"}]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export_path = root / "zotero.json"
            export_path.write_text(json.dumps(export), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=root / "runs"), contextlib.redirect_stdout(output):
                status = main(["local-zotero-search", "--input", str(export_path), "--query", "BiFeO3 ferroelectric", "--run-id", "local_cli"])
            result = json.loads(output.getvalue())
            artifact = (root / "runs" / "local_cli" / "retrieval_candidates.json").read_text(encoding="utf-8")
            audit = (root / "runs" / "local_cli" / "events.jsonl").read_text(encoding="utf-8")
        self.assertEqual(status, 0)
        self.assertEqual(result["candidate_count"], 1)
        self.assertIn("zotero:BFO1", artifact)
        self.assertNotIn("not persisted", artifact)
        self.assertNotIn(str(export_path), audit)

    def test_sciverse_search_writes_a_metadata_only_candidate_artifact(self) -> None:
        response = SciverseResponse(
            payload={
                "hits": [
                    {
                        "doc_id": "doc_1",
                        "title": "Safe candidate",
                        "score": 0.8,
                        "is_content_accessible": True,
                        "content": "raw full text must not be stored",
                    }
                ]
            },
            status_code=200,
            request_id="request_fixture",
        )
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            output = io.StringIO()
            with (
                patch("cosmatter.cli._runs_dir", return_value=runs_dir),
                patch("cosmatter.cli.SciverseAdapter") as adapter,
                contextlib.redirect_stdout(output),
            ):
                adapter.return_value.agentic_search.return_value = response
                status = main(["sciverse-search", "--query", "BiFeO3 phase", "--top-k", "3", "--run-id", "retrieval_cli"])
            result = json.loads(output.getvalue())
            candidates = json.loads((runs_dir / "retrieval_cli" / "retrieval_candidates.json").read_text(encoding="utf-8"))
            audit = (runs_dir / "retrieval_cli" / "events.jsonl").read_text(encoding="utf-8")

        self.assertEqual(status, 0)
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(candidates["candidates"][0]["document_id"], "doc_1")
        self.assertNotIn("raw full text", json.dumps(candidates))
        self.assertNotIn("raw full text", audit)


    def test_sciverse_context_requires_screening_and_never_persists_text_in_run(self) -> None:
        context = "authorized bounded source context"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "context_cli"
            run.mkdir(parents=True)
            mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_context")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            history = {"candidates": [{"document_id": "doc_1", "title": "paper", "is_content_accessible": True}]}
            (run / "retrieval_candidates.json").write_text(json.dumps(history), encoding="utf-8")
            screening = candidate_screening_from_review(mission.mission_id, history, {"decisions": [{"document_id": "doc_1", "decision": "include_for_fulltext", "reason_codes": ["material_match"]}]})
            write_candidate_screening(run, screening)
            output_path = root / "review.txt"
            output = io.StringIO()
            with (patch("cosmatter.cli._runs_dir", return_value=runs), patch("cosmatter.cli.SciverseAdapter") as adapter, contextlib.redirect_stdout(output)):
                adapter.return_value.read_content.return_value = SciverseContentResponse(context, 24, True, 200, "request_context")
                status = main(["sciverse-read-context", "--run-id", "context_cli", "--document-id", "doc_1", "--offset", "0", "--limit", "200", "--output", str(output_path)])
            reviewed_context = output_path.read_text(encoding="utf-8")
            event_log = (run / "events.jsonl").read_text(encoding="utf-8")
            receipt_log = (run / "provider_receipts.jsonl").read_text(encoding="utf-8")
            run_contents = "\n".join(path.read_text(encoding="utf-8") for path in run.rglob("*") if path.is_file())
        self.assertEqual(status, 0, output.getvalue())
        self.assertEqual(reviewed_context, context)
        self.assertNotIn(context, event_log)
        self.assertNotIn(context, receipt_log)
        self.assertNotIn(context, run_contents)

    def test_sciverse_context_refuses_unscreened_candidate_before_provider_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "context_reject"
            run.mkdir(parents=True)
            mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_reject")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run / "retrieval_candidates.json").write_text(json.dumps({"candidates": [{"document_id": "doc_1", "title": "paper", "is_content_accessible": True}]}), encoding="utf-8")
            output = io.StringIO()
            with (patch("cosmatter.cli._runs_dir", return_value=runs), patch("cosmatter.cli.SciverseAdapter") as adapter, contextlib.redirect_stdout(output)):
                status = main(["sciverse-read-context", "--run-id", "context_reject", "--document-id", "doc_1", "--output", str(root / "review.txt")])
            self.assertEqual(status, 2)
            adapter.return_value.read_content.assert_not_called()
            self.assertFalse((run / "provider_receipts.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
