import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.models import MissionBrief
from cosmatter.question_set import REVIEWED_STATUS


class CliQuestionSetTests(unittest.TestCase):
    def test_template_then_complete_review_freezes_question_set_and_safe_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "question_eval"
            run.mkdir(parents=True)
            mission = MissionBrief(
                question="Evaluate a human-reviewed BFO research-question set.",
                material="BiFeO3 evaluation campaign",
                property_name="question quality and evidence maturity",
                scope="bounded question-level evaluation",
                mission_id="mission_question_eval",
            )
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            review_path = root / "private_question_review.json"
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                template_status = main([
                    "create-bfo-question-set-review-template", "--question-set-id", "bfo-eval-v1", "--output", str(review_path)
                ])
            review = json.loads(review_path.read_text(encoding="utf-8"))
            review["trust_status"] = REVIEWED_STATUS
            for item in review["questions"]:
                item["review_decision"] = "include"
                item["review_checks"] = {name: True for name in item["review_checks"]}
                item["review_note"] = "Human reviewer completed all five bounded checks."
            review_path.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
            freeze_output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(freeze_output):
                freeze_status = main(["record-frozen-question-set", "--run-id", "question_eval", "--input", str(review_path)])
            result = json.loads(freeze_output.getvalue())
            frozen = json.loads((run / "frozen_question_set.json").read_text(encoding="utf-8"))
            audit_text = (run / "question_set_review_audit.json").read_text(encoding="utf-8")
            events_text = (run / "events.jsonl").read_text(encoding="utf-8")
        self.assertEqual(template_status, 0, output.getvalue())
        self.assertEqual(freeze_status, 0, freeze_output.getvalue())
        self.assertEqual(result["included_question_count"], 8)
        self.assertEqual(frozen["question_count"], 8)
        self.assertEqual(result["freeze_gate"], "ready_for_question_level_evaluation_not_metrics")
        self.assertNotIn("Human reviewer completed", audit_text)
        self.assertNotIn(str(review_path), audit_text)
        self.assertNotIn(str(review_path), events_text)
        self.assertIn("human_reviewed_question_set_frozen", events_text)

    def test_blank_template_cannot_be_recorded_as_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "blank_question_eval"
            run.mkdir(parents=True)
            mission = MissionBrief("Evaluate questions", "BiFeO3", "question quality", "bounded", mission_id="mission_blank")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            review_path = root / "blank.json"
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["create-bfo-question-set-review-template", "--output", str(review_path)]), 0)
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status = main(["record-frozen-question-set", "--run-id", "blank_question_eval", "--input", str(review_path)])
            written = (run / "frozen_question_set.json").exists()
        self.assertEqual(status, 2)
        self.assertIn("trust status", json.loads(output.getvalue())["error"])
        self.assertFalse(written)


if __name__ == "__main__":
    unittest.main()
