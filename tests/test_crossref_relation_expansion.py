import unittest

from cosmatter.crossref import CrossrefWork
from cosmatter.crossref_relation_expansion import TRUST_STATUS, CrossrefRelationExpansionError, build_crossref_relation_expansion
from cosmatter.models import AccessPolicy, EvidenceCard, MissionBrief, Provenance, ReviewStatus, Stance
from cosmatter.verification import VerificationDecision


class CrossrefRelationExpansionTests(unittest.TestCase):
    def test_builds_non_scientific_reference_edges_and_preserves_field_availability(self) -> None:
        mission = MissionBrief(question="q", material="BiFeO3", property_name="phase", scope="scope", mission_id="mission_1")
        card = EvidenceCard(claim="claim", stance=Stance.SUPPORT, material="BiFeO3", property_name="phase", conditions={}, quote="short", provenance=Provenance(document_id="doc_1", locator="p.1", source="fixture", doi="10.1000/root", access_policy=AccessPolicy.AUTHORIZED), evidence_id="evidence_1")
        decision = VerificationDecision(mission_id="mission_1", evidence_id="evidence_1", status=ReviewStatus.ACCEPTED, reason="accepted")
        expansion = build_crossref_relation_expansion(mission, card, decision, CrossrefWork("10.1000/root", ("10.1000/a",), True, None))
        self.assertEqual(expansion["trust_status"], TRUST_STATUS)
        self.assertEqual(expansion["edges"], [{"edge_type": "crossref_reference", "target_doi": "10.1000/a"}])
        self.assertTrue(expansion["reference_field_present"])

    def test_rejects_mismatched_crossref_record(self) -> None:
        mission = MissionBrief(question="q", material="BiFeO3", property_name="phase", scope="scope", mission_id="mission_1")
        card = EvidenceCard(claim="claim", stance=Stance.SUPPORT, material="BiFeO3", property_name="phase", conditions={}, quote="short", provenance=Provenance(document_id="doc_1", locator="p.1", source="fixture", doi="10.1000/root"), evidence_id="evidence_1")
        decision = VerificationDecision(mission_id="mission_1", evidence_id="evidence_1", status=ReviewStatus.ACCEPTED, reason="accepted")
        with self.assertRaises(CrossrefRelationExpansionError):
            build_crossref_relation_expansion(mission, card, decision, CrossrefWork("10.1000/other", (), False, None))
