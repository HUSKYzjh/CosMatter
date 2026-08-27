"""Bind a plan-only PotentialScope campaign to a validated autonomy policy."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .potential_scope_autonomy_policy import (
    PotentialScopeAutonomyPolicyError,
    authorize_plan_only_action,
    autonomy_policy_sha256,
)
from .potential_scope_campaign_runner import PotentialScopeCampaignRunnerError, build_plan_only_campaign, campaign_sha256


class PotentialScopePolicyBoundCampaignError(ValueError):
    """Raised when campaign/policy bindings are unsafe."""


def build_policy_bound_plan_only_campaign(
    *,
    machine: object,
    reviewed_source_registry: object,
    system_spec: object,
    passports: object,
    condition_matrix: object,
    autonomy_policy: object,
) -> dict[str, Any]:
    """Compose a campaign only if the human-frozen policy permits every local stage."""
    try:
        decisions = [
            authorize_plan_only_action(policy=autonomy_policy, system_spec=system_spec, action=action)
            for action in ("validate_local_artifacts", "derive_plugin_task_proposals", "rank_proposed_task_cards")
        ]
        if not all(item["permitted"] for item in decisions):
            raise PotentialScopePolicyBoundCampaignError("human-frozen policy blocks an automatic planning stage")
        campaign = build_plan_only_campaign(
            machine=machine,
            reviewed_source_registry=reviewed_source_registry,
            system_spec=system_spec,
            passports=passports,
            condition_matrix=condition_matrix,
        )
    except (PotentialScopeAutonomyPolicyError, PotentialScopeCampaignRunnerError) as error:
        raise PotentialScopePolicyBoundCampaignError("policy-bound plan-only campaign cannot be created") from error
    return {
        "schema_version": "1.0",
        "trust_status": "human_frozen_policy_bound_plan_only_campaign_not_executed",
        "autonomy_policy_sha256": autonomy_policy_sha256(system_spec=system_spec, policy=autonomy_policy),
        "campaign_sha256": campaign_sha256(campaign),
        "campaign": campaign,
        "policy_decisions": decisions,
        "execution_permitted": False,
        "execution_boundary": "The policy binds only local planning actions. Every TestCard remains proposed and cannot be promoted to execution by this package.",
    }
