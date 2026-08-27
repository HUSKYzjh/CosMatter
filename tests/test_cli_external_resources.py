import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main


class ExternalResourceDisclosureCliTests(unittest.TestCase):
    def test_records_human_completed_disclosure_after_mission_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            disclosure = root / "resources.json"
            disclosure.write_text(json.dumps({
                "schema_version": "1.0",
                "trust_status": "human_completed_external_resource_disclosure_not_execution_evidence",
                "resources": [{
                    "name": "OpenAlex", "category": "database", "purpose": "citation metadata",
                    "access_method": "API", "version_or_access_date": "2026-08-13",
                    "license_or_terms": "current provider terms reviewed",
                    "redistribution_boundary": "derived metadata only", "used_in_final_result": False,
                }],
                "reviewer": "reviewer", "review_date": "2026-08-13",
            }), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=root / "runs"), contextlib.redirect_stdout(output):
                self.assertEqual(main([
                    "create-mission", "--run-id", "resource_cli", "--mission-id", "mission_resource_cli",
                    "--question", "question", "--material", "BiFeO3", "--property", "phase stability", "--scope", "films",
                ]), 0, output.getvalue())
                status = main([
                    "record-external-resource-disclosure", "--run-id", "resource_cli", "--input", str(disclosure),
                ])
            payload = json.loads((root / "runs" / "resource_cli" / "external_resource_disclosure.json").read_text(encoding="utf-8"))
        self.assertEqual(status, 0, output.getvalue())
        self.assertEqual(payload["resources"][0]["name"], "OpenAlex")


if __name__ == "__main__":
    unittest.main()
