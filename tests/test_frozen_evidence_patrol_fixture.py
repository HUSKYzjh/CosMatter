import json
import unittest

from cosmatter.config import AGENT_ROOT
from cosmatter.facilities import review_evidence
from cosmatter.models import AccessPolicy, EvidenceCard, Provenance, Stance


class FrozenEvidencePatrolFixtureTests(unittest.TestCase):
    def test_incomplete_conditions_fixture_is_rejected_without_using_paper_text(self) -> None:
        path = AGENT_ROOT / "examples" / "frozen" / "bfo_evidence_patrol_incomplete_conditions.json"
        fixture = json.loads(path.read_text(encoding="utf-8"))
        entry = fixture["evidence_card"]
        card = EvidenceCard(
            claim="Synthetic regression record; not a scientific claim.",
            stance=Stance(entry["stance"]),
            material=fixture["material"],
            property_name=fixture["property_name"],
            conditions=entry["conditions"],
            quote="Synthetic fixture only; no paper text is included.",
            provenance=Provenance(entry["evidence_id"], "fixture", "CosMatter frozen test", access_policy=AccessPolicy.LOCAL_ONLY),
            evidence_id=entry["evidence_id"],
        )
        review = review_evidence(card)

        self.assertTrue(fixture["synthetic"])
        self.assertEqual(review.status.value, fixture["expected_review"]["status"])
        self.assertEqual(set(review.missing_conditions), set(fixture["expected_review"]["missing_conditions"]))


if __name__ == "__main__":
    unittest.main()
