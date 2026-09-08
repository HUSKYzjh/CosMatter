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

    def test_approve_plan_freezes_independent_query_tracks_and_candidate_minimums(self) -> None:
        reviewed = {
            "subquestions": ["Which approved route should be searched?"],
            "queries": ["exact PST", "analogue perovskite", "configuration algorithm"],
            "counter_queries": ["surrogate counterexample"],
            "query_tracks": [
                {"query_index": 0, "research_track": "exact_material"},
                {"query_index": 1, "research_track": "mechanism_analogue"},
                {"query_index": 2, "research_track": "algorithm"},
            ],
            "track_candidate_minimums": {"exact_material": 4, "mechanism_analogue": 3, "algorithm": 4},
        }
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "tracked_plan"
            run_dir.mkdir()
            mission = MissionBrief("why", "PST", "response", "MD only", mission_id="mission_tracked_plan")
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            input_path = runs_dir / "reviewed_plan.json"
            input_path.write_text(json.dumps(reviewed), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(output):
                status = main(["approve-plan", "--run-id", "tracked_plan", "--input", str(input_path)])
            plan = json.loads((run_dir / "flight_plan.json").read_text(encoding="utf-8"))
            result = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(plan["query_tracks"], reviewed["query_tracks"])
        self.assertEqual(plan["track_candidate_minimums"], reviewed["track_candidate_minimums"])
        self.assertEqual(result["query_track_planning_status"], "approved_independent_tracks")
        self.assertEqual(result["query_track_counts"], {"exact_material": 1, "mechanism_analogue": 1, "algorithm": 1})
        self.assertNotIn("exact PST", json.dumps(result))

    def test_approve_plan_rejects_incomplete_or_duplicate_query_track_assignments(self) -> None:
        base = {
            "subquestions": ["bounded"],
            "queries": ["exact", "analogue", "algorithm"],
            "counter_queries": ["counter"],
            "track_candidate_minimums": {"exact_material": 4, "mechanism_analogue": 3, "algorithm": 4},
        }
        invalid_assignments = [
            [
                {"query_index": 0, "research_track": "exact_material"},
                {"query_index": 1, "research_track": "mechanism_analogue"},
                {"query_index": 1, "research_track": "algorithm"},
            ],
            [
                {"query_index": 0, "research_track": "exact_material"},
                {"query_index": 1, "research_track": "mechanism_analogue"},
                {"query_index": 2, "research_track": "mechanism_analogue"},
            ],
        ]
        from cosmatter.planning import PlanApprovalError, approved_flight_plan_from_payload
        mission = MissionBrief("why", "PST", "response", "MD only")
        for query_tracks in invalid_assignments:
            with self.subTest(query_tracks=query_tracks), self.assertRaises(PlanApprovalError):
                approved_flight_plan_from_payload(mission, {**base, "query_tracks": query_tracks})


if __name__ == "__main__":
    unittest.main()
