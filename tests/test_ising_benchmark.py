import unittest

from cosmatter.ising_benchmark import (
    IsingBenchmarkError,
    build_ising_benchmark_plan,
    propose_ising_followups,
    run_ising_benchmark,
)


class IsingBenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = build_ising_benchmark_plan(
            lattice_size=8,
            temperatures=(2.0, 2.269),
            burn_in_sweeps=4,
            measurement_sweeps=24,
            seed=20260811,
        )

    def test_plan_names_all_three_classical_algorithms_and_is_seeded(self) -> None:
        repeated = build_ising_benchmark_plan(
            lattice_size=8,
            temperatures=(2.0, 2.269),
            burn_in_sweeps=4,
            measurement_sweeps=24,
            seed=20260811,
        )
        self.assertEqual(self.plan, repeated)
        self.assertEqual(self.plan["algorithms"], ["metropolis", "wolff", "swendsen_wang"])
        self.assertIn("not_run", self.plan["trust_status"])

    def test_execution_emits_aggregate_autocorrelation_and_effective_sample_metrics(self) -> None:
        result = run_ising_benchmark(plan=self.plan)
        self.assertEqual(len(result["algorithm_metrics"]), 6)
        self.assertEqual(len(result["replicate_metrics"]), 18)
        self.assertTrue(all(row["replicate_count"] == 3 for row in result["algorithm_metrics"]))
        self.assertTrue(all(row["integrated_autocorrelation_time_sweeps"] >= 0.5 for row in result["algorithm_metrics"]))
        self.assertTrue(all(row["effective_samples_per_second"] > 0 for row in result["algorithm_metrics"]))
        self.assertTrue(all("relative_to_metropolis" in row for row in result["algorithm_metrics"]))
        self.assertEqual(result["measurement_environment"]["parallelism"], "single Python process; no GPU or MPI")
        self.assertIn("measurement sweeps only", result["measurement_environment"]["timing_scope"])
        self.assertIn("scope_limited", result["trust_status"])

    def test_followups_are_approval_required_and_plan_bound(self) -> None:
        followups = propose_ising_followups(plan=self.plan, result=run_ising_benchmark(plan=self.plan))
        self.assertTrue(followups["proposed_refinement"]["approval_required"])
        self.assertEqual(followups["plan_sha256"], followups["plan_sha256"])

    def test_rejects_invalid_benchmark_size(self) -> None:
        with self.assertRaises(IsingBenchmarkError):
            build_ising_benchmark_plan(
                lattice_size=3,
                temperatures=(2.269,),
                burn_in_sweeps=0,
                measurement_sweeps=24,
                seed=1,
            )


if __name__ == "__main__":
    unittest.main()
