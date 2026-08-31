import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.agent_benchmark import AgentBenchmarkError, evaluate_frozen_agent_benchmark
from cosmatter.cli import main
from cosmatter.config import AGENT_ROOT


class AgentBenchmarkTests(unittest.TestCase):
    def test_synthetic_fixture_exercises_retrieval_extraction_and_gap_boundaries(self) -> None:
        report = evaluate_frozen_agent_benchmark(AGENT_ROOT / "examples" / "frozen" / "bfo_agent_benchmark.json", "benchmark_test")
        self.assertEqual(report.retrieval_precision_at_k, 1.0)
        self.assertEqual(report.retrieval_ndcg_at_k, 1.0)
        self.assertEqual(report.extraction_locator_accuracy, 1.0)
        self.assertEqual(report.gap_evidence_boundary_precision, 1.0)
        self.assertEqual(report.fixture_sha256, hashlib.sha256((AGENT_ROOT / "examples" / "frozen" / "bfo_agent_benchmark.json").read_bytes()).hexdigest())

    def test_cli_writes_explicitly_synthetic_metric_record(self) -> None:
        fixture = AGENT_ROOT / "examples" / "frozen" / "bfo_agent_benchmark.json"
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory)
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                self.assertEqual(main(["evaluate-agent-benchmark", "--fixture", str(fixture), "--run-id", "benchmark_cli"]), 0)
            payload = json.loads((runs / "benchmark_cli" / "agent_benchmark.json").read_text(encoding="utf-8"))
            audit = (runs / "benchmark_cli" / "events.jsonl").read_text(encoding="utf-8")
        self.assertTrue(payload["synthetic"])
        self.assertEqual(payload["fixture_sha256"], hashlib.sha256(fixture.read_bytes()).hexdigest())
        self.assertIn("synthetic_agent_benchmark_evaluated", audit)
        self.assertNotIn("Synthetic material composition statement", audit)

    def test_rejects_a_non_synthetic_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps({"synthetic": False}), encoding="utf-8")
            with self.assertRaises(AgentBenchmarkError):
                evaluate_frozen_agent_benchmark(path, "benchmark_test")


if __name__ == "__main__":
    unittest.main()
