from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
