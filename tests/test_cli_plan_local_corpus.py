import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.corpus_preparation import corpus_manifest_from_review, write_corpus_manifest
from cosmatter.models import FlightPlan, MissionBrief


def selection() -> dict[str, object]:
    return {
        "corpus_id": "bfo_local_fixture", "material": "BiFeO3",
        "documents": [
            {"document_id": "doc_1", "title": "BiFeO3 phase stability", "doi": None, "access_policy": "institutional_access_internal_review_only"},
            {"document_id": "doc_2", "title": "BiFeO3 counterexample", "doi": None, "access_policy": "institutional_access_internal_review_only"},
        ],
    }


class CliPlanLocalCorpusTests(unittest.TestCase):
    def test_executes_only_approved_primary_and_counter_queries_without_persisting_index_or_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "local_plan"
            run.mkdir(parents=True)
            mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_local_plan")
            plan = FlightPlan(mission.mission_id, ("conditions",), ("BiFeO3 approved primary",), ("BiFeO3 approved counter",), max_papers=10)
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run / "flight_plan.json").write_text(json.dumps(plan.to_dict()), encoding="utf-8")
            write_corpus_manifest(run, corpus_manifest_from_review(mission_id=mission.mission_id, material=mission.material, selection=selection()))
            first = root / "private-primary.md"
            second = root / "private-counter.md"
            first.write_text("BiFeO3 approved primary phase stability conditions", encoding="utf-8")
            second.write_text("BiFeO3 approved counter contradictory phase report", encoding="utf-8")
            index = root / "private-index.json"
            index.write_text(json.dumps({"documents": [
                {"document_id": "doc_1", "title": "BiFeO3 phase stability", "path": str(first), "parser_provenance": "mineru_reviewed_local_output"},
                {"document_id": "doc_2", "title": "BiFeO3 counterexample", "path": str(second), "parser_provenance": "mineru_reviewed_local_output"},
            ]}), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                primary_status = main(["execute-plan-local-corpus-query", "--run-id", "local_plan", "--index", str(index), "--query-index", "0"])
                counter_status = main(["execute-plan-local-corpus-query", "--run-id", "local_plan", "--index", str(index), "--query-index", "0", "--counter"])
            history = json.loads((run / "retrieval_candidates.json").read_text(encoding="utf-8"))
            audit = (run / "events.jsonl").read_text(encoding="utf-8")
        self.assertEqual(primary_status, 0, output.getvalue())
        self.assertEqual(counter_status, 0, output.getvalue())
        self.assertEqual(history["search_count"], 2)
        self.assertEqual([entry["query"] for entry in history["searches"]], ["BiFeO3 approved primary", "BiFeO3 approved counter"])
        self.assertNotIn(str(index), json.dumps(history))
        self.assertNotIn(str(first), json.dumps(history))
        self.assertNotIn("BiFeO3 approved primary", audit)
        self.assertNotIn("BiFeO3 approved counter", audit)
        self.assertNotIn(str(index), audit)

    def test_rejects_unapproved_query_index_before_local_source_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "local_plan"
            run.mkdir(parents=True)
            mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_local_plan")
            plan = FlightPlan(mission.mission_id, ("conditions",), ("BiFeO3 approved primary",), ("BiFeO3 approved counter",))
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run / "flight_plan.json").write_text(json.dumps(plan.to_dict()), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status = main(["execute-plan-local-corpus-query", "--run-id", "local_plan", "--index", str(root / "missing-index.json"), "--query-index", "1"])
            result = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertIn("outside", result["error"])


if __name__ == "__main__":
    unittest.main()
