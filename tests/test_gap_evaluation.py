import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.facilities import DiscrepancyMatrix, DiscrepancyRow
from cosmatter.counterevidence import CounterevidenceExecution
from cosmatter.gap_analysis import candidates_from_discrepancies, write_gap_candidates
from cosmatter.gap_evaluation import (
    GapReviewEvaluationError,
    gap_evaluation_from_assessments,
    gap_review_template,
    load_reviewed_gap_assessment,
)
from cosmatter.models import AccessPolicy, EvidenceCard, MissionBrief, Provenance, ReviewStatus, Stance
from cosmatter.verification import VerificationDecision


def gap_ids() -> tuple[str, ...]:
    return ("gap_001", "gap_002")


def review_instructions() -> dict[str, str]:
    return {
        "counterevidence_reviewed": "Checked the executed bounded counterevidence history.",
        "bounded_novelty_search_outcome": "A bounded outcome is not a global novelty claim.",
    }


def reviewed_payload() -> dict[str, object]:
    return {
        "schema_version": "1.1",
        "mission_id": "mission_1",
        "trust_status": "human_expert_reviewed_gap_assessment_for_evaluation",
        "assessment_instructions": review_instructions(),
        "assessments": [
            {
                "gap_id": "gap_001", "expert_approved": True, "novelty_rating": 4,
                "actionability_rating": 5, "evidence_complete": True,
                "counterevidence_reviewed": True,
                "bounded_novelty_search_outcome": "no_direct_match_in_bounded_search",
            },
            {
                "gap_id": "gap_002", "expert_approved": False, "novelty_rating": 2,
                "actionability_rating": 3, "evidence_complete": False,
                "counterevidence_reviewed": True,
                "bounded_novelty_search_outcome": "related_prior_work_found",
            },
        ],
    }


def generated_candidates(mission_id: str):
    support = EvidenceCard("support", Stance.SUPPORT, "BiFeO3", "phase stability", {"sample_form": "film", "strain_percent": 1}, "short", Provenance("doc1", "p1", "fixture", access_policy=AccessPolicy.OA), evidence_id="e1")
    contradict = EvidenceCard("contradict", Stance.CONTRADICT, "BiFeO3", "phase stability", {"sample_form": "film", "strain_percent": 2}, "short", Provenance("doc2", "p2", "fixture", access_policy=AccessPolicy.OA), evidence_id="e2")
    decisions = (
        VerificationDecision(mission_id, "e1", ReviewStatus.ACCEPTED, "complete"),
        VerificationDecision(mission_id, "e2", ReviewStatus.ACCEPTED, "complete"),
    )
    matrix = DiscrepancyMatrix((DiscrepancyRow("film", ("e1",), ("e2",), ("strain_percent",), ()),), ("counter",))
    return candidates_from_discrepancies(
        mission_id, "BiFeO3", "phase stability", (support, contradict), decisions, matrix,
        CounterevidenceExecution(1, 1, 1, "a" * 64),
    )


class GapEvaluationTests(unittest.TestCase):
    def test_template_and_aggregate_metrics(self) -> None:
        template = gap_review_template(mission_id="mission_1", gap_ids=gap_ids())
        self.assertEqual(template["trust_status"], "blank_human_gap_review_template_not_evaluation_result")
        self.assertIn("counterevidence_reviewed", template["assessment_instructions"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "assessment.json"
            path.write_text(json.dumps(reviewed_payload()), encoding="utf-8")
            assessments = load_reviewed_gap_assessment(path, mission_id="mission_1", gap_ids=gap_ids())
        result = gap_evaluation_from_assessments(mission_id="mission_1", assessments=assessments)
        self.assertEqual(result["expert_approval_rate"], 0.5)
        self.assertEqual(result["mean_novelty_rating"], 3.0)
        self.assertEqual(result["evidence_completeness_rate"], 0.5)
        self.assertEqual(result["counterevidence_review_rate"], 1.0)
        self.assertEqual(result["bounded_no_direct_match_rate"], 0.5)
        self.assertEqual(result["related_prior_work_found_rate"], 0.5)

    def test_blank_or_incomplete_assessment_is_rejected(self) -> None:
        blank = gap_review_template(mission_id="mission_1", gap_ids=gap_ids())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "assessment.json"
            path.write_text(json.dumps(blank), encoding="utf-8")
            with self.assertRaises(GapReviewEvaluationError):
                load_reviewed_gap_assessment(path, mission_id="mission_1", gap_ids=gap_ids())
            invalid = reviewed_payload()
            invalid["assessments"][0]["counterevidence_reviewed"] = False
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaises(GapReviewEvaluationError):
                load_reviewed_gap_assessment(path, mission_id="mission_1", gap_ids=gap_ids())

    def test_cli_creates_template_and_writes_aggregate_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "gap_eval"
            run.mkdir(parents=True)
            mission = MissionBrief("q", "BiFeO3", "phase stability", "films", mission_id="mission_1")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            candidates = generated_candidates(mission.mission_id)
            write_gap_candidates(run, candidates)
            reviewed = {
                "schema_version": "1.1",
                "mission_id": mission.mission_id,
                "trust_status": "human_expert_reviewed_gap_assessment_for_evaluation",
                "assessment_instructions": review_instructions(),
                "assessments": [{
                    "gap_id": candidates[0].gap_id, "expert_approved": True,
                    "novelty_rating": 4, "actionability_rating": 4,
                    "evidence_complete": True, "counterevidence_reviewed": True,
                    "bounded_novelty_search_outcome": "inconclusive",
                }],
            }
            reviewed_path = root / "reviewed.json"
            reviewed_path.write_text(json.dumps(reviewed), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                template_status = main(["create-gap-review-template", "--run-id", "gap_eval"])
                eval_status = main(["evaluate-human-gaps", "--run-id", "gap_eval", "--input", str(reviewed_path)])
            template = (run / "human_gap_review_template.json").read_text(encoding="utf-8")
            artifact = (run / "human_gap_evaluation.json").read_text(encoding="utf-8")
        self.assertEqual(template_status, 0, output.getvalue())
        self.assertEqual(eval_status, 0, output.getvalue())
        self.assertIn("blank_human_gap_review_template", template)
        self.assertIn("counterevidence_review_rate", artifact)
        self.assertNotIn("gap_001", artifact)


if __name__ == "__main__":
    unittest.main()
