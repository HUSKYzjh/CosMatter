import copy
import unittest

from cosmatter.machine_config import machine_config_template
from cosmatter.potential_task_plugins import PotentialTaskPluginError, default_task_plugin_registry


class PotentialTaskPluginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.machine = machine_config_template()
        self.request = {
            "system_spec_id": "bfo_scope_v1",
            "system_spec_sha256": "a" * 64,
            "potential_model_ids": ["potential_a", "potential_b"],
            "reference_method": "approved external reference protocol",
            "condition_axes": {
                "strain_percent": [-2.0, 2.0],
                "temperature_k": [300.0, 900.0],
                "defect_fraction": [0.0, 0.125],
            },
            "literature_source_ids": ["source_map_001", "source_map_002"],
        }

    def test_plugins_return_only_proposed_literature_bound_cards(self) -> None:
        payload = default_task_plugin_registry().plan(machine=self.machine, request=self.request)
        self.assertEqual(payload["machine_execution_mode"], "plan_only")
        self.assertEqual(len(payload["proposed_test_cards"]), 5)
        self.assertEqual(payload["skipped_plugins"], [])
        for card in payload["proposed_test_cards"]:
            self.assertEqual(card["approval_state"], "proposed")
            self.assertFalse(card["execution_permitted"])
            self.assertEqual(card["literature_source_ids"], ["source_map_001", "source_map_002"])
            self.assertNotIn("command", card)

    def test_plugin_without_literature_axis_is_skipped(self) -> None:
        request = copy.deepcopy(self.request)
        del request["condition_axes"]["temperature_k"]
        payload = default_task_plugin_registry().plan(machine=self.machine, request=request)
        skipped = {item["plugin_id"]: item for item in payload["skipped_plugins"]}
        self.assertEqual(skipped["finite_temperature"]["reason"], "missing_literature_declared_axes")
        self.assertNotIn("finite_temperature", {item["plugin_id"] for item in payload["proposed_test_cards"]})

    def test_rejects_unmapped_literature_and_unknown_plugin(self) -> None:
        request = copy.deepcopy(self.request)
        request["literature_source_ids"] = []
        with self.assertRaises(PotentialTaskPluginError):
            default_task_plugin_registry().plan(machine=self.machine, request=request)
        with self.assertRaises(PotentialTaskPluginError):
            default_task_plugin_registry().plan(machine=self.machine, request=self.request, plugin_ids=("unknown",))


if __name__ == "__main__":
    unittest.main()
