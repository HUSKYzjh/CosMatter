import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.question_set import (
    BLANK_REVIEW_STATUS,
    REVIEWED_STATUS,
    QuestionSetError,
    bfo_question_set_review_template,
    freeze_reviewed_question_set,
    write_frozen_question_set,
    write_question_set_review_template,
)


def reviewed_template() -> dict[str, object]:
    payload = bfo_question_set_review_template()
    payload["trust_status"] = REVIEWED_STATUS
    for item in payload["questions"]:
        item["review_decision"] = "include"
        item["review_checks"] = {name: True for name in item["review_checks"]}
        item["review_note"] = "Checked against the five question-quality criteria."
    payload["questions"][-1]["review_decision"] = "exclude"
    payload["questions"][-1]["review_checks"]["scope_bounded"] = False
    payload["questions"][-1]["review_note"] = "Excluded because the intended boundary needs refinement."
    return payload


class QuestionSetTests(unittest.TestCase):
    def test_bfo_template_contains_distinct_unreviewed_questions_across_evidence_levels(self) -> None:
        template = bfo_question_set_review_template()
        self.assertEqual(template["trust_status"], BLANK_REVIEW_STATUS)
        self.assertEqual(len(template["questions"]), 8)
        self.assertEqual(len({item["question_id"] for item in template["questions"]}), 8)
        self.assertIn("already_reproduced", {item["intended_evidence_level"] for item in template["questions"]})
        self.assertTrue(all(item["review_decision"] == "unreviewed" for item in template["questions"]))
        self.assertTrue(all(set(item["review_checks"].values()) == {None} for item in template["questions"]))
        with self.assertRaisesRegex(QuestionSetError, "trust status"):
            freeze_reviewed_question_set(mission_id="mission_bfo", mission_material="BiFeO3", review=template)

    def test_review_freezes_only_included_questions_and_writes_count_only_audit(self) -> None:
        frozen, audit = freeze_reviewed_question_set(
            mission_id="mission_bfo", mission_material="BiFeO3 evaluation", review=reviewed_template()
        )
        self.assertEqual(frozen["question_count"], 7)
        self.assertEqual(audit["reviewed_question_count"], 8)
        self.assertEqual(audit["included_question_count"], 7)
        self.assertEqual(audit["excluded_question_count"], 1)
        self.assertEqual(audit["freeze_gate"], "ready_for_question_level_evaluation_not_metrics")
        self.assertEqual(frozen["question_set_sha256"], audit["frozen_question_set_sha256"])
        self.assertNotIn("review_note", json.dumps(frozen, ensure_ascii=False))
        self.assertNotIn("Checked against", json.dumps(audit, ensure_ascii=False))

    def test_included_question_must_pass_every_check_and_material_must_match(self) -> None:
        review = reviewed_template()
        review["questions"][0]["review_checks"]["scope_bounded"] = False
        with self.assertRaisesRegex(QuestionSetError, "pass every quality check"):
            freeze_reviewed_question_set(mission_id="mission_bfo", mission_material="BiFeO3", review=review)
        with self.assertRaisesRegex(QuestionSetError, "material family"):
            freeze_reviewed_question_set(mission_id="mission_other", mission_material="SrTiO3", review=reviewed_template())

    def test_duplicate_question_and_overwrite_attempts_fail_closed(self) -> None:
        duplicate = reviewed_template()
        duplicate["questions"][1]["question"] = duplicate["questions"][0]["question"]
        with self.assertRaisesRegex(QuestionSetError, "unique"):
            freeze_reviewed_question_set(mission_id="mission_bfo", mission_material="BiFeO3", review=duplicate)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template_path = root / "review.json"
            write_question_set_review_template(template_path, bfo_question_set_review_template())
            with self.assertRaises(FileExistsError):
                write_question_set_review_template(template_path, bfo_question_set_review_template())
            frozen, audit = freeze_reviewed_question_set(
                mission_id="mission_bfo", mission_material="BiFeO3", review=reviewed_template()
            )
            write_frozen_question_set(root / "run", frozen, audit)
            with self.assertRaisesRegex(QuestionSetError, "cannot be overwritten"):
                write_frozen_question_set(root / "run", frozen, audit)

    def test_writer_rejects_tampered_frozen_counts_and_audit_gate(self) -> None:
        frozen, audit = freeze_reviewed_question_set(
            mission_id="mission_bfo", mission_material="BiFeO3", review=reviewed_template()
        )
        with tempfile.TemporaryDirectory() as directory:
            tampered_frozen = dict(frozen)
            tampered_frozen["question_count"] = 99
            with self.assertRaisesRegex(QuestionSetError, "content hash"):
                write_frozen_question_set(Path(directory) / "bad-count", tampered_frozen, audit)
            tampered_audit = dict(audit)
            tampered_audit["freeze_gate"] = "metrics_completed"
            with self.assertRaisesRegex(QuestionSetError, "gate"):
                write_frozen_question_set(Path(directory) / "bad-gate", frozen, tampered_audit)


if __name__ == "__main__":
    unittest.main()
