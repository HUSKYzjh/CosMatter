import unittest

from cosmatter.counterevidence import CounterevidenceGateError, require_executed_counterevidence
from cosmatter.models import FlightPlan


class CounterevidenceGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = FlightPlan("mission_1", ("scope",), ("primary",), ("counter_a", "counter_b"))

    def test_requires_every_approved_counter_query_to_have_executed(self) -> None:
        result = require_executed_counterevidence(
            self.plan,
            {"searches": [
                {"query": "primary", "candidates": []},
                {"query": "counter_a", "candidates": []},
                {"query": "counter_b", "candidates": []},
            ]},
        )
        self.assertEqual(result.planned_query_count, 2)
        self.assertEqual(result.executed_query_count, 2)

    def test_rejects_a_plan_only_counter_query(self) -> None:
        with self.assertRaisesRegex(CounterevidenceGateError, "must execute every"):
            require_executed_counterevidence(
                self.plan,
                {"searches": [{"query": "counter_a", "candidates": []}]},
            )


if __name__ == "__main__":
    unittest.main()
