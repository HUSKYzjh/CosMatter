import json
import unittest

from cosmatter.config import AGENT_ROOT
from cosmatter.facilities import condition_differential
from cosmatter.models import AccessPolicy, EvidenceCard, Provenance, Stance


class BfoFrozenFixtureTests(unittest.TestCase):
    def test_synthetic_fixture_exercises_condition_difference_without_claiming_science(self) -> None:
        path = AGENT_ROOT / "examples" / "frozen" / "bfo_route_diagnostics.json"
        fixture = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(fixture["synthetic"])
        cards = tuple(
            EvidenceCard(
                claim="Synthetic regression record; not a scientific claim.",
                stance=Stance(item["stance"]),
                material=fixture["material"],
                property_name=fixture["property_name"],
                conditions=item["conditions"],
                quote="Synthetic fixture only; no paper text is included.",
                provenance=Provenance(item["evidence_id"], "fixture", "CosMatter frozen test", access_policy=AccessPolicy.LOCAL_ONLY),
                evidence_id=item["evidence_id"],
            )
            for item in fixture["evidence_cards"]
        )
        matrix = condition_differential(cards, tuple(fixture["counterevidence_queries"]))
        self.assertEqual(set(matrix.rows[0].differing_fields), set(fixture["expected_differing_fields"]))


if __name__ == "__main__":
    unittest.main()
