import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.models import MissionBrief
from cosmatter.stage_contract import StageContractError, stage_contract, validate_stage_contract


class StageContractTests(unittest.TestCase):
    def test_empty_run_has_fixed_requirements_and_no_research_content(self) -> None:
        mission = MissionBrief(
            "private question that must not be projected", "BiFeO3", "phase stability", "private scope",
            mission_id="mission_contract",
        )
        with tempfile.TemporaryDirectory() as directory:
            contract = stage_contract(Path(directory), mission)

        self.assertEqual(contract["schema_version"], "cosmatter.stage-contract/v1")
        self.assertEqual(contract["next_stage"], "plan")
        self.assertIn(contract["runtime_safety"], {"verified", "attention_required"})
        self.assertEqual([item["stage"] for item in contract["stages"]], ["intake", "plan", "retrieval", "screening", "parse", "extraction", "gap", "report", "evaluation"])
        self.assertEqual(contract["stages"][1]["completion_requirements"], ["approved_flight_plan"])
        self.assertEqual(contract["stages"][3]["human_gate"], "candidate_screening")
        rendered = json.dumps(contract)
        self.assertNotIn("private question", rendered)
        self.assertNotIn("BiFeO3", rendered)
        self.assertNotIn("private scope", rendered)

    def test_schema_rejects_mutable_recovery_and_unknown_fields(self) -> None:
        mission = MissionBrief("private", "BiFeO3", "phase", "scope", mission_id="mission_contract")
        with tempfile.TemporaryDirectory() as directory:
            contract = stage_contract(Path(directory), mission)
        contract["stages"][0]["recovery_route"] = "execute_arbitrary_command"
        with self.assertRaises(StageContractError):
            validate_stage_contract(contract, expected_mission_id=mission.mission_id)
        with tempfile.TemporaryDirectory() as directory:
            contract = stage_contract(Path(directory), mission)
            contract["source_url"] = "https://example.invalid"
            with self.assertRaises(StageContractError):
                validate_stage_contract(contract, expected_mission_id=mission.mission_id)


if __name__ == "__main__":
    unittest.main()
