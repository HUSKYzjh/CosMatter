"""Fixed, non-executing workflow-DAG declaration and readiness projection.

The declaration makes dependencies and data boundaries reviewable.  It is not
a scheduler: no command, provider request, model prompt, authorisation, retry,
or asynchronous work item can be represented or emitted here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import AGENT_ROOT
from .harness_catalog import default_cosmatter_plugin_catalogue
from .models import MissionBrief
from .stage_contract import StageContractError, stage_contract


WORKFLOW_DAG_SCHEMA_VERSION = "cosmatter.workflow-dag/v1"
WORKFLOW_DAG_TRUST_STATUS = "loopback_declared_dag_readiness_projection_not_execution_authorization"
_DEFINITION_SCHEMA_VERSION = "cosmatter.workflow-dag-definition/v1"
_DAG_ID = "cosmatter_review_gated_linear_workflow"
_STAGES = ("intake", "plan", "retrieval", "screening", "parse", "extraction", "gap", "report", "evaluation")
_STATUSES = {"completed", "ready", "waiting_human_review", "blocked"}
_EXECUTION_CLASSES = {"local_review_gated", "explicit_consent_required", "human_review_required"}
_CLASSIFICATIONS = {"mission", "public_metadata", "private_fulltext", "reviewable_excerpt", "accepted_evidence", "run_summary"}


class WorkflowDagError(ValueError):
    """Raised when a fixed DAG declaration or projection is malformed."""


def load_workflow_dag_definition() -> dict[str, Any]:
    """Load and validate the sole checked-in DAG declaration.

    The file is data, not a user-supplied recipe.  Its closed shape prevents it
    from becoming a general-purpose scheduler configuration surface.
    """
    path = AGENT_ROOT / "configs" / "cosmatter_workflow_dag.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorkflowDagError("workflow DAG definition is unavailable") from error
    validate_workflow_dag_definition(payload)
    return payload


def workflow_dag_projection(run_id: str, run_dir: Path, mission: MissionBrief) -> dict[str, Any]:
    """Project one locally-audited eligible stage, without scheduling it."""
    if not isinstance(run_id, str) or not run_id:
        raise WorkflowDagError("run_id is invalid")
    definition = load_workflow_dag_definition()
    try:
        contract = stage_contract(run_dir, mission)
    except StageContractError as error:
        raise WorkflowDagError(str(error)) from error
    stage_by_name = {item["stage"]: item for item in contract["stages"]}
    next_stage = contract["next_stage"]
    eligible = (
        [next_stage]
        if next_stage is not None
        and contract["runtime_safety"] == "verified"
        and stage_by_name[next_stage]["status"] == "ready"
        else []
    )
    result = {
        "schema_version": WORKFLOW_DAG_SCHEMA_VERSION,
        "run_id": run_id,
        "mission_id": mission.mission_id,
        "trust_status": WORKFLOW_DAG_TRUST_STATUS,
        "dag_id": definition["dag_id"],
        "max_concurrency": definition["max_concurrency"],
        "scheduler_status": "declarative_only_no_execution_authorization",
        "runtime_safety": contract["runtime_safety"],
        "eligible_stages": eligible,
        "blocked_stage_count": sum(item["status"] == "blocked" for item in contract["stages"]),
        "human_review_required": any(item["status"] == "waiting_human_review" for item in contract["stages"]),
        "stages": [
            {
                "stage": item["stage"],
                "depends_on": spec["depends_on"],
                "status": stage_by_name[item["stage"]]["status"],
                "allowed_descriptors": spec["allowed_descriptors"],
                "data_classification": spec["data_classification"],
                "execution_class": spec["execution_class"],
            }
            for item, spec in zip(contract["stages"], definition["stages"])
        ],
    }
    validate_workflow_dag_projection(result, expected_run_id=run_id, expected_mission_id=mission.mission_id)
    return result


def validate_workflow_dag_definition(payload: object) -> None:
    fields = {"schema_version", "dag_id", "execution_boundary", "max_concurrency", "stages"}
    if not isinstance(payload, dict) or set(payload) != fields:
        raise WorkflowDagError("workflow DAG definition fields are invalid")
    if payload.get("schema_version") != _DEFINITION_SCHEMA_VERSION or payload.get("dag_id") != _DAG_ID or payload.get("execution_boundary") != "declaration_and_readiness_projection_only" or payload.get("max_concurrency") != 1:
        raise WorkflowDagError("workflow DAG definition identity is invalid")
    stages = payload.get("stages")
    if not isinstance(stages, list) or len(stages) != len(_STAGES):
        raise WorkflowDagError("workflow DAG stages are invalid")
    descriptors = {item.plugin_id for item in default_cosmatter_plugin_catalogue()}
    previous: str | None = None
    for expected, item in zip(_STAGES, stages):
        fields = {"stage", "depends_on", "allowed_descriptors", "data_classification", "execution_class"}
        if not isinstance(item, dict) or set(item) != fields or item.get("stage") != expected:
            raise WorkflowDagError("workflow DAG stage identity is invalid")
        expected_dependencies = [] if previous is None else [previous]
        if item.get("depends_on") != expected_dependencies or not isinstance(item.get("allowed_descriptors"), list) or len(set(item["allowed_descriptors"])) != len(item["allowed_descriptors"]) or any(not isinstance(value, str) or value not in descriptors for value in item["allowed_descriptors"]):
            raise WorkflowDagError("workflow DAG dependencies or descriptors are invalid")
        if item.get("data_classification") not in _CLASSIFICATIONS or item.get("execution_class") not in _EXECUTION_CLASSES:
            raise WorkflowDagError("workflow DAG data boundary is invalid")
        previous = expected


def validate_workflow_dag_projection(payload: object, *, expected_run_id: str | None = None, expected_mission_id: str | None = None) -> None:
    fields = {"schema_version", "run_id", "mission_id", "trust_status", "dag_id", "max_concurrency", "scheduler_status", "runtime_safety", "eligible_stages", "blocked_stage_count", "human_review_required", "stages"}
    if not isinstance(payload, dict) or set(payload) != fields:
        raise WorkflowDagError("workflow DAG projection fields are invalid")
    if payload.get("schema_version") != WORKFLOW_DAG_SCHEMA_VERSION or payload.get("trust_status") != WORKFLOW_DAG_TRUST_STATUS or payload.get("dag_id") != _DAG_ID or payload.get("max_concurrency") != 1 or payload.get("scheduler_status") != "declarative_only_no_execution_authorization" or payload.get("runtime_safety") not in {"verified", "attention_required"}:
        raise WorkflowDagError("workflow DAG projection identity is invalid")
    if not isinstance(payload.get("run_id"), str) or not payload["run_id"] or (expected_run_id is not None and payload["run_id"] != expected_run_id) or not isinstance(payload.get("mission_id"), str) or not payload["mission_id"] or (expected_mission_id is not None and payload["mission_id"] != expected_mission_id):
        raise WorkflowDagError("workflow DAG projection identifiers are invalid")
    if not isinstance(payload.get("eligible_stages"), list) or len(payload["eligible_stages"]) > 1 or any(stage not in _STAGES for stage in payload["eligible_stages"]) or not isinstance(payload.get("blocked_stage_count"), int) or payload["blocked_stage_count"] < 0 or payload["blocked_stage_count"] > len(_STAGES) or not isinstance(payload.get("human_review_required"), bool):
        raise WorkflowDagError("workflow DAG projection status is invalid")
    definition = load_workflow_dag_definition()
    stages = payload.get("stages")
    if not isinstance(stages, list) or len(stages) != len(_STAGES):
        raise WorkflowDagError("workflow DAG projection stages are invalid")
    first_unfinished: str | None = None
    blocked = 0
    waiting = False
    for expected, item, spec in zip(_STAGES, stages, definition["stages"]):
        fields = {"stage", "depends_on", "status", "allowed_descriptors", "data_classification", "execution_class"}
        if not isinstance(item, dict) or set(item) != fields or item.get("stage") != expected or item.get("depends_on") != spec["depends_on"] or item.get("allowed_descriptors") != spec["allowed_descriptors"] or item.get("data_classification") != spec["data_classification"] or item.get("execution_class") != spec["execution_class"] or item.get("status") not in _STATUSES:
            raise WorkflowDagError("workflow DAG projection stage is invalid")
        if first_unfinished is None and item["status"] != "completed":
            first_unfinished = expected
        blocked += item["status"] == "blocked"
        waiting = waiting or item["status"] == "waiting_human_review"
    expected_eligible = [first_unfinished] if first_unfinished is not None and payload["runtime_safety"] == "verified" and next(item for item in stages if item["stage"] == first_unfinished)["status"] == "ready" else []
    if payload["eligible_stages"] != expected_eligible or payload["blocked_stage_count"] != blocked or payload["human_review_required"] != waiting:
        raise WorkflowDagError("workflow DAG projection does not match stage state")
