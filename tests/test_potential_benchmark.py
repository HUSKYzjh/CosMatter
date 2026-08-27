import unittest

from cosmatter.potential_benchmark import (
    PotentialBenchmarkError,
    evaluate_potential_results,
    generate_potential_boundary_plan,
    propose_potential_followups,
)


class PotentialBenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = generate_potential_boundary_plan(
            system_label="BiFeO3 epitaxial films", potential_models=("dp_baseline", "nequip_candidate"),
            reference_method="approved DFT single-point protocol", seed=20260811,
            controls={"strain_percent": (-2.0, 2.0), "temperature_k": (300.0, 900.0)},
        )

    def test_plan_is_seeded_and_exposes_three_boundary_regimes(self) -> None:
        repeated = generate_potential_boundary_plan(
            system_label="BiFeO3 epitaxial films", potential_models=("dp_baseline", "nequip_candidate"),
            reference_method="approved DFT single-point protocol", seed=20260811,
            controls={"strain_percent": (-2.0, 2.0), "temperature_k": (300.0, 900.0)},
        )
        self.assertEqual(self.plan, repeated)
        self.assertEqual(len(self.plan["tasks"]), 9)
        self.assertEqual({regime: sum(task["regime"] == regime for task in self.plan["tasks"]) for regime in ("in_domain", "near_boundary", "out_of_domain")}, {"in_domain": 3, "near_boundary": 3, "out_of_domain": 3})
        self.assertEqual(self.plan["samples_per_regime"], 3)
        self.assertEqual(self.plan["baseline_model_id"], "dp_baseline")
        self.assertEqual(self.plan["trust_status"], "framework_test_plan_not_executed_calculation")

    def test_custom_sample_count_is_deterministic_and_bounded(self) -> None:
        plan = generate_potential_boundary_plan(
            system_label="BiFeO3 epitaxial films", potential_models=("dp_baseline", "nequip_candidate"),
            reference_method="approved DFT single-point protocol", seed=20260811,
            controls={"strain_percent": (-2.0, 2.0)}, samples_per_regime=5,
        )
        self.assertEqual(len(plan["tasks"]), 15)
        with self.assertRaises(PotentialBenchmarkError):
            generate_potential_boundary_plan(
                system_label="BiFeO3", potential_models=("a", "b"), reference_method="DFT", seed=1,
                controls={"strain_percent": (-2.0, 2.0)}, samples_per_regime=33,
            )

    def test_imported_results_are_compared_by_boundary_regime(self) -> None:
        results = []
        for task in self.plan["tasks"]:
            for model_id, delta in (("dp_baseline", 0.02), ("nequip_candidate", 0.01)):
                if task["regime"] == "out_of_domain":
                    delta *= 8
                results.append({
                    "task_id": task["task_id"], "model_id": model_id,
                    "atom_count": 20,
                    "reference_energy_ev": -10.0, "predicted_energy_ev": -10.0 + delta,
                    "force_rmse_ev_per_a": delta, "wall_time_seconds": 5.0,
                })
        report = evaluate_potential_results(plan=self.plan, results=results)
        candidate = next(item for item in report["model_summaries"] if item["model_id"] == "nequip_candidate")
        self.assertTrue(candidate["boundary_warning"])
        self.assertEqual(report["trust_status"], "imported_external_result_comparison_requires_human_scientific_review")
        self.assertEqual(report["execution_protocol_status"], "not_recorded")
        self.assertEqual(candidate["relative_to_baseline"]["baseline_model_id"], "dp_baseline")
        self.assertGreater(candidate["relative_to_baseline"]["energy_error_reduction_fraction_per_atom"], 0.0)

    def test_followups_target_worst_observed_regime_without_execution(self) -> None:
        results = []
        for task in self.plan["tasks"]:
            for model_id in self.plan["potential_models"]:
                delta = 0.1 if task["regime"] == "out_of_domain" and model_id == "dp_baseline" else 0.01
                results.append({"task_id": task["task_id"], "model_id": model_id, "atom_count": 20, "reference_energy_ev": -2.0,
                                "predicted_energy_ev": -2.0 + delta, "force_rmse_ev_per_a": delta, "wall_time_seconds": 1.0})
        followups = propose_potential_followups(plan=self.plan, evaluation=evaluate_potential_results(plan=self.plan, results=results))
        self.assertEqual(followups["trigger"]["regime"], "out_of_domain")
        self.assertTrue(all(task["approval_required"] for task in followups["followup_tasks"]))
        self.assertIn("not_executed", followups["trust_status"])

    def test_followups_anchor_to_one_observed_task_not_a_regime_average(self) -> None:
        anchor_task = next(task for task in self.plan["tasks"] if task["regime"] == "out_of_domain")
        results = []
        for task in self.plan["tasks"]:
            for model_id in self.plan["potential_models"]:
                delta = 0.01
                if task["task_id"] == anchor_task["task_id"] and model_id == "nequip_candidate":
                    delta = 0.5
                results.append({
                    "task_id": task["task_id"], "model_id": model_id,
                    "atom_count": 20,
                    "reference_energy_ev": -2.0, "predicted_energy_ev": -2.0 + delta,
                    "force_rmse_ev_per_a": delta, "wall_time_seconds": 1.0,
                })
        followups = propose_potential_followups(
            plan=self.plan,
            evaluation=evaluate_potential_results(plan=self.plan, results=results),
        )
        self.assertEqual(followups["trigger"]["task_id"], anchor_task["task_id"])
        self.assertEqual(followups["trigger"]["model_id"], "nequip_candidate")
        self.assertTrue(all(item["anchor_controls"] == anchor_task["controls"] for item in followups["followup_tasks"]))
        self.assertTrue(all(item["target_model_id"] == "nequip_candidate" for item in followups["followup_tasks"]))
    def test_rejects_model_comparison_with_inconsistent_reference_energy_for_one_task(self) -> None:
        task = self.plan["tasks"][0]
        results = [
            {"task_id": task["task_id"], "model_id": "dp_baseline", "atom_count": 20, "reference_energy_ev": -2.0,
             "predicted_energy_ev": -1.9, "force_rmse_ev_per_a": 0.1, "wall_time_seconds": 1.0},
            {"task_id": task["task_id"], "model_id": "nequip_candidate", "atom_count": 20, "reference_energy_ev": -1.0,
             "predicted_energy_ev": -0.9, "force_rmse_ev_per_a": 0.1, "wall_time_seconds": 1.0},
        ]
        for other in self.plan["tasks"][1:]:
            for model_id in self.plan["potential_models"]:
                results.append({"task_id": other["task_id"], "model_id": model_id, "atom_count": 20, "reference_energy_ev": -2.0,
                                "predicted_energy_ev": -1.9, "force_rmse_ev_per_a": 0.1, "wall_time_seconds": 1.0})
        with self.assertRaises(PotentialBenchmarkError):
            evaluate_potential_results(plan=self.plan, results=results)
    def test_missing_model_task_pair_is_rejected(self) -> None:
        with self.assertRaises(PotentialBenchmarkError):
            evaluate_potential_results(plan=self.plan, results=[])

    def test_rejects_task_model_rows_with_inconsistent_atom_count(self) -> None:
        results = []
        for task in self.plan["tasks"]:
            for model_id in self.plan["potential_models"]:
                results.append({
                    "task_id": task["task_id"], "model_id": model_id,
                    "atom_count": 21 if task is self.plan["tasks"][0] and model_id == "nequip_candidate" else 20,
                    "reference_energy_ev": -2.0, "predicted_energy_ev": -1.9,
                    "force_rmse_ev_per_a": 0.1, "wall_time_seconds": 1.0,
                })
        with self.assertRaises(PotentialBenchmarkError):
            evaluate_potential_results(plan=self.plan, results=results)


if __name__ == "__main__":
    unittest.main()
