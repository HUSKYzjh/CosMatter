import unittest

from cosmatter.models import AccessPolicy, EvidenceCard, MissionBrief, Provenance, ReviewStatus, Stance
from cosmatter.openalex import OpenAlexWork
from cosmatter.relation_expansion import RelationExpansionError, build_relation_expansion
from cosmatter.verification import VerificationDecision


class RelationExpansionTests(unittest.TestCase):
    def test_distinguishes_citation_references_from_algorithmic_related_works(self) -> None:
        mission = MissionBrief(question="q", material="BiFeO3", property_name="phase", scope="scope", mission_id="mission_1")
        card = EvidenceCard(
            claim="claim", stance=Stance.SUPPORT, material="BiFeO3", property_name="phase", conditions={}, quote="short quote",
            provenance=Provenance(document_id="doc_1", locator="p.1", source="fixture", doi="10.1000/test", access_policy=AccessPolicy.AUTHORIZED),
            evidence_id="evidence_1",
        )
        decision = VerificationDecision(mission_id="mission_1", evidence_id="evidence_1", status=ReviewStatus.ACCEPTED, reason="accepted")
        work = OpenAlexWork("https://openalex.org/W1", ("https://openalex.org/W2",), ("https://openalex.org/W3",), None)
        expansion = build_relation_expansion(mission, card, decision, work)
        self.assertEqual([edge["edge_type"] for edge in expansion["edges"]], ["citation_reference", "algorithmic_related"])
        self.assertIn("not_scientific_evidence", expansion["trust_status"])

    def test_rejects_nonaccepted_or_doi_less_evidence(self) -> None:
        mission = MissionBrief(question="q", material="BiFeO3", property_name="phase", scope="scope", mission_id="mission_1")
        card = EvidenceCard(claim="claim", stance=Stance.SUPPORT, material="BiFeO3", property_name="phase", conditions={}, quote="short quote", provenance=Provenance(document_id="doc_1", locator="p.1", source="fixture"), evidence_id="evidence_1")
        decision = VerificationDecision(mission_id="mission_1", evidence_id="evidence_1", status=ReviewStatus.ACCEPTED, reason="accepted")
        with self.assertRaises(RelationExpansionError):
            build_relation_expansion(mission, card, decision, OpenAlexWork("https://openalex.org/W1", (), (), None))
