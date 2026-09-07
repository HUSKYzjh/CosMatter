import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.validation_rejections import (
    ValidationRejectionError,
    detect_cli_validation_rejection,
    load_validation_rejections,
    record_cli_validation_rejection,
    summarize_validation_rejections,
)


class ValidationRejectionTests(unittest.TestCase):
    def test_detects_only_allowlisted_parameter_classes_without_retaining_values(self) -> None:
        self.assertEqual(
            detect_cli_validation_rejection(["sciverse-read-context", "--limit", "8192"]),
            ("sciverse_read_context", "limit_above_maximum"),
        )
        self.assertEqual(
            detect_cli_validation_rejection(["sciverse-read-context", "--offset=-1"]),
            ("sciverse_read_context", "offset_below_minimum"),
        )
        self.assertEqual(
            detect_cli_validation_rejection(["sciverse-read-context", "--limit", "private-query"]),
            ("sciverse_read_context", "invalid_integer"),
        )
        self.assertIsNone(detect_cli_validation_rejection(["sciverse-read-context", "--limit", "4000"]))
        self.assertIsNone(detect_cli_validation_rejection(["another-command", "--limit", "8192"]))
        self.assertIsNone(detect_cli_validation_rejection(["sciverse-read-context", "--", "--limit", "8192"]))
        self.assertEqual(
            detect_cli_validation_rejection(["sciverse-read-context", "--limit", "private-query", "--offset", "-1"]),
            ("sciverse_read_context", "invalid_integer"),
        )

    def test_cli_parse_rejections_are_counted_for_an_existing_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory)
            run = runs / "bounded_parse"
            run.mkdir()
            (run / "mission.json").write_text("{}", encoding="utf-8")
            with patch("cosmatter.cli._runs_dir", return_value=runs):
                for flag, value in (("--offset", "-1"), ("--limit", "8192")):
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                        main([
                            "sciverse-read-context", "--run-id", "bounded_parse",
                            "--document-id", "private-document", "--output", "private-output.txt",
                            flag, value,
                        ])
            records = load_validation_rejections(
                run / "validation_rejections.jsonl", expected_run_id="bounded_parse"
            )
            summary = summarize_validation_rejections(records)
            rendered = json.dumps(records)

        self.assertEqual(len(records), 2)
        self.assertEqual(summary, [
            {"command": "sciverse_read_context", "reason_code": "limit_above_maximum", "rejection_count": 1},
            {"command": "sciverse_read_context", "reason_code": "offset_below_minimum", "rejection_count": 1},
        ])
        self.assertNotIn("8192", rendered)
        self.assertNotIn("private-document", rendered)
        self.assertNotIn("private-output", rendered)

    def test_nonexistent_or_traversal_run_is_not_created(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory)
            self.assertFalse(record_cli_validation_rejection(
                ["sciverse-read-context", "--run-id", "missing", "--limit", "8192"], runs
            ))
            self.assertFalse(record_cli_validation_rejection(
                ["sciverse-read-context", "--run-id", "../escape", "--limit", "8192"], runs
            ))
            self.assertEqual(list(runs.iterdir()), [])

    def test_loader_rejects_unknown_reason_or_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "validation_rejections.jsonl"
            path.write_text(json.dumps({
                "schema_version": "cosmatter.validation-rejection/v1",
                "run_id": "run_1",
                "command": "sciverse_read_context",
                "reason_code": "raw_private_value",
                "occurred_at": "2026-09-07T00:00:00Z",
            }) + "\n", encoding="utf-8")
            with self.assertRaises(ValidationRejectionError):
                load_validation_rejections(path, expected_run_id="run_1")
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["reason_code"] = "limit_above_maximum"
            payload["occurred_at"] = "2026-09-07T08:00:00+08:00"
            path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            with self.assertRaises(ValidationRejectionError):
                load_validation_rejections(path, expected_run_id="run_1")


if __name__ == "__main__":
    unittest.main()
