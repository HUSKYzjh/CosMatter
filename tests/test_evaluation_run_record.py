import tempfile
import unittest
from pathlib import Path

from cosmatter.evaluation_run_record import (
    EvaluationRunRecordError,
    evaluation_run_record_template,
    reviewed_evaluation_run_record,
    write_evaluation_run_record_template,
)
from tests.question_set_helpers import write_synthetic_frozen_question_set


def manifest():
    return {
        "mission_id": "mission_1",
        "corpus_id": "bfo_90_v1",
        "documents": [{"document_id": "d1"}, {"document_id": "d2"}],
    }


class EvaluationRunRecordTests(unittest.TestCase):
    def test_template_binds_manifest_and_blank_state(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            binding = write_synthetic_frozen_question_set(run)
            template = evaluation_run_record_template(run_dir=run, manifest=manifest(), mission_id="mission_1")
            self.assertEqual(template["frozen_corpus_document_count"], 2)
            self.assertEqual(template["frozen_question_set_sha256"], binding["frozen_question_set_sha256"])
            self.assertEqual(template["trust_status"], "blank_human_real_corpus_evaluation_run_record_not_a_result")
            path = write_evaluation_run_record_template(run, template)
            self.assertTrue(path.exists())

    def test_reviewed_record_must_match_actual_metric_files(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            write_synthetic_frozen_question_set(run)
            record = evaluation_run_record_template(run_dir=run, manifest=manifest(), mission_id="mission_1")
            record["trust_status"] = "human_reviewed_real_corpus_evaluation_run_record"
            record["execution_completed_on"] = "2026-08-08"
            record["code_revision"] = "test-snapshot"
            record["metric_artifacts"]["human_retrieval_evaluation"] = "generated"
            with self.assertRaises(EvaluationRunRecordError):
                reviewed_evaluation_run_record(run_dir=run, manifest=manifest(), mission_id="mission_1", payload=record)
            (run / "human_retrieval_evaluation.json").write_text("{}", encoding="utf-8")
            saved = reviewed_evaluation_run_record(run_dir=run, manifest=manifest(), mission_id="mission_1", payload=record)
        self.assertEqual(saved["metric_artifacts"]["human_retrieval_evaluation"], "generated")

    def test_record_rejects_question_set_changed_after_template_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            write_synthetic_frozen_question_set(run)
            record = evaluation_run_record_template(run_dir=run, manifest=manifest(), mission_id="mission_1")
            record["trust_status"] = "human_reviewed_real_corpus_evaluation_run_record"
            record["execution_completed_on"] = "2026-09-05"
            record["code_revision"] = "test-snapshot"
            record["frozen_question_set_sha256"] = "sha256:" + "0" * 64
            with self.assertRaisesRegex(EvaluationRunRecordError, "question set"):
                reviewed_evaluation_run_record(run_dir=run, manifest=manifest(), mission_id="mission_1", payload=record)


if __name__ == "__main__":
    unittest.main()


