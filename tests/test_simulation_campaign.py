import copy
import unittest

from cosmatter.models import MissionBrief
from cosmatter.simulation_campaign import (
    SIMULATION_CAMPAIGN_BOUNDARY,
    SIMULATION_CAMPAIGN_SCHEMA_VERSION,
    SIMULATION_CAMPAIGN_TRUST_STATUS,
    SimulationCampaignError,
    build_approved_simulation_campaign,
    simulation_campaign_ui_projection,
)


class SimulationCampaignTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mission = MissionBrief(
            mission_id="mission_campaign_001",
            question="Can an evidence-bound DFT plan test a bounded phase-stability hypothesis?",
            material="BiFeO3",
            property_name="phase stability",
            scope="epitaxial thin films",
        )
        self.payload = {
            "schema_version": SIMULATION_CAMPAIGN_SCHEMA_VERSION,
            "trust_status": SIMULATION_CAMPAIGN_TRUST_STATUS,
            "campaign_id": "campaign_bfo_dft_001",
            "mission_id": self.mission.mission_id,
            "simulation_kind": "dft",
            "evidence_ids": ["evidence_accepted"],
            "hypothesis": {
                "statement": "A bounded strain contrast changes the relative phase energy.",
                "variables": "epitaxial strain within the reviewed boundary",
                "control": "same composition and bounded defect assumptions",
                "observable": "aggregate relative energy ordering",
                "falsifier": "the ordering remains unchanged across the reviewed contrast",
            },
            "protocol": {
                "engine": "externally operated DFT engine",
                "recipe_id": "reviewed_recipe_001",
                "method_boundary": "reviewed functional and structural boundary",
                "convergence_or_sampling_boundary": "reviewed convergence settings",
                "result_summary_boundary": "external aggregate rows only; no raw structures or logs",
            },
            "input_manifest": {
                "input_count": 1,
                "inputs": [{
                    "input_id": "input_manifest_001",
                    "sha256": "a" * 64,
                    "source_kind": "human-reviewed input manifest",
                    "license_status": "reviewed license clearance",
                }],
            },
            "execution_profile": {
                "mode": "disabled", "adapter_kind": "none", "allowed_engines": [], "allowed_recipe_ids": [],
                "max_jobs": 0, "max_gpu_jobs": 0, "max_dft_jobs": 0,
                "scheduler_submission_enabled": False, "polling_enabled": False,
            },
            "approval": {
                "status": "approved_plan_only", "reviewer": "human reviewer",
                "approved_on": "2026-09-02", "rationale": "accepted evidence defines a bounded planning question",
            },
            "execution_permitted": False,
            "execution_boundary": SIMULATION_CAMPAIGN_BOUNDARY,
        }

    def test_accepts_only_the_fixed_disabled_profile_and_projects_no_identifiers(self) -> None:
        campaign = build_approved_simulation_campaign(
            mission=self.mission, accepted_evidence_ids={"evidence_accepted"}, payload=self.payload
        )
        projection = simulation_campaign_ui_projection(campaign, self.mission.mission_id)
        self.assertEqual(projection, {
            "delivery_status": "approved_plan_only", "simulation_kind": "dft", "evidence_count": 1,
            "input_count": 1, "execution_permitted": False, "execution_state": "not_started",
        })
        self.assertNotIn("evidence_ids", projection)
        self.assertNotIn("reviewer", projection)
        self.assertNotIn("sha256", projection)

    def test_rejects_every_attempt_to_enable_or_schedule_execution(self) -> None:
        for mutate in (
            lambda payload: payload.__setitem__("execution_permitted", True),
            lambda payload: payload["execution_profile"].__setitem__("max_jobs", 1),
            lambda payload: payload["execution_profile"].__setitem__("scheduler_submission_enabled", True),
            lambda payload: payload["execution_profile"].__setitem__("allowed_engines", ["external-engine"]),
        ):
            with self.subTest(mutate=mutate):
                candidate = copy.deepcopy(self.payload)
                mutate(candidate)
                with self.assertRaises(SimulationCampaignError):
                    build_approved_simulation_campaign(
                        mission=self.mission, accepted_evidence_ids={"evidence_accepted"}, payload=candidate
                    )

    def test_rejects_unaccepted_evidence_and_private_paths(self) -> None:
        unaccepted = copy.deepcopy(self.payload)
        unaccepted["evidence_ids"] = ["evidence_unreviewed"]
        with self.assertRaises(SimulationCampaignError):
            build_approved_simulation_campaign(mission=self.mission, accepted_evidence_ids={"evidence_accepted"}, payload=unaccepted)
        unsafe = copy.deepcopy(self.payload)
        unsafe["protocol"]["engine"] = "C:\\Users\\Agent\\private-engine"
        with self.assertRaises(SimulationCampaignError):
            build_approved_simulation_campaign(mission=self.mission, accepted_evidence_ids={"evidence_accepted"}, payload=unsafe)


if __name__ == "__main__":
    unittest.main()
