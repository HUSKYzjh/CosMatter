from __future__ import annotations

import unittest

from cosmatter.potential_scope_autonomy_policy import PotentialScopeAutonomyPolicyError, authorize_plan_only_action, build_plan_only_autonomy_policy
from cosmatter.potential_scope_intake import build_system_spec, system_spec_sha256


def _system_spec() -> dict[str, object]:
    source_id = "ps_src_0123456789abcdef"
    return {"schema_version": "1.0", "trust_status": "human_frozen_literature_bound_system_spec", "system_spec_id": "synthetic_scope", "material_systems": ["SyntheticMaterial"], "scope_description": "Synthetic planning scope.", "target_observables": ["relative_phase_energy"], "condition_axes": [{"axis_id": "strain_percent", "unit": "percent", "lower_bound": -1.0, "upper_bound": 1.0, "source_ids": [source_id]}], "potential_model_ids": ["model_a", "model_b"], "reference_method": "synthetic_reference", "pre_registered_metrics": ["energy_mae_ev_per_atom"], "literature_source_ids": [source_id], "approval": {"status": "human_frozen", "reviewer": "Synthetic Reviewer", "frozen_on": "2026-08-20"}, "execution_boundary": "Planning only."}


def _policy(spec: dict[str, object]) -> dict[str, object]:
    return {"schema_version": "1.0", "trust_status": "human_frozen_planning_only_autonomy_policy", "system_spec_sha256": system_spec_sha256(build_system_spec(spec)), "allowed_actions": ["validate_local_artifacts", "derive_plugin_task_proposals", "rank_proposed_task_cards"], "forbidden_actions": ["external_api_call", "pdf_or_markdown_read", "structure_generation", "model_load", "potential_inference", "dft_submission", "md_submission", "mc_submission", "training", "scheduler_poll"], "budgets": {"dft_tasks": 0, "gpu_tasks": 0, "external_calls": 0}, "approval": {"status": "human_frozen", "reviewer": "Synthetic Reviewer", "frozen_on": "2026-08-20"}}


class PotentialScopeAutonomyPolicyTests(unittest.TestCase):
    def test_only_declared_local_planning_actions_are_permitted(self) -> None:
        spec = _system_spec(); policy = _policy(spec)
        self.assertTrue(authorize_plan_only_action(policy=policy, system_spec=spec, action="derive_plugin_task_proposals")["permitted"])
        denied = authorize_plan_only_action(policy=policy, system_spec=spec, action="dft_submission")
        self.assertFalse(denied["permitted"])
        self.assertFalse(denied["execution_permitted"])

    def test_policy_with_nonzero_external_or_compute_budget_is_rejected(self) -> None:
        spec = _system_spec(); policy = _policy(spec); policy["budgets"]["external_calls"] = 1
        with self.assertRaises(PotentialScopeAutonomyPolicyError):
            build_plan_only_autonomy_policy(system_spec=spec, payload=policy)


if __name__ == "__main__":
    unittest.main()
