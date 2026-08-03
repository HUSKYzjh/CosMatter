import json
import unittest
from pathlib import Path

from cosmatter.config import AGENT_ROOT
from cosmatter.ui_export import UI_SCHEMA_VERSION


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(_keys(item) for item in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(_keys(item) for item in value)) if value else set()
    return set()


class UiDemoFixtureTests(unittest.TestCase):
    def test_fixture_is_a_safe_and_renderable_ui_bundle(self) -> None:
        fixture_path = AGENT_ROOT / "examples" / "ui-demo" / "route_diagnostics.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

        self.assertEqual(fixture["schema_version"], UI_SCHEMA_VERSION)
        self.assertEqual(fixture["fleet_assignment"]["fleet_type"], "route_diagnostics")
        self.assertTrue(fixture["evidence_cards"][0]["is_synthetic"])
        self.assertEqual(fixture["evidence_cards"][0]["review_status"], "accepted")
        self.assertIn("document_id", fixture["evidence_cards"][0]["provenance"])
        self.assertIn("locator", fixture["evidence_cards"][0]["provenance"])
        forbidden = {"api_key", "token", "authorization", "password", "secret", "full_text", "audit_events"}
        self.assertFalse(_keys(fixture) & forbidden)

    def test_web_has_manual_bundle_import_without_network_fetch(self) -> None:
        web_dir = AGENT_ROOT / "web"
        html = (web_dir / "index.html").read_text(encoding="utf-8")
        script = (web_dir / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="ui-bundle-file"', html)
        self.assertIn("FileReader", script)
        self.assertNotIn("fetch(", script)


if __name__ == "__main__":
    unittest.main()
