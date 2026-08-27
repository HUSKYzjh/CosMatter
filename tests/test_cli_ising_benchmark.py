import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main


class IsingBenchmarkCliTests(unittest.TestCase):
    def test_creates_runs_and_refines_bounded_classical_mc_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=root / "runs"), contextlib.redirect_stdout(output):
                self.assertEqual(main([
                    "create-ising-benchmark-plan", "--run-id", "ising_cli", "--lattice-size", "8",
                    "--temperature", "2.0", "--temperature", "2.269", "--burn-in-sweeps", "4",
                    "--measurement-sweeps", "24", "--seed", "7",
                ]), 0, output.getvalue())
                self.assertEqual(main(["run-ising-benchmark", "--run-id", "ising_cli"]), 0, output.getvalue())
                self.assertEqual(main(["propose-ising-followups", "--run-id", "ising_cli"]), 0, output.getvalue())
                self.assertEqual(main(["export-ising-benchmark-summary", "--run-id", "ising_cli"]), 0, output.getvalue())
            run = root / "runs" / "ising_cli"
            result = json.loads((run / "ising_benchmark_result.json").read_text(encoding="utf-8"))
            followups = json.loads((run / "ising_benchmark_followups.json").read_text(encoding="utf-8"))
            summary = json.loads((run / "ising_benchmark_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(len(result["algorithm_metrics"]), 6)
        self.assertTrue(followups["proposed_refinement"]["approval_required"])
        self.assertNotIn("replicate_metrics", summary)


if __name__ == "__main__":
    unittest.main()
