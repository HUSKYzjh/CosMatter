import unittest

from cosmatter.facilities import verification_decision
from cosmatter.models import AccessPolicy, EvidenceCard, Provenance, ReviewStatus, Stance
from cosmatter.verification import VerificationDecision


class VerificationTests(unittest.TestCase):
    def test_accepted_decision_cannot_keep_missing_conditions(self) -> None:
        with self.assertRaises(ValueError):
            VerificationDecision("mission_1", "evidence_1", ReviewStatus.ACCEPTED, "ok", ("temperature_k",))

    def test_facility_creates_rejected_decision_for_incomplete_conditions(self) -> None:
        card = EvidenceCard("claim", Stance.SUPPORT, "BiFeO3", "phase", {"sample_form": "film"}, "fixture quote", Provenance("doc", "page:1", "fixture", access_policy=AccessPolicy.OA))
        decision = verification_decision("mission_1", card)
        self.assertEqual(decision.status, ReviewStatus.REJECTED)
        self.assertIn("temperature_k", decision.missing_conditions)


if __name__ == "__main__":
    unittest.main()
