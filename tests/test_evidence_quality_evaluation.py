import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.artifacts import persist_evidence_review
from cosmatter.cli import main
from cosmatter.evidence_quality_evaluation import (
    EvidenceQualityEvaluationError,
    evidence_quality_evaluation_from_assessments,
    evidence_quality_review_template,
    load_reviewed_evidence_quality_assessment,
)
from cosmatter.models import AccessPolicy, EvidenceCard, MissionBrief, Provenance, Stance


def card(evidence_id: str, stance: Stance) -> EvidenceCard:
    return EvidenceCard(
        claim="bounded claim", stance=stance, material="BiFeO3", property_name="phase",
        conditions={"sample_form": "film", "strain_percent": -1, "substrate": "LAO", "thickness_nm": 30, "temperature_k": 300, "method": "XRD"},
        quote="short reviewer-selected excerpt", provenance=Provenance("doc_" + evidence_id, "page:1", "fixture", access_policy=AccessPolicy.AUTHORIZED), evidence_id=evidence_id,
    )


class EvidenceQualityEvaluationTests(unittest.TestCase):
    def test_evaluates_only_current_complete_human_review(self) -> None:
        cards = (card("support", Stance.SUPPORT), card("contradict", Stance.CONTRADICT))
        template = evidence_quality_review_template(mission_id="mission_quality", cards=cards)
        self.assertNotIn("claim", json.dumps(template))
        reviewed = dict(template, trust_status="human_reviewed_evidence_quality_assessment_for_evaluation")
        reviewed["assessments"] = [
            {**template["assessments"][0], "citation_locator_correct": True, "conditions_complete": True, "predicted_contradiction_correct": None},
            {**template["assessments"][1], "citation_locator_correct": True, "conditions_complete": False, "predicted_contradiction_correct": True},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.json"
            path.write_text(json.dumps(reviewed), encoding="utf-8")
            assessments = load_reviewed_evidence_quality_assessment(path, mission_id="mission_quality", cards=cards)
        result = evidence_quality_evaluation_from_assessments(mission_id="mission_quality", assessments=assessments)
        self.assertEqual(result["citation_precision"], 1.0)
        self.assertEqual(result["condition_completeness"], 0.5)
        self.assertEqual(result["contradiction_precision"], 1.0)
        self.assertNotIn("doc_support", json.dumps(result))

    def test_rejects_stale_locator_and_incomplete_contradiction_review(self) -> None:
        cards = (card("contradict", Stance.CONTRADICT),)
        template = evidence_quality_review_template(mission_id="mission_quality", cards=cards)
        reviewed = dict(template, trust_status="human_reviewed_evidence_quality_assessment_for_evaluation")
        reviewed["assessments"] = [{**template["assessments"][0], "locator": "page:9", "citation_locator_correct": True, "conditions_complete": True, "predicted_contradiction_correct": None}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.json"
            path.write_text(json.dumps(reviewed), encoding="utf-8")
            with self.assertRaises(EvidenceQualityEvaluationError):
                load_reviewed_evidence_quality_assessment(path, mission_id="mission_quality", cards=cards)

    def test_cli_creates_template_and_writes_aggregate_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory)
            run = runs / "quality"
            run.mkdir()
            mission = MissionBrief("question", "BiFeO3", "phase", "films", mission_id="mission_quality")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            persist_evidence_review(run, mission.mission_id, card("support", Stance.SUPPORT))
            persist_evidence_review(run, mission.mission_id, card("contradict", Stance.CONTRADICT))
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                self.assertEqual(main(["create-evidence-quality-review-template", "--run-id", "quality"]), 0)
            template = json.loads((run / "human_evidence_quality_review_template.json").read_text(encoding="utf-8"))
            template["trust_status"] = "human_reviewed_evidence_quality_assessment_for_evaluation"
            for assessment in template["assessments"]:
                assessment["citation_locator_correct"] = True
                assessment["conditions_complete"] = True
                assessment["predicted_contradiction_correct"] = True if assessment["predicted_stance"] == "contradict" else None
            review_path = runs / "review.json"
            review_path.write_text(json.dumps(template), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                self.assertEqual(main(["evaluate-human-evidence-quality", "--run-id", "quality", "--input", str(review_path)]), 0)
            result = json.loads((run / "human_evidence_quality_evaluation.json").read_text(encoding="utf-8"))
            audit = (run / "events.jsonl").read_text(encoding="utf-8")
        self.assertEqual(result["contradiction_precision"], 1.0)
        self.assertNotIn("doc_support", json.dumps(result))
        self.assertNotIn("doc_support", audit)


if __name__ == "__main__":
    unittest.main()
