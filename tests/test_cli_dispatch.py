import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main


class CliDispatchTests(unittest.TestCase):
    def test_assign_fleet_writes_auditable_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=Path(directory)), contextlib.redirect_stdout(output):
                status = main(
                    [
                        "assign-fleet",
                        "--question",
                        "为什么两篇论文对 BiFeO3 应变相变有不同结论？",
                        "--material",
                        "BiFeO3",
                        "--property",
                        "phase stability",
                        "--scope",
                        "epitaxial thin films",
                        "--run-id",
                        "dispatch_test",
                    ]
                )
            payload = json.loads(output.getvalue())
            assignment = json.loads((Path(directory) / "dispatch_test" / "fleet_assignment.json").read_text(encoding="utf-8"))
        self.assertEqual(status, 0)
        self.assertEqual(payload["fleet_type"], "route_diagnostics")
        self.assertEqual(assignment["mission_type"], "literature_discrepancy")
        self.assertIn("condition_differential", assignment["required_facilities"])


if __name__ == "__main__":
    unittest.main()
