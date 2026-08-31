import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.decision_memory import DecisionMemoryError, load_decision_memory_index, rebuild_decision_memory_index, write_decision_memory_entry


def entry(**overrides):
    return {
        "id": "sciverse-rate-limit", "category": "failure_recovery", "status": "active",
        "source": "local_audit", "created_at": "2026-08-29T00:00:00+00:00", "expires_on": "2026-12-31",
        "title": "Sciverse rate-limit recovery", "body": "After a rate-limit event, require a new explicit run decision before resuming.",
        **overrides,
    }


class DecisionMemoryTests(unittest.TestCase):
    def test_markdown_is_source_of_truth_and_index_rebuilds_after_human_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Path(directory) / "memory"
            path = write_decision_memory_entry(memory, entry())
            index = load_decision_memory_index(memory)
            self.assertEqual(index["entry_count"], 1)
            self.assertEqual(index["entries"][0]["status"], "active")
            self.assertNotIn("After a rate-limit", json.dumps(index))
            path.write_text(path.read_text(encoding="utf-8").replace("status: active", "status: resolved"), encoding="utf-8")
            rebuilt = rebuild_decision_memory_index(memory)
            self.assertEqual(rebuilt["entries"][0]["status"], "resolved")

    def test_scientific_content_and_invalid_markdown_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Path(directory) / "memory"
            with self.assertRaises(DecisionMemoryError):
                write_decision_memory_entry(memory, entry(body="This paper quote must be remembered."))
            memory.mkdir()
            (memory / "bad-entry.md").write_text("unstructured", encoding="utf-8")
            with self.assertRaises(DecisionMemoryError):
                rebuild_decision_memory_index(memory)

    def test_cli_writes_and_lists_metadata_without_note_body(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "entry.json"; input_path.write_text(json.dumps(entry()), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._decision_memory_dir", return_value=root / "memory"), contextlib.redirect_stdout(output):
                self.assertEqual(main(["record-decision-memory", "--input", str(input_path)]), 0)
                self.assertEqual(main(["list-decision-memory"]), 0)
            rendered = output.getvalue()
            self.assertIn('"entry_count": 1', rendered)
            self.assertNotIn("After a rate-limit", rendered)
            self.assertNotIn(str(root), rendered)


if __name__ == "__main__":
    unittest.main()
