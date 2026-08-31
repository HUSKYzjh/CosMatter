import unittest
from dataclasses import replace

from cosmatter.facility_contracts import FacilityContractError, facility_contract, facility_contracts, validate_facility_contracts, validate_fleet_facility_contracts
from cosmatter.fleet_config import load_fleet_specs
from cosmatter.models import FacilityType, FleetType
from cosmatter.config import AGENT_ROOT


class FacilityContractTests(unittest.TestCase):
    def test_every_configurable_facility_has_a_closed_schema_allowlist_and_failure_path(self) -> None:
        contracts = facility_contracts()
        self.assertEqual({item.facility_type for item in contracts}, set(FacilityType))
        for contract in contracts:
            manifest = contract.manifest()
            self.assertEqual(manifest["schema_version"], "cosmatter.facility-contract/v1")
            self.assertTrue(manifest["input_schema"])
            self.assertTrue(manifest["output_schema"])
            self.assertTrue(manifest["allowed_descriptors"])
            self.assertTrue(manifest["failure_modes"])
            self.assertEqual(manifest["execution_boundary"], "static_contract_only_not_execution_authorization")

    def test_rejects_unknown_descriptor_and_wrong_fleet_attachment(self) -> None:
        contracts = list(facility_contracts())
        contracts[0] = replace(contracts[0], allowed_descriptors=("unknown.execute",))
        with self.assertRaises(FacilityContractError):
            validate_facility_contracts(contracts)
        specs = load_fleet_specs(AGENT_ROOT / "configs" / "fleets")
        contract = facility_contract(FacilityType.CONDITION_DIFFERENTIAL)
        self.assertEqual(contract.fleet_types, (FleetType.ROUTE_DIAGNOSTICS,))
        wrong = replace(specs[FleetType.ROUTE_DIAGNOSTICS], required_facilities=(FacilityType.SOURCE_LOCATOR,))
        with self.assertRaises(FacilityContractError):
            validate_fleet_facility_contracts((wrong,))

    def test_project_fleet_configuration_is_covered_by_matching_contracts(self) -> None:
        specs = load_fleet_specs(AGENT_ROOT / "configs" / "fleets")
        validate_fleet_facility_contracts(specs.values())


if __name__ == "__main__":
    unittest.main()
