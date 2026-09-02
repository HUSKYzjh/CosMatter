"""A local, deterministic stand-in for the first AiiDA execution trial.

It models only the approval and provenance state machine needed before a real
adapter can be considered.  No AiiDA package, network connection, subprocess,
queue, structure file, credential, or calculation code is used here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .simulation_campaign import SimulationCampaignError, simulation_campaign_ui_projection
from .simulation_contracts import canonical_sha256


class AiidaMockTrialError(ValueError):
    """Raised for an invalid mock-trial authorization or state transition."""


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_AUTH_FIELDS = {"schema_version", "trust_status", "artifact_id", "campaign_sha256", "adapter_kind", "recipe_id", "public_structure_ref", "max_jobs", "max_retries", "approval"}
_APPROVAL_FIELDS = {"status", "reviewer", "approved_on", "rationale"}
_STATE_FIELDS = {"schema_version", "trust_status", "artifact_id", "trial_sha256", "external_process_uuid", "status", "attempt", "transition_count", "provenance_boundary"}
_FORBIDDEN = ("api_key", "token=", "password=", "c:\\users\\", "/home/", "\\\\", "ssh ", "sbatch", "qsub", "powershell", "cmd.exe")


def approve_aiida_mock_trial(*, campaign: object, mission_id: str, payload: object) -> dict[str, Any]:
    """Validate the one-job public-fixture mock authorization."""
    try:
        simulation_campaign_ui_projection(campaign, mission_id)
    except SimulationCampaignError as error:
        raise AiidaMockTrialError(f"approved plan-only campaign is required: {error}") from error
    if not isinstance(payload, dict) or set(payload) != _AUTH_FIELDS:
        raise AiidaMockTrialError("AiiDA mock authorization has unsupported or missing fields")
    if payload.get("schema_version") != "1.0" or payload.get("trust_status") != "human_approved_aiida_mock_trial_not_real_execution":
        raise AiidaMockTrialError("AiiDA mock authorization schema or trust status is invalid")
    for name in ("artifact_id", "recipe_id", "public_structure_ref"):
        _identifier(payload.get(name), name)
    if payload.get("adapter_kind") != "aiida_mock" or payload.get("recipe_id") != "mock_relax_static_v1" or not str(payload.get("public_structure_ref", "")).startswith("public_fixture:"):
        raise AiidaMockTrialError("only the fixed public-fixture relax-static mock recipe is allowed")
    expected_campaign = canonical_sha256(campaign)
    if payload.get("campaign_sha256") != expected_campaign or not _SHA.fullmatch(str(payload.get("campaign_sha256"))):
        raise AiidaMockTrialError("AiiDA mock authorization is not bound to this campaign")
    if payload.get("max_jobs") != 1 or payload.get("max_retries") != 1:
        raise AiidaMockTrialError("AiiDA mock trial is fixed to one job and one retry")
    approval = payload.get("approval")
    if not isinstance(approval, dict) or set(approval) != _APPROVAL_FIELDS or approval.get("status") != "approved_mock_only":
        raise AiidaMockTrialError("AiiDA mock trial requires explicit mock-only human approval")
    for name, value in approval.items():
        _text(value, f"approval {name}")
    return dict(payload)


def new_mock_process(trial: object) -> dict[str, Any]:
    """Create a persisted mock process checkpoint; it does not submit anything."""
    auth = _validated_trial(trial)
    digest = canonical_sha256(auth)
    return {
        "schema_version": "1.0", "trust_status": "local_aiida_mock_process_not_real_execution",
        "artifact_id": f"{auth['artifact_id']}:process", "trial_sha256": digest,
        "external_process_uuid": f"mock-{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}",
        "status": "created", "attempt": 0, "transition_count": 0,
        "provenance_boundary": "Local state-machine fixture only; no AiiDA daemon, queue, engine, remote directory, credential, or calculation was contacted.",
    }


def advance_mock_process(*, trial: object, state: object, action: str) -> dict[str, Any]:
    """Apply submit/poll/cancel/retry/resume to the fixed local mock state machine."""
    auth = _validated_trial(trial)
    current = _validated_state(state, canonical_sha256(auth))
    transitions = {
        ("created", "submit"): "submitted", ("submitted", "poll"): "running", ("running", "poll"): "finished",
        ("created", "cancel"): "cancelled", ("submitted", "cancel"): "cancelled", ("running", "cancel"): "cancelled",
        ("failed", "retry"): "submitted",
    }
    if action == "resume":
        return dict(current)
    target = transitions.get((current["status"], action))
    if target is None:
        raise AiidaMockTrialError("AiiDA mock process action is invalid for its current state")
    if action == "retry" and current["attempt"] >= auth["max_retries"]:
        raise AiidaMockTrialError("AiiDA mock retry budget is exhausted")
    next_state = dict(current)
    next_state["status"] = target
    next_state["transition_count"] += 1
    if action == "retry":
        next_state["attempt"] += 1
    return next_state


def inject_mock_failure_for_test(*, trial: object, state: object) -> dict[str, Any]:
    """Deterministic test-only fault injection; never exposed as an execution API."""
    auth = _validated_trial(trial)
    current = _validated_state(state, canonical_sha256(auth))
    if current["status"] not in {"submitted", "running"}:
        raise AiidaMockTrialError("only an active mock process can receive a synthetic failure")
    failed = dict(current)
    failed["status"] = "failed"
    failed["transition_count"] += 1
    return failed


def write_mock_process(run_dir: Path, state: dict[str, Any]) -> Path:
    path = run_dir / "aiida_mock_process.json"
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_mock_trial(run_dir: Path, trial: dict[str, Any]) -> Path:
    path = run_dir / "aiida_mock_trial.json"
    if path.exists():
        raise AiidaMockTrialError("AiiDA mock authorization already exists; create a new run for another trial")
    path.write_text(json.dumps(trial, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _validated_trial(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _AUTH_FIELDS:
        raise AiidaMockTrialError("AiiDA mock authorization is invalid")
    # Its campaign binding was checked by approval; retain a strict standalone shape here.
    if value.get("schema_version") != "1.0" or value.get("trust_status") != "human_approved_aiida_mock_trial_not_real_execution" or value.get("adapter_kind") != "aiida_mock" or value.get("recipe_id") != "mock_relax_static_v1" or value.get("max_jobs") != 1 or value.get("max_retries") != 1 or not _SHA.fullmatch(str(value.get("campaign_sha256"))):
        raise AiidaMockTrialError("AiiDA mock authorization is invalid")
    return value


def _validated_state(value: object, trial_sha256: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _STATE_FIELDS or value.get("schema_version") != "1.0" or value.get("trust_status") != "local_aiida_mock_process_not_real_execution" or value.get("trial_sha256") != trial_sha256:
        raise AiidaMockTrialError("AiiDA mock process checkpoint is invalid")
    if value.get("status") not in {"created", "submitted", "running", "finished", "failed", "cancelled"} or not isinstance(value.get("attempt"), int) or not isinstance(value.get("transition_count"), int) or value["attempt"] < 0 or value["transition_count"] < 0:
        raise AiidaMockTrialError("AiiDA mock process state is invalid")
    _identifier(value.get("artifact_id"), "process artifact_id")
    _identifier(value.get("external_process_uuid"), "external process UUID")
    _text(value.get("provenance_boundary"), "provenance boundary")
    return value


def _identifier(value: object, label: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise AiidaMockTrialError(f"{label} must be a safe identifier")


def _text(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 600 or any(item in value.casefold() for item in _FORBIDDEN):
        raise AiidaMockTrialError(f"{label} is unsafe")
