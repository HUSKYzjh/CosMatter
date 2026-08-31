"""Compact, artifact-only readiness audit for the literature-agent workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .candidate_screening import CandidateScreeningError, load_candidate_screening, screening_matches_candidates
from .content_access import ContentAccessError, has_sciverse_content_access
from .gap_analysis import GapAnalysisError, load_gap_candidates
from .models import MissionBrief
from .planning import PlanApprovalError, load_approved_flight_plan
from .provider_receipts import ProviderReceiptError, audit_candidate_receipt_links, audit_source_parse_receipt_links
from .source_parse import SourceParseArtifactError, load_source_parse_tasks


class WorkflowReadinessError(ValueError):
    pass


_STAGES = ("intake", "plan", "retrieval", "screening", "parse", "extraction", "gap", "report", "evaluation")
_STATUS = {"completed", "ready", "waiting_human_review", "blocked"}


def workflow_readiness(run_dir: Path, mission: MissionBrief) -> dict[str, Any]:
    """Summarize what actually exists; it never executes a provider or reads text."""
    plan = _plan(run_dir, mission)
    retrieval = _retrieval(run_dir, plan)
    screening = _screening(run_dir, mission, retrieval)
    parse = _parse_progress(run_dir, mission.mission_id)
    map_count = _document_count(run_dir / "source_maps", "mission_id", mission.mission_id)
    fact_count = _fact_count(run_dir / "material_facts", mission.mission_id)
    gap = _gap_progress(run_dir / "research_gap_candidates.json")
    gap_count = gap["counts"]["gap_candidate_count"]
    accepted_evidence_count = _accepted_evidence_count(run_dir / "verification_decisions.json", mission.mission_id)
    report = _report_progress(run_dir, mission.mission_id)
    evaluation = _evaluation_progress(
        run_dir,
        mission.mission_id,
        accepted_evidence_count=accepted_evidence_count,
        retrieval_completed=retrieval["status"] == "completed",
        fact_count=fact_count,
        gap_count=gap_count if gap["status"] == "completed" else 0,
        corpus_manifest_present=(run_dir / "corpus_manifest.json").exists(),
    )
    gap_status = gap["status"] if gap["status"] == "blocked" else (
        "completed" if gap_count else ("ready" if fact_count and retrieval["status"] == "completed" else "blocked")
    )
    parse_status = parse["status"] if parse["task_count"] else _next_parse_status(screening)
    stages = [
        _stage("intake", "completed", {"mission_artifact_count": 1}),
        _stage("plan", plan["status"], plan["counts"]),
        _stage("retrieval", retrieval["status"], retrieval["counts"]),
        _stage("screening", screening["status"], screening["counts"]),
        _stage("parse", parse_status, parse["counts"]),
        _stage("extraction", "completed" if fact_count else ("waiting_human_review" if map_count else "blocked"), {"source_map_document_count": map_count, "fact_document_count": fact_count}),
        _stage("gap", gap_status, {**gap["counts"], "llm_draft_present": int((run_dir / "research_gap_draft.json").exists())}),
        _stage("report", report["status"] if report["status"] == "blocked" else ("completed" if report["status"] == "completed" else ("ready" if gap_status == "completed" else "blocked")), report["counts"]),
        _stage("evaluation", evaluation["status"], evaluation["counts"]),
    ]
    return {
        "schema_version": "1.0",
        "mission_id": mission.mission_id,
        "trust_status": "derived_workflow_readiness_not_scientific_evidence",
        "stages": stages,
        "next_stage": next((item["stage"] for item in stages if item["status"] != "completed"), None),
    }


def write_workflow_readiness(run_dir: Path, artifact: dict[str, Any]) -> Path:
    _validate(artifact)
    path = run_dir / "workflow_readiness.json"
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def continuation_next_stage(artifact: object, mission_id: str) -> str:
    """Return the audited continuation stage carried by a safe run package.

    A continuation package may deliberately omit private parse caches and raw
    provider receipts. It therefore resumes from the readiness snapshot
    audited before export, instead of recomputing a misleadingly earlier state.
    """
    _validate(artifact)
    if artifact["mission_id"] != mission_id:
        raise WorkflowReadinessError("workflow readiness mission does not match run package mission")
    next_stage = artifact["next_stage"]
    if next_stage is not None and next_stage not in _STAGES:
        raise WorkflowReadinessError("workflow readiness next stage is invalid")
    return next_stage or "evaluation"


def _plan(run_dir: Path, mission: MissionBrief) -> dict[str, Any]:
    try:
        plan = load_approved_flight_plan(run_dir, mission.mission_id)
    except PlanApprovalError:
        return {"status": "waiting_human_review", "counts": {"primary_query_count": 0, "counter_query_count": 0}, "plan": None}
    return {"status": "completed", "counts": {"primary_query_count": len(plan.queries), "counter_query_count": len(plan.counter_queries)}, "plan": plan}


def _retrieval(run_dir: Path, plan_info: dict[str, Any]) -> dict[str, Any]:
    plan = plan_info["plan"]
    if plan is None:
        return {"status": "blocked", "counts": {"candidate_count": 0, "primary_queries_executed": 0, "counter_queries_executed": 0}, "payload": None}
    payload = _candidate_history(run_dir / "retrieval_candidates.json")
    if payload is None:
        return {"status": "ready", "counts": {"candidate_count": 0, "primary_queries_executed": 0, "counter_queries_executed": 0, "provider_linked_origin_count": 0, "provider_receipt_link_valid": 1}, "payload": None}
    executed = {item["query"] for item in payload["searches"]}
    primary = len(set(plan.queries) & executed)
    counter = len(set(plan.counter_queries) & executed)
    try:
        receipt_audit = audit_candidate_receipt_links(payload, run_dir / "provider_receipts.jsonl")
        receipt_valid = 1
        provider_origins = receipt_audit["provider_linked_origin_count"]
    except ProviderReceiptError:
        receipt_valid = 0
        provider_origins = _provider_linked_origin_count(payload)
    complete = primary == len(plan.queries) and counter == len(plan.counter_queries)
    return {"status": "blocked" if not receipt_valid else ("completed" if complete else "ready"), "counts": {"candidate_count": len(payload["candidates"]), "primary_queries_executed": primary, "counter_queries_executed": counter, "provider_linked_origin_count": provider_origins, "provider_receipt_link_valid": receipt_valid}, "payload": payload}


def _screening(run_dir: Path, mission: MissionBrief, retrieval: dict[str, Any]) -> dict[str, Any]:
    payload = retrieval["payload"]
    if payload is None:
        return {"status": "blocked", "counts": {"candidate_count": 0, "included_for_fulltext_count": 0}}
    identifiers = {item["document_id"] for item in payload["candidates"]}
    try:
        artifact = load_candidate_screening(run_dir / "candidate_screening.json", mission.mission_id)
    except CandidateScreeningError:
        return {"status": "blocked", "counts": {"candidate_count": len(identifiers), "included_for_fulltext_count": 0, "candidate_fingerprint_current": 0}}
    if artifact is None or not screening_matches_candidates(artifact, payload):
        return {"status": "waiting_human_review", "counts": {"candidate_count": len(identifiers), "included_for_fulltext_count": 0, "candidate_fingerprint_current": 0}}
    included = {
        item["document_id"]
        for item in artifact["decisions"]
        if item["decision"] == "include_for_fulltext"
    }
    upstream_accessible = {
        item["document_id"]
        for item in payload["candidates"]
        if item["document_id"] in included and item.get("is_content_accessible") is True
    }
    try:
        confirmed = {
            document_id
            for document_id in included - upstream_accessible
            if has_sciverse_content_access(
                run_dir,
                mission_id=mission.mission_id,
                candidate_payload=payload,
                document_id=document_id,
            )
        }
    except ContentAccessError:
        return {
            "status": "blocked",
            "counts": {
                "candidate_count": len(identifiers),
                "included_for_fulltext_count": len(included),
                "candidate_fingerprint_current": 1,
                "upstream_content_accessible_count": len(upstream_accessible),
                "confirmed_content_access_count": 0,
                "fulltext_eligible_count": len(upstream_accessible),
                "content_access_confirmation_valid": 0,
            },
        }
    return {
        "status": "completed",
        "counts": {
            "candidate_count": len(identifiers),
            "included_for_fulltext_count": len(included),
            "candidate_fingerprint_current": 1,
            "upstream_content_accessible_count": len(upstream_accessible),
            "confirmed_content_access_count": len(confirmed),
            "fulltext_eligible_count": len(upstream_accessible | confirmed),
            "content_access_confirmation_valid": 1,
        },
    }


def _next_parse_status(screening: dict[str, Any]) -> str:
    if screening["status"] != "completed":
        return "blocked"
    if screening["counts"].get("fulltext_eligible_count", 0):
        return "ready"
    if screening["counts"].get("included_for_fulltext_count", 0):
        return "waiting_human_review"
    return "blocked"


def _candidate_history(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise WorkflowReadinessError("retrieval candidate artifact is invalid JSON") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("candidates"), list) or not isinstance(payload.get("searches"), list):
        raise WorkflowReadinessError("retrieval candidate artifact is invalid")
    candidates = payload["candidates"]
    searches = payload["searches"]
    if any(not isinstance(item, dict) or not isinstance(item.get("document_id"), str) or not item["document_id"].strip() for item in candidates) or any(not isinstance(item, dict) or not isinstance(item.get("query"), str) or not item["query"].strip() for item in searches):
        raise WorkflowReadinessError("retrieval candidate history is invalid")
    return payload


def _provider_linked_origin_count(payload: dict[str, Any]) -> int:
    count = 0
    for candidate in payload["candidates"]:
        origins = candidate.get("retrieval_origins", []) if isinstance(candidate, dict) else []
        if isinstance(origins, list):
            count += sum(isinstance(item, dict) and item.get("receipt_id") is not None for item in origins)
    return count


def _parse_progress(run_dir: Path, mission_id: str) -> dict[str, Any]:
    """Require a completed MinerU ledger and its matching hash-only receipts."""
    path = run_dir / "source_parse_tasks.json"
    try:
        artifact = load_source_parse_tasks(path, mission_id)
    except SourceParseArtifactError as error:
        raise WorkflowReadinessError("source parse task ledger is invalid") from error
    if artifact is None:
        return {"status": "ready", "task_count": 0, "counts": {"task_count": 0, "done_task_count": 0, "active_task_count": 0, "failed_task_count": 0, "parse_receipt_link_valid": 1}}
    states = [item["state"] for item in artifact["tasks"]]
    done = states.count("done")
    active = states.count("pending") + states.count("running")
    failed = states.count("failed")
    try:
        receipt_audit = audit_source_parse_receipt_links(artifact, run_dir / "provider_receipts.jsonl")
        receipt_valid = int(
            receipt_audit["receipt_linked_task_count"] == len(states)
            and receipt_audit["stale_task_state_count"] == 0
            and receipt_audit["unlinked_task_count"] == 0
        )
    except ProviderReceiptError:
        receipt_valid = 0
    status = "blocked" if failed or not receipt_valid else ("completed" if done and not active else "ready")
    return {"status": status, "task_count": len(states), "counts": {"task_count": len(states), "done_task_count": done, "active_task_count": active, "failed_task_count": failed, "parse_receipt_link_valid": receipt_valid}}


_EVALUATION_ARTIFACTS = {
    "evidence_quality": (
        "human_evidence_quality_evaluation.json",
        "1.0",
        "metrics_from_human_reviewed_evidence_locator_condition_and_contradiction_audit",
        {"schema_version", "mission_id", "trust_status", "evidence_count", "predicted_contradiction_count", "citation_precision", "condition_completeness", "contradiction_precision"},
    ),
    "retrieval": (
        "human_retrieval_evaluation.json",
        "1.1",
        "metrics_from_human_reviewed_gold_standard",
        {"schema_version", "mission_id", "corpus_id", "trust_status", "identity_resolution_policy", "search_index", "k", "raw_retrieved_count", "retrieved_count", "doi_resolved_candidate_count", "duplicate_alias_count", "gold_relevant_count", "gold_partially_relevant_count", "precision_at_k", "recall_at_k", "ndcg_at_k"},
    ),
    "material_facts": (
        "human_material_fact_evaluation.json",
        "1.0",
        "metrics_for_review_gated_material_fact_pipeline_not_raw_llm_accuracy",
        {"schema_version", "mission_id", "corpus_id", "trust_status", "gold_fact_count", "reviewed_fact_count", "exact_match_count", "precision", "recall", "f1", "unit_match_denominator", "unit_match_accuracy"},
    ),
    "research_gaps": (
        "human_gap_evaluation.json",
        "1.1",
        "metrics_from_human_expert_review_of_evidence_bound_gap_candidates",
        {"schema_version", "mission_id", "trust_status", "candidate_count", "expert_approval_rate", "mean_novelty_rating", "mean_actionability_rating", "evidence_completeness_rate", "counterevidence_review_rate", "bounded_no_direct_match_rate", "related_prior_work_found_rate", "inconclusive_novelty_search_rate"},
    ),
}


def _report_progress(run_dir: Path, mission_id: str) -> dict[str, Any]:
    """Require the persisted report to have a current, schema-valid evidence audit."""
    manifest_present = (run_dir / "mission_report.json").is_file()
    structured_present = (run_dir / "research_report.md").is_file()
    audit_path = run_dir / "report_evidence_audit.json"
    counts = {
        "evidence_manifest_present": int(manifest_present),
        "structured_report_present": int(structured_present),
        "report_evidence_audit_present": int(audit_path.is_file()),
        "report_evidence_audit_valid": 0,
    }
    if not manifest_present or not structured_present:
        return {"status": "ready", "counts": counts}
    if not audit_path.is_file():
        return {"status": "ready", "counts": counts}
    try:
        payload = json.loads(audit_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "blocked", "counts": counts}
    expected = {
        "schema_version", "mission_id", "report_id", "trust_status",
        "accepted_evidence_count", "manifest_evidence_count",
        "accepted_evidence_manifest_coverage", "research_gap_candidate_count",
        "gap_evidence_reference_count", "gap_evidence_accepted_coverage",
        "structured_report_identifier_coverage", "accepted_evidence_locator_rendered_coverage",
        "reviewed_material_fact_count", "reviewed_material_fact_rendered_coverage",
        "cross_document_comparison_count", "comparison_observation_reference_count",
        "comparison_observation_rendered_coverage",
        "executed_gap_counterevidence_boundary_count", "gap_counterevidence_boundary_rendered_coverage",
        "human_source_locator_review_required",
    }
    valid = (
        isinstance(payload, dict)
        and set(payload) == expected
        and payload.get("schema_version") == "1.3"
        and payload.get("mission_id") == mission_id
        and payload.get("trust_status") == "artifact_level_identifier_audit_not_scientific_validity_assessment"
    )
    if not valid:
        return {"status": "blocked", "counts": counts}
    counts["report_evidence_audit_valid"] = 1
    return {"status": "completed", "counts": counts}


def _gap_progress(path: Path) -> dict[str, Any]:
    """Count only persisted Gap candidates with executed counterevidence proof."""
    base_counts = {
        "gap_candidate_count": 0,
        "executed_counterevidence_boundary_count": 0,
        "gap_artifact_valid": 0,
    }
    if not path.exists():
        return {"status": "ready", "counts": base_counts}
    try:
        candidates = load_gap_candidates(path)
    except GapAnalysisError:
        return {"status": "blocked", "counts": base_counts}
    expected_status = "all_approved_counterevidence_queries_recorded"
    executed = sum(
        candidate.counterevidence_boundary is not None
        and candidate.counterevidence_boundary.status == expected_status
        for candidate in candidates
    )
    if not candidates or executed != len(candidates):
        return {"status": "blocked", "counts": base_counts}
    return {
        "status": "completed",
        "counts": {
            "gap_candidate_count": len(candidates),
            "executed_counterevidence_boundary_count": executed,
            "gap_artifact_valid": 1,
        },
    }


def _accepted_evidence_count(path: Path, mission_id: str) -> int:
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise WorkflowReadinessError("verification decision artifact is invalid JSON") from error
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise WorkflowReadinessError("verification decision artifact is invalid")
    return sum(item.get("mission_id") == mission_id and item.get("status") == "accepted" for item in payload)


def _evaluation_progress(
    run_dir: Path,
    mission_id: str,
    *,
    accepted_evidence_count: int,
    retrieval_completed: bool,
    fact_count: int,
    gap_count: int,
    corpus_manifest_present: bool,
) -> dict[str, Any]:
    """Make unfinished human evaluation visible without fabricating a score."""
    required = {
        "evidence_quality": accepted_evidence_count > 0,
        "retrieval": corpus_manifest_present and retrieval_completed,
        "material_facts": corpus_manifest_present and fact_count > 0,
        "research_gaps": gap_count > 0,
    }
    valid: dict[str, bool] = {}
    invalid = 0
    for name, (filename, schema_version, trust_status, fields) in _EVALUATION_ARTIFACTS.items():
        path = run_dir / filename
        if not path.exists():
            valid[name] = False
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            valid[name] = False
            invalid += 1
            continue
        is_valid = (
            isinstance(payload, dict)
            and set(payload) == fields
            and payload.get("schema_version") == schema_version
            and payload.get("mission_id") == mission_id
            and payload.get("trust_status") == trust_status
        )
        valid[name] = is_valid
        invalid += int(not is_valid)
    required_count = sum(required.values())
    completed_count = sum(required[name] and valid[name] for name in required)
    status = "blocked" if invalid else ("completed" if required_count and completed_count == required_count else ("waiting_human_review" if required_count else "blocked"))
    return {
        "status": status,
        "counts": {
            "required_metric_family_count": required_count,
            "completed_metric_family_count": completed_count,
            "invalid_metric_artifact_count": invalid,
            "evidence_quality_evaluation_present": int(valid["evidence_quality"]),
            "retrieval_evaluation_present": int(valid["retrieval"]),
            "material_fact_evaluation_present": int(valid["material_facts"]),
            "gap_evaluation_present": int(valid["research_gaps"]),
        },
    }


def _task_count(path: Path, mission_id: str) -> int:
    return _array_field_count(path, mission_id, "tasks")


def _document_count(directory: Path, mission_field: str, mission_id: str) -> int:
    return sum(_object_has_mission(path, mission_field, mission_id) for path in directory.glob("*.json")) if directory.exists() else 0


def _fact_count(directory: Path, mission_id: str) -> int:
    return sum(_object_has_mission(path, "mission_id", mission_id) for path in directory.glob("*.json")) if directory.exists() else 0


def _array_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise WorkflowReadinessError("workflow artifact is invalid JSON") from error
    if not isinstance(payload, list):
        raise WorkflowReadinessError("workflow artifact is invalid")
    return len(payload)


def _array_field_count(path: Path, mission_id: str, field: str) -> int:
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise WorkflowReadinessError("workflow artifact is invalid JSON") from error
    if not isinstance(payload, dict) or payload.get("mission_id") != mission_id or not isinstance(payload.get(field), list):
        raise WorkflowReadinessError("workflow artifact is invalid")
    return len(payload[field])


def _object_has_mission(path: Path, field: str, mission_id: str) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and payload.get(field) == mission_id


def _stage(stage: str, status: str, counts: dict[str, int]) -> dict[str, Any]:
    return {"stage": stage, "status": status, "counts": counts}


def _validate(artifact: object) -> None:
    if not isinstance(artifact, dict) or set(artifact) != {"schema_version", "mission_id", "trust_status", "stages", "next_stage"} or artifact.get("schema_version") != "1.0" or artifact.get("trust_status") != "derived_workflow_readiness_not_scientific_evidence":
        raise WorkflowReadinessError("workflow readiness artifact is invalid")
    if not isinstance(artifact.get("mission_id"), str) or not isinstance(artifact.get("stages"), list) or len(artifact["stages"]) != len(_STAGES):
        raise WorkflowReadinessError("workflow readiness identity is invalid")
    for expected, item in zip(_STAGES, artifact["stages"]):
        if not isinstance(item, dict) or set(item) != {"stage", "status", "counts"} or item.get("stage") != expected or item.get("status") not in _STATUS or not isinstance(item.get("counts"), dict) or any(not isinstance(value, int) or value < 0 for value in item["counts"].values()):
            raise WorkflowReadinessError("workflow readiness stages are invalid")
    expected_next = next((item["stage"] for item in artifact["stages"] if item["status"] != "completed"), None)
    if artifact["next_stage"] != expected_next:
        raise WorkflowReadinessError("workflow readiness next stage does not match stage states")
