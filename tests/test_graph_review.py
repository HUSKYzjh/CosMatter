from __future__ import annotations
import unittest
from cosmatter.graph_review import GraphReviewRequest

class GraphReviewTests(unittest.TestCase):
    def test_request_is_pending_and_cannot_claim_evidence_acceptance(self) -> None:
        request = GraphReviewRequest("mission_1", "graph:" + "a" * 32, ("evidence:" + "b" * 32,), "Check relation semantics.")
        self.assertEqual(request.to_dict()["status"], "pending_human_review_not_evidence_acceptance")
    def test_request_rejects_duplicate_nodes(self) -> None:
        with self.assertRaises(ValueError):
            GraphReviewRequest("mission_1", "graph:" + "a" * 32, ("node", "node"), "Check.")
