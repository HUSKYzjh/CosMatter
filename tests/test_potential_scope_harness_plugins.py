from __future__ import annotations

import unittest

from cosmatter.potential_scope_harness_plugins import PotentialScopeHarness, PotentialScopeHarnessPluginError


class PotentialScopeHarnessPluginTests(unittest.TestCase):
    def test_static_manifests_describe_capabilities_without_executors(self) -> None:
        manifests = PotentialScopeHarness().manifests()
        self.assertEqual([item["plugin_id"] for item in manifests], sorted(item["plugin_id"] for item in manifests))
        self.assertEqual(len(manifests), 5)
        self.assertTrue(all("scheduler" in item["execution_boundary"] for item in manifests))

    def test_private_triage_prompt_is_denied_without_two_explicit_consents(self) -> None:
        host = PotentialScopeHarness()
        with self.assertRaises(PotentialScopeHarnessPluginError):
            host.invoke(plugin_id="potential_scope.private_triage_prompt", payload={"pool": {}}, authorizations=())

    def test_unknown_plugin_is_denied(self) -> None:
        with self.assertRaises(PotentialScopeHarnessPluginError):
            PotentialScopeHarness().invoke(plugin_id="not_a_plugin", payload={})


if __name__ == "__main__":
    unittest.main()
