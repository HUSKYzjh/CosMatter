"""Strict, human-frozen autonomy policy for the PotentialScope plan-only mode.

The policy is deliberately more restrictive than a general automation policy:
it can authorize only deterministic local artifact validation, TestCard
proposal and priority derivation.  It cannot grant a calculation capability.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .potential_scope_intake import AUTONOMY_POLICY_SCHEMA_VERSION, PotentialScopeIntakeError, build_system_spec, system_spec_sha256


class PotentialScopeAutonomyPolicyError(ValueError):
    """Raised when a policy expands beyond the frozen plan-only boundary."""


_ALLOWED_ACTIONS = {"validate_local_artifacts", "derive_plugin_task_proposals", "rank_proposed_task_cards"}
_REQUIRED_FORBIDDEN = {
    "external_api_call", "pdf_or_markdown_read", "structure_generation", "model_load", "potential_inference",
    "dft_submission", "md_submission", "mc_submission", "training", "scheduler_poll",
}


def build_plan_only_autonomy_policy(*, system_spec: object, payload: object) -> dict[str, Any]:
    """Validate a policy that cannot promote or execute a TestCard."""
    try:
        spec = build_system_spec(system_spec)
    except PotentialScopeIntakeError as error:
        raise PotentialScopeAutonomyPolicyError("SystemSpec is invalid") from error
    expected = {"schema_version", "trust_status", "system_spec_sha256", "allowed_actions", "forbidden_actions", "budgets", "approval"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise PotentialScopeAutonomyPolicyError("autonomy policy has unsupported or missing fields")
    if payload.get("schema_version") != AUTONOMY_POLICY_SCHEMA_VERSION or payload.get("trust_status") != "human_frozen_planning_only_autonomy_policy":
        raise PotentialScopeAutonomyPolicyError("autonomy policy identity is invalid")
    if payload.get("system_spec_sha256") != system_spec_sha256(spec):
        raise PotentialScopeAutonomyPolicyError("autonomy policy belongs to another SystemSpec")
    actions = payload.get("allowed_actions")
    if not isinstance(actions, list) or not actions or len(actions) != len(set(actions)) or not set(actions).issubset(_ALLOWED_ACTIONS):
        raise PotentialScopeAutonomyPolicyError("autonomy policy allowed actions exceed plan-only scope")
    forbidden = payload.get("forbidden_actions")
    if not isinstance(forbidden, list) or len(forbidden) != len(set(forbidden)) or not _REQUIRED_FORBIDDEN.issubset(set(forbidden)):
        raise PotentialScopeAutonomyPolicyError("autonomy policy must forbid all execution-capable actions")
    budgets = payload.get("budgets")
    if not isinstance(budgets, dict) or set(budgets) != {"dft_tasks", "gpu_tasks", "external_calls"} or any(value != 0 for value in budgets.values()):
        raise PotentialScopeAutonomyPolicyError("plan-only autonomy policy budgets must all remain zero")
    approval = payload.get("approval")
    if not isinstance(approval, dict) or set(approval) != {"status", "reviewer", "frozen_on"} or approval.get("status") != "human_frozen":
        raise PotentialScopeAutonomyPolicyError("autonomy policy requires a human frozen approval")
    for key in ("reviewer", "frozen_on"):
        if not isinstance(approval.get(key), str) or not approval[key].strip() or len(approval[key]) > 200:
            raise PotentialScopeAutonomyPolicyError("autonomy policy approval fields are invalid")
    return {**payload, "allowed_actions": sorted(actions), "forbidden_actions": sorted(forbidden)}


def authorize_plan_only_action(*, policy: object, system_spec: object, action: object) -> dict[str, Any]:
    """Return an auditable decision; it does not perform the requested action."""
    reviewed = build_plan_only_autonomy_policy(system_spec=system_spec, payload=policy)
    if not isinstance(action, str) or not action:
        raise PotentialScopeAutonomyPolicyError("requested action is invalid")
    permitted = action in reviewed["allowed_actions"]
    return {
        "system_spec_sha256": reviewed["system_spec_sha256"],
        "action": action,
        "permitted": permitted,
        "reason": "allowed_by_human_frozen_plan_only_policy" if permitted else "not_allowed_by_human_frozen_plan_only_policy",
        "execution_permitted": False,
        "next_boundary": "A positive decision permits only local plan derivation. It cannot approve, queue, run, import, train, infer, submit, poll, or interpret a calculation.",
    }


def autonomy_policy_sha256(*, system_spec: object, policy: object) -> str:
    reviewed = build_plan_only_autonomy_policy(system_spec=system_spec, payload=policy)
    return hashlib.sha256(json.dumps(reviewed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
