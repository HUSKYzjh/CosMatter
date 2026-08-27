"""Bind reviewed PotentialScope artifacts into one non-executable plan package.

This module is deliberately downstream of the human review boundary.  It reads
only JSON artifacts supplied by the caller, checks that every cited source ID
exists in the quote-free private registry, and emits task proposals.  It never
opens PDFs or Markdown, calls a provider, reads model files, constructs a
structure, executes a command, or submits a calculation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .machine_config import MachineConfigError, validate_machine_config
from .potential_scope_intake import (
    PotentialScopeIntakeError,
    build_condition_matrix,
    build_plugin_request,
    build_potential_passport,
    build_system_spec,
    system_spec_sha256,
)
from .potential_scope_review_registry import PotentialScopeReviewRegistryError, build_reviewed_source_registry
from .potential_task_plugins import PotentialTaskPluginError, default_task_plugin_registry


FROZEN_PLUGIN_PLAN_SCHEMA_VERSION = "1.0"


class PotentialScopeFrozenPlanError(ValueError):
    """Raised when frozen artifacts cannot safely produce a plan-only package."""


def build_frozen_plugin_plan(
    *,
    machine: object,
    system_spec: object,
    passports: object,
    condition_matrix: object,
    reviewed_source_registry: object,
) -> dict[str, Any]:
    """Generate one validated, literature-bound package of proposed TestCards."""
    registry = _validated_registry(reviewed_source_registry)
    source_ids = {item["source_id"] for item in registry["sources"]}
    try:
        validated_machine = validate_machine_config(machine)
        spec = build_system_spec(system_spec)
        if not set(spec["literature_source_ids"]).issubset(source_ids):
            raise PotentialScopeFrozenPlanError("SystemSpec cites source IDs absent from the reviewed private registry")
        if not isinstance(passports, list):
            raise PotentialScopeFrozenPlanError("PotentialPassports must be an array")
        reviewed_passports = [build_potential_passport(system_spec=spec, payload=item) for item in passports]
        matrix = build_condition_matrix(system_spec=spec, payload=condition_matrix)
        request = build_plugin_request(system_spec=spec, passports=reviewed_passports, condition_matrix=matrix)
        proposal = default_task_plugin_registry().plan(machine=validated_machine, request=request)
    except (MachineConfigError, PotentialScopeIntakeError, PotentialTaskPluginError) as error:
        raise PotentialScopeFrozenPlanError(str(error)) from error
    if proposal["machine_execution_mode"] != "plan_only" or any(card["approval_state"] != "proposed" or card["execution_permitted"] for card in proposal["proposed_test_cards"]):
        raise PotentialScopeFrozenPlanError("frozen plugin plan must remain proposed and non-executable")
    return {
        "schema_version": FROZEN_PLUGIN_PLAN_SCHEMA_VERSION,
        "trust_status": "human_frozen_literature_bound_plugin_plan_not_executed",
        "source_registry_sha256": _canonical_sha256(registry),
        "system_spec_sha256": system_spec_sha256(spec),
        "machine_profile_id": validated_machine["profile_id"],
        "machine_execution_mode": validated_machine["execution_mode"],
        "literature_source_ids": list(request["literature_source_ids"]),
        "proposal": proposal,
        "execution_boundary": (
            "This package is a literature-bound plan only. It contains no structure, model, command, scheduler target, "
            "calculation input or result, and it cannot authorize execution."
        ),
    }


def write_frozen_plugin_plan(path: Path, plan: object) -> Path:
    _validate_frozen_plugin_plan(plan)
    if path.suffix.casefold() != ".json":
        raise PotentialScopeFrozenPlanError("frozen plugin plan output must use a .json filename")
    if path.exists():
        raise PotentialScopeFrozenPlanError("frozen plugin plan already exists and will not be overwritten")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as error:
        raise PotentialScopeFrozenPlanError("frozen plugin plan cannot be written") from error
    return path


def _validated_registry(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "mission_id", "trust_status", "sources", "review_boundary"}:
        raise PotentialScopeFrozenPlanError("reviewed source registry has unsupported or missing fields")
    if payload.get("trust_status") != "human_reviewed_private_source_registry_not_evidence":
        raise PotentialScopeFrozenPlanError("reviewed source registry must be explicitly human reviewed")
    try:
        return build_reviewed_source_registry(mission_id=payload.get("mission_id"), entries=payload.get("sources"))
    except PotentialScopeReviewRegistryError as error:
        raise PotentialScopeFrozenPlanError("reviewed source registry is invalid") from error


def _validate_frozen_plugin_plan(payload: object) -> None:
    expected = {
        "schema_version",
        "trust_status",
        "source_registry_sha256",
        "system_spec_sha256",
        "machine_profile_id",
        "machine_execution_mode",
        "literature_source_ids",
        "proposal",
        "execution_boundary",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise PotentialScopeFrozenPlanError("frozen plugin plan has unsupported or missing fields")
    if payload.get("schema_version") != FROZEN_PLUGIN_PLAN_SCHEMA_VERSION or payload.get("trust_status") != "human_frozen_literature_bound_plugin_plan_not_executed":
        raise PotentialScopeFrozenPlanError("frozen plugin plan identity is invalid")
    if not isinstance(payload.get("machine_profile_id"), str) or not payload["machine_profile_id"]:
        raise PotentialScopeFrozenPlanError("frozen plugin plan machine profile is invalid")
    if payload.get("machine_execution_mode") != "plan_only":
        raise PotentialScopeFrozenPlanError("frozen plugin plan execution mode must remain plan_only")
    for field in ("source_registry_sha256", "system_spec_sha256"):
        digest = payload.get(field)
        if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise PotentialScopeFrozenPlanError(f"frozen plugin plan {field} is invalid")
    if not isinstance(payload.get("execution_boundary"), str) or not payload["execution_boundary"].strip():
        raise PotentialScopeFrozenPlanError("frozen plugin plan execution boundary is invalid")
    proposal = payload.get("proposal")
    if not isinstance(proposal, dict) or proposal.get("machine_execution_mode") != "plan_only":
        raise PotentialScopeFrozenPlanError("frozen plugin plan proposal is invalid")
    cards = proposal.get("proposed_test_cards")
    if not isinstance(cards, list) or any(
        not isinstance(card, dict) or card.get("approval_state") != "proposed" or card.get("execution_permitted") is not False
        for card in cards
    ):
        raise PotentialScopeFrozenPlanError("frozen plugin plan proposal contains an executable or non-proposed card")


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
