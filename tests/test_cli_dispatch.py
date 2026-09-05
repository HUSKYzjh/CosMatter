import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.audit import FlightRecorder
from cosmatter.cli import main
from cosmatter.models import MissionState


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

    def test_backfilled_assignment_preserves_the_existing_run_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_id = "dispatch_backfill"
            FlightRecorder(runs_dir, run_id).record(
                event_type="source_parse_completed",
                actor="fixture",
                state=MissionState.EXTRACT,
                payload={"trust_status": "synthetic_fixture"},
            )
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(output):
                status = main([
                    "assign-fleet",
                    "--question", "为什么两篇论文对 BiFeO3 应变相变有不同结论？",
                    "--material", "BiFeO3",
                    "--property", "phase stability",
                    "--scope", "epitaxial thin films",
                    "--run-id", run_id,
                ])
            events = [json.loads(line) for line in (runs_dir / run_id / "events.jsonl").read_text(encoding="utf-8").splitlines()]

        self.assertEqual(status, 0)
        self.assertEqual(events[-1]["event_type"], "fleet_assigned")
        self.assertEqual(events[-1]["state"], MissionState.EXTRACT.value)


if __name__ == "__main__":
    unittest.main()
