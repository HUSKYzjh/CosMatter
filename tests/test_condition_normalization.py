import unittest

from cosmatter.condition_normalization import ConditionNormalizationError, condition_normalization_from_review
from cosmatter.models import EvidenceCard, MissionBrief, Provenance, ReviewStatus, Stance
from cosmatter.verification import VerificationDecision


class ConditionNormalizationTests(unittest.TestCase):
    def test_maps_only_accepted_raw_scalar_conditions_without_conversion(self) -> None:
        mission = MissionBrief(question="q", material="BiFeO3", property_name="phase", scope="s", mission_id="m1")
        card = EvidenceCard(claim="c", stance=Stance.SUPPORT, material="BiFeO3", property_name="phase", conditions={"thickness_nm": 30}, quote="q", provenance=Provenance(document_id="d1", locator="p1", source="fixture"), evidence_id="e1")
        decision = VerificationDecision(mission_id="m1", evidence_id="e1", status=ReviewStatus.ACCEPTED, reason="ok")
        artifact = condition_normalization_from_review(mission, (card,), (decision,), {"mappings":[{"evidence_id":"e1","raw_field":"thickness_nm","canonical_field":"thickness","unit":"nm"}]})
        self.assertEqual(artifact["mappings"][0]["unit"], "nm")

    def test_rejects_unrecorded_condition(self) -> None:
        mission = MissionBrief(question="q", material="BiFeO3", property_name="phase", scope="s", mission_id="m1")
        card = EvidenceCard(claim="c", stance=Stance.SUPPORT, material="BiFeO3", property_name="phase", conditions={}, quote="q", provenance=Provenance(document_id="d1", locator="p1", source="fixture"), evidence_id="e1")
        decision = VerificationDecision(mission_id="m1", evidence_id="e1", status=ReviewStatus.ACCEPTED, reason="ok")
        with self.assertRaises(ConditionNormalizationError): condition_normalization_from_review(mission, (card,), (decision,), {"mappings":[{"evidence_id":"e1","raw_field":"thickness_nm","canonical_field":"thickness","unit":"nm"}]})

    def test_rejects_missing_or_nonfinite_raw_condition_values(self) -> None:
        mission = MissionBrief(question="q", material="BiFeO3", property_name="phase", scope="s", mission_id="m1")
        decision = VerificationDecision(mission_id="m1", evidence_id="e1", status=ReviewStatus.ACCEPTED, reason="ok")
        selection = {"mappings": [{"evidence_id": "e1", "raw_field": "thickness_nm", "canonical_field": "thickness", "unit": "nm"}]}
        for value in ("unknown ", " ", float("nan"), float("inf"), True, None, {"value": 30}):
            card = EvidenceCard(claim="c", stance=Stance.SUPPORT, material="BiFeO3", property_name="phase", conditions={"thickness_nm": value}, quote="q", provenance=Provenance(document_id="d1", locator="p1", source="fixture"), evidence_id="e1")
            with self.assertRaises(ConditionNormalizationError):
                condition_normalization_from_review(mission, (card,), (decision,), selection)
