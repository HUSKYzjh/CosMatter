import tempfile
import unittest
from pathlib import Path

from cosmatter.counterevidence import CounterevidenceExecution
from cosmatter.facilities import condition_differential
from cosmatter.gap_analysis import GapAnalysisError, candidates_from_discrepancies, load_gap_candidates, write_gap_candidates
from cosmatter.models import AccessPolicy, EvidenceCard, Provenance, ReviewStatus, Stance
from cosmatter.verification import VerificationDecision


class GapAnalysisTests(unittest.TestCase):
    def card(self, identifier, stance, strain):
        return EvidenceCard(
            claim="located claim", stance=stance, material="BiFeO3", property_name="phase stability",
            conditions={"sample_form": "film", "strain_percent": strain, "substrate": "STO", "thickness_nm": 20, "temperature_k": 300, "method": "XRD"},
            quote="short reviewed quote", provenance=Provenance(identifier, "p.1", "fixture", access_policy=AccessPolicy.AUTHORIZED), evidence_id=identifier,
        )

    def accepted_fixture(self):
        cards = (self.card("e1", Stance.SUPPORT, 1.0), self.card("e2", Stance.CONTRADICT, -1.0))
        decisions = tuple(VerificationDecision("m1", card.evidence_id, ReviewStatus.ACCEPTED, "ok") for card in cards)
        matrix = condition_differential(cards, ("counter",))
        return cards, decisions, matrix

    def test_candidate_requires_accepted_conflicting_evidence_and_explicit_conditions(self):
        cards, decisions, matrix = self.accepted_fixture()
        result = candidates_from_discrepancies("m1", "BiFeO3", "phase stability", cards, decisions, matrix)
        self.assertEqual(result[0].evidence_ids, ("e1", "e2"))
        self.assertEqual(result[0].novelty_status, "unverified_requires_bounded_literature_review")
        self.assertIn("strain_percent", result[0].falsifiable_hypothesis)
        self.assertEqual(result[0].counterevidence_boundary.status, "not_attested")

    def test_executed_boundary_round_trips_and_is_required_for_persistence(self):
        cards, decisions, matrix = self.accepted_fixture()
        execution = CounterevidenceExecution(1, 1, 2, "a" * 64)
        candidates = candidates_from_discrepancies("m1", "BiFeO3", "phase stability", cards, decisions, matrix, execution)
        boundary = candidates[0].counterevidence_boundary
        self.assertEqual(boundary.status, "all_approved_counterevidence_queries_recorded")
        self.assertEqual(boundary.executed_query_count, 1)
        self.assertEqual(boundary.candidate_history_sha256, "a" * 64)
        with tempfile.TemporaryDirectory() as directory:
            path = write_gap_candidates(Path(directory), candidates)
            reloaded = load_gap_candidates(path)
        self.assertEqual(reloaded[0].counterevidence_boundary, boundary)
        unexecuted = candidates_from_discrepancies("m1", "BiFeO3", "phase stability", cards, decisions, matrix)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(GapAnalysisError, "counterevidence execution is incomplete"):
                write_gap_candidates(Path(directory), unexecuted)

    def test_rejects_malformed_in_memory_execution_boundary(self):
        cards, decisions, matrix = self.accepted_fixture()
        with self.assertRaisesRegex(GapAnalysisError, "retrieval-history fingerprint"):
            candidates_from_discrepancies(
                "m1", "BiFeO3", "phase stability", cards, decisions, matrix,
                CounterevidenceExecution(1, 1, 1, "not-a-digest"),
            )

    def test_rejects_accepted_decisions_from_a_different_mission(self):
        cards = (self.card("e1", Stance.SUPPORT, 1.0), self.card("e2", Stance.CONTRADICT, -1.0))
        decisions = tuple(VerificationDecision("other_mission", card.evidence_id, ReviewStatus.ACCEPTED, "ok") for card in cards)
        with self.assertRaises(GapAnalysisError):
            candidates_from_discrepancies("m1", "BiFeO3", "phase stability", cards, decisions, condition_differential(cards, ("counter",)))

    def test_rejects_when_evidence_is_not_accepted(self):
        cards = (self.card("e1", Stance.SUPPORT, 1.0), self.card("e2", Stance.CONTRADICT, -1.0))
        decisions = (
            VerificationDecision("m1", "e1", ReviewStatus.ACCEPTED, "ok"),
            VerificationDecision("m1", "e2", ReviewStatus.REJECTED, "bad"),
        )
        with self.assertRaises(GapAnalysisError):
            candidates_from_discrepancies("m1", "BiFeO3", "phase stability", cards, decisions, condition_differential(cards, ("counter",)))


if __name__ == "__main__":
    unittest.main()
