import copy
import json
import math
import random
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from cosmatter.pst_configuration_search import (
    A_SITE_COUNT,
    ABLATION_TRUST_STATUS,
    EvaluationBudgetLedger,
    PLAN_TRUST_STATUS,
    PstConfiguration,
    PstConfigurationSearchError,
    SyntheticEvaluation,
    build_pst_configuration_search_plan,
    motif_descriptors,
    random_configuration,
    realizable_composition,
    run_synthetic_mrmt_ablation,
    validate_pst_configuration_search_plan,
    validate_synthetic_ablation,
    write_pst_configuration_search_plan,
    write_synthetic_mrmt_ablation,
)


def _translated(configuration: PstConfiguration, dx: int, dy: int, dz: int) -> PstConfiguration:
    values = tuple(
        configuration.occupations[((x + dx) % 8) * 64 + ((y + dy) % 8) * 8 + (z + dz) % 8]
        for x in range(8)
        for y in range(8)
        for z in range(8)
    )
    return PstConfiguration(values)


def _plan_payload() -> dict[str, object]:
    return {
        "composition_requested": "0.5",
        "potential_id": "pst-potential-reviewed-v1",
        "potential_hash": "a" * 64,
        "objective_spec": {
            "mode": "pareto",
            "components": ["dielectric_response", "piezoelectric_response"],
            "conditions_hash": "b" * 64,
            "uncertainty_method": "independent-seed bootstrap confidence intervals",
        },
        "md_protocol_id": "pst-md-reviewed-v1",
        "md_protocol_hash": "c" * 64,
        "chain_count": 4,
        "random_baseline_count": 48,
        "short_md_steps": 20000,
        "short_md_repeats": 3,
        "promotion_rule": "promote only under the preregistered uncertainty-aware Pareto rule",
        "long_md_steps": 100000,
        "long_md_independent_seeds": [11, 29, 47],
        "max_evaluations": 192,
        "aggregate_md_step_budget": 12000000,
        "max_wallclock_hours": 24,
        "max_accelerator_hours": 48,
        "failure_policy": "record failed receipts and do not impute a property value",
        "stopping_rule": "stop at the first frozen resource bound",
    }


class PstConfigurationTests(unittest.TestCase):
    def test_composition_is_exact_and_never_silently_rounded(self) -> None:
        self.assertEqual(realizable_composition("0.5"), (256, 256, "0.5"))
        self.assertEqual(realizable_composition("0.125"), (64, 448, "0.125"))
        with self.assertRaises(PstConfigurationSearchError):
            realizable_composition("0.1")

    def test_fixed_composition_swap_and_random_generation_preserve_counts(self) -> None:
        configuration = random_configuration(173, random.Random(7))
        pb = configuration.occupations.index(1)
        sr = configuration.occupations.index(0)
        changed = configuration.swap(pb, sr)
        self.assertEqual((changed.n_pb, changed.n_sr), (173, A_SITE_COUNT - 173))
        with self.assertRaises(PstConfigurationSearchError):
            configuration.swap(pb, pb)
        with self.assertRaises(PstConfigurationSearchError):
            PstConfiguration((True,) + (0,) * (A_SITE_COUNT - 1))

    def test_periodic_translations_have_one_configuration_hash(self) -> None:
        configuration = random_configuration(193, random.Random(17))
        translated = _translated(configuration, 3, 6, 2)
        self.assertNotEqual(configuration.occupations, translated.occupations)
        self.assertEqual(configuration.configuration_hash(), translated.configuration_hash())
        self.assertEqual(configuration.canonical_translation(), translated.canonical_translation())

    def test_motif_descriptors_are_bounded_proposal_inputs_not_properties(self) -> None:
        descriptors = motif_descriptors(random_configuration(256, random.Random(23)))
        self.assertEqual(set(descriptors), {"nearest_neighbor_unlike_fraction", "warren_cowley_alpha_1", "composition_wave_power"})
        self.assertGreaterEqual(descriptors["nearest_neighbor_unlike_fraction"], 0.0)
        self.assertLessEqual(descriptors["nearest_neighbor_unlike_fraction"], 1.0)
        self.assertTrue(math.isfinite(descriptors["warren_cowley_alpha_1"]))
        self.assertEqual(set(descriptors["composition_wave_power"]), {"100", "010", "001", "200", "020", "002"})
        self.assertNotIn("dielectric", json.dumps(descriptors))
        self.assertNotIn("piezoelectric", json.dumps(descriptors))


