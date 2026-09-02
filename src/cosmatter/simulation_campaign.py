"""Plan-only contracts for evidence-bound computational campaigns.

This module deliberately does *not* execute DFT, molecular dynamics, model
training, scheduler submission, or provider calls.  It records an approved
campaign boundary that an external laboratory may later implement under its
own controls.  The persisted record is intentionally small: no structures,
trajectories, commands, credentials, private paths, or numerical results are
accepted.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .models import MissionBrief
from .simulation_contracts import (
    SimulationContractError,
    canonical_sha256,
    contract_schema_versions,
    disabled_execution_profile,
    validate_execution_profile,
    validate_input_manifest,
    validate_simulation_hypothesis,
    validate_simulation_protocol,
)


SIMULATION_CAMPAIGN_SCHEMA_VERSION = "1.1"
SIMULATION_CAMPAIGN_TRUST_STATUS = "human_approved_simulation_campaign_plan_only"
SIMULATION_CAMPAIGN_STATE = "approved_plan_only"
SIMULATION_CAMPAIGN_BOUNDARY = (
    "CosMatter records an evidence-bound plan only. It does not submit jobs, "
    "run engines, poll schedulers, access credentials, or import raw calculation artifacts."
)

_CAMPAIGN_FIELDS = {
    "schema_version", "trust_status", "campaign_id", "mission_id", "simulation_kind",
    "evidence_ids", "hypothesis", "protocol", "input_manifest", "execution_profile",
    "contract_schema_versions", "contract_hashes", "approval", "execution_permitted", "execution_boundary",
}
_LEGACY_CAMPAIGN_FIELDS = {
    "schema_version", "trust_status", "campaign_id", "mission_id", "simulation_kind",
    "evidence_ids", "hypothesis", "protocol", "input_manifest", "execution_profile",
    "approval", "execution_permitted", "execution_boundary",
}
_HYPOTHESIS_FIELDS = {"statement", "variables", "control", "observable", "falsifier"}
_PROTOCOL_FIELDS = {
    "engine", "recipe_id", "method_boundary", "convergence_or_sampling_boundary",
    "result_summary_boundary",
}
_INPUT_MANIFEST_FIELDS = {"input_count", "inputs"}
_INPUT_FIELDS = {"input_id", "sha256", "source_kind", "license_status"}
_EXECUTION_PROFILE_FIELDS = {
    "mode", "adapter_kind", "allowed_engines", "allowed_recipe_ids", "max_jobs",
    "max_gpu_jobs", "max_dft_jobs", "scheduler_submission_enabled", "polling_enabled",
}
_APPROVAL_FIELDS = {"status", "reviewer", "approved_on", "rationale"}
_SIMULATION_KINDS = {"dft", "md", "potential_benchmark"}
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_TEXT = (
    "api_key", "apikey", "authorization", "bearer ", "password=", "token=",
    "c:\\users\\", "/home/", "\\\\", "sbatch", "qsub", "cmd.exe", "powershell", "bash -", "ssh ",
)


class SimulationCampaignError(ValueError):
    """Raised when a campaign crosses the plan-only execution boundary."""


def simulation_campaign_template(mission: MissionBrief) -> dict[str, Any]:
    """Return a non-approvable human-editable campaign template."""
    legacy = {
        "schema_version": "1.0",
        "trust_status": "human_authored_simulation_campaign_template_not_execution",
        "campaign_id": "campaign_pending_human_review",
        "mission_id": mission.mission_id,
        "simulation_kind": "dft",
        "evidence_ids": ["evidence_pending_human_review"],
        "hypothesis": {
            "statement": "【待人工填写：可证伪假设】",
            "variables": "【待人工填写：变量与范围】",
            "control": "【待人工填写：对照边界】",
            "observable": "【待人工填写：汇总观察量】",
            "falsifier": "【待人工填写：何种结果会否定假设】",
        },
        "protocol": {
            "engine": "【待人工填写：外部引擎名称；不会由 CosMatter 调用】",
            "recipe_id": "【待人工填写：已审阅配方标识】",
            "method_boundary": "【待人工填写：方法、近似与系统边界】",
            "convergence_or_sampling_boundary": "【待人工填写：收敛或采样边界】",
            "result_summary_boundary": "Only aggregate result rows may be recorded externally; raw structures, trajectories, logs and credentials stay outside CosMatter.",
        },
        "input_manifest": {"input_count": 0, "inputs": []},
        "execution_profile": _disabled_execution_profile(),
        "approval": {
            "status": "pending_human_approval", "reviewer": "【待人工填写】",
            "approved_on": "", "rationale": "【待人工填写：为何该证据边界足以计划计算】",
        },
        "execution_permitted": False,
        "execution_boundary": SIMULATION_CAMPAIGN_BOUNDARY,
    }
    return migrate_simulation_campaign(legacy)


def migrate_simulation_campaign(payload: object) -> dict[str, Any]:
    """Upgrade the original 1.0 aggregate record to explicit 1.1 contracts.

    Migration is deterministic and only succeeds for the former fixed
    plan-only profile. It never invents an execution capability or a result.
    """
    if not isinstance(payload, dict):
        raise SimulationCampaignError("simulation campaign must be an object")
    if payload.get("schema_version") == SIMULATION_CAMPAIGN_SCHEMA_VERSION:
        return deepcopy(payload)
    if payload.get("schema_version") != "1.0" or set(payload) != _LEGACY_CAMPAIGN_FIELDS:
        raise SimulationCampaignError("simulation campaign schema version is unsupported")
    legacy = deepcopy(payload)
    if legacy.get("execution_profile") != _disabled_execution_profile():
        raise SimulationCampaignError("legacy simulation campaign does not retain the fixed disabled profile")
    campaign_id = legacy.get("campaign_id")
    if not isinstance(campaign_id, str) or not _SAFE_ID.fullmatch(campaign_id):
        raise SimulationCampaignError("legacy campaign_id must be a safe identifier")
    evidence_ids = legacy.get("evidence_ids")
    if not isinstance(evidence_ids, list) or not all(isinstance(item, str) and _SAFE_ID.fullmatch(item) for item in evidence_ids):
        raise SimulationCampaignError("legacy evidence IDs are invalid")
    hypothesis = {
        "schema_version": "1.0", "artifact_id": f"{campaign_id}:hypothesis", "campaign_id": campaign_id,
        "evidence_ids": evidence_ids, **legacy["hypothesis"],
    }
    hypothesis_sha256 = canonical_sha256(hypothesis)
    protocol = {
        "schema_version": "1.0", "artifact_id": f"{campaign_id}:protocol", "campaign_id": campaign_id,
        "hypothesis_sha256": hypothesis_sha256, **legacy["protocol"],
    }
    protocol_sha256 = canonical_sha256(protocol)
    input_manifest = {
        "schema_version": "1.0", "artifact_id": f"{campaign_id}:input-manifest", "campaign_id": campaign_id,
        "protocol_sha256": protocol_sha256, **legacy["input_manifest"],
    }
    input_manifest_sha256 = canonical_sha256(input_manifest)
    execution_profile = disabled_execution_profile(campaign_id=campaign_id, input_manifest_sha256=input_manifest_sha256)
    return {
        **{key: value for key, value in legacy.items() if key not in {"hypothesis", "protocol", "input_manifest", "execution_profile", "schema_version"}},
        "schema_version": SIMULATION_CAMPAIGN_SCHEMA_VERSION,
        "hypothesis": hypothesis,
        "protocol": protocol,
        "input_manifest": input_manifest,
        "execution_profile": execution_profile,
        "contract_schema_versions": contract_schema_versions(),
        "contract_hashes": {
            "hypothesis_sha256": hypothesis_sha256,
            "protocol_sha256": protocol_sha256,
            "input_manifest_sha256": input_manifest_sha256,
            "execution_profile_sha256": canonical_sha256(execution_profile),
        },
    }


def build_approved_simulation_campaign(
    *, mission: MissionBrief, accepted_evidence_ids: set[str], payload: object
) -> dict[str, Any]:
    """Validate a human-approved campaign while enforcing default-deny execution."""
    normalized = _rebind_contracts_for_submission(migrate_simulation_campaign(payload))
    if set(normalized) != _CAMPAIGN_FIELDS:
        raise SimulationCampaignError("simulation campaign has unsupported or missing fields")
    if normalized.get("schema_version") != SIMULATION_CAMPAIGN_SCHEMA_VERSION:
        raise SimulationCampaignError("simulation campaign schema version is invalid")
    if normalized.get("trust_status") != SIMULATION_CAMPAIGN_TRUST_STATUS:
        raise SimulationCampaignError("simulation campaign trust status is invalid")
    _validate_normalized_campaign(normalized, mission_id=mission.mission_id, accepted_evidence_ids=accepted_evidence_ids)
    return normalized


def _rebind_contracts_for_submission(payload: dict[str, Any]) -> dict[str, Any]:
    """Refresh only deterministic technical bindings before human approval.

    The editable template intentionally cannot ask a reviewer to hand-compute
    four cascading SHA-256 values.  This helper never fills scientific fields
    and never repairs execution settings: altered profile values remain in the
    payload and are rejected by ``validate_execution_profile``.
    """
    if set(payload) != _CAMPAIGN_FIELDS:
        return payload
    candidate = deepcopy(payload)
    campaign_id = candidate.get("campaign_id")
    evidence_ids = candidate.get("evidence_ids")
    if not isinstance(campaign_id, str) or not _SAFE_ID.fullmatch(campaign_id) or not isinstance(evidence_ids, list):
        return candidate
    hypothesis = candidate.get("hypothesis")
    protocol = candidate.get("protocol")
    manifest = candidate.get("input_manifest")
    profile = candidate.get("execution_profile")
    if not all(isinstance(item, dict) for item in (hypothesis, protocol, manifest, profile)):
        return candidate
    hypothesis.update({"schema_version": "1.0", "artifact_id": f"{campaign_id}:hypothesis", "campaign_id": campaign_id, "evidence_ids": evidence_ids})
    hypothesis_sha256 = canonical_sha256(hypothesis)
    protocol.update({"schema_version": "1.0", "artifact_id": f"{campaign_id}:protocol", "campaign_id": campaign_id, "hypothesis_sha256": hypothesis_sha256})
    protocol_sha256 = canonical_sha256(protocol)
    manifest.update({"schema_version": "1.0", "artifact_id": f"{campaign_id}:input-manifest", "campaign_id": campaign_id, "protocol_sha256": protocol_sha256})
    input_manifest_sha256 = canonical_sha256(manifest)
    profile.update({"schema_version": "1.0", "artifact_id": f"{campaign_id}:execution-profile", "campaign_id": campaign_id, "input_manifest_sha256": input_manifest_sha256})
    candidate["contract_schema_versions"] = contract_schema_versions()
    candidate["contract_hashes"] = {
        "hypothesis_sha256": hypothesis_sha256, "protocol_sha256": protocol_sha256,
        "input_manifest_sha256": input_manifest_sha256, "execution_profile_sha256": canonical_sha256(profile),
    }
    return candidate


def write_approved_simulation_campaign(run_dir: Path, payload: dict[str, Any]) -> Path:
    """Persist one approved plan-only campaign without replacing its approval record."""
    path = run_dir / "simulation_campaign.json"
    if path.exists():
        raise SimulationCampaignError("approved simulation campaign already exists; create a new run for a new approval")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def deny_simulation_execution(payload: object, mission_id: str) -> dict[str, Any]:
    """Return the only P0 execution response: an auditable refusal.

    This function deliberately contains no adapter dispatch, subprocess, HTTP,
    scheduler, provider, or retry code.  Its existence keeps future callers
    from treating a missing endpoint as permission to bypass the campaign
    boundary.
    """
    projection = simulation_campaign_ui_projection(payload, mission_id)
    return {
        "execution_status": "denied_plan_only",
        "execution_permitted": False,
        "reason": projection["continuation_reason"],
        "budget": projection["budget"],
    }


def simulation_campaign_ui_projection(payload: object, mission_id: str) -> dict[str, Any]:
    """Return a minimal browser-safe status, never identifiers or protocols."""
    normalized = migrate_simulation_campaign(payload)
    evidence_ids = normalized.get("evidence_ids")
    if not isinstance(evidence_ids, list):
        raise SimulationCampaignError("simulation campaign evidence IDs are invalid")
    _validate_normalized_campaign(normalized, mission_id=mission_id, accepted_evidence_ids=set(evidence_ids))
    manifest = normalized["input_manifest"]
    input_count = manifest["input_count"]
    return {
        "delivery_status": SIMULATION_CAMPAIGN_STATE,
        "simulation_kind": normalized["simulation_kind"],
        "evidence_count": len(evidence_ids),
        "input_count": input_count,
        "execution_permitted": False,
        "execution_state": "blocked_plan_only",
        "chain": {"evidence": "bound", "hypothesis": "approved", "protocol": "approved", "execution": "blocked"},
        "missing_fields": [],
        "budget": {"max_jobs": 0, "max_gpu_jobs": 0, "max_dft_jobs": 0},
        "continuation_reason": "execution profile is intentionally disabled; no scheduler, engine, child process, or network request is available",
    }


def _disabled_execution_profile() -> dict[str, Any]:
    return {
        "mode": "disabled", "adapter_kind": "none", "allowed_engines": [], "allowed_recipe_ids": [],
        "max_jobs": 0, "max_gpu_jobs": 0, "max_dft_jobs": 0,
        "scheduler_submission_enabled": False, "polling_enabled": False,
    }


def _validate_normalized_campaign(payload: dict[str, Any], *, mission_id: str, accepted_evidence_ids: set[str]) -> None:
    if payload.get("mission_id") != mission_id:
        raise SimulationCampaignError("simulation campaign does not match the mission")
    if payload.get("trust_status") != SIMULATION_CAMPAIGN_TRUST_STATUS:
        raise SimulationCampaignError("simulation campaign is not an approved plan-only record")
    _safe_id(payload.get("campaign_id"), "campaign_id")
    if payload.get("simulation_kind") not in _SIMULATION_KINDS:
        raise SimulationCampaignError("simulation kind must be dft, md, or potential_benchmark")
    evidence_ids = payload.get("evidence_ids")
    _validate_evidence_ids(evidence_ids, accepted_evidence_ids)
    assert isinstance(evidence_ids, list)
    try:
        hypothesis = validate_simulation_hypothesis(payload.get("hypothesis"), campaign_id=payload["campaign_id"], evidence_ids=set(evidence_ids))
        hypothesis_sha256 = canonical_sha256(hypothesis)
        protocol = validate_simulation_protocol(payload.get("protocol"), campaign_id=payload["campaign_id"], hypothesis_sha256=hypothesis_sha256)
        protocol_sha256 = canonical_sha256(protocol)
        manifest = validate_input_manifest(payload.get("input_manifest"), campaign_id=payload["campaign_id"], protocol_sha256=protocol_sha256)
        input_manifest_sha256 = canonical_sha256(manifest)
        profile = validate_execution_profile(payload.get("execution_profile"), campaign_id=payload["campaign_id"], input_manifest_sha256=input_manifest_sha256)
    except SimulationContractError as error:
        raise SimulationCampaignError(str(error)) from error
    hashes = {
        "hypothesis_sha256": hypothesis_sha256, "protocol_sha256": protocol_sha256,
        "input_manifest_sha256": input_manifest_sha256, "execution_profile_sha256": canonical_sha256(profile),
    }
    if payload.get("contract_schema_versions") != contract_schema_versions() or payload.get("contract_hashes") != hashes:
        raise SimulationCampaignError("simulation campaign contract schema versions or hash bindings are invalid")
    _validate_approval(payload.get("approval"))
    if payload.get("execution_permitted") is not False:
        raise SimulationCampaignError("execution_permitted must remain false")
    if payload.get("execution_boundary") != SIMULATION_CAMPAIGN_BOUNDARY:
        raise SimulationCampaignError("simulation campaign execution boundary is invalid")


def _validate_evidence_ids(value: object, accepted: set[str]) -> None:
    if not isinstance(value, list) or not value or len(value) > 48 or not all(isinstance(item, str) for item in value):
        raise SimulationCampaignError("simulation campaign requires one to 48 accepted evidence IDs")
    if len(set(value)) != len(value) or any(item not in accepted for item in value):
        raise SimulationCampaignError("simulation campaign evidence IDs must be uniquely accepted for this mission")


def _validate_text_object(value: object, fields: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise SimulationCampaignError(f"{label} has unsupported or missing fields")
    for field, item in value.items():
        _safe_text(item, f"{label}.{field}")


def _validate_input_manifest(value: object) -> None:
    if not isinstance(value, dict) or set(value) != _INPUT_MANIFEST_FIELDS:
        raise SimulationCampaignError("input manifest has unsupported or missing fields")
    count, inputs = value.get("input_count"), value.get("inputs")
    if not isinstance(count, int) or isinstance(count, bool) or not isinstance(inputs, list) or not 1 <= count <= 100 or count != len(inputs):
        raise SimulationCampaignError("input manifest count must match one to 100 inputs")
    input_ids: set[str] = set()
    for item in inputs:
        if not isinstance(item, dict) or set(item) != _INPUT_FIELDS:
            raise SimulationCampaignError("input manifest entry has unsupported or missing fields")
        _safe_id(item.get("input_id"), "input_manifest.input_id")
        if item["input_id"] in input_ids:
            raise SimulationCampaignError("input manifest identifiers must be unique")
        input_ids.add(item["input_id"])
        if not isinstance(item.get("sha256"), str) or not _SHA256.fullmatch(item["sha256"]):
            raise SimulationCampaignError("input manifest sha256 must be lowercase hexadecimal")
        _safe_text(item.get("source_kind"), "input_manifest.source_kind")
        _safe_text(item.get("license_status"), "input_manifest.license_status")


def _validate_disabled_execution_profile(value: object) -> None:
    if not isinstance(value, dict) or set(value) != _EXECUTION_PROFILE_FIELDS or value != _disabled_execution_profile():
        raise SimulationCampaignError("execution profile must remain the fixed disabled profile")


def _validate_approval(value: object) -> None:
    if not isinstance(value, dict) or set(value) != _APPROVAL_FIELDS or value.get("status") != SIMULATION_CAMPAIGN_STATE:
        raise SimulationCampaignError("simulation campaign requires approved_plan_only human approval")
    for field in ("reviewer", "approved_on", "rationale"):
        _safe_text(value.get(field), f"approval.{field}")


def _safe_id(value: object, label: str) -> None:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise SimulationCampaignError(f"{label} must be a short safe identifier")


def _safe_text(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise SimulationCampaignError(f"{label} must be non-empty text of at most 500 characters")
    lowered = value.casefold()
    if "待人工填写" in value or "【" in value or any(marker in lowered for marker in _FORBIDDEN_TEXT):
        raise SimulationCampaignError(f"{label} must not contain placeholders, credentials, or private paths")
