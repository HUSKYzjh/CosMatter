from __future__ import annotations

import unittest

from cosmatter.potential_scope_campaign_runner import build_plan_only_campaign
from cosmatter.potential_scope_result_analysis import (
    build_applicability_map,
    build_applicability_policy,
    build_external_result_import_receipt,
    draft_boundary_claim_candidates,
    import_aggregate_result_rows,
)
from tests.test_potential_scope_campaign_runner import _fixture


class PotentialScopeResultAnalysisTests(unittest.TestCase):
    def _campaign(self):
        return build_plan_only_campaign(**_fixture())

    def _receipt(self, campaign):
        cards = campaign["frozen_plan"]["proposal"]["proposed_test_cards"]
        return build_external_result_import_receipt(
            campaign=campaign,
            payload={"schema_version": "1.0", "trust_status": "human_approved_external_result_import_receipt_not_execution_record", "campaign_sha256": __import__("cosmatter.potential_scope_campaign_runner", fromlist=["campaign_sha256"]).campaign_sha256(campaign), "approved_test_ids": [card["test_id"] for card in cards], "potential_model_ids": ["model_a", "model_b"], "approval": {"status": "approved_for_external_result_import", "reviewer": "Synthetic Reviewer", "approved_on": "2026-08-20", "external_runner": "Synthetic external runner"}, "result_boundary": "Aggregate numeric rows only; no private files."},
        )

    def test_only_complete_approved_numeric_matrix_can_enter_applicability_map(self) -> None:
        campaign = self._campaign(); receipt = self._receipt(campaign)
        rows = []
        for index, test_id in enumerate(receipt["approved_test_ids"], start=1):
            for model_id, prediction in (("model_a", -10.0), ("model_b", -9.6)):
                rows.append({"test_id": test_id, "model_id": model_id, "atom_count": 10, "reference_energy_ev": -10.0, "predicted_energy_ev": prediction, "force_rmse_ev_per_a": 0.1 if model_id == "model_a" else 0.5, "wall_time_seconds": float(index)})
        imported = import_aggregate_result_rows(campaign=campaign, receipt=receipt, rows=rows)
        policy = build_applicability_policy(imported_results=imported, payload={"schema_version": "1.0", "trust_status": "human_frozen_condition_limited_applicability_policy", "imported_results_sha256": __import__("hashlib").sha256(__import__("json").dumps(imported, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(), "max_energy_error_ev_per_atom": 0.02, "max_force_rmse_ev_per_a": 0.2, "failure_multiplier": 2.0, "approval": {"status": "human_frozen", "reviewer": "Synthetic Reviewer", "approved_on": "2026-08-20", "external_runner": "Synthetic external runner"}})
        app_map = build_applicability_map(campaign=campaign, imported_results=imported, applicability_policy=policy)
        self.assertIn("observed_failure", {cell["state"] for cell in app_map["cells"]})
        candidates = draft_boundary_claim_candidates(applicability_map=app_map)
        self.assertTrue(candidates["candidates"])
        self.assertTrue(all(item["human_review"] == "required" for item in candidates["candidates"]))

    def test_partial_matrix_is_rejected(self) -> None:
        campaign = self._campaign(); receipt = self._receipt(campaign)
        with self.assertRaisesRegex(ValueError, "cover every"):
            import_aggregate_result_rows(campaign=campaign, receipt=receipt, rows=[])


if __name__ == "__main__":
    unittest.main()
