"""Versioned, hash-bound contracts for a plan-only simulation campaign.

The contracts are data validators, not calculation adapters.  They do not
construct commands, open network connections, start child processes, or accept
raw structures and trajectories.  Receipt and reviewed-evidence validators are
defined now so their future P1 importer has a stable boundary, but P0 never
persists either kind of result.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any


CONTRACT_SCHEMA_VERSION = "1.0"
SIMULATION_CONTRACT_KINDS = (
    "simulation_hypothesis", "simulation_protocol", "input_manifest", "execution_profile",
    "external_run_receipt", "reviewed_simulation_evidence",
)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN = (
    "api_key", "apikey", "authorization", "bearer ", "password=", "token=", "c:\\users\\",
    "/home/", "\\\\", "sbatch", "qsub", "cmd.exe", "powershell", "bash -", "ssh ",
)


class SimulationContractError(ValueError):
    """Raised when a simulation contract exceeds the data-only boundary."""


def canonical_sha256(value: object) -> str:
    """Hash stable JSON without allowing caller-controlled serialisation."""
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def contract_schema_versions() -> dict[str, str]:
    return {kind: CONTRACT_SCHEMA_VERSION for kind in SIMULATION_CONTRACT_KINDS}


def validate_simulation_hypothesis(value: object, *, campaign_id: str, evidence_ids: set[str]) -> dict[str, Any]:
    fields = {"schema_version", "artifact_id", "campaign_id", "evidence_ids", "statement", "variables", "control", "observable", "falsifier"}
    _object_fields(value, fields, "simulation hypothesis")
    assert isinstance(value, dict)
    _version(value, "simulation hypothesis")
    _identifier(value.get("artifact_id"), "simulation hypothesis artifact_id")
    _equal(value.get("campaign_id"), campaign_id, "simulation hypothesis campaign_id")
    _evidence_ids(value.get("evidence_ids"), evidence_ids, "simulation hypothesis")
    for field in fields - {"schema_version", "artifact_id", "campaign_id", "evidence_ids"}:
        _text(value.get(field), f"simulation hypothesis {field}")
    return value


def validate_simulation_protocol(value: object, *, campaign_id: str, hypothesis_sha256: str) -> dict[str, Any]:
    fields = {"schema_version", "artifact_id", "campaign_id", "hypothesis_sha256", "engine", "recipe_id", "method_boundary", "convergence_or_sampling_boundary", "result_summary_boundary"}
    _object_fields(value, fields, "simulation protocol")
    assert isinstance(value, dict)
    _version(value, "simulation protocol")
    _identifier(value.get("artifact_id"), "simulation protocol artifact_id")
    _equal(value.get("campaign_id"), campaign_id, "simulation protocol campaign_id")
    _hash(value.get("hypothesis_sha256"), "simulation protocol hypothesis_sha256")
    _equal(value.get("hypothesis_sha256"), hypothesis_sha256, "simulation protocol hypothesis hash")
    for field in fields - {"schema_version", "artifact_id", "campaign_id", "hypothesis_sha256"}:
        _text(value.get(field), f"simulation protocol {field}")
    return value


def validate_input_manifest(value: object, *, campaign_id: str, protocol_sha256: str) -> dict[str, Any]:
    fields = {"schema_version", "artifact_id", "campaign_id", "protocol_sha256", "input_count", "inputs"}
    entry_fields = {"input_id", "sha256", "source_kind", "license_status"}
    _object_fields(value, fields, "input manifest")
    assert isinstance(value, dict)
    _version(value, "input manifest")
    _identifier(value.get("artifact_id"), "input manifest artifact_id")
    _equal(value.get("campaign_id"), campaign_id, "input manifest campaign_id")
    _hash(value.get("protocol_sha256"), "input manifest protocol_sha256")
    _equal(value.get("protocol_sha256"), protocol_sha256, "input manifest protocol hash")
    count, inputs = value.get("input_count"), value.get("inputs")
    if not isinstance(count, int) or isinstance(count, bool) or not isinstance(inputs, list) or not 1 <= count <= 100 or len(inputs) != count:
        raise SimulationContractError("input manifest count must exactly match one to 100 entries")
    identifiers: set[str] = set()
    for entry in inputs:
        _object_fields(entry, entry_fields, "input manifest entry")
        assert isinstance(entry, dict)
        _identifier(entry.get("input_id"), "input manifest input_id")
        if entry["input_id"] in identifiers:
            raise SimulationContractError("input manifest input_id values must be unique")
        identifiers.add(entry["input_id"])
        _hash(entry.get("sha256"), "input manifest input sha256")
        _text(entry.get("source_kind"), "input manifest source_kind")
        _text(entry.get("license_status"), "input manifest license_status")
    return value


def disabled_execution_profile(*, campaign_id: str, input_manifest_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "artifact_id": f"{campaign_id}:execution-profile",
        "campaign_id": campaign_id,
        "input_manifest_sha256": input_manifest_sha256,
        "mode": "disabled", "adapter_kind": "none", "allowed_engines": [], "allowed_recipe_ids": [],
        "max_jobs": 0, "max_gpu_jobs": 0, "max_dft_jobs": 0,
        "scheduler_submission_enabled": False, "polling_enabled": False,
    }


def validate_execution_profile(value: object, *, campaign_id: str, input_manifest_sha256: str) -> dict[str, Any]:
    fields = {"schema_version", "artifact_id", "campaign_id", "input_manifest_sha256", "mode", "adapter_kind", "allowed_engines", "allowed_recipe_ids", "max_jobs", "max_gpu_jobs", "max_dft_jobs", "scheduler_submission_enabled", "polling_enabled"}
    _object_fields(value, fields, "execution profile")
    assert isinstance(value, dict)
    _version(value, "execution profile")
    _identifier(value.get("artifact_id"), "execution profile artifact_id")
    _equal(value.get("campaign_id"), campaign_id, "execution profile campaign_id")
    _hash(value.get("input_manifest_sha256"), "execution profile input manifest sha256")
    _equal(value.get("input_manifest_sha256"), input_manifest_sha256, "execution profile input manifest hash")
    expected = disabled_execution_profile(campaign_id=campaign_id, input_manifest_sha256=input_manifest_sha256)
    if value != expected:
        raise SimulationContractError("execution profile must remain the fixed disabled, zero-budget profile")
    return value


def validate_external_run_receipt(value: object, *, campaign_id: str, input_manifest_sha256: str) -> dict[str, Any]:
    """Validate an imported, aggregate-only external result receipt.

    Version 1.0 is retained solely to validate legacy test fixtures.  Version
    1.1 is the P1 import boundary: it binds the protocol, declares one bounded
    result family, and accepts no paths, commands, raw files, or credentials.
    """
    if not isinstance(value, dict):
        raise SimulationContractError("external run receipt must be an object")
    if value.get("schema_version") == "1.1":
        return _validate_external_run_receipt_v11(value, campaign_id=campaign_id, input_manifest_sha256=input_manifest_sha256)
    fields = {"schema_version", "artifact_id", "campaign_id", "input_manifest_sha256", "external_run_id", "status", "output_summary_sha256", "exit_class", "resource_summary", "convergence_status"}
    _object_fields(value, fields, "external run receipt")
    assert isinstance(value, dict)
    _version(value, "external run receipt")
    for key in ("artifact_id", "external_run_id"):
        _identifier(value.get(key), f"external run receipt {key}")
    _equal(value.get("campaign_id"), campaign_id, "external run receipt campaign_id")
    _hash(value.get("input_manifest_sha256"), "external run receipt input manifest sha256")
    _equal(value.get("input_manifest_sha256"), input_manifest_sha256, "external run receipt input manifest hash")
    _hash(value.get("output_summary_sha256"), "external run receipt output summary sha256")
    if value.get("status") not in {"succeeded", "failed", "cancelled", "unknown"} or value.get("exit_class") not in {"completed", "failed", "cancelled", "unknown"}:
        raise SimulationContractError("external run receipt status is invalid")
    if value.get("convergence_status") not in {"converged", "not_converged", "not_applicable", "unknown"}:
        raise SimulationContractError("external run receipt convergence status is invalid")
    resource = value.get("resource_summary")
    if not isinstance(resource, dict) or set(resource) != {"cpu_seconds", "gpu_seconds", "job_count"}:
        raise SimulationContractError("external run receipt resource summary is invalid")
    for number in resource.values():
        if not isinstance(number, (int, float)) or isinstance(number, bool) or not math.isfinite(float(number)) or float(number) < 0:
            raise SimulationContractError("external run receipt resource values must be finite non-negative numbers")
    return value


def validate_reviewed_simulation_evidence(value: object, *, campaign_id: str, receipt_sha256: str) -> dict[str, Any]:
    """Validate a human review record without promoting it to an EvidenceCard."""
    if not isinstance(value, dict):
        raise SimulationContractError("reviewed simulation evidence must be an object")
    if value.get("schema_version") == "1.1":
        fields = {"schema_version", "artifact_id", "campaign_id", "receipt_sha256", "review_status", "relation_to_hypothesis", "applicability_boundary", "uncertainty", "reviewer", "reviewed_on", "evidencecard_gate"}
        _object_fields(value, fields, "reviewed simulation evidence")
        _identifier(value.get("artifact_id"), "reviewed simulation evidence artifact_id")
        _equal(value.get("campaign_id"), campaign_id, "reviewed simulation evidence campaign_id")
        _hash(value.get("receipt_sha256"), "reviewed simulation evidence receipt_sha256")
        _equal(value.get("receipt_sha256"), receipt_sha256, "reviewed simulation evidence receipt hash")
        if value.get("review_status") != "human_reviewed_pending_evidencecard_gate" or value.get("relation_to_hypothesis") not in {"supports", "contradicts", "uncertain"} or value.get("evidencecard_gate") != "not_submitted":
            raise SimulationContractError("reviewed simulation evidence remains outside the EvidenceCard gate")
        for field in ("applicability_boundary", "uncertainty", "reviewer", "reviewed_on"):
            _text(value.get(field), f"reviewed simulation evidence {field}")
        return value
    fields = {"schema_version", "artifact_id", "campaign_id", "receipt_sha256", "review_status", "relation_to_hypothesis", "applicability_boundary", "uncertainty", "reviewer", "reviewed_on"}
    _object_fields(value, fields, "reviewed simulation evidence")
    assert isinstance(value, dict)
    _version(value, "reviewed simulation evidence")
    _identifier(value.get("artifact_id"), "reviewed simulation evidence artifact_id")
    _equal(value.get("campaign_id"), campaign_id, "reviewed simulation evidence campaign_id")
    _hash(value.get("receipt_sha256"), "reviewed simulation evidence receipt sha256")
    _equal(value.get("receipt_sha256"), receipt_sha256, "reviewed simulation evidence receipt hash")
    if value.get("review_status") != "human_reviewed_pending_evidencecard_gate" or value.get("relation_to_hypothesis") not in {"supports", "contradicts", "uncertain"}:
        raise SimulationContractError("reviewed simulation evidence remains a human-reviewed non-EvidenceCard record")
    for field in ("applicability_boundary", "uncertainty", "reviewer", "reviewed_on"):
        _text(value.get(field), f"reviewed simulation evidence {field}")
    return value


def _validate_external_run_receipt_v11(value: dict[str, Any], *, campaign_id: str, input_manifest_sha256: str) -> dict[str, Any]:
    fields = {"schema_version", "artifact_id", "campaign_id", "input_manifest_sha256", "protocol_sha256", "external_run_id", "status", "output_summary_sha256", "exit_class", "resource_summary", "convergence_status", "result_kind", "metrics", "external_execution_assertion"}
    _object_fields(value, fields, "external run receipt")
    for key in ("artifact_id", "external_run_id"):
        _identifier(value.get(key), f"external run receipt {key}")
    _equal(value.get("campaign_id"), campaign_id, "external run receipt campaign_id")
    for field, expected in (("input_manifest_sha256", input_manifest_sha256),):
        _hash(value.get(field), f"external run receipt {field}")
        _equal(value.get(field), expected, f"external run receipt {field}")
    _hash(value.get("protocol_sha256"), "external run receipt protocol_sha256")
    _hash(value.get("output_summary_sha256"), "external run receipt output_summary_sha256")
    if value.get("status") != "succeeded" or value.get("exit_class") != "completed" or value.get("convergence_status") not in {"converged", "not_applicable"}:
        raise SimulationContractError("P1 external run receipt must be a completed, converged or not-applicable aggregate result")
    resource = value.get("resource_summary")
    if not isinstance(resource, dict) or set(resource) != {"cpu_seconds", "gpu_seconds", "job_count"}:
        raise SimulationContractError("external run receipt resource summary is invalid")
    for number in resource.values():
        if not isinstance(number, (int, float)) or isinstance(number, bool) or not math.isfinite(float(number)) or float(number) < 0:
            raise SimulationContractError("external run receipt resource values must be finite non-negative numbers")
    kind = value.get("result_kind")
    metrics = value.get("metrics")
    required = {
        "energy_force_summary": {"sample_count", "energy_mae_ev_per_atom", "force_rmse_ev_per_a"},
        "relaxation_summary": {"ionic_steps", "initial_energy_ev", "final_energy_ev", "max_force_ev_per_a"},
        "md_aggregate_summary": {"sample_count", "mean_temperature_k", "temperature_std_k", "mean_total_energy_ev"},
    }
    if kind not in required or not isinstance(metrics, dict) or set(metrics) != required[kind]:
        raise SimulationContractError("external run receipt result kind or aggregate metrics are invalid")
    for field, number in metrics.items():
        if not isinstance(number, (int, float)) or isinstance(number, bool) or not math.isfinite(float(number)):
            raise SimulationContractError(f"external run receipt metric {field} must be finite")
        if field in {"sample_count", "ionic_steps"} and (int(number) != number or number < 1):
            raise SimulationContractError(f"external run receipt metric {field} must be a positive integer")
        if field in {"energy_mae_ev_per_atom", "force_rmse_ev_per_a", "max_force_ev_per_a", "temperature_std_k"} and number < 0:
            raise SimulationContractError(f"external run receipt metric {field} must be non-negative")
    _equal(value.get("external_execution_assertion"), "external_result_imported_read_only_not_cosmatter_execution", "external execution assertion")
    return value


def _object_fields(value: object, fields: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise SimulationContractError(f"{label} has unsupported or missing fields")


def _version(value: dict[str, Any], label: str) -> None:
    if value.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise SimulationContractError(f"{label} schema version is invalid")


def _identifier(value: object, label: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise SimulationContractError(f"{label} must be a safe identifier")


def _hash(value: object, label: str) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise SimulationContractError(f"{label} must be a lowercase SHA-256")


def _equal(value: object, expected: object, label: str) -> None:
    if value != expected:
        raise SimulationContractError(f"{label} does not match its bound upstream contract")


def _evidence_ids(value: object, allowed: set[str], label: str) -> None:
    if not isinstance(value, list) or not value or len(value) > 48 or not all(isinstance(item, str) and _ID.fullmatch(item) for item in value):
        raise SimulationContractError(f"{label} requires one to 48 safe evidence IDs")
    if len(set(value)) != len(value) or not set(value).issubset(allowed):
        raise SimulationContractError(f"{label} evidence IDs must be uniquely accepted for this mission")


def _text(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise SimulationContractError(f"{label} must be non-empty text of at most 500 characters")
    lowered = value.casefold()
    if "待人工填写" in value or "【" in value or any(marker in lowered for marker in _FORBIDDEN):
        raise SimulationContractError(f"{label} must not contain placeholders, credentials, private paths, or command templates")
