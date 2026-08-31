import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cosmatter.plugin_hygiene import audit_plugin_candidate, validate_plugin_hygiene_report


class PluginHygieneTests(unittest.TestCase):
    def _candidate(self, root: Path, source: str, scripts: dict[str, str] | None = None) -> Path:
        candidate = root / "candidate"; candidate.mkdir()
        (candidate / "package.json").write_text(json.dumps({"name": "synthetic-candidate", "version": "1.0.0", "scripts": scripts or {}}), encoding="utf-8")
        (candidate / "index.js").write_text(source, encoding="utf-8")
        return candidate

    def test_benign_candidate_is_manual_review_only_and_does_not_reveal_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = self._candidate(Path(directory), "export const plugin = 'synthetic';")
            report = audit_plugin_candidate(candidate)
        validate_plugin_hygiene_report(report)
        self.assertEqual(report["admission_recommendation"], "manual_review_required")
        self.assertEqual(report["finding_counts"], {"high": 0, "medium": 0})
        self.assertNotIn("synthetic';", json.dumps(report))

    def test_lifecycle_dynamic_execution_and_credential_signal_block_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = self._candidate(Path(directory), "eval(process.env.API_TOKEN)", {"postinstall": "node setup.js"})
            report = audit_plugin_candidate(candidate)
        self.assertEqual(report["admission_recommendation"], "blocked_high_risk")
        self.assertGreaterEqual(report["finding_counts"]["high"], 2)
        self.assertNotIn("API_TOKEN", json.dumps(report))

    def test_cli_never_echoes_candidate_path_or_source(self) -> None:
        root = Path(__file__).resolve().parents[1]
        tool = root / "tools" / "audit_dsh_plugin_candidate.py"
        with tempfile.TemporaryDirectory() as directory:
            candidate = self._candidate(Path(directory), "eval('secret-source')")
            result = subprocess.run([sys.executable, str(tool), "--candidate-dir", str(candidate)], cwd=root, text=True, encoding="utf-8", capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertIn('"admission_recommendation": "blocked_high_risk"', result.stdout)
        self.assertNotIn(str(candidate), result.stdout)
        self.assertNotIn("secret-source", result.stdout)


if __name__ == "__main__":
    unittest.main()
