from __future__ import annotations

import unittest

from cosmatter.fleet_registry import (
    FleetReadiness,
    all_channels_are_flagship_mediated,
    bridge_allowed_outputs,
    fleet_by_id,
    fleet_registry,
    museum_catalog,
)


class FleetRegistryTests(unittest.TestCase):
    def test_registry_has_ten_specialised_fleets_and_flagship_mediation(self) -> None:
        fleets = fleet_registry()
        self.assertGreaterEqual(len(fleets), 8)
        self.assertEqual(len({fleet.fleet_id for fleet in fleets}), len(fleets))
        self.assertTrue(all_channels_are_flagship_mediated(fleets))
        self.assertTrue(all(fleet.channels for fleet in fleets))

    def test_future_computation_fleets_are_explicitly_framework_only(self) -> None:
        for fleet_id in ("dft", "potential", "dynamics"):
            fleet = fleet_by_id(fleet_id)
            self.assertEqual(fleet.readiness, FleetReadiness.FRAMEWORK_ONLY)
            self.assertTrue(all(tool.readiness is FleetReadiness.FRAMEWORK_ONLY for ship in fleet.ships for tool in ship.tools))

    def test_museum_catalogue_and_bridge_outputs_are_traceable(self) -> None:
        museum = museum_catalog()
        self.assertEqual(len(museum["fleets"]), 10)
        self.assertGreaterEqual(len(museum["ships"]), 30)
        self.assertGreaterEqual(len(museum["tools"]), 40)
        self.assertIn("corpus_manifest", bridge_allowed_outputs("pioneer"))
        self.assertIn("training_plan", bridge_allowed_outputs("potential"))


if __name__ == "__main__":
    unittest.main()
