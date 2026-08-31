from __future__ import annotations

import unittest

from cosmatter.graph_plan_review import GraphPlanApproval


class GraphPlanReviewTests(unittest.TestCase):
    def test_approval_is_not_an_execution_or_evidence_acceptance(self) -> None:
        approval = GraphPlanApproval("mission_1", "graph:" + "a" * 32, "graph_plan_abcdef", "researcher", "Ready for manual follow-up.").to_dict()
        self.assertEqual(approval["status"], "human_approved_graph_plan_follow_up_not_execution_or_evidence_acceptance")

    def test_approval_rejects_unrelated_plan_identifier(self) -> None:
        with self.assertRaises(ValueError):
            GraphPlanApproval("mission_1", "graph:" + "a" * 32, "plan_abcdef", "researcher", "No.")


if __name__ == "__main__":
    unittest.main()
