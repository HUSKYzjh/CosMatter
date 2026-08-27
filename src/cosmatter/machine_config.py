"""DP-GEN-inspired, non-executable machine configuration for PotentialScope.

The configuration intentionally describes *capability and safety policy*, not a
researcher's workstation or HPC cluster.  In the current ``plan_only`` mode it
cannot contain a command, scheduler queue, host name, private path or
credential, and validation refuses every submission-capable setting.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MACHINE_CONFIG_SCHEMA_VERSION = "1.0"
_PLUGIN_IDS = {
    "static_property",
    "strain_path",
    "defect_boundary",
    "finite_temperature",
    "reference_label",
}
_EXECUTOR_IDS = {"potential_inference", "dft_reference", "molecular_dynamics", "monte_carlo"}


class MachineConfigError(ValueError):
    """Raised when a machine configuration would enable unsafe execution."""


def machine_config_template() -> dict[str, Any]:
    """Return the only supported configuration for the literature-only phase."""
    return {
        "schema_version": MACHINE_CONFIG_SCHEMA_VERSION,
        "profile_id": "literature_planning_only",
        "execution_mode": "plan_only",
        "trust_status": "human_reviewed_machine_capability_template_no_calculations_submitted",
        "scheduler": {
            "kind": "disabled",
            "submission_enabled": False,
            "polling_enabled": False,
        },
        "resources": {
            "max_concurrent_tasks": 0,
            "max_gpu_tasks": 0,
            "max_dft_tasks": 0,
            "queue_or_partition": None,
        },
        "executors": {
            executor_id: {
                "enabled": False,
                "command_template": None,
                "result_import_only": True,
            }
            for executor_id in sorted(_EXECUTOR_IDS)
        },
        "task_plugins": {
            plugin_id: {
                "enabled": True,
                "execution_permitted": False,
                "requires_literature_source_ids": True,
                "requires_human_approval": True,
            }
            for plugin_id in sorted(_PLUGIN_IDS)
        },
        "data_policy": {
            "input_evidence_boundary": "Only reviewer-mapped literature conditions and metadata may seed task proposals.",
            "private_structures_and_fulltext_outside_run_directory": True,
            "allow_imported_aggregate_results_only": True,
            "forbid_credentials_private_paths_and_raw_calculation_files": True,
        },
        "execution_boundary": "This file creates planning artifacts only. DFT, potential inference, MD, MC, training and scheduler submission are disabled until a separately reviewed execution profile is introduced.",
    }


def validate_machine_config(payload: object) -> dict[str, Any]:
    """Validate the planning profile and return an immutable-by-convention dict."""
    if not isinstance(payload, dict):
        raise MachineConfigError("machine configuration must be an object")
    expected = set(machine_config_template())
    if set(payload) != expected:
        raise MachineConfigError("machine configuration has unsupported or missing fields")
    if payload.get("schema_version") != MACHINE_CONFIG_SCHEMA_VERSION:
        raise MachineConfigError("machine configuration schema version is invalid")
    if payload.get("profile_id") != "literature_planning_only" or payload.get("execution_mode") != "plan_only":
        raise MachineConfigError("only the literature_planning_only plan_only profile is supported")
    if payload.get("trust_status") != "human_reviewed_machine_capability_template_no_calculations_submitted":
        raise MachineConfigError("machine configuration trust status is invalid")
    _validate_scheduler(payload.get("scheduler"))
    _validate_resources(payload.get("resources"))
    _validate_executors(payload.get("executors"))
    _validate_plugins(payload.get("task_plugins"))
    _validate_data_policy(payload.get("data_policy"))
    _safe_text(payload.get("execution_boundary"), "execution boundary")
    return payload


def load_machine_config(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MachineConfigError(f"cannot load machine configuration: {error}") from error
    return validate_machine_config(payload)


def write_machine_config(path: Path, payload: object | None = None) -> Path:
    """Write a validated planning-only configuration; never creates a run job."""
    config = validate_machine_config(machine_config_template() if payload is None else payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _validate_scheduler(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {"kind", "submission_enabled", "polling_enabled"}:
        raise MachineConfigError("scheduler configuration is invalid")
    if value != {"kind": "disabled", "submission_enabled": False, "polling_enabled": False}:
        raise MachineConfigError("planning-only machine configuration must disable scheduler submission and polling")


def _validate_resources(value: object) -> None:
    expected = {"max_concurrent_tasks", "max_gpu_tasks", "max_dft_tasks", "queue_or_partition"}
    if not isinstance(value, dict) or set(value) != expected:
        raise MachineConfigError("resource configuration is invalid")
    if any(value.get(key) != 0 for key in ("max_concurrent_tasks", "max_gpu_tasks", "max_dft_tasks")):
        raise MachineConfigError("planning-only machine configuration must have zero execution capacity")
    if value.get("queue_or_partition") is not None:
        raise MachineConfigError("planning-only machine configuration cannot name a queue or partition")


def _validate_executors(value: object) -> None:
    if not isinstance(value, dict) or set(value) != _EXECUTOR_IDS:
        raise MachineConfigError("executor configuration is incomplete")
    for executor_id, executor in value.items():
        if not isinstance(executor, dict) or set(executor) != {"enabled", "command_template", "result_import_only"}:
            raise MachineConfigError(f"executor {executor_id} is invalid")
        if executor != {"enabled": False, "command_template": None, "result_import_only": True}:
            raise MachineConfigError("planning-only machine configuration cannot enable or define an executor")


def _validate_plugins(value: object) -> None:
    expected_fields = {"enabled", "execution_permitted", "requires_literature_source_ids", "requires_human_approval"}
    if not isinstance(value, dict) or set(value) != _PLUGIN_IDS:
        raise MachineConfigError("task-plugin configuration is incomplete")
    for plugin_id, plugin in value.items():
        if not isinstance(plugin, dict) or set(plugin) != expected_fields:
            raise MachineConfigError(f"task plugin {plugin_id} is invalid")
        if plugin != {"enabled": True, "execution_permitted": False, "requires_literature_source_ids": True, "requires_human_approval": True}:
            raise MachineConfigError("planning-only task plugins must require literature sources and human approval")


def _validate_data_policy(value: object) -> None:
    expected = {
        "input_evidence_boundary",
        "private_structures_and_fulltext_outside_run_directory",
        "allow_imported_aggregate_results_only",
        "forbid_credentials_private_paths_and_raw_calculation_files",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise MachineConfigError("data policy is invalid")
    _safe_text(value.get("input_evidence_boundary"), "input evidence boundary")
    for field in expected - {"input_evidence_boundary"}:
        if value.get(field) is not True:
            raise MachineConfigError("planning-only data policy safety flags must remain true")


def _safe_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 1000:
        raise MachineConfigError(f"{field} must be non-empty text")
    lowered = value.casefold()
    if any(marker in lowered for marker in ("api_key", "authorization", "bearer ", "c:\\users\\", "/home/", "ssh://")):
        raise MachineConfigError(f"{field} must not include credentials or private paths")
