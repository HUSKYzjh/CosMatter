"""Read-only stage contracts for an auditable CosMatter run.

This module turns the existing readiness audit into a fixed, display-safe
control-plane view.  It deliberately describes *what must be true* before a
stage is complete; it never contains a question, candidate, URL, source text,
provider payload, credential, or a command that can execute a recovery step.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import MissionBrief
from .runtime_invariants import RuntimeInvariantError, audit_runtime_invariants
from .workflow_readiness import WorkflowReadinessError, workflow_readiness


STAGE_CONTRACT_SCHEMA_VERSION = "cosmatter.stage-contract/v1"
STAGE_CONTRACT_TRUST_STATUS = "loopback_stage_contract_not_scientific_evidence_or_execution_authorization"
_STAGES = ("intake", "plan", "retrieval", "screening", "parse", "extraction", "gap", "report", "evaluation")
_STATUSES = {"completed", "ready", "waiting_human_review", "blocked"}
_RUNTIME_SAFETY = {"verified", "attention_required"}
_STAGE_FIELDS = {"stage", "status", "completion_requirements", "human_gate", "expected_outputs", "recovery_route", "metrics"}

# These symbols are intentional UI/API contract values, not paths or commands.
# Keeping them fixed means a model cannot manufacture new recovery authority.
_CONTRACTS: dict[str, dict[str, Any]] = {
    "intake": {
        "completion_requirements": ("mission_boundary_recorded",),
        "human_gate": "mission_definition",
        "expected_outputs": ("mission_brief",),
        "recovery_route": "mission_boundary_review",
    },
    "plan": {
        "completion_requirements": ("approved_flight_plan",),
        "human_gate": "plan_approval",
        "expected_outputs": ("approved_flight_plan",),
        "recovery_route": "plan_review",
    },
    "retrieval": {
        "completion_requirements": ("approved_queries_executed", "provider_receipt_links_valid"),
        "human_gate": "mission_scoped_egress_consent",
        "expected_outputs": ("retrieval_candidate_history", "provider_receipt_links"),
        "recovery_route": "authorized_retrieval_review",
    },
    "screening": {
        "completion_requirements": ("candidate_fingerprint_current", "human_candidate_screening_complete"),
        "human_gate": "candidate_screening",
        "expected_outputs": ("candidate_screening_decision",),
        "recovery_route": "candidate_screening_review",
    },
    "parse": {
        "completion_requirements": ("fulltext_access_confirmed", "mineru_task_receipts_linked"),
        "human_gate": "content_access_and_parse_consent",
        "expected_outputs": ("source_parse_task_ledger",),
        "recovery_route": "content_access_review",
    },
    "extraction": {
        "completion_requirements": ("human_source_map_recorded", "human_evidence_decision_recorded"),
        "human_gate": "source_map_and_evidence_review",
        "expected_outputs": ("source_map", "material_fact", "verification_decision"),
        "recovery_route": "source_map_review",
    },
    "gap": {
        "completion_requirements": ("accepted_evidence_conditions_compared", "counterevidence_boundary_executed"),
        "human_gate": "gap_candidate_review",
        "expected_outputs": ("research_gap_candidate",),
        "recovery_route": "counterevidence_review",
    },
    "report": {
        "completion_requirements": ("review_gated_inputs_available", "report_audit_valid"),
        "human_gate": "report_review",
        "expected_outputs": ("review_gated_report",),
        "recovery_route": "report_audit_review",
    },
    "evaluation": {
        "completion_requirements": ("required_human_metric_families_complete",),
        "human_gate": "evaluation_review",
        "expected_outputs": ("human_evaluation_summary",),
        "recovery_route": "evaluation_review",
    },
}


class StageContractError(ValueError):
    """Raised only when the locally derived contract cannot be validated."""


def stage_contract(run_dir: Path, mission: MissionBrief) -> dict[str, Any]:
    """Derive a fixed contract view from local readiness and invariant audits.

    The invariant audit is intentionally reduced to a two-state safety signal.
    Detailed audit results remain local audit artifacts and are not copied into
    a model-visible control-plane projection.
    """
    try:
        readiness = workflow_readiness(run_dir, mission)
    except WorkflowReadinessError as error:
        raise StageContractError(str(error)) from error
    try:
        runtime_safety = "verified" if audit_runtime_invariants(run_dir, mission.mission_id)["passed"] else "attention_required"
    except RuntimeInvariantError:
        runtime_safety = "attention_required"
    result = {
        "schema_version": STAGE_CONTRACT_SCHEMA_VERSION,
        "mission_id": mission.mission_id,
        "trust_status": STAGE_CONTRACT_TRUST_STATUS,
        "next_stage": readiness["next_stage"],
        "runtime_safety": runtime_safety,
        "stages": [
            {
                "stage": item["stage"],
                "status": item["status"],
                "completion_requirements": list(_CONTRACTS[item["stage"]]["completion_requirements"]),
                "human_gate": _CONTRACTS[item["stage"]]["human_gate"],
                "expected_outputs": list(_CONTRACTS[item["stage"]]["expected_outputs"]),
                "recovery_route": _CONTRACTS[item["stage"]]["recovery_route"],
                "metrics": item["counts"],
            }
            for item in readiness["stages"]
        ],
    }
    validate_stage_contract(result, expected_mission_id=mission.mission_id)
    return result


def validate_stage_contract(payload: object, *, expected_mission_id: str | None = None) -> None:
    """Validate the closed, non-sensitive stage-contract schema."""
    fields = {"schema_version", "mission_id", "trust_status", "next_stage", "runtime_safety", "stages"}
    if not isinstance(payload, dict) or set(payload) != fields:
        raise StageContractError("stage contract fields are invalid")
    if payload.get("schema_version") != STAGE_CONTRACT_SCHEMA_VERSION or payload.get("trust_status") != STAGE_CONTRACT_TRUST_STATUS:
        raise StageContractError("stage contract identity is invalid")
    mission_id = payload.get("mission_id")
    if not isinstance(mission_id, str) or not mission_id.strip() or (expected_mission_id is not None and mission_id != expected_mission_id):
        raise StageContractError("stage contract mission is invalid")
    next_stage = payload.get("next_stage")
    if next_stage is not None and next_stage not in _STAGES:
        raise StageContractError("stage contract next stage is invalid")
    if payload.get("runtime_safety") not in _RUNTIME_SAFETY or not isinstance(payload.get("stages"), list) or len(payload["stages"]) != len(_STAGES):
        raise StageContractError("stage contract status is invalid")
    expected_next: str | None = None
    for expected, item in zip(_STAGES, payload["stages"]):
        if not isinstance(item, dict) or set(item) != _STAGE_FIELDS or item.get("stage") != expected or item.get("status") not in _STATUSES:
            raise StageContractError("stage contract stage is invalid")
        contract = _CONTRACTS[expected]
        if item.get("completion_requirements") != list(contract["completion_requirements"]) or item.get("human_gate") != contract["human_gate"] or item.get("expected_outputs") != list(contract["expected_outputs"]) or item.get("recovery_route") != contract["recovery_route"]:
            raise StageContractError("stage contract template is invalid")
        metrics = item.get("metrics")
        if not isinstance(metrics, dict) or not metrics or any(not isinstance(key, str) or not key or not isinstance(value, int) or value < 0 or value > 1_000_000 for key, value in metrics.items()):
            raise StageContractError("stage contract metrics are invalid")
        if expected_next is None and item["status"] != "completed":
            expected_next = expected
    if payload["next_stage"] != expected_next:
        raise StageContractError("stage contract next stage does not match readiness")
