import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

from cosmatter.audit import FlightRecorder
from cosmatter.models import MissionState
from cosmatter.config import AGENT_ROOT, Settings


class AuditAndConfigTests(unittest.TestCase):
    def test_config_status_never_contains_secret_value(self) -> None:
        secret = "do-not-print-this"
        settings = Settings.load(
            {
                "SCIVERSE_API_TOKEN": secret,
                "DEEPSEEK_API_KEY": "another-secret",
                "LLM_PROVIDER": "deepseek",
                "LLM_MODEL": "example",
            }
        )
        status = json.dumps(settings.status())
        self.assertTrue(settings.sciverse_configured)
        self.assertNotIn(secret, status)
        self.assertNotIn("another-secret", status)

    def test_default_config_does_not_read_parent_workspace_env(self) -> None:
        with patch("cosmatter.config._read_dotenv", return_value={}) as dotenv_reader:
            Settings.load({})
        self.assertEqual(dotenv_reader.call_args_list, [call(AGENT_ROOT / ".env")])

    def test_flight_recorder_redacts_sensitive_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            recorder = FlightRecorder(Path(directory), "run_test")
            recorder.record(
                event_type="config_checked",
                actor="system",
                state=MissionState.INTAKE,
                payload={"api_token": "must-not-appear", "nested": {"authorization": "hidden"}},
            )
            content = recorder.path.read_text(encoding="utf-8")
        self.assertIn("[REDACTED]", content)
        self.assertNotIn("must-not-appear", content)
        self.assertNotIn("hidden", content)
