import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.sciverse import SciverseResponse


class CliRetrievalTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
