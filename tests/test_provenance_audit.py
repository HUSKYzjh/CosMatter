import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.models import AccessPolicy, EvidenceCard, MissionBrief, Provenance, ReviewStatus, Stance
from cosmatter.provenance_audit import ProvenanceAuditError, audit_accepted_evidence_provenance, write_evidence_provenance_audit
from cosmatter.verification import VerificationDecision


QUOTE = "A BiFeO3 thin film was measured at 300 K."


def _card(evidence_id: str, document_id: str, quote: str = QUOTE) -> EvidenceCard:
    return EvidenceCard(
        "bounded claim", Stance.SUPPORT, "BiFeO3", "phase stability", {"sample_form": "film"}, quote,
        Provenance(document_id, "page:3 paragraph:2", "fixture", access_policy=AccessPolicy.AUTHORIZED), evidence_id=evidence_id,
    )


class ProvenanceAuditTests(unittest.TestCase):
    def test_requires_exact_map_linkage_for_every_accepted_card_without_quotes(self) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_provenance")
        cards = (_card("mapped", "doc_mapped"), _card("manual", "doc_manual"))
        decisions = tuple(VerificationDecision(mission.mission_id, card.evidence_id, ReviewStatus.ACCEPTED, "complete") for card in cards)
        source_map = {
            "mission_id": mission.mission_id,
            "trust_status": "human_reviewed_parser_selection",
            "document_id": "doc_mapped",
            "segments": [{"locator": "page:3 paragraph:2", "quote_sha256": hashlib.sha256(QUOTE.encode("utf-8")).hexdigest()}],
        }
        manual_map = {**source_map, "document_id": "doc_manual"}
        result = audit_accepted_evidence_provenance(mission=mission, cards=cards, decisions=decisions, source_maps=(source_map, manual_map))
        self.assertEqual(result["exact_reviewed_source_map_match_count"], 2)
        self.assertEqual(result["manual_locator_only_count"], 0)
        self.assertNotIn(QUOTE, json.dumps(result))
        with tempfile.TemporaryDirectory() as directory:
            path = write_evidence_provenance_audit(Path(directory), result)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["accepted_evidence_count"], 2)

    def test_rejects_tampered_card_when_its_document_has_a_source_map(self) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_provenance")
        card = _card("mapped", "doc_mapped", "different quote")
        decision = VerificationDecision(mission.mission_id, card.evidence_id, ReviewStatus.ACCEPTED, "complete")
        source_map = {
            "mission_id": mission.mission_id,
            "trust_status": "human_reviewed_parser_selection",
            "document_id": "doc_mapped",
            "segments": [{"locator": "page:3 paragraph:2", "quote_sha256": hashlib.sha256(QUOTE.encode("utf-8")).hexdigest()}],
        }
        with self.assertRaises(ProvenanceAuditError):
            audit_accepted_evidence_provenance(mission=mission, cards=(card,), decisions=(decision,), source_maps=(source_map,))


if __name__ == "__main__":
    unittest.main()
