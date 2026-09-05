"""Synthetic frozen-question fixtures shared by evaluation-boundary tests."""

from pathlib import Path

from cosmatter.question_set import (
    REVIEWED_STATUS,
    bfo_question_set_review_template,
    freeze_reviewed_question_set,
    load_frozen_question_set_binding,
    write_frozen_question_set,
)


def write_synthetic_frozen_question_set(run_dir: Path, mission_id: str = "mission_1") -> dict[str, object]:
    review = bfo_question_set_review_template("synthetic-bfo-question-set")
    review["trust_status"] = REVIEWED_STATUS
    for item in review["questions"]:
        item["review_decision"] = "include"
        item["review_checks"] = {name: True for name in item["review_checks"]}
        item["review_note"] = "Synthetic fixture decision for contract testing only."
    frozen, audit = freeze_reviewed_question_set(
        mission_id=mission_id, mission_material="BiFeO3", review=review
    )
    write_frozen_question_set(run_dir, frozen, audit)
    binding = load_frozen_question_set_binding(run_dir, mission_id=mission_id)
    assert binding is not None
    return binding
