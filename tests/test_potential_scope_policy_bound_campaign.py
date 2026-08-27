from __future__ import annotations

import unittest

from cosmatter.potential_scope_policy_bound_campaign import build_policy_bound_plan_only_campaign
from cosmatter.potential_scope_intake import build_system_spec, system_spec_sha256
from tests.test_potential_scope_campaign_runner import _fixture


def _policy(spec: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "trust_status": "human_frozen_planning_only_autonomy_policy",
        "system_spec_sha256": system_spec_sha256(build_system_spec(spec)),
        "allowed_actions": ["validate_local_artifacts", "derive_plugin_task_proposals", "rank_proposed_task_cards"],
        "forbidden_actions": ["external_api_call", "pdf_or_markdown_read", "structure_generation", "model_load", "potential_inference", "dft_submission", "md_submission", "mc_submission", "training", "scheduler_poll"],
        "budgets": {"dft_tasks": 0, "gpu_tasks": 0, "external_calls": 0},
        "approval": {"status": "human_frozen", "reviewer": "Synthetic Reviewer", "frozen_on": "2026-08-20"},
    }


class PotentialScopePolicyBoundCampaignTests(unittest.TestCase):
    def test_policy_binds_the_automatic_chain_without_enabling_execution(self) -> None:
        inputs = _fixture()
        package = build_policy_bound_plan_only_campaign(**inputs, autonomy_policy=_policy(inputs["system_spec"]))
        self.assertFalse(package["execution_permitted"])
        self.assertEqual(package["campaign"]["campaign_state"], "planned")
        self.assertTrue(all(row["permitted"] for row in package["policy_decisions"]))


if __name__ == "__main__":
    unittest.main()
