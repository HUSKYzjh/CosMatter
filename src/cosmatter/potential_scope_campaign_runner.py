"""Automatic *plan-only* composition of the PotentialScope plugin chain.

This is the autonomous portion permitted by the current machine policy.  It
deterministically composes preflight, TestCard proposal and prioritisation from
human-frozen, quote-free artifacts.  It does not open private literature,
load a potential, construct structures, invoke a provider, or submit any
calculation.  Every derived card remains ``proposed`` and non-executable.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .potential_scope_harness_plugins import PotentialScopeHarness, PotentialScopeHarnessPluginError


PLAN_ONLY_CAMPAIGN_SCHEMA_VERSION = "1.0"


class PotentialScopeCampaignRunnerError(ValueError):
    """Raised when a campaign cannot safely be planned or persisted."""


def build_plan_only_campaign(
    *,
    machine: object,
    reviewed_source_registry: object,
    system_spec: object,
    passports: object,
    condition_matrix: object,
) -> dict[str, Any]:
    """Compose the full allowed planning chain into one safe campaign artifact."""
    payload = {
        "machine": machine,
        "reviewed_source_registry": reviewed_source_registry,
        "system_spec": system_spec,
        "passports": passports,
        "condition_matrix": condition_matrix,
    }
    host = PotentialScopeHarness()
    try:
        preflight = host.invoke(plugin_id="potential_scope.campaign_preflight", payload=payload)["result"]
    except PotentialScopeHarnessPluginError as error:
        raise PotentialScopeCampaignRunnerError("campaign preflight rejected the supplied artifacts") from error
    trace: list[dict[str, Any]] = [{"plugin_id": "potential_scope.campaign_preflight", "state": "completed"}]
    if not preflight["ready_for_plan_only_proposal"]:
        return {
            "schema_version": PLAN_ONLY_CAMPAIGN_SCHEMA_VERSION,
            "trust_status": "potential_scope_plan_only_campaign_blocked_not_execution",
            "campaign_state": "blocked",
            "preflight": preflight,
            "frozen_plan": None,
            "prioritized_queue": None,
            "plugin_trace": trace,
            "execution_boundary": _boundary(),
        }
    try:
        frozen_plan = host.invoke(plugin_id="potential_scope.plan_only_test_cards", payload=payload)["result"]
        trace.append({"plugin_id": "potential_scope.plan_only_test_cards", "state": "completed"})
        prioritized_queue = host.invoke(
            plugin_id="potential_scope.prioritize_test_cards",
            payload={
                "frozen_plan": frozen_plan,
                "system_spec": system_spec,
                "passports": passports,
                "condition_matrix": condition_matrix,
            },
        )["result"]
        trace.append({"plugin_id": "potential_scope.prioritize_test_cards", "state": "completed"})
    except PotentialScopeHarnessPluginError as error:
        raise PotentialScopeCampaignRunnerError("a plan-only campaign plugin rejected validated preflight inputs") from error
    campaign = {
        "schema_version": PLAN_ONLY_CAMPAIGN_SCHEMA_VERSION,
        "trust_status": "human_frozen_literature_bound_plan_only_campaign_not_executed",
        "campaign_state": "planned",
        "preflight": preflight,
        "frozen_plan": frozen_plan,
        "prioritized_queue": prioritized_queue,
        "plugin_trace": trace,
        "execution_boundary": _boundary(),
    }
    validate_plan_only_campaign(campaign)
    return campaign


def validate_plan_only_campaign(payload: object) -> dict[str, Any]:
    """Prove that an automatically composed campaign still has no executor."""
    expected = {
        "schema_version", "trust_status", "campaign_state", "preflight", "frozen_plan",
        "prioritized_queue", "plugin_trace", "execution_boundary",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise PotentialScopeCampaignRunnerError("plan-only campaign fields are invalid")
    if payload.get("schema_version") != PLAN_ONLY_CAMPAIGN_SCHEMA_VERSION:
        raise PotentialScopeCampaignRunnerError("plan-only campaign schema version is invalid")
    if payload.get("campaign_state") == "blocked":
        if payload.get("trust_status") != "potential_scope_plan_only_campaign_blocked_not_execution" or payload.get("frozen_plan") is not None or payload.get("prioritized_queue") is not None:
            raise PotentialScopeCampaignRunnerError("blocked campaign state is inconsistent")
    elif payload.get("campaign_state") == "planned":
        if payload.get("trust_status") != "human_frozen_literature_bound_plan_only_campaign_not_executed":
            raise PotentialScopeCampaignRunnerError("planned campaign trust status is invalid")
        plan = payload.get("frozen_plan")
        queue = payload.get("prioritized_queue")
        if not isinstance(plan, dict) or plan.get("machine_execution_mode") != "plan_only":
            raise PotentialScopeCampaignRunnerError("planned campaign has no plan-only frozen plan")
        cards = plan.get("proposal", {}).get("proposed_test_cards") if isinstance(plan.get("proposal"), dict) else None
        if not isinstance(cards, list) or not cards or any(card.get("approval_state") != "proposed" or card.get("execution_permitted") is not False for card in cards if isinstance(card, dict)):
            raise PotentialScopeCampaignRunnerError("planned campaign TestCards are not strictly proposed")
        queue_cards = queue.get("proposed_queue") if isinstance(queue, dict) else None
        if not isinstance(queue_cards, list) or any(item.get("approval_state") != "proposed" or item.get("execution_permitted") is not False for item in queue_cards if isinstance(item, dict)):
            raise PotentialScopeCampaignRunnerError("planned campaign priority queue is not strictly proposed")
    else:
        raise PotentialScopeCampaignRunnerError("plan-only campaign state is invalid")
    if not isinstance(payload.get("preflight"), dict) or not isinstance(payload.get("plugin_trace"), list):
        raise PotentialScopeCampaignRunnerError("plan-only campaign audit fields are invalid")
    if not isinstance(payload.get("execution_boundary"), str) or not payload["execution_boundary"].strip():
        raise PotentialScopeCampaignRunnerError("plan-only campaign boundary is invalid")
    return payload


def write_plan_only_campaign(path: Path, campaign: object) -> Path:
    """Write a safe campaign artifact once; private stores and run dirs are refused."""
    normalized = validate_plan_only_campaign(campaign)
    if path.suffix.casefold() != ".json" or path.exists():
        raise PotentialScopeCampaignRunnerError("campaign output must be a new JSON file")
    forbidden_parts = {"runs", "private", "private_storage", "03_paper"}
    if any(part.casefold() in forbidden_parts for part in path.parts):
        raise PotentialScopeCampaignRunnerError("campaign output must not be written to a private or run directory")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as error:
        raise PotentialScopeCampaignRunnerError("campaign output cannot be written") from error
    return path


def campaign_sha256(campaign: object) -> str:
    """Return a stable identifier for a safe campaign payload."""
    normalized = validate_plan_only_campaign(campaign)
    return hashlib.sha256(json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _boundary() -> str:
    return (
        "This automatic campaign only validates frozen artifacts, derives proposed TestCards and ranks them. "
        "It cannot read private full text, access model weights, generate structures, call an API, execute inference, "
        "run DFT/MD/MC, train, submit or poll a scheduler, import results, or create a scientific conclusion."
    )
