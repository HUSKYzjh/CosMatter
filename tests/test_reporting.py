import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.models import AccessPolicy, EvidenceCard, MissionBrief, Provenance, ReviewStatus, Stance
from cosmatter.reporting import ReportGateError, build_evidence_manifest, write_mission_report
from cosmatter.verification import VerificationDecision


def card(evidence_id: str) -> EvidenceCard:
    return EvidenceCard(
        "synthetic claim",
        Stance.SUPPORT,
        "BiFeO3",
        "phase stability",
        {"sample_form": "film"},
        "synthetic short quote",
        Provenance("doc_1", "page:1", "fixture", access_policy=AccessPolicy.OA),
        evidence_id=evidence_id,
    )


class ReportingTests(unittest.TestCase):
    def test_report_contains_only_accepted_evidence_identifiers(self) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_1")
        accepted = card("accepted")
        rejected = card("rejected")
        report = build_evidence_manifest(
            mission,
            (accepted, rejected),
            (
                VerificationDecision("mission_1", "accepted", ReviewStatus.ACCEPTED, "complete"),
                VerificationDecision("mission_1", "rejected", ReviewStatus.REJECTED, "missing conditions"),
            ),
        )

        self.assertEqual(report.evidence_ids, ("accepted",))
        self.assertIn("does not by itself establish", report.summary)

    def test_report_requires_accepted_evidence_and_excludes_quotes_on_disk(self) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_1")
        rejected = card("rejected")
        with self.assertRaises(ReportGateError):
            build_evidence_manifest(
                mission,
                (rejected,),
                (VerificationDecision("mission_1", "rejected", ReviewStatus.REJECTED, "missing conditions"),),
            )
        report = build_evidence_manifest(
            mission,
            (card("accepted"),),
            (VerificationDecision("mission_1", "accepted", ReviewStatus.ACCEPTED, "complete"),),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = write_mission_report(Path(directory), report)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["evidence_ids"], ["accepted"])
        self.assertNotIn("synthetic short quote", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
