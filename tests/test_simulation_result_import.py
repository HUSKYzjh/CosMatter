import copy
import unittest

from cosmatter.models import MissionBrief
from cosmatter.simulation_campaign import SIMULATION_CAMPAIGN_BOUNDARY, SIMULATION_CAMPAIGN_TRUST_STATUS, build_approved_simulation_campaign
from cosmatter.simulation_contracts import canonical_sha256
from cosmatter.simulation_result_import import SimulationResultImportError, import_external_run_receipt, review_external_run_receipt, simulation_evidence_ui_projection


class SimulationResultImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mission = MissionBrief("mission_result_001", "Can a bounded result be reviewed?", "BiFeO3", "phase stability", "thin film")
        self.campaign = build_approved_simulation_campaign(mission=self.mission, accepted_evidence_ids={"evidence_accepted"}, payload={
            "schema_version": "1.0", "trust_status": SIMULATION_CAMPAIGN_TRUST_STATUS, "campaign_id": "campaign_result_001", "mission_id": self.mission.mission_id, "simulation_kind": "dft", "evidence_ids": ["evidence_accepted"],
            "hypothesis": {"statement": "bounded contrast", "variables": "strain", "control": "composition", "observable": "energy", "falsifier": "no contrast"},
            "protocol": {"engine": "external reviewed engine", "recipe_id": "recipe_001", "method_boundary": "bounded method", "convergence_or_sampling_boundary": "reviewed convergence", "result_summary_boundary": "aggregate values only"},
            "input_manifest": {"input_count": 1, "inputs": [{"input_id": "input_001", "sha256": "a" * 64, "source_kind": "reviewed input", "license_status": "reviewed license clearance"}]},
            "execution_profile": {"mode": "disabled", "adapter_kind": "none", "allowed_engines": [], "allowed_recipe_ids": [], "max_jobs": 0, "max_gpu_jobs": 0, "max_dft_jobs": 0, "scheduler_submission_enabled": False, "polling_enabled": False},
            "approval": {"status": "approved_plan_only", "reviewer": "reviewer", "approved_on": "2026-09-02", "rationale": "bounded question"}, "execution_permitted": False, "execution_boundary": SIMULATION_CAMPAIGN_BOUNDARY,
        })
        self.receipt = {
            "schema_version": "1.1", "artifact_id": "receipt_result_001", "campaign_id": self.campaign["campaign_id"],
            "input_manifest_sha256": self.campaign["contract_hashes"]["input_manifest_sha256"], "protocol_sha256": self.campaign["contract_hashes"]["protocol_sha256"], "external_run_id": "external_result_001", "status": "succeeded", "output_summary_sha256": "b" * 64, "exit_class": "completed", "resource_summary": {"cpu_seconds": 12, "gpu_seconds": 0, "job_count": 1}, "convergence_status": "converged", "result_kind": "energy_force_summary", "metrics": {"sample_count": 4, "energy_mae_ev_per_atom": 0.01, "force_rmse_ev_per_a": 0.02}, "external_execution_assertion": "external_result_imported_read_only_not_cosmatter_execution",
        }

    def test_import_and_human_review_produce_a_safe_pending_evidencecard_projection(self) -> None:
        accepted = import_external_run_receipt(campaign=self.campaign, mission_id=self.mission.mission_id, payload=self.receipt)
        review = {"schema_version": "1.1", "artifact_id": "review_result_001", "campaign_id": self.campaign["campaign_id"], "receipt_sha256": canonical_sha256(accepted), "review_status": "human_reviewed_pending_evidencecard_gate", "relation_to_hypothesis": "supports", "applicability_boundary": "only reviewed thin-film strain range", "uncertainty": "finite sampling and method boundary remain", "reviewer": "human reviewer", "reviewed_on": "2026-09-02", "evidencecard_gate": "not_submitted"}
        reviewed = review_external_run_receipt(campaign=self.campaign, mission_id=self.mission.mission_id, receipt=accepted, payload=review)
        projection = simulation_evidence_ui_projection(campaign=self.campaign, mission_id=self.mission.mission_id, receipt=accepted, review=reviewed)
        self.assertEqual(projection["delivery_status"], "human_reviewed_pending_evidencecard_gate")
        self.assertEqual(projection["result_kind"], "energy_force_summary")
        self.assertNotIn("external_result_001", str(projection))
        self.assertNotIn("0.01", str(projection))

    def test_rejects_wrong_protocol_raw_path_and_automatic_evidencecard_promotion(self) -> None:
        wrong_protocol = copy.deepcopy(self.receipt)
        wrong_protocol["protocol_sha256"] = "c" * 64
        with self.assertRaises(SimulationResultImportError):
            import_external_run_receipt(campaign=self.campaign, mission_id=self.mission.mission_id, payload=wrong_protocol)
        unsafe = copy.deepcopy(self.receipt)
        unsafe["metrics"] = {"sample_count": 4, "energy_mae_ev_per_atom": 0.01, "force_rmse_ev_per_a": "C:\\Users\\Agent\\raw"}
        with self.assertRaises(SimulationResultImportError):
            import_external_run_receipt(campaign=self.campaign, mission_id=self.mission.mission_id, payload=unsafe)
        accepted = import_external_run_receipt(campaign=self.campaign, mission_id=self.mission.mission_id, payload=self.receipt)
        review = {"schema_version": "1.1", "artifact_id": "review_result_001", "campaign_id": self.campaign["campaign_id"], "receipt_sha256": canonical_sha256(accepted), "review_status": "human_reviewed_pending_evidencecard_gate", "relation_to_hypothesis": "supports", "applicability_boundary": "bounded", "uncertainty": "uncertain", "reviewer": "reviewer", "reviewed_on": "2026-09-02", "evidencecard_gate": "submitted"}
        with self.assertRaises(SimulationResultImportError):
            review_external_run_receipt(campaign=self.campaign, mission_id=self.mission.mission_id, receipt=accepted, payload=review)


if __name__ == "__main__":
    unittest.main()
