from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cosmatter.local_api import LocalMissionApi


class PluginPolicyApiTests(unittest.TestCase):
    def test_catalogue_and_authorization_plan_are_nonexecuting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api = LocalMissionApi(Path(directory) / "runs")
            created = api.create_mission({"run_id": "policy_api", "question": "How does strain change phase stability?", "material": "BiFeO3", "property": "phase stability", "scope": "thin films"})
            catalogue = api.plugin_catalogue()
            self.assertEqual(catalogue["trust_status"], "static_catalogue_not_plugin_execution_or_evidence_acceptance")
            self.assertTrue(any(item["plugin_id"] == "graph.plan_assist" for item in catalogue["plugins"]))
            decision = api.plan_plugin_authorization("policy_api", {"plugin_id": "graph.plan_assist", "authorizations": ["mission_scoped_egress_consent"]})
            self.assertEqual(decision["mission_id"], created["mission_id"])
            self.assertFalse(decision["permitted"])
            self.assertIn("deepseek_request_consent", decision["missing_authorizations"])
            self.assertEqual(decision["trust_status"], "nonexecuting_authorization_plan_not_consent_or_execution")
            self.assertFalse((api.runs_dir / "policy_api" / "flight_plan.json").exists())


if __name__ == "__main__":
    unittest.main()
