import tempfile
import unittest
from pathlib import Path

from cosmatter.evaluation_run_record import (
    EvaluationRunRecordError,
    evaluation_run_record_template,
    reviewed_evaluation_run_record,
    write_evaluation_run_record_template,
)


def manifest():
    return {
        "mission_id": "mission_1",
        "corpus_id": "bfo_90_v1",
        "documents": [{"document_id": "d1"}, {"document_id": "d2"}],
    }


class EvaluationRunRecordTests(unittest.TestCase):
    def test_template_binds_manifest_and_blank_state(self):
        template = evaluation_run_record_template(manifest=manifest(), mission_id="mission_1")
        self.assertEqual(template["frozen_corpus_document_count"], 2)
        self.assertEqual(template["trust_status"], "blank_human_real_corpus_evaluation_run_record_not_a_result")
        with tempfile.TemporaryDirectory() as directory:
            path = write_evaluation_run_record_template(Path(directory), template)
            self.assertTrue(path.exists())

    def test_reviewed_record_must_match_actual_metric_files(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            record = evaluation_run_record_template(manifest=manifest(), mission_id="mission_1")
            record["trust_status"] = "human_reviewed_real_corpus_evaluation_run_record"
            record["execution_completed_on"] = "2026-08-08"
            record["code_revision"] = "test-snapshot"
            record["metric_artifacts"]["human_retrieval_evaluation"] = "generated"
            with self.assertRaises(EvaluationRunRecordError):
                reviewed_evaluation_run_record(run_dir=run, manifest=manifest(), mission_id="mission_1", payload=record)
            (run / "human_retrieval_evaluation.json").write_text("{}", encoding="utf-8")
            saved = reviewed_evaluation_run_record(run_dir=run, manifest=manifest(), mission_id="mission_1", payload=record)
        self.assertEqual(saved["metric_artifacts"]["human_retrieval_evaluation"], "generated")


if __name__ == "__main__":
    unittest.main()


