import tempfile
import unittest
from pathlib import Path

from cosmatter.ising_benchmark import build_ising_benchmark_plan, propose_ising_followups, run_ising_benchmark
from cosmatter.ising_summary import IsingSummaryError, ising_benchmark_summary, write_ising_benchmark_summary


class IsingSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = build_ising_benchmark_plan(
            lattice_size=8, temperatures=(2.0,), burn_in_sweeps=4,
            measurement_sweeps=24, seed=8, repetitions=2,
        )
        self.result = run_ising_benchmark(plan=self.plan)

    def test_exports_aggregate_only_and_preserves_approval_gate(self) -> None:
        followups = propose_ising_followups(plan=self.plan, result=self.result)
        summary = ising_benchmark_summary(plan=self.plan, result=self.result, followups=followups)
        self.assertEqual(len(summary["metrics"]), 3)
        self.assertNotIn("replicate_metrics", summary)
        self.assertTrue(summary["followup_proposal"]["proposed_refinement"]["approval_required"])
        with tempfile.TemporaryDirectory() as directory:
            path = write_ising_benchmark_summary(Path(directory), summary)
            self.assertTrue(path.is_file())

    def test_rejects_result_bound_to_a_different_plan(self) -> None:
        modified = dict(self.result)
        modified["seed"] = 9
        with self.assertRaises(IsingSummaryError):
            ising_benchmark_summary(plan=self.plan, result=modified)


if __name__ == "__main__":
    unittest.main()
