import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DshSyntheticReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.tool = self.root / "tools" / "verify_dsh_synthetic_replay.py"
        self.session = self.root / "fixtures" / "dsh_replay" / "synthetic_review_gated_workflow.session.jsonl"
        self.expected = self.root / "fixtures" / "dsh_replay" / "synthetic_review_gated_workflow.workspace.expected.json"

    def test_keyless_synthetic_session_replays_real_review_gates(self) -> None:
        result = subprocess.run([sys.executable, str(self.tool), "--session", str(self.session), "--expected", str(self.expected)], cwd=self.root, text=True, encoding="utf-8", capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["checks"]["artifact_count"], 2)
        self.assertNotIn("fixture-token", result.stdout)
        self.assertNotIn("Synthetic phase-stability workflow", result.stdout)

    def test_tampered_expected_workspace_fails_without_revealing_fixture_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            expected = json.loads(self.expected.read_text(encoding="utf-8"))
            expected["expected"]["candidate_count"] = 99
            path = Path(directory) / "tampered.expected.json"
            path.write_text(json.dumps(expected), encoding="utf-8")
            result = subprocess.run([sys.executable, str(self.tool), "--session", str(self.session), "--expected", str(path)], cwd=self.root, text=True, encoding="utf-8", capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 2)
        self.assertIn('"passed": false', result.stdout)
        self.assertNotIn("fixture-token", result.stdout)
        self.assertNotIn("Synthetic phase-stability workflow", result.stdout)


if __name__ == "__main__":
    unittest.main()
