import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main


def _reviewed_plan() -> dict[str, object]:
    return {
        "composition_requested": "0.5",
        "potential_id": "private-reviewed-potential-label",
        "potential_hash": "a" * 64,
        "objective_spec": {
            "mode": "pareto",
            "components": ["dielectric_response", "piezoelectric_response"],
            "conditions_hash": "b" * 64,
            "uncertainty_method": "independent-seed confidence intervals",
        },
        "md_protocol_id": "private-reviewed-protocol-label",
        "md_protocol_hash": "c" * 64,
        "chain_count": 4,
        "random_baseline_count": 48,
        "short_md_steps": 20000,
        "short_md_repeats": 3,
        "promotion_rule": "use only preregistered executed-result uncertainty",
        "long_md_steps": 100000,
        "long_md_independent_seeds": [11, 29, 47],
        "max_evaluations": 192,
        "aggregate_md_step_budget": 12000000,
        "max_wallclock_hours": 24,
        "max_accelerator_hours": 48,
        "failure_policy": "retain failed receipts without property imputation",
        "stopping_rule": "stop at the first frozen resource bound",
    }


class PstConfigurationSearchCliTests(unittest.TestCase):
    def test_plan_and_synthetic_ablation_are_replayable_without_md_or_property_prediction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "reviewed_plan.json"
            input_path.write_text(json.dumps(_reviewed_plan()), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=root / "runs"), contextlib.redirect_stdout(output):
                self.assertEqual(main([
                    "create-pst-configuration-search-plan", "--run-id", "pst_cli", "--input", str(input_path),
                ]), 0, output.getvalue())
                self.assertEqual(main([
                    "run-pst-synthetic-ablation", "--run-id", "pst_cli", "--evaluation-budget", "48",
                    "--search-seed", "11", "--search-seed", "29", "--search-seed", "47",
                ]), 0, output.getvalue())
            run_dir = root / "runs" / "pst_cli"
            plan = json.loads((run_dir / "pst_configuration_search_plan.json").read_text(encoding="utf-8"))
            ablation = json.loads((run_dir / "pst_mrmt_synthetic_ablation.json").read_text(encoding="utf-8"))
            events = (run_dir / "events.jsonl").read_text(encoding="utf-8")

        self.assertFalse(plan["execution_authorized"])
        self.assertEqual(plan["property_prediction_count"], 0)
        self.assertEqual(ablation["property_prediction_count"], 0)
        self.assertTrue(ablation["mrmt_outperforms_uniform_random_every_seed"])
        self.assertNotIn("private-reviewed-potential-label", output.getvalue())
        self.assertNotIn("private-reviewed-potential-label", events)

    def test_synthetic_ablation_requires_three_unique_seeds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "reviewed_plan.json"
            input_path.write_text(json.dumps(_reviewed_plan()), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=root / "runs"), contextlib.redirect_stdout(output):
                self.assertEqual(main([
                    "create-pst-configuration-search-plan", "--run-id", "pst_bad_seed", "--input", str(input_path),
                ]), 0)
                status = main([
                    "run-pst-synthetic-ablation", "--run-id", "pst_bad_seed",
                    "--search-seed", "7", "--search-seed", "7", "--search-seed", "9",
                ])
        self.assertEqual(status, 2)
        self.assertIn("three unique", output.getvalue())


if __name__ == "__main__":
    unittest.main()
