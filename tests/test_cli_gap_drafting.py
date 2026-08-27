import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.deepseek import DraftCompletion
from cosmatter.models import FlightPlan, MissionBrief


class CliGapDraftingTests(unittest.TestCase):
    def test_draft_requires_executed_counterevidence_and_never_echoes_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "gap_draft_cli"
            run_dir.mkdir()
            mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_gap_draft_cli")
            plan = FlightPlan(mission.mission_id, ("Which condition differs?",), ("primary",), ("counter",))
            history = {"schema_version": "1.1", "query": "counter", "candidate_count": 0, "search_count": 1, "candidates": [], "searches": [{"query": "counter", "candidate_count": 0, "candidates": []}]}
            matrix = [{"condition_cluster": "film", "supporting_evidence_ids": ["support"], "contradicting_evidence_ids": ["contradict"], "differing_fields": ["strain_percent"], "unknowns": []}]
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run_dir / "flight_plan.json").write_text(json.dumps(plan.to_dict()), encoding="utf-8")
            (run_dir / "retrieval_candidates.json").write_text(json.dumps(history), encoding="utf-8")
            (run_dir / "condition_matrix.json").write_text(json.dumps(matrix), encoding="utf-8")
            output = io.StringIO()
            with (
                patch("cosmatter.cli._runs_dir", return_value=runs_dir),
                patch("cosmatter.cli.DeepSeekAdapter") as adapter,
                contextlib.redirect_stdout(output),
            ):
                adapter.return_value.draft.return_value = DraftCompletion("private gap brainstorm", "fixture-model", "request_fixture")
                status = main(["draft-gap-hypotheses", "--run-id", "gap_draft_cli"])
            result = json.loads(output.getvalue())
            draft = json.loads((run_dir / "research_gap_draft.json").read_text(encoding="utf-8"))
            event_log = (run_dir / "events.jsonl").read_text(encoding="utf-8")
            candidate_exists = (run_dir / "research_gap_candidates.json").exists()

        self.assertEqual(status, 0)
        self.assertEqual(result["trust_status"], "untrusted_draft_not_candidate_or_finding")
        self.assertEqual(draft["content"], "private gap brainstorm")
        self.assertFalse(candidate_exists)
        self.assertNotIn("private gap brainstorm", output.getvalue())
        self.assertNotIn("private gap brainstorm", event_log)
        self.assertIn("research_gap_hypotheses_drafted", event_log)


if __name__ == "__main__":
    unittest.main()
