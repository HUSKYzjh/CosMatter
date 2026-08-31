from __future__ import annotations

import unittest

from cosmatter.graph_plan import GraphPlanDraft


class GraphPlanTests(unittest.TestCase):
    def test_plan_is_untrusted_and_nonexecuting(self) -> None:
        value = GraphPlanDraft("mission_1", "graph:" + "a" * 32, ("evidence:" + "b" * 32,), "Inspect conflict").to_dict()
        self.assertEqual(value["trust_status"], "untrusted_graph_plan_draft_not_execution_or_evidence_acceptance")
        self.assertEqual(value["proposed_action"], "request_human_to_review_or_project_graph")
        self.assertTrue(str(value["plan_id"]).startswith("graph_plan_"))

    def test_plan_rejects_duplicate_nodes_and_invalid_intent(self) -> None:
        with self.assertRaises(ValueError):
            GraphPlanDraft("mission_1", "graph:" + "a" * 32, ("node", "node"), "Inspect conflict")
        with self.assertRaises(ValueError):
            GraphPlanDraft("mission_1", "graph:" + "a" * 32, ("node",), "x" * 501)


if __name__ == "__main__":
    unittest.main()