class PstConfigurationPlanTests(unittest.TestCase):
    def test_plan_is_machine_readable_and_cannot_contain_execution_results(self) -> None:
        plan = build_pst_configuration_search_plan(_plan_payload())
        validate_pst_configuration_search_plan(plan)
        self.assertEqual(plan["trust_status"], PLAN_TRUST_STATUS)
        self.assertEqual(plan["composition"], {"requested": "0.5", "n_pb": 256, "n_sr": 256, "realized": "0.5"})
        self.assertFalse(plan["execution_authorized"])
        self.assertEqual(plan["property_prediction_count"], 0)
        self.assertEqual(plan["configuration_hashes"], [])
        with tempfile.TemporaryDirectory() as directory:
            path = write_pst_configuration_search_plan(Path(directory) / "pst_configuration_search_plan.json", plan)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), plan)
            self.assertEqual(write_pst_configuration_search_plan(path, plan), path)
            changed = copy.deepcopy(plan)
            changed["chain_count"] += 1
            with self.assertRaisesRegex(PstConfigurationSearchError, "cannot be overwritten"):
                write_pst_configuration_search_plan(path, changed)

        tampered = copy.deepcopy(plan)
        tampered["configuration_hashes"] = ["d" * 64]
        with self.assertRaises(PstConfigurationSearchError):
            validate_pst_configuration_search_plan(tampered)

    def test_plan_rejects_unrealizable_composition_and_incomplete_review_contract(self) -> None:
        payload = _plan_payload()
        payload["composition_requested"] = "0.1"
        with self.assertRaises(PstConfigurationSearchError):
            build_pst_configuration_search_plan(payload)
        payload = _plan_payload()
        del payload["stopping_rule"]
        with self.assertRaises(PstConfigurationSearchError):
            build_pst_configuration_search_plan(payload)


class PstEvaluationBudgetTests(unittest.TestCase):
    def test_cache_key_binds_configuration_potential_protocol_and_seed(self) -> None:
        ledger = EvaluationBudgetLedger(2)
        configuration = random_configuration(256, random.Random(31))

        def evaluator(item: PstConfiguration, seed: int) -> SyntheticEvaluation:
            item_hash = item.configuration_hash()
            return SyntheticEvaluation(item_hash, 0.5, tuple(1 for _ in range(A_SITE_COUNT)), sha256(f"{item_hash}:{seed}".encode()).hexdigest())

        first, cached = ledger.evaluate(configuration, potential_hash="a" * 64, protocol_hash="b" * 64, seed=1, evaluator=evaluator)
        second, cached_again = ledger.evaluate(configuration, potential_hash="a" * 64, protocol_hash="b" * 64, seed=1, evaluator=evaluator)
        self.assertFalse(cached)
        self.assertTrue(cached_again)
        self.assertEqual(first, second)
        self.assertEqual(ledger.used, 1)
        ledger.evaluate(configuration, potential_hash="a" * 64, protocol_hash="b" * 64, seed=2, evaluator=evaluator)
        with self.assertRaises(PstConfigurationSearchError):
            ledger.evaluate(configuration, potential_hash="c" * 64, protocol_hash="b" * 64, seed=2, evaluator=evaluator)


class PstSyntheticAblationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.artifact = run_synthetic_mrmt_ablation(evaluation_budget=48, search_seeds=(11, 29, 47))

    def test_ablation_is_same_budget_traceable_and_has_no_property_predictions(self) -> None:
        artifact = self.artifact
        validate_synthetic_ablation(artifact)
        self.assertEqual(artifact["trust_status"], ABLATION_TRUST_STATUS)
        self.assertEqual(artifact["property_prediction_count"], 0)
        for method_runs in artifact["runs"].values():
            for run in method_runs:
                self.assertEqual(run["evaluation_count"], 48)
                self.assertEqual(run["unique_configuration_count"], 48)
                self.assertEqual(run["property_prediction_count"], 0)
                self.assertRegex(run["best_configuration_hash"], r"^[0-9a-f]{64}$")
                self.assertRegex(run["best_receipt_id"], r"^[0-9a-f]{64}$")

    def test_mrmt_reproducibly_beats_uniform_random_on_frozen_synthetic_target(self) -> None:
        artifact = self.artifact
        self.assertTrue(artifact["mrmt_outperforms_uniform_random_every_seed"])
        random_scores = {run["search_seed"]: run["best_score"] for run in artifact["runs"]["uniform_random"]}
        for run in artifact["runs"]["mrmt"]:
            self.assertGreater(run["best_score"], random_scores[run["search_seed"]])

    def test_synthetic_artifact_is_replayable_and_tampering_fails_closed(self) -> None:
        replay = run_synthetic_mrmt_ablation(evaluation_budget=48, search_seeds=(11, 29, 47))
        self.assertEqual(replay, self.artifact)
        with tempfile.TemporaryDirectory() as directory:
            path = write_synthetic_mrmt_ablation(Path(directory) / "pst_mrmt_synthetic_ablation.json", replay)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), self.artifact)
        tampered = copy.deepcopy(replay)
        tampered["runs"]["mrmt"][0]["property_prediction_count"] = 1
        with self.assertRaises(PstConfigurationSearchError):
            validate_synthetic_ablation(tampered)
        tampered = copy.deepcopy(replay)
        tampered["aggregates"]["mrmt"]["mean_best_score"] = 1.0
        with self.assertRaisesRegex(PstConfigurationSearchError, "aggregates"):
            validate_synthetic_ablation(tampered)


if __name__ == "__main__":
    unittest.main()
