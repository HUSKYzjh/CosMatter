import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.deepseek import DraftCompletion
from cosmatter.models import MissionBrief


class CliPlanningTests(unittest.TestCase):
    def test_draft_plan_persists_untrusted_output_without_echoing_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "planning_cli"
            run_dir.mkdir()
            mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_planning_cli")
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            output = io.StringIO()
            with (
                patch("cosmatter.cli._runs_dir", return_value=runs_dir),
                patch("cosmatter.cli.DeepSeekAdapter") as adapter,
                contextlib.redirect_stdout(output),
            ):
                adapter.return_value.draft.return_value = DraftCompletion("synthetic private draft content", "deepseek-v4-flash", "request_fixture")
                status = main(["draft-plan", "--run-id", "planning_cli"])
            result = json.loads(output.getvalue())
            draft = json.loads((run_dir / "research_plan_draft.json").read_text(encoding="utf-8"))
            audit = (run_dir / "events.jsonl").read_text(encoding="utf-8")

        self.assertEqual(status, 0)
        self.assertEqual(result["trust_status"], "untrusted_draft")
        self.assertEqual(draft["content"], "synthetic private draft content")
        self.assertNotIn("synthetic private draft content", output.getvalue())
        self.assertNotIn("synthetic private draft content", audit)


if __name__ == "__main__":
    unittest.main()
