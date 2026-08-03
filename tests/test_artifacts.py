import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.artifacts import ArtifactWriteError, persist_evidence_review
from cosmatter.models import AccessPolicy, EvidenceCard, Provenance, Stance


def card(evidence_id: str, **conditions: object) -> EvidenceCard:
    return EvidenceCard(
        "synthetic claim",
        Stance.SUPPORT,
        "BiFeO3",
        "phase stability",
        conditions,
        "synthetic short quote",
        Provenance("fixture_document", "page:1", "fixture", access_policy=AccessPolicy.OA),
        evidence_id=evidence_id,
    )


class ArtifactTests(unittest.TestCase):
    def test_paired_artifacts_keep_rejected_evidence_for_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run_1"
            decision = persist_evidence_review(run_dir, "mission_1", card("evidence_1", sample_form="film"))
            evidence = json.loads((run_dir / "evidence_cards.json").read_text(encoding="utf-8"))
            decisions = json.loads((run_dir / "verification_decisions.json").read_text(encoding="utf-8"))

        self.assertEqual(decision.status.value, "rejected")
        self.assertEqual(evidence[0]["evidence_id"], "evidence_1")
        self.assertEqual(decisions[0]["status"], "rejected")

    def test_duplicate_evidence_is_not_silently_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run_1"
            persist_evidence_review(run_dir, "mission_1", card("evidence_1", sample_form="film"))
            with self.assertRaises(ArtifactWriteError):
                persist_evidence_review(run_dir, "mission_1", card("evidence_1", sample_form="film"))


if __name__ == "__main__":
    unittest.main()
