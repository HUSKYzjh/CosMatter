import unittest

from cosmatter.dispatch import MissionDispatcher
from cosmatter.models import AccessPolicy, EvidenceCard, MissionBrief, Provenance, ReviewStatus, Stance
from cosmatter.ui_export import UiExportError, approved_evidence_projection, build_ui_bundle
from cosmatter.verification import VerificationDecision


def card(evidence_id: str, quote: str = "short approved quote") -> EvidenceCard:
    return EvidenceCard("claim", Stance.SUPPORT, "BiFeO3", "phase", {"sample_form": "film"}, quote, Provenance("doc_" + evidence_id, "page:1", "fixture", access_policy=AccessPolicy.OA), evidence_id=evidence_id)


class UiApprovedProjectionTests(unittest.TestCase):
    def test_only_accepted_short_evidence_is_projected(self) -> None:
        accepted = card("accepted")
        rejected = card("rejected")
        decisions = (
            VerificationDecision("mission_1", "accepted", ReviewStatus.ACCEPTED, "complete"),
            VerificationDecision("mission_1", "rejected", ReviewStatus.REJECTED, "missing conditions", ("temperature_k",)),
        )
        evidence, summary = approved_evidence_projection("mission_1", (accepted, rejected), decisions)
        self.assertEqual([item["evidence_id"] for item in evidence], ["accepted"])
        self.assertEqual(summary["accepted_count"], 1)
        self.assertEqual(summary["rejected_count"], 1)
        self.assertNotIn("missing conditions", str(summary))

    def test_bundle_keeps_only_approved_evidence_and_summary(self) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase", "films", mission_id="mission_1")
        assignment = MissionDispatcher.from_project().assign(mission)
        accepted = card("accepted")
        rejected = card("rejected")
        bundle = build_ui_bundle(
            mission,
            assignment,
            evidence_cards=(accepted, rejected),
            verification_decisions=(
                VerificationDecision("mission_1", "accepted", ReviewStatus.ACCEPTED, "complete"),
                VerificationDecision("mission_1", "rejected", ReviewStatus.REJECTED, "missing conditions"),
            ),
        )
        self.assertEqual([item["evidence_id"] for item in bundle["evidence_cards"]], ["accepted"])
        self.assertEqual(bundle["status"]["verification_summary"]["rejected_count"], 1)
        self.assertEqual(bundle["verification_decisions"], [])
    def test_duplicate_decisions_are_rejected(self) -> None:
        accepted = card("accepted")
        decisions = (
            VerificationDecision("mission_1", "accepted", ReviewStatus.ACCEPTED, "complete"),
            VerificationDecision("mission_1", "accepted", ReviewStatus.REJECTED, "reversed"),
        )
        with self.assertRaises(UiExportError):
            approved_evidence_projection("mission_1", (accepted,), decisions)
    def test_long_quote_is_not_projected(self) -> None:
        long_card = card("long", "x" * 501)
        decision = VerificationDecision("mission_1", "long", ReviewStatus.ACCEPTED, "complete")
        evidence, summary = approved_evidence_projection("mission_1", (long_card,), (decision,))
        self.assertEqual(evidence, [])
        self.assertEqual(summary["withheld_count"], 1)


if __name__ == "__main__":
    unittest.main()
