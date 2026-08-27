import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main


class PotentialBenchmarkCliTests(unittest.TestCase):
    def test_plan_accepts_utf8_bom_controls_template(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            controls = root / "controls_bom.json"
            controls.write_text(json.dumps({"strain_percent": [-2.0, 2.0]}), encoding="utf-8-sig")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=root / "runs"), contextlib.redirect_stdout(output):
                status = main([
                    "create-potential-benchmark-plan", "--run-id", "potential_bom", "--system", "BiFeO3",
                    "--model", "baseline", "--model", "candidate", "--reference-method", "DFT protocol",
                    "--controls", str(controls), "--seed", "8",
                ])
        self.assertEqual(status, 0, output.getvalue())

    def test_plan_then_complete_imported_result_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            controls = root / "controls.json"
            controls.write_text(json.dumps({"strain_percent": [-2.0, 2.0]}), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=root / "runs"), contextlib.redirect_stdout(output):
                status = main([
                    "create-potential-benchmark-plan", "--run-id", "potential_cli", "--system", "BiFeO3",
                    "--model", "baseline", "--model", "candidate", "--reference-method", "DFT protocol",
                    "--controls", str(controls), "--seed", "8", "--samples-per-regime", "2",
                ])
                self.assertEqual(status, 0, output.getvalue())
                plan = json.loads((root / "runs" / "potential_cli" / "potential_benchmark_plan.json").read_text(encoding="utf-8"))
                rows = [
                    {"task_id": task["task_id"], "model_id": model, "atom_count": 20, "reference_energy_ev": -1.0,
                     "predicted_energy_ev": -0.99, "force_rmse_ev_per_a": 0.01, "wall_time_seconds": 2.0}
                    for task in plan["tasks"] for model in plan["potential_models"]
                ]
                result_path = root / "results.json"
                result_path.write_text(json.dumps(rows), encoding="utf-8")
                status = main(["evaluate-potential-benchmark", "--run-id", "potential_cli", "--input", str(result_path)])
                self.assertEqual(status, 0, output.getvalue())
                status = main(["propose-potential-followups", "--run-id", "potential_cli"])
            self.assertEqual(status, 0, output.getvalue())
            evaluation = json.loads((root / "runs" / "potential_cli" / "potential_benchmark_evaluation.json").read_text(encoding="utf-8"))
            followups = json.loads((root / "runs" / "potential_cli" / "potential_benchmark_followups.json").read_text(encoding="utf-8"))
        self.assertEqual(evaluation["seed"], 8)
        self.assertEqual(len(plan["tasks"]), 6)
        self.assertEqual(len(evaluation["model_summaries"]), 2)
        self.assertTrue(all(item["approval_required"] for item in followups["followup_tasks"]))


if __name__ == "__main__":
    unittest.main()
