import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.models import MissionBrief
from cosmatter.sensitive_artifact_audit import audit_sensitive_artifacts, load_sensitive_artifact_audit, write_sensitive_artifact_audit


class SensitiveArtifactAuditTests(unittest.TestCase):
    def test_clean_run_writes_only_a_count_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / "candidate.json").write_text(json.dumps({"title": "Safe title"}), encoding="utf-8")
            artifact = audit_sensitive_artifacts(run, "mission_safe")
            path = write_sensitive_artifact_audit(run, artifact)
            loaded = load_sensitive_artifact_audit(path, "mission_safe")

        self.assertTrue(artifact["is_clean"])
        self.assertEqual(artifact["findings"], [])
        self.assertTrue(path.name == "sensitive_artifact_audit.json")
        self.assertEqual(loaded, artifact)

    def test_forbidden_values_are_counted_without_being_retained(self) -> None:
        url = "https://example.invalid/private-paper.pdf"
        token = "gho_abcdefghijklmnop"
        private_path = r"D:\CosMatter\case-data\runtime\private\paper.md"
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / "unsafe.txt").write_text(f"{url}\n{token}\n{private_path}\n", encoding="utf-8")
            artifact = audit_sensitive_artifacts(run, "mission_unsafe")

        serialized = json.dumps(artifact)
        self.assertFalse(artifact["is_clean"])
        self.assertNotIn(url, serialized)
        self.assertNotIn(token, serialized)
        self.assertNotIn(private_path, serialized)
        self.assertEqual({item["category"] for item in artifact["findings"]}, {"complete_url", "credential_token", "private_absolute_path"})

    def test_cli_persists_a_safe_summary_without_match_values(self) -> None:
        url = "https://example.invalid/private-paper.pdf"
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory)
            run = runs / "audit_cli"
            run.mkdir()
            mission = MissionBrief("question", "BiFeO3", "phase stability", "films", mission_id="mission_audit_cli")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run / "unsafe.txt").write_text(url, encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status = main(["audit-sensitive-artifacts", "--run-id", "audit_cli"])
            result = json.loads(output.getvalue())
            persisted = (run / "sensitive_artifact_audit.json").read_text(encoding="utf-8")

        self.assertEqual(status, 0)
        self.assertFalse(result["is_clean"])
        self.assertNotIn(url, output.getvalue())
        self.assertNotIn(url, persisted)


if __name__ == "__main__":
    unittest.main()
