import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from tests.test_ingestion import draft


class CliIngestionTests(unittest.TestCase):
    def test_ingest_evidence_records_only_a_summary_in_cli_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "ingestion_cli"
            run_dir.mkdir()
            (run_dir / "mission.json").write_text(json.dumps({"mission_id": "mission_cli"}), encoding="utf-8")
            (run_dir / "retrieval_candidates.json").write_text(
                json.dumps({"candidates": [{"document_id": "doc_1", "is_content_accessible": True}]}),
                encoding="utf-8",
            )
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
