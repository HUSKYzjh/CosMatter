"""Plugin-first task planning for literature-driven potential applicability work.

This is deliberately a *planning harness*, inspired by pluggable task
architectures.  Plugins are pure functions: they inspect a bounded request and
return proposed TestCard-like records.  They never invoke calculators, create
structures, submit jobs, call a scheduler, use a network, or alter an imported
result.  Such operations remain outside CosMatter and require a future,
separately-reviewed execution profile.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable

from .machine_config import MachineConfigError, validate_machine_config


TASK_PLUGIN_SCHEMA_VERSION = "1.0"


class PotentialTaskPluginError(ValueError):
    """Raised for unsafe, malformed or untraceable task-plugin requests."""


@dataclass(frozen=True)
class TaskPlugin:
    """Stable plugin contract, comparable to a harness tool registration."""

    plugin_id: str
    title: str
    required_axes: tuple[str, ...]
    observable: str
    executor_class: str
    planner: Callable[[dict[str, Any]], list[dict[str, Any]]]

    def manifest(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "title": self.title,
            "required_axes": list(self.required_axes),
            "observable": self.observable,
            "executor_class": self.executor_class,
            "planning_only": True,
            "execution_contract": "No command, scheduler, network or calculator access is exposed by this plugin.",
        }


class TaskPluginRegistry:
    """Small explicit registry: no dynamic import or executable plugin loading."""

    def __init__(self, plugins: tuple[TaskPlugin, ...]) -> None:
        if len({plugin.plugin_id for plugin in plugins}) != len(plugins):
            raise PotentialTaskPluginError("task-plugin identifiers must be unique")
        self._plugins = {plugin.plugin_id: plugin for plugin in plugins}

    def manifests(self) -> list[dict[str, Any]]:
        return [self._plugins[key].manifest() for key in sorted(self._plugins)]

    def get(self, plugin_id: str) -> TaskPlugin:
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            raise PotentialTaskPluginError(f"unknown task plugin: {plugin_id}")
        return plugin

    def plan(self, *, machine: object, request: object, plugin_ids: tuple[str, ...] | None = None) -> dict[str, Any]:
        try:
            validated_machine = validate_machine_config(machine)
        except MachineConfigError as error:
            raise PotentialTaskPluginError(str(error)) from error
        validated_request = _validate_request(request)
        selected = tuple(sorted(plugin_ids or tuple(self._plugins)))
        if not selected:
            raise PotentialTaskPluginError("at least one task plugin must be selected")
        unknown = set(selected) - set(self._plugins)
        if unknown:
            raise PotentialTaskPluginError("unknown task plugins: " + ", ".join(sorted(unknown)))
        proposed: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for plugin_id in selected:
            policy = validated_machine["task_plugins"][plugin_id]
            plugin = self._plugins[plugin_id]
            missing_axes = [axis for axis in plugin.required_axes if axis not in validated_request["condition_axes"]]
            if not policy["enabled"]:
                skipped.append({"plugin_id": plugin_id, "reason": "disabled_by_machine_policy"})
            elif missing_axes:
                skipped.append({"plugin_id": plugin_id, "reason": "missing_literature_declared_axes", "missing_axes": missing_axes})
            else:
                proposed.extend(plugin.planner(validated_request))
        for sequence, proposal in enumerate(proposed, start=1):
            proposal["test_id"] = _test_id(validated_request, proposal["plugin_id"], sequence)
            proposal["sequence"] = sequence
            proposal["system_spec_id"] = validated_request["system_spec_id"]
            proposal["system_spec_sha256"] = validated_request["system_spec_sha256"]
            proposal["potential_model_ids"] = list(validated_request["potential_model_ids"])
            proposal["reference_method"] = validated_request["reference_method"]
            proposal["literature_source_ids"] = list(validated_request["literature_source_ids"])
            proposal["approval_state"] = "proposed"
            proposal["execution_permitted"] = False
            proposal["input_boundary"] = "condition coordinates are literature-derived declarations; no structure is generated or loaded"
            proposal["result_boundary"] = "no calculation is run; any future aggregate result import requires an approved external protocol"
        return {
            "schema_version": TASK_PLUGIN_SCHEMA_VERSION,
            "trust_status": "literature_grounded_plugin_task_proposals_not_executed_calculations",
            "machine_profile_id": validated_machine["profile_id"],
            "machine_execution_mode": validated_machine["execution_mode"],
            "request_sha256": _canonical_sha256(validated_request),
            "system_spec_id": validated_request["system_spec_id"],
            "literature_source_ids": list(validated_request["literature_source_ids"]),
            "plugins": self.manifests(),
            "selected_plugin_ids": list(selected),
            "proposed_test_cards": proposed,
            "skipped_plugins": skipped,
            "execution_boundary": "All output cards are proposed only. This harness cannot submit, poll, launch, train, simulate or infer.",
        }


def default_task_plugin_registry() -> TaskPluginRegistry:
    return TaskPluginRegistry((
        TaskPlugin("static_property", "静态性质对照", (), "energy_force_stress", "potential_inference", _static_property),
        TaskPlugin("strain_path", "连续应变路径", ("strain_percent",), "energy_force_stress_path", "potential_inference", _strain_path),
        TaskPlugin("defect_boundary", "缺陷与边界条件", ("defect_fraction",), "defect_energy_force_stress", "dft_reference", _defect_boundary),
        TaskPlugin("finite_temperature", "有限温稳定性", ("temperature_k",), "stability_diagnostics", "molecular_dynamics", _finite_temperature),
        TaskPlugin("reference_label", "参考标注计划", (), "reference_energy_force_stress", "dft_reference", _reference_label),
    ))


def _static_property(request: dict[str, Any]) -> list[dict[str, Any]]:
    return [_proposal(
        plugin_id="static_property",
        purpose="Compare declared potential outputs against a future approved reference at literature-declared condition axes.",
        condition_axes=request["condition_axes"],
        expected_boundary="interpolation_or_boundary_to_be_observed_after_import",
    )]


def _strain_path(request: dict[str, Any]) -> list[dict[str, Any]]:
    return [_proposal(
        plugin_id="strain_path",
        purpose="Plan a continuous strain-path check around a literature-declared strain interval; no structures or path points are generated here.",
        condition_axes={"strain_percent": request["condition_axes"]["strain_percent"]},
        expected_boundary="strain_transferability_to_be_observed_after_import",
    )]


def _defect_boundary(request: dict[str, Any]) -> list[dict[str, Any]]:
    return [_proposal(
        plugin_id="defect_boundary",
        purpose="Plan a defect-boundary comparison only for a reviewer-declared defect fraction; charge state and structure recipe remain external human-reviewed inputs.",
        condition_axes={"defect_fraction": request["condition_axes"]["defect_fraction"]},
        expected_boundary="defect_extrapolation_to_be_observed_after_import",
    )]


def _finite_temperature(request: dict[str, Any]) -> list[dict[str, Any]]:
    return [_proposal(
        plugin_id="finite_temperature",
        purpose="Plan finite-temperature stability diagnostics within a literature-declared temperature interval; no MD or MC is started.",
        condition_axes={"temperature_k": request["condition_axes"]["temperature_k"]},
        expected_boundary="finite_temperature_stability_to_be_observed_after_import",
    )]


def _reference_label(request: dict[str, Any]) -> list[dict[str, Any]]:
    return [_proposal(
        plugin_id="reference_label",
        purpose="Reserve a review-gated reference-label packet for future external calculation; it has no scheduler target or command.",
        condition_axes=request["condition_axes"],
        expected_boundary="reference_coverage_gap_to_be_observed_after_import",
    )]


def _proposal(*, plugin_id: str, purpose: str, condition_axes: dict[str, list[float]], expected_boundary: str) -> dict[str, Any]:
    return {
        "plugin_id": plugin_id,
        "purpose": purpose,
        "condition_axes": {key: list(value) for key, value in sorted(condition_axes.items())},
        "expected_boundary": expected_boundary,
        "required_result_fields": ["task_id", "model_id", "atom_count", "reference_energy_ev", "predicted_energy_ev", "force_rmse_ev_per_a", "wall_time_seconds"],
        "stop_condition": "human approval absent or an external protocol is not approved",
    }


def _validate_request(payload: object) -> dict[str, Any]:
    expected = {"system_spec_id", "system_spec_sha256", "potential_model_ids", "reference_method", "condition_axes", "literature_source_ids"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise PotentialTaskPluginError("task-plugin request has unsupported or missing fields")
    _identifier(payload.get("system_spec_id"), "system_spec_id")
    digest = payload.get("system_spec_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.casefold()):
        raise PotentialTaskPluginError("system_spec_sha256 must be a SHA-256 hex digest")
    models = payload.get("potential_model_ids")
    if not isinstance(models, list) or not (2 <= len(models) <= 16) or len(set(models)) != len(models):
        raise PotentialTaskPluginError("two through sixteen unique potential model identifiers are required")
    for model_id in models:
        _identifier(model_id, "potential model identifier")
    _safe_text(payload.get("reference_method"), "reference method")
    axes = payload.get("condition_axes")
    if not isinstance(axes, dict) or not axes or len(axes) > 12:
        raise PotentialTaskPluginError("one through twelve literature-declared condition axes are required")
    normalized_axes: dict[str, list[float]] = {}
    for name, bounds in axes.items():
        _identifier(name, "condition axis")
        if not isinstance(bounds, list) or len(bounds) != 2 or not all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in bounds):
            raise PotentialTaskPluginError("condition axes require numeric [minimum, maximum] bounds")
        lower, upper = float(bounds[0]), float(bounds[1])
        if not lower < upper:
            raise PotentialTaskPluginError("condition-axis bounds must have minimum < maximum")
        normalized_axes[name] = [lower, upper]
    source_ids = payload.get("literature_source_ids")
    if not isinstance(source_ids, list) or not (1 <= len(source_ids) <= 100) or len(set(source_ids)) != len(source_ids):
        raise PotentialTaskPluginError("one through one hundred unique reviewer-mapped literature source identifiers are required")
    for source_id in source_ids:
        _identifier(source_id, "literature source identifier")
    return {
        "system_spec_id": payload["system_spec_id"],
        "system_spec_sha256": digest.casefold(),
        "potential_model_ids": tuple(payload["potential_model_ids"]),
        "reference_method": payload["reference_method"].strip(),
        "condition_axes": normalized_axes,
        "literature_source_ids": tuple(sorted(source_ids)),
    }


def _identifier(value: object, field: str) -> None:
    if not isinstance(value, str) or not value or len(value) > 128 or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in value):
        raise PotentialTaskPluginError(f"{field} must be a short identifier without paths or spaces")


def _safe_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise PotentialTaskPluginError(f"{field} must be non-empty text")
    lowered = value.casefold()
    if any(marker in lowered for marker in ("api_key", "authorization", "bearer ", "c:\\users\\", "/home/", "ssh://")):
        raise PotentialTaskPluginError(f"{field} must not contain credentials or private paths")


def _test_id(request: dict[str, Any], plugin_id: str, sequence: int) -> str:
    digest = hashlib.sha256(f"{request['system_spec_sha256']}:{plugin_id}:{sequence}".encode("utf-8")).hexdigest()[:12]
    return f"test_{plugin_id}_{digest}"


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
