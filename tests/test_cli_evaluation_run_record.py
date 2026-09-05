import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.corpus_preparation import corpus_manifest_from_review, write_corpus_manifest
from cosmatter.models import MissionBrief
from tests.question_set_helpers import write_synthetic_frozen_question_set


def selection() -> dict[str, object]:
    return {
        "corpus_id": "bfo_90_v1",
        "material": "BiFeO3",
        "documents": [
            {"document_id": "bfo_001", "title": "Synthetic bibliographic title one", "doi": None, "access_policy": "institutional_access_internal_review_only"},
            {"document_id": "bfo_002", "title": "Synthetic bibliographic title two", "doi": "10.0000/synthetic.2", "access_policy": "institutional_access_internal_review_only"},
        ],
    }


class CliEvaluationRunRecordTests(unittest.TestCase):
    def test_cli_binds_and_records_human_real_corpus_evaluation_disclosure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory)
            run = runs / "evaluation_cli"
            run.mkdir()
            mission = MissionBrief(question="q", material="BiFeO3", property_name="phase", scope="scope", mission_id="mission_1")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            manifest = corpus_manifest_from_review(mission_id=mission.mission_id, material=mission.material, selection=selection())
            write_corpus_manifest(run, manifest)
            write_synthetic_frozen_question_set(run)
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status_template = main(["create-evaluation-run-record-template", "--run-id", "evaluation_cli"])
            template_path = run / "real_corpus_evaluation_run_record_template.json"
            record = json.loads(template_path.read_text(encoding="utf-8"))
            record["trust_status"] = "human_reviewed_real_corpus_evaluation_run_record"
            record["execution_completed_on"] = "2026-08-08"
            record["code_revision"] = "test-snapshot"
            input_path = run / "reviewed_record.json"
            input_path.write_text(json.dumps(record), encoding="utf-8")
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status_record = main(["record-evaluation-run-record", "--run-id", "evaluation_cli", "--input", str(input_path)])
            saved = json.loads((run / "real_corpus_evaluation_run_record.json").read_text(encoding="utf-8"))
            events = (run / "events.jsonl").read_text(encoding="utf-8")
            failure_written = (run / "evaluation_failure_case_log.json").is_file()
            cost_written = (run / "evaluation_api_cost_latency.json").is_file()
        self.assertEqual(status_template, 0, output.getvalue())
        self.assertEqual(status_record, 0, output.getvalue())
        self.assertEqual(saved["frozen_corpus_document_count"], 2)
        self.assertEqual(saved["question_set_id"], "synthetic-bfo-question-set")
        self.assertEqual(saved["frozen_question_count"], 8)
        self.assertIn("evaluation_run_record_template_created", events)
        self.assertIn("human_real_corpus_evaluation_run_recorded", events)
        self.assertNotIn(str(input_path), output.getvalue())

    def test_cli_records_safe_aggregate_operational_disclosures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory)
            run = runs / "evaluation_operational_cli"
            run.mkdir()
            mission = MissionBrief(question="q", material="BiFeO3", property_name="phase", scope="scope", mission_id="mission_1")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            manifest = corpus_manifest_from_review(mission_id=mission.mission_id, material=mission.material, selection=selection())
            write_corpus_manifest(run, manifest)
            failure_input = run / "failure.json"
            failure_input.write_text(json.dumps({"schema_version": "1.0", "mission_id": "mission_1", "corpus_id": "bfo_90_v1", "trust_status": "human_reviewed_aggregate_evaluation_failure_case_log", "categories": []}), encoding="utf-8")
            cost_input = run / "cost.json"
            cost_input.write_text(json.dumps({"schema_version": "1.0", "mission_id": "mission_1", "corpus_id": "bfo_90_v1", "trust_status": "human_reviewed_aggregate_evaluation_api_cost_latency", "measurement_scope": "local-only evaluation window", "providers": []}), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                failure_status = main(["record-evaluation-failure-case-log", "--run-id", "evaluation_operational_cli", "--input", str(failure_input)])
                cost_status = main(["record-evaluation-api-cost-latency", "--run-id", "evaluation_operational_cli", "--input", str(cost_input)])
            events = (run / "events.jsonl").read_text(encoding="utf-8")
            failure_written = (run / "evaluation_failure_case_log.json").is_file()
            cost_written = (run / "evaluation_api_cost_latency.json").is_file()
        self.assertEqual(failure_status, 0, output.getvalue())
        self.assertEqual(cost_status, 0, output.getvalue())
        self.assertTrue(failure_written)
        self.assertTrue(cost_written)
        self.assertIn("human_reviewed_evaluation_failure_case_log_recorded", events)
        self.assertIn("human_reviewed_evaluation_api_cost_latency_recorded", events)
        self.assertNotIn(str(failure_input), output.getvalue())

if __name__ == "__main__":
    unittest.main()
