import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DshHarnessRecipeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.tool = self.root / "tools" / "verify_dsh_harness_recipe.py"
        self.recipe = self.root / "configs" / "dsh_harness_recipe.json"

    def test_recipe_reports_versions_checks_and_boundaries_without_sensitive_fixture_data(self) -> None:
        result = subprocess.run([sys.executable, str(self.tool)], cwd=self.root, text=True, encoding="utf-8", capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertTrue(report["passed"])
        self.assertEqual([item["name"] for item in report["checks"]], ["release_matrix", "market_snapshot_review", "third_party_admission", "synthetic_replay"])
        self.assertEqual(report["environment"]["dsh"], "0.1.0-rc.7")
        self.assertNotIn("fixture-token", result.stdout)
        self.assertNotIn("Synthetic phase-stability workflow", result.stdout)

    def test_recipe_rejects_a_relative_path_escape_before_running_checks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            recipe = json.loads(self.recipe.read_text(encoding="utf-8"))
            recipe["fixture"] = "../.env"
            path = Path(directory) / "bad_recipe.json"
            path.write_text(json.dumps(recipe), encoding="utf-8")
            result = subprocess.run([sys.executable, str(self.tool), "--recipe", str(path)], cwd=self.root, text=True, encoding="utf-8", capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 2)
        self.assertIn('"passed": false', result.stdout)
        self.assertNotIn(".env", result.stdout)


if __name__ == "__main__":
    unittest.main()
