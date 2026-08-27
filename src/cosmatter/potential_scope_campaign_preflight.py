"""Quote-free readiness inspection for a non-executing PotentialScope campaign."""

from __future__ import annotations

from typing import Any

from .machine_config import MachineConfigError, validate_machine_config
from .potential_scope_frozen_plan import PotentialScopeFrozenPlanError, build_frozen_plugin_plan
from .potential_scope_intake import (
    PotentialScopeIntakeError,
    build_condition_matrix,
    build_potential_passport,
    build_system_spec,
)
from .potential_scope_review_registry import PotentialScopeReviewRegistryError, build_reviewed_source_registry


CAMPAIGN_PREFLIGHT_SCHEMA_VERSION = "1.0"


def inspect_campaign(
    *,
    machine: object | None,
    reviewed_source_registry: object | None,
    system_spec: object | None,
    passports: object | None,
    condition_matrix: object | None,
) -> dict[str, Any]:
    """Return an aggregate readiness report, never an execution instruction.

    Inputs are already quote-free/frozen JSON artifacts. The return value holds
    only stage states, counts, and generic blocking reasons; it deliberately
    omits document/source identifiers, condition values, model versions and
    private paths.
    """
    blocks: list[str] = []
    stages: dict[str, dict[str, Any]] = {}
    try:
        validated_machine = validate_machine_config(machine)
        stages["machine"] = {"state": "ready", "execution_mode": validated_machine["execution_mode"]}
    except MachineConfigError:
        validated_machine = None
        stages["machine"] = {"state": "blocked"}
        blocks.append("machine_plan_only_profile_missing_or_invalid")
    try:
        if not isinstance(reviewed_source_registry, dict):
            raise PotentialScopeReviewRegistryError("missing registry")
        registry = build_reviewed_source_registry(
            mission_id=reviewed_source_registry.get("mission_id"), entries=reviewed_source_registry.get("sources")
        )
        if reviewed_source_registry.get("trust_status") != "human_reviewed_private_source_registry_not_evidence":
            raise PotentialScopeReviewRegistryError("wrong registry gate")
        stages["reviewed_sources"] = {"state": "ready", "source_count": len(registry["sources"])}
    except PotentialScopeReviewRegistryError:
        registry = None
        stages["reviewed_sources"] = {"state": "blocked", "source_count": 0}
        blocks.append("human_reviewed_source_registry_missing_or_invalid")
    try:
        spec = build_system_spec(system_spec)
        source_ids = {row["source_id"] for row in registry["sources"]} if registry else set()
        if not set(spec["literature_source_ids"]).issubset(source_ids):
            raise PotentialScopeIntakeError("unregistered sources")
        stages["system_spec"] = {"state": "ready", "model_count": len(spec["potential_model_ids"]), "axis_count": len(spec["condition_axes"])}
    except PotentialScopeIntakeError:
        spec = None
        stages["system_spec"] = {"state": "blocked"}
        blocks.append("human_frozen_system_spec_missing_or_not_bound_to_reviewed_sources")
    try:
        if spec is None or not isinstance(passports, list):
            raise PotentialScopeIntakeError("missing passports")
        checked_passports = [build_potential_passport(system_spec=spec, payload=item) for item in passports]
        if {item["model_id"] for item in checked_passports} != set(spec["potential_model_ids"]):
            raise PotentialScopeIntakeError("passport coverage")
        stages["potential_passports"] = {"state": "ready", "passport_count": len(checked_passports)}
    except PotentialScopeIntakeError:
        checked_passports = None
        stages["potential_passports"] = {"state": "blocked"}
        blocks.append("human_reviewed_potential_passports_missing_or_incomplete")
    try:
        if spec is None:
            raise PotentialScopeIntakeError("missing system spec")
        matrix = build_condition_matrix(system_spec=spec, payload=condition_matrix)
        stages["condition_matrix"] = {"state": "ready", "cell_count": len(matrix["cells"])}
    except PotentialScopeIntakeError:
        matrix = None
        stages["condition_matrix"] = {"state": "blocked", "cell_count": 0}
        blocks.append("human_reviewed_literature_condition_matrix_missing_or_invalid")
    try:
        if None in (validated_machine, registry, spec, checked_passports, matrix):
            raise PotentialScopeFrozenPlanError("prerequisites missing")
        plan = build_frozen_plugin_plan(
            machine=validated_machine,
            system_spec=spec,
            passports=checked_passports,
            condition_matrix=matrix,
            reviewed_source_registry=registry,
        )
        stages["plugin_plan"] = {
            "state": "ready",
            "proposed_test_card_count": len(plan["proposal"]["proposed_test_cards"]),
            "skipped_plugin_count": len(plan["proposal"]["skipped_plugins"]),
            "execution_permitted": False,
        }
    except PotentialScopeFrozenPlanError:
        stages["plugin_plan"] = {"state": "blocked", "execution_permitted": False}
        blocks.append("nonexecuting_plugin_plan_cannot_be_derived_until_all_frozen_artifacts_validate")
    return {
        "schema_version": CAMPAIGN_PREFLIGHT_SCHEMA_VERSION,
        "trust_status": "potential_scope_campaign_preflight_not_evidence_not_execution",
        "stages": stages,
        "blocking_reasons": blocks,
        "ready_for_plan_only_proposal": not blocks,
        "execution_boundary": "This is a local readiness inspection only. It cannot authorize or start calculations, model loading, scheduler work, training, inference, or external calls.",
    }
