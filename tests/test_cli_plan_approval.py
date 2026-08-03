import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.models import MissionBrief


class CliPlanApprovalTests(unittest.TestCase):
    def test_approve_plan_writes_a_bounded_plan_without_echoing_queries(self) -> None:
        reviewed = {
            "subquestions": ["Which conditions matter?"],
            "queries": ["BiFeO3 strain phase"],
            "counter_queries": ["BiFeO3 phase contradictory conditions"],
        }
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "plan_approval"
            run_dir.mkdir()
            mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_plan_approval")
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            input_path = runs_dir / "reviewed_plan.json"
            input_path.write_text(json.dumps(reviewed), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(output):
                status = main(["approve-plan", "--run-id", "plan_approval", "--input", str(input_path)])
            result = json.loads(output.getvalue())
            plan = json.loads((run_dir / "flight_plan.json").read_text(encoding="utf-8"))
            audit = (run_dir / "events.jsonl").read_text(encoding="utf-8")

        self.assertEqual(status, 0)
        self.assertEqual(plan["queries"], reviewed["queries"])
        self.assertIn("plan_id", result)
        self.assertNotIn(reviewed["queries"][0], output.getvalue())
        self.assertNotIn(reviewed["queries"][0], audit)


if __name__ == "__main__":
    unittest.main()
