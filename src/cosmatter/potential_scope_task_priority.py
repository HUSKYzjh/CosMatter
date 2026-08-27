"""Literature-bound, non-executing prioritisation for PotentialScope TestCards."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .potential_scope_intake import PotentialScopeIntakeError, build_condition_matrix, build_potential_passport, build_system_spec


PRIORITIZED_PLUGIN_QUEUE_SCHEMA_VERSION = "1.0"


class PotentialScopeTaskPriorityError(ValueError):
    """Raised when a proposed plan cannot be safely prioritised."""


def prioritize_proposed_test_cards(*, frozen_plan: object, system_spec: object, passports: object, condition_matrix: object) -> dict[str, Any]:
    """Rank only existing proposed cards using frozen literature coverage roles.

    This function does not decide that a model is accurate or inaccurate. A
    high rank means only that a future human-approved comparison would be more
    informative under the declared scope.
    """
    _validate_frozen_plan(frozen_plan)
    try:
        spec = build_system_spec(system_spec)
        if not isinstance(passports, list):
            raise PotentialScopeIntakeError("passports must be an array")
        checked_passports = [build_potential_passport(system_spec=spec, payload=item) for item in passports]
        if {row["model_id"] for row in checked_passports} != set(spec["potential_model_ids"]):
            raise PotentialScopeIntakeError("passports do not cover SystemSpec models")
        matrix = build_condition_matrix(system_spec=spec, payload=condition_matrix)
    except PotentialScopeIntakeError as error:
        raise PotentialScopeTaskPriorityError("frozen priority inputs are invalid") from error
    if frozen_plan["system_spec_sha256"] != _sha(spec):
        raise PotentialScopeTaskPriorityError("frozen plugin plan belongs to another SystemSpec")
    role_by_axis: dict[str, set[str]] = {axis["axis_id"]: set() for axis in spec["condition_axes"]}
    for cell in matrix["cells"]:
        for axis_id in cell["condition_values"]:
            role_by_axis[axis_id].add(cell["coverage_role"])
    unknown_envelope = any(item["training_envelope_status"] == "training_envelope_unknown" for item in checked_passports)
    queued: list[dict[str, Any]] = []
    for card in frozen_plan["proposal"]["proposed_test_cards"]:
        axes = set(card["condition_axes"])
        reasons: list[str] = []
        if any("conflict_candidate" in role_by_axis.get(axis, set()) for axis in axes):
            reasons.append("literature_condition_conflict_candidate")
        if any("coverage_gap" in role_by_axis.get(axis, set()) for axis in axes):
            reasons.append("literature_condition_coverage_gap")
        if unknown_envelope:
            reasons.append("at_least_one_model_training_envelope_unknown")
        if not reasons:
            reasons.append("reported_condition_baseline")
        priority = _priority(reasons, plugin_id=card["plugin_id"])
        queued.append(
            {
                "test_id": card["test_id"],
                "plugin_id": card["plugin_id"],
                "priority_band": priority,
                "priority_reasons": reasons,
                "boundary_question": _boundary_question(reasons),
                "approval_state": "proposed",
                "execution_permitted": False,
            }
        )
    queued.sort(key=lambda item: (_priority_order(item["priority_band"]), item["plugin_id"], item["test_id"]))
    for rank, item in enumerate(queued, start=1):
        item["rank"] = rank
    return {
        "schema_version": PRIORITIZED_PLUGIN_QUEUE_SCHEMA_VERSION,
        "trust_status": "human_frozen_literature_bound_prioritized_plugin_queue_not_executed",
        "frozen_plan_sha256": _sha(frozen_plan),
        "system_spec_sha256": frozen_plan["system_spec_sha256"],
        "condition_coverage_summary": {
            "reported_cells": sum(cell["coverage_role"] == "reported" for cell in matrix["cells"]),
            "conflict_candidate_cells": sum(cell["coverage_role"] == "conflict_candidate" for cell in matrix["cells"]),
            "coverage_gap_cells": sum(cell["coverage_role"] == "coverage_gap" for cell in matrix["cells"]),
            "any_training_envelope_unknown": unknown_envelope,
        },
        "proposed_queue": queued,
        "execution_boundary": "Ranks are planning metadata only. No card is approved, queued, run, inferred, trained, submitted, or interpreted as a scientific result.",
    }


def _validate_frozen_plan(payload: object) -> None:
    if not isinstance(payload, dict) or payload.get("trust_status") != "human_frozen_literature_bound_plugin_plan_not_executed":
        raise PotentialScopeTaskPriorityError("a human-frozen non-executing plugin plan is required")
    if payload.get("machine_execution_mode") != "plan_only" or not isinstance(payload.get("system_spec_sha256"), str) or len(payload["system_spec_sha256"]) != 64:
        raise PotentialScopeTaskPriorityError("frozen plugin plan execution boundary is invalid")
    proposal = payload.get("proposal")
    cards = proposal.get("proposed_test_cards") if isinstance(proposal, dict) else None
    if not isinstance(cards, list) or not cards:
        raise PotentialScopeTaskPriorityError("frozen plugin plan cards are invalid")
    for card in cards:
        if not isinstance(card, dict) or card.get("approval_state") != "proposed" or card.get("execution_permitted") is not False:
            raise PotentialScopeTaskPriorityError("only non-executing proposed cards can be prioritised")
        if not isinstance(card.get("test_id"), str) or not isinstance(card.get("plugin_id"), str) or not isinstance(card.get("condition_axes"), dict):
            raise PotentialScopeTaskPriorityError("frozen plugin plan card fields are invalid")


def _priority(reasons: list[str], *, plugin_id: str) -> str:
    if "literature_condition_conflict_candidate" in reasons:
        return "high"
    if "literature_condition_coverage_gap" in reasons:
        return "high" if plugin_id == "reference_label" else "medium"
    if "at_least_one_model_training_envelope_unknown" in reasons:
        return "medium"
    return "low"


def _priority_order(value: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}[value]


def _boundary_question(reasons: list[str]) -> str:
    if "literature_condition_conflict_candidate" in reasons:
        return "Can a future approved reference comparison resolve the literature-declared condition conflict?"
    if "literature_condition_coverage_gap" in reasons:
        return "Would a future approved comparison reduce the declared condition-coverage gap?"
    if "at_least_one_model_training_envelope_unknown" in reasons:
        return "Is a future approved comparison needed before relying on a model with an unknown training envelope?"
    return "Does this reported-condition baseline remain comparable under the frozen scope?"


def _sha(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
