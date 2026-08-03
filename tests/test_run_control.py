import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.models import MissionBrief, MissionState
from cosmatter.run_control import build_run_status, cancel_run, require_active_run
from cosmatter.state_machine import InvalidTransitionError, MissionMachine
from cosmatter.ui_export import _timeline_projection


class RunControlTests(unittest.TestCase):
    def _mission_file(self, run_dir: Path) -> None:
        mission = MissionBrief(
            question="test question", material="BiFeO3", property_name="phase stability", scope="test scope", mission_id="mission_control"
        )
        (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")

    def test_machine_allows_cancellation_only_from_nonterminal_states(self) -> None:
        machine = MissionMachine()
        machine.transition(MissionState.CANCELLED)
        self.assertEqual(machine.state, MissionState.CANCELLED)
        with self.assertRaises(InvalidTransitionError):
            machine.transition(MissionState.PLAN)

    def test_marker_blocks_later_external_action_and_status_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run_1"
            run_dir.mkdir()
            cancel_run(run_dir, "mission_control")
            with self.assertRaisesRegex(ValueError, "cancelled"):
                require_active_run(run_dir, "mission_control")
            status = build_run_status("run_1", "mission_control", MissionState.RETRIEVE, None)
            cancelled = build_run_status("run_1", "mission_control", MissionState.RETRIEVE, {"status": "cancelled"})
        self.assertEqual(status["state"], "RETRIEVE")
        self.assertEqual(cancelled["state"], "CANCELLED")
        self.assertNotIn("reason", json.dumps(cancelled))

    def test_cli_cancel_and_status_are_idempotent_and_gate_draft_before_provider_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "run_1"
            run_dir.mkdir()
            self._mission_file(run_dir)
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(output):
                cancelled_status = main(["cancel-mission", "--run-id", "run_1"])
                repeated_cancel_status = main(["cancel-mission", "--run-id", "run_1"])
                status_code = main(["run-status", "--run-id", "run_1"])
                draft_status = main(["draft-plan", "--run-id", "run_1"])
            audit = (run_dir / "events.jsonl").read_text(encoding="utf-8")
            timeline = _timeline_projection(run_dir / "events.jsonl")

        self.assertEqual(cancelled_status, 0)
        self.assertEqual(repeated_cancel_status, 0)
        self.assertEqual(status_code, 0)
        self.assertEqual(draft_status, 2)
        self.assertIn('"state": "CANCELLED"', output.getvalue())
        self.assertIn('"mission_cancelled"', audit)
        self.assertIn("任务已取消；未启动后续外部请求", [entry["action"] for entry in timeline])
        self.assertNotIn("test question", output.getvalue())
