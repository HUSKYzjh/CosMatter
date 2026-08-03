import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.models import FlightPlan, MissionBrief
from cosmatter.sciverse import SciverseResponse


class CliPlanQueryTests(unittest.TestCase):
    def test_execute_plan_query_uses_only_approved_indexed_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "plan_query"
            run_dir.mkdir()
            mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_plan_query")
            plan = FlightPlan(mission.mission_id, ("Which conditions?",), ("BiFeO3 approved query",), ("BiFeO3 counter query",))
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run_dir / "flight_plan.json").write_text(json.dumps(plan.to_dict()), encoding="utf-8")
            response = SciverseResponse({"hits": [{"doc_id": "doc_1", "title": "Candidate", "is_content_accessible": True}]}, 200, "request_plan")
            output = io.StringIO()
            with (
                patch("cosmatter.cli._runs_dir", return_value=runs_dir),
                patch("cosmatter.cli.SciverseAdapter") as adapter,
                contextlib.redirect_stdout(output),
            ):
                adapter.return_value.agentic_search.return_value = response
                status = main(["execute-plan-query", "--run-id", "plan_query", "--query-index", "0"])
            result = json.loads(output.getvalue())
            candidates = json.loads((run_dir / "retrieval_candidates.json").read_text(encoding="utf-8"))
            audit = (run_dir / "events.jsonl").read_text(encoding="utf-8")

        self.assertEqual(status, 0)
        adapter.return_value.agentic_search.assert_called_once_with("BiFeO3 approved query", top_k=20)
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(candidates["query"], "BiFeO3 approved query")
        self.assertNotIn("BiFeO3 approved query", audit)

    def test_execute_plan_query_can_use_approved_counterevidence_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "counter_query"
            run_dir.mkdir()
            mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_counter_query")
            plan = FlightPlan(mission.mission_id, ("Which conditions?",), ("primary query",), ("approved counter query",))
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run_dir / "flight_plan.json").write_text(json.dumps(plan.to_dict()), encoding="utf-8")
            response = SciverseResponse({"hits": [{"doc_id": "doc_1", "title": "Candidate"}]}, 200, "request_counter")
            output = io.StringIO()
            with (
                patch("cosmatter.cli._runs_dir", return_value=runs_dir),
                patch("cosmatter.cli.SciverseAdapter") as adapter,
                contextlib.redirect_stdout(output),
            ):
                adapter.return_value.agentic_search.return_value = response
                status = main(["execute-plan-query", "--run-id", "counter_query", "--query-index", "0", "--counter"])
            result = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        adapter.return_value.agentic_search.assert_called_once_with("approved counter query", top_k=20)
        self.assertEqual(result["query_kind"], "counter")
    def test_execute_plan_query_rejects_outside_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "plan_query"
            run_dir.mkdir()
            mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_plan_query")
            plan = FlightPlan(mission.mission_id, ("Which conditions?",), ("BiFeO3 approved query",), ("BiFeO3 counter query",))
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run_dir / "flight_plan.json").write_text(json.dumps(plan.to_dict()), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(output):
                status = main(["execute-plan-query", "--run-id", "plan_query", "--query-index", "2"])
            payload = json.loads(output.getvalue())

        self.assertEqual(status, 2)
        self.assertIn("outside", payload["error"])


if __name__ == "__main__":
    unittest.main()
