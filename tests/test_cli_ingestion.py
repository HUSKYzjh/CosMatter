import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.candidate_screening import candidate_screening_from_review, write_candidate_screening
from cosmatter.cli import main
from cosmatter.source_map import source_map_from_review, write_source_map_for_document
from tests.test_ingestion import draft


class CliIngestionTests(unittest.TestCase):
    def test_ingest_evidence_records_only_a_summary_in_cli_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "ingestion_cli"
            run_dir.mkdir()
            (run_dir / "mission.json").write_text(json.dumps({"mission_id": "mission_cli"}), encoding="utf-8")
            candidates = {"candidates": [{"document_id": "doc_1", "is_content_accessible": True}]}
            (run_dir / "retrieval_candidates.json").write_text(json.dumps(candidates), encoding="utf-8")
            write_candidate_screening(run_dir, candidate_screening_from_review(
                "mission_cli", candidates,
                {"decisions": [{"document_id": "doc_1", "decision": "include_for_fulltext", "reason_codes": ["material_match"]}]},
            ))
            source_map = source_map_from_review(
                mission_id="mission_cli", document_id="doc_1",
                source_task={"provider": "mineru", "task_id": "task_1", "state": "done", "document_id": "doc_1"},
                selection={"document_id": "doc_1", "segments": [{"segment_id": "s1", "locator": "page:1", "kind": "paragraph", "quote": "Synthetic short quote only."}]},
            )
            write_source_map_for_document(run_dir, source_map)
            draft_path = runs_dir / "draft.json"
            draft_path.write_text(json.dumps(draft()), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(output):
                status = main(["ingest-evidence", "--run-id", "ingestion_cli", "--input", str(draft_path)])
            result = json.loads(output.getvalue())
            audit = (run_dir / "events.jsonl").read_text(encoding="utf-8")

        self.assertEqual(status, 0)
        self.assertEqual(result["status"], "accepted")
        self.assertNotIn("Synthetic short quote", output.getvalue())
        self.assertNotIn("Synthetic short quote", audit)


if __name__ == "__main__":
    unittest.main()
