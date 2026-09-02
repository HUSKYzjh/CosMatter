import copy
import unittest

from cosmatter.aiida_mock_trial import AiidaMockTrialError, advance_mock_process, approve_aiida_mock_trial, inject_mock_failure_for_test, new_mock_process
from cosmatter.models import MissionBrief
from cosmatter.simulation_campaign import SIMULATION_CAMPAIGN_BOUNDARY, SIMULATION_CAMPAIGN_TRUST_STATUS, build_approved_simulation_campaign
from cosmatter.simulation_contracts import canonical_sha256


class AiidaMockTrialTests(unittest.TestCase):
    def setUp(self) -> None:
        mission = MissionBrief("mission_aiida_mock", "Can a mock trial preserve provenance?", "BiFeO3", "phase stability", "thin film")
        self.campaign = build_approved_simulation_campaign(mission=mission, accepted_evidence_ids={"evidence_accepted"}, payload={
            "schema_version": "1.0", "trust_status": SIMULATION_CAMPAIGN_TRUST_STATUS, "campaign_id": "campaign_aiida_mock", "mission_id": mission.mission_id, "simulation_kind": "dft", "evidence_ids": ["evidence_accepted"],
            "hypothesis": {"statement": "bounded contrast", "variables": "strain", "control": "composition", "observable": "energy", "falsifier": "no contrast"}, "protocol": {"engine": "external reviewed engine", "recipe_id": "recipe_001", "method_boundary": "bounded method", "convergence_or_sampling_boundary": "reviewed convergence", "result_summary_boundary": "aggregate values only"},
            "input_manifest": {"input_count": 1, "inputs": [{"input_id": "input_001", "sha256": "a" * 64, "source_kind": "reviewed input", "license_status": "reviewed license clearance"}]}, "execution_profile": {"mode": "disabled", "adapter_kind": "none", "allowed_engines": [], "allowed_recipe_ids": [], "max_jobs": 0, "max_gpu_jobs": 0, "max_dft_jobs": 0, "scheduler_submission_enabled": False, "polling_enabled": False},
            "approval": {"status": "approved_plan_only", "reviewer": "reviewer", "approved_on": "2026-09-02", "rationale": "bounded question"}, "execution_permitted": False, "execution_boundary": SIMULATION_CAMPAIGN_BOUNDARY,
        })
        self.mission_id = mission.mission_id
        self.trial = {"schema_version": "1.0", "trust_status": "human_approved_aiida_mock_trial_not_real_execution", "artifact_id": "mock_trial_001", "campaign_sha256": canonical_sha256(self.campaign), "adapter_kind": "aiida_mock", "recipe_id": "mock_relax_static_v1", "public_structure_ref": "public_fixture:perovskite_001", "max_jobs": 1, "max_retries": 1, "approval": {"status": "approved_mock_only", "reviewer": "reviewer", "approved_on": "2026-09-02", "rationale": "local fixture only"}}

    def test_mock_state_machine_covers_submit_poll_cancel_retry_and_resume(self) -> None:
        trial = approve_aiida_mock_trial(campaign=self.campaign, mission_id=self.mission_id, payload=self.trial)
        state = new_mock_process(trial)
        state = advance_mock_process(trial=trial, state=state, action="submit")
        state = advance_mock_process(trial=trial, state=state, action="poll")
        self.assertEqual(advance_mock_process(trial=trial, state=state, action="resume"), state)
        failed = inject_mock_failure_for_test(trial=trial, state=state)
        retried = advance_mock_process(trial=trial, state=failed, action="retry")
        finished = advance_mock_process(trial=trial, state=advance_mock_process(trial=trial, state=retried, action="poll"), action="poll")
        self.assertEqual(finished["status"], "finished")
        cancelled = advance_mock_process(trial=trial, state=advance_mock_process(trial=trial, state=new_mock_process(trial), action="submit"), action="cancel")
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertIn("no AiiDA daemon", finished["provenance_boundary"])

    def test_rejects_private_or_real_execution_authorization(self) -> None:
        private = copy.deepcopy(self.trial)
        private["public_structure_ref"] = "C:\\Users\\Agent\\secret"
        with self.assertRaises(AiidaMockTrialError):
            approve_aiida_mock_trial(campaign=self.campaign, mission_id=self.mission_id, payload=private)
        over_budget = copy.deepcopy(self.trial)
        over_budget["max_jobs"] = 2
        with self.assertRaises(AiidaMockTrialError):
            approve_aiida_mock_trial(campaign=self.campaign, mission_id=self.mission_id, payload=over_budget)


if __name__ == "__main__":
    unittest.main()
