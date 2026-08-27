"""Auditable external-execution protocol for potential benchmark plans.

CosMatter does not execute DFT, molecular dynamics, Monte Carlo, or potential
inference.  This module turns a deterministic boundary plan into a compact
protocol that an approved external runner may implement.  It records exactly
which model/version and reference method are intended, without accepting
structure files, trajectories, credentials, or numeric results.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .potential_benchmark import POTENTIAL_BENCHMARK_SCHEMA_VERSION


PROTOCOL_SCHEMA_VERSION = "1.0"
_FIELDS = {
    "schema_version", "trust_status", "plan_sha256", "system_label",
    "reference_protocol", "potential_models", "structure_generation",
    "task_packets", "approval", "measurement_environment", "result_import_contract",
}
_MODEL_FIELDS = {"model_id", "implementation", "version_or_commit", "license_or_terms", "artifact_identifier"}
_REFERENCE_FIELDS = {"method", "version_or_input_set", "energy_unit", "force_unit", "convergence_or_sampling_boundary"}
_STRUCTURE_FIELDS = {"generator", "generator_version_or_commit", "input_boundary", "output_boundary"}
_APPROVAL_FIELDS = {"status", "reviewer", "approved_on", "allowed_external_runner"}
_MEASUREMENT_FIELDS = {"hardware_class", "accelerator_or_cpu", "parallelism", "numerical_precision", "timing_scope"}


class PotentialProtocolError(ValueError):
    """Raised when a potential-execution protocol is not plan-bound or safe."""


def build_potential_execution_protocol(*, plan: dict[str, Any], payload: object) -> dict[str, Any]:
    """Validate a human-authored execution protocol against a benchmark plan."""
    _validate_plan(plan)
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise PotentialProtocolError("potential execution protocol has unsupported or missing fields")
    if payload.get("schema_version") != PROTOCOL_SCHEMA_VERSION:
        raise PotentialProtocolError("potential execution protocol schema version is invalid")
    if payload.get("trust_status") != "human_authored_execution_protocol_not_executed_calculation":
        raise PotentialProtocolError("potential execution protocol trust status is invalid")
    expected_sha = _sha256(plan)
    if payload.get("plan_sha256") != expected_sha or payload.get("system_label") != plan["system_label"]:
        raise PotentialProtocolError("potential execution protocol does not match the benchmark plan")
    _validate_reference(payload.get("reference_protocol"), plan)
    _validate_models(payload.get("potential_models"), plan)
    _validate_structure_generation(payload.get("structure_generation"))
    _validate_approval(payload.get("approval"))
    _validate_measurement_environment(payload.get("measurement_environment"))
    _validate_task_packets(payload.get("task_packets"), plan)
    _validate_result_contract(payload.get("result_import_contract"))
    return payload


def execution_protocol_template(*, plan: dict[str, Any]) -> dict[str, Any]:
    """Create a blank, non-executable protocol bound to a benchmark plan."""
    _validate_plan(plan)
    return {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "trust_status": "human_authored_execution_protocol_not_executed_calculation",
        "plan_sha256": _sha256(plan),
        "system_label": plan["system_label"],
        "reference_protocol": {
            "method": plan["reference_method"],
            "version_or_input_set": "【待人工填写：代码版本、赝势/泛函或采样方案】",
            "energy_unit": "eV",
            "force_unit": "eV/angstrom",
            "convergence_or_sampling_boundary": "【待人工填写：收敛阈值、k 点、步数或统计边界】",
        },
        "potential_models": [{
            "model_id": model_id,
            "implementation": "【待人工填写】",
            "version_or_commit": "【待人工填写】",
            "license_or_terms": "【待人工填写】",
            "artifact_identifier": "【待人工填写：不含本地绝对路径】",
        } for model_id in plan["potential_models"]],
        "structure_generation": {
            "generator": "【待人工填写】",
            "generator_version_or_commit": "【待人工填写】",
            "input_boundary": "Task controls only; approved structure generator runs externally.",
            "output_boundary": "Private structures/trajectories remain outside CosMatter; import aggregate result rows only.",
        },
        "task_packets": [{
            "task_id": task["task_id"], "regime": task["regime"], "controls": task["controls"],
            "required_outputs": ["atom_count", "reference_energy_ev", "predicted_energy_ev", "force_rmse_ev_per_a", "wall_time_seconds"],
        } for task in plan["tasks"]],
        "approval": {
            "status": "pending_human_approval",
            "reviewer": "【待人工填写】",
            "approved_on": "",
            "allowed_external_runner": "【待人工填写】",
        },
        "measurement_environment": {
            "hardware_class": "[human review required: CPU/GPU node class]",
            "accelerator_or_cpu": "[human review required: device model or approved queue specification]",
            "parallelism": "[human review required: threads, GPUs or MPI ranks]",
            "numerical_precision": "[human review required: float64, float32 or mixed precision]",
            "timing_scope": "Wall time covers model inference only; excludes queueing, structure generation and reference calculation.",
        },        "result_import_contract": {
            "only_aggregate_numeric_rows": True,
            "rejects_structures_trajectories_logs_and_credentials": True,
            "requires_complete_task_model_matrix": True,
            "scientific_claim_boundary": "Imported comparison requires human scientific review; it does not by itself establish transferability.",
        },
    }


def potential_execution_protocol_sha256(payload: object) -> str:
    """Return a stable identifier after validating the protocol structure."""
    if not isinstance(payload, dict):
        raise PotentialProtocolError("potential execution protocol must be an object")
    return _sha256(payload)


def write_potential_execution_protocol(run_dir: Path, payload: object) -> Path:
    protocol = build_potential_execution_protocol(plan=_load_plan(run_dir), payload=payload)
    path = run_dir / "potential_execution_protocol.json"
    path.write_text(json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _load_plan(run_dir: Path) -> dict[str, Any]:
    try:
        plan = json.loads((run_dir / "potential_benchmark_plan.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PotentialProtocolError(f"cannot load potential benchmark plan: {error}") from error
    if not isinstance(plan, dict):
        raise PotentialProtocolError("potential benchmark plan must be an object")
    return plan


def _validate_plan(plan: object) -> None:
    if not isinstance(plan, dict) or plan.get("schema_version") != POTENTIAL_BENCHMARK_SCHEMA_VERSION:
        raise PotentialProtocolError("potential benchmark plan schema is invalid")
    if plan.get("trust_status") != "framework_test_plan_not_executed_calculation":
        raise PotentialProtocolError("potential benchmark plan is not a framework-only plan")
    if not isinstance(plan.get("potential_models"), list) or not isinstance(plan.get("tasks"), list):
        raise PotentialProtocolError("potential benchmark plan is incomplete")


def _validate_reference(value: object, plan: dict[str, Any]) -> None:
    if not isinstance(value, dict) or set(value) != _REFERENCE_FIELDS or value.get("method") != plan["reference_method"]:
        raise PotentialProtocolError("reference protocol is invalid or differs from the benchmark plan")
    for key in _REFERENCE_FIELDS:
        if not isinstance(value.get(key), str) or not value[key].strip() or len(value[key]) > 500:
            raise PotentialProtocolError("reference protocol fields must be non-empty text")
    if value["energy_unit"] != "eV" or value["force_unit"] != "eV/angstrom":
        raise PotentialProtocolError("reference protocol must use eV and eV/angstrom for the current result importer")


def _validate_models(value: object, plan: dict[str, Any]) -> None:
    if not isinstance(value, list) or len(value) != len(plan["potential_models"]):
        raise PotentialProtocolError("potential model disclosure is incomplete")
    found: set[str] = set()
    for model in value:
        if not isinstance(model, dict) or set(model) != _MODEL_FIELDS:
            raise PotentialProtocolError("potential model disclosure has unsupported or missing fields")
        model_id = model.get("model_id")
        if not isinstance(model_id, str) or model_id not in plan["potential_models"] or model_id in found:
            raise PotentialProtocolError("potential model identifiers must match the benchmark plan exactly once")
        found.add(model_id)
        for key in _MODEL_FIELDS - {"model_id"}:
            _safe_text(model.get(key), "potential model disclosure")


def _validate_structure_generation(value: object) -> None:
    if not isinstance(value, dict) or set(value) != _STRUCTURE_FIELDS:
        raise PotentialProtocolError("structure generation disclosure has unsupported or missing fields")
    for item in value.values():
        _safe_text(item, "structure generation disclosure")


def _validate_approval(value: object) -> None:
    if not isinstance(value, dict) or set(value) != _APPROVAL_FIELDS:
        raise PotentialProtocolError("approval record has unsupported or missing fields")
    if value.get("status") not in {"pending_human_approval", "approved_for_external_execution"}:
        raise PotentialProtocolError("approval status is invalid")
    for key in ("reviewer", "allowed_external_runner"):
        _safe_text(value.get(key), "approval record")
    if value["status"] == "pending_human_approval" and value.get("approved_on") != "":
        raise PotentialProtocolError("pending protocol must not claim an approval date")
    if value["status"] == "approved_for_external_execution":
        _safe_text(value.get("approved_on"), "approval record")


def _validate_measurement_environment(value: object) -> None:
    if not isinstance(value, dict) or set(value) != _MEASUREMENT_FIELDS:
        raise PotentialProtocolError("measurement environment has unsupported or missing fields")
    for item in value.values():
        _safe_text(item, "measurement environment")

def _validate_task_packets(value: object, plan: dict[str, Any]) -> None:
    if not isinstance(value, list) or len(value) != len(plan["tasks"]):
        raise PotentialProtocolError("task packets are incomplete")
    expected = {task["task_id"]: task for task in plan["tasks"]}
    for packet in value:
        if not isinstance(packet, dict) or set(packet) != {"task_id", "regime", "controls", "required_outputs"}:
            raise PotentialProtocolError("task packet has unsupported or missing fields")
        original = expected.get(packet.get("task_id"))
        if original is None or packet.get("regime") != original["regime"] or packet.get("controls") != original["controls"]:
            raise PotentialProtocolError("task packet must exactly retain benchmark plan coordinates")
        if packet.get("required_outputs") != ["atom_count", "reference_energy_ev", "predicted_energy_ev", "force_rmse_ev_per_a", "wall_time_seconds"]:
            raise PotentialProtocolError("task packet result fields do not match the importer contract")


def _validate_result_contract(value: object) -> None:
    required = {
        "only_aggregate_numeric_rows", "rejects_structures_trajectories_logs_and_credentials",
        "requires_complete_task_model_matrix", "scientific_claim_boundary",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise PotentialProtocolError("result import contract has unsupported or missing fields")
    if not all(value.get(key) is True for key in required - {"scientific_claim_boundary"}):
        raise PotentialProtocolError("result import contract safety flags must remain true")
    _safe_text(value.get("scientific_claim_boundary"), "result import contract")


def _safe_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise PotentialProtocolError(f"{field} must be non-empty text")
    lowered = value.casefold()
    if any(marker in lowered for marker in ("api_key", "authorization", "bearer ", "c:\\users\\", "/home/")):
        raise PotentialProtocolError(f"{field} must not include credentials or private paths")


def _sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
