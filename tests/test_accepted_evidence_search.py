from __future__ import annotations

import unittest
from dataclasses import replace

from cosmatter.accepted_evidence_search import AcceptedEvidenceSearchError, search_accepted_evidence
from cosmatter.models import AccessPolicy, EvidenceCard, MissionBrief, Provenance, ReviewStatus, Stance
from cosmatter.verification import VerificationDecision


class AcceptedEvidenceSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mission = MissionBrief("How does strain affect phase stability?", "BiFeO3", "phase stability", "thin films", mission_id="mission_search")
        self.accepted = EvidenceCard("Strain changes phase stability in the reported thin-film condition.", Stance.SUPPORT, "BiFeO3", "phase stability", {"strain_percent": 1.0}, "private quote", Provenance("doc_1", "figure:2", "reviewed fixture", access_policy=AccessPolicy.AUTHORIZED), evidence_id="evidence_accepted")
        self.rejected = EvidenceCard("Unreviewed competing text.", Stance.CONTRADICT, "BiFeO3", "phase stability", {}, "private other quote", Provenance("doc_2", "line:9", "reviewed fixture", access_policy=AccessPolicy.AUTHORIZED), evidence_id="evidence_rejected")

    def test_returns_only_accepted_safe_pointers_without_quotes(self) -> None:
        decision = VerificationDecision(self.mission.mission_id, self.accepted.evidence_id, ReviewStatus.ACCEPTED, "human reviewed")
        result = search_accepted_evidence(mission=self.mission, cards=(self.accepted, self.rejected), decisions=(decision,), query="strain phase stability")
        self.assertEqual(result["accepted_evidence_count"], 1)
        self.assertEqual(result["result_count"], 1)
        self.assertEqual(result["results"][0]["evidence_id"], self.accepted.evidence_id)
        rendered = str(result)
        self.assertNotIn("private quote", rendered)
        self.assertNotIn("private other quote", rendered)
        self.assertNotIn("strain phase stability", rendered)

    def test_refuses_search_when_no_accepted_evidence_exists(self) -> None:
        with self.assertRaisesRegex(AcceptedEvidenceSearchError, "at least one accepted"):
            search_accepted_evidence(mission=self.mission, cards=(self.accepted,), decisions=(), query="strain")

    def test_exact_id_only_matches_one_currently_accepted_card(self) -> None:
        decision = VerificationDecision(self.mission.mission_id, self.accepted.evidence_id, ReviewStatus.ACCEPTED, "human reviewed")
        cards = (self.accepted, self.rejected)
        result = search_accepted_evidence(mission=self.mission, cards=cards, decisions=(decision,), evidence_id=self.accepted.evidence_id)
        self.assertEqual(result["match_mode"], "exact_id")
        self.assertEqual([hit["evidence_id"] for hit in result["results"]], [self.accepted.evidence_id])
        for mismatched in (self.accepted.evidence_id.upper(), "evidence", self.rejected.evidence_id):
            result = search_accepted_evidence(mission=self.mission, cards=cards, decisions=(decision,), evidence_id=mismatched)
            self.assertEqual(result["results"], [])
        with self.assertRaisesRegex(AcceptedEvidenceSearchError, "ambiguous verification"):
            search_accepted_evidence(mission=self.mission, cards=cards, decisions=(decision, decision), evidence_id=self.accepted.evidence_id)
        with self.assertRaisesRegex(AcceptedEvidenceSearchError, "provide a query or"):
            search_accepted_evidence(mission=self.mission, cards=cards, decisions=(decision,), query="strain", evidence_id=self.accepted.evidence_id)

    def test_exact_location_returns_all_distinct_accepted_cards_at_one_document_locator(self) -> None:
        same_place = replace(self.accepted, evidence_id="card_b")
        next_figure = replace(self.accepted, evidence_id="card_c", provenance=replace(self.accepted.provenance, locator="figure:20"))
        other_paper = replace(self.accepted, evidence_id="card_d", provenance=replace(self.accepted.provenance, document_id="doc_2"))
        unreviewed = replace(self.accepted, evidence_id="card_e")
        reviewed = [self.accepted, same_place, next_figure, other_paper]
        decisions = [VerificationDecision(self.mission.mission_id, card.evidence_id, ReviewStatus.ACCEPTED, "reviewed") for card in reviewed]
        fixture = dict(mission=self.mission, cards=[*reviewed, unreviewed], decisions=decisions)
        exact = dict(document_id="doc_1", locator="figure:2")
        result = search_accepted_evidence(**fixture, **exact)
        self.assertEqual((result["match_mode"], result["matched_count"]), ("exact_locator", 2))
        self.assertEqual([hit["evidence_id"] for hit in result["results"]], sorted([self.accepted.evidence_id, same_place.evidence_id]))
        self.assertNotIn("private quote", str(result))
        bounded = search_accepted_evidence(**fixture, **exact, limit=1)
        self.assertEqual((len(bounded["results"]), bounded["matched_count"]), (1, 2))
        self.assertEqual(search_accepted_evidence(**fixture, document_id="doc_1", locator="Figure:2")["results"], [])
        for invalid in ({"document_id": "doc_1"}, {"locator": "figure:2"}, {**exact, "evidence_id": "card_b"},
                        {**exact, "query": "strain"}, {**exact, "locator": "x" * 241}, {**exact, "locator": "x\ny"}):
            with self.subTest(invalid=invalid), self.assertRaises(AcceptedEvidenceSearchError):
                search_accepted_evidence(**fixture, **invalid)
        with self.assertRaisesRegex(AcceptedEvidenceSearchError, "ambiguous"):
            search_accepted_evidence(**{**fixture, "decisions": [*decisions, decisions[0]]}, **exact)
        with self.assertRaisesRegex(AcceptedEvidenceSearchError, "ambiguous"):
            search_accepted_evidence(**{**fixture, "cards": [*reviewed, replace(other_paper, evidence_id=same_place.evidence_id)]}, **exact)


if __name__ == "__main__":
    unittest.main()
