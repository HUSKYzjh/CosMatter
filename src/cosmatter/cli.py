"""Small command-line surface for the CosMatter M1.1 baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence

from cosmatter.audit import AuditPathError, FlightRecorder, safe_run_id
from cosmatter.models import MissionBrief, MissionState, PaperCandidate
from cosmatter.state_machine import MissionMachine

from .config import AGENT_ROOT, Settings, data_root
from .public_candidate_discovery import PublicDiscoveryError, discover_arxiv_candidates, probe_public_pdf
from .dispatch import MissionDispatcher
from .deepseek import DeepSeekAdapter, DeepSeekConfigurationError, DeepSeekRequestError
from .evaluation import EvaluationError, evaluate_frozen_route_fixture, write_evaluation_record
from .evaluation_run_record import EvaluationRunRecordError, evaluation_run_record_template, reviewed_evaluation_run_record, write_evaluation_run_record_template, write_reviewed_evaluation_run_record
from .evaluation_operational_disclosure import (EvaluationOperationalDisclosureError, api_cost_latency_from_review, failure_case_log_from_review, write_api_cost_latency, write_failure_case_log)
from .agent_benchmark import AgentBenchmarkError, evaluate_frozen_agent_benchmark, write_agent_benchmark_record
from .human_evaluation import HumanEvaluationError, load_reviewed_retrieval_gold, retrieval_evaluation_from_gold, write_human_retrieval_evaluation
from .retrieval_route_comparison import RetrievalRouteComparisonError, compare_human_retrieval_routes, write_retrieval_route_comparison
from .material_evaluation import MaterialFactEvaluationError, load_reviewed_material_fact_gold, material_fact_evaluation_from_gold, write_material_fact_evaluation
from .gap_evaluation import GapReviewEvaluationError, gap_evaluation_from_assessments, gap_review_template, load_reviewed_gap_assessment, write_gap_evaluation, write_gap_review_template
from .evidence_quality_evaluation import EvidenceQualityEvaluationError, evidence_quality_evaluation_from_assessments, evidence_quality_review_template, load_reviewed_evidence_quality_assessment, write_evidence_quality_evaluation, write_evidence_quality_review_template
from .evidence_maturity_registry import EvidenceMaturityRegistryError, audit_evidence_maturity_registry_against_runs, load_evidence_maturity_registry, write_evidence_maturity_registry, write_evidence_maturity_registry_audit
from .report_audit import ReportAuditError, audit_report_evidence, write_report_evidence_audit
from .provider_receipts import ProviderReceiptError, append_provider_receipt, audit_candidate_receipt_links, audit_source_parse_receipt_links, mineru_output_receipt, mineru_task_receipt, sciverse_content_receipt, sciverse_search_receipt, write_candidate_receipt_audit, write_source_parse_receipt_audit
from .counterevidence import CounterevidenceGateError, require_executed_counterevidence
from .provenance_audit import ProvenanceAuditError, audit_accepted_evidence_provenance, write_evidence_provenance_audit
from .facilities import DiscrepancyMatrix, DiscrepancyRow, FacilityGateError, condition_differential, write_condition_matrix
from .ingestion import EvidenceIngestionError, ingest_evidence_draft, require_eligible_candidate
from .content_access import ContentAccessError, record_sciverse_content_access
from .planning import PlanApprovalError, approved_flight_plan_from_payload, load_approved_flight_plan, research_planning_prompts, write_approved_flight_plan, write_untrusted_plan_draft
from .retrieval import RetrievalArtifactError, candidates_from_sciverse, write_candidate_artifact
from .gap_analysis import GapAnalysisError, candidates_from_discrepancies, load_gap_candidates, write_gap_candidates
from .gap_drafting import GapDraftingError, research_gap_drafting_prompts, write_untrusted_research_gap_draft
from .candidate_screening import CandidateScreeningError, candidate_screening_from_automated_trial, candidate_screening_from_review, candidate_screening_template, require_document_screened_for_fulltext, write_automated_trial_candidate_screening, write_candidate_screening, write_candidate_screening_template
from .workflow_readiness import WorkflowReadinessError, workflow_readiness, write_workflow_readiness
from .runtime_invariants import RuntimeInvariantError, audit_runtime_invariants, write_runtime_invariant_audit
from .decision_memory import DecisionMemoryError, load_decision_memory_index, rebuild_decision_memory_index, write_decision_memory_entry
from .sensitive_artifact_audit import SensitiveArtifactAuditError, audit_sensitive_artifacts, write_sensitive_artifact_audit
from .submission_manifest import SubmissionManifestError, build_submission_execution_manifest, write_submission_execution_manifest
from .submission_readiness import SubmissionReadinessError, submission_readiness
from .submission_bundle import SubmissionBundleError, build_source_bundle
from .external_resources import ExternalResourceDisclosureError, load_external_resource_disclosure, write_external_resource_disclosure
from .final_submission import FinalSubmissionError, build_final_submission_package
from .material_extraction import MaterialExtractionError, iter_material_facts, material_extraction_prompts, material_fact_review_template, material_facts_from_review, validate_material_fact_source_links, write_material_fact_review_template, write_material_facts_for_document, write_untrusted_material_extraction_draft
from .material_draft_preview import MaterialDraftPreviewError, preview_untrusted_material_draft
from .material_draft_traceability_audit import MaterialDraftTraceabilityAuditError, audit_untrusted_material_draft, write_material_draft_traceability_audit
from .automated_trial_fact_audit import AutomatedTrialFactAuditError, automated_trial_fact_audit_from_review, write_automated_trial_fact_audit
from .knowledge_fusion import KnowledgeFusionError, fuse_reviewed_material_facts, load_material_fact_fusion, write_material_fact_fusion
from .local_library import LocalLibraryError, candidates_from_zotero_export
from .local_corpus import LocalCorpusSearchError, candidates_from_local_source_index
from .scibase_local import SciBaseLocalError, build_scibase_local_index, rows_from_scibase_parquet
from .corpus_preparation import CorpusPreparationError, candidates_from_authorized_corpus_manifest, corpus_manifest_from_review, corpus_manifest_from_selection_review, corpus_selection_template_from_zotero_candidates, gold_standard_template_from_manifest, load_corpus_manifest, write_corpus_manifest, write_corpus_selection_template, write_gold_standard_template
from .corpus_readiness import CorpusReadinessError, frozen_corpus_readiness, write_frozen_corpus_readiness
from .annotation_coverage import AnnotationCoverageError, annotation_coverage_audit, write_annotation_coverage_audit
from .bibliographic_source_coverage import (
    BibliographicSourceCoverageError,
    bibliographic_source_coverage_audit,
    bibliographic_source_template_from_manifest,
    write_bibliographic_source_coverage_audit,
    write_bibliographic_source_template,
)
from .reading_guide import ReadingGuideError, build_reading_guide, write_reading_guide
from .mineru import MinerUAdapter, MinerUConfigurationError, MinerURequestError
from .mineru_local_review import MinerULocalReviewError, load_mineru_markdown_review_pool, prepare_mineru_markdown_review_pool, source_map_pool_review_template, source_map_selection_from_pool_review, write_source_map_pool_review_selection, write_source_map_pool_review_template
from .mcp_server import serve_stdio
from .source_parse import SourceParseArtifactError, load_source_parse_tasks, migrate_legacy_source_parse_task_ids, private_task_id_for_document, record_source_parse_task, task_for_document, update_source_parse_task
from .source_map import AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS, SourceMapError, iter_source_maps, load_source_map_for_document, source_map_from_pool_review, source_map_from_review, write_source_map_for_document
from .run_control import RunControlError, build_run_status, cancel_run, load_run_control, require_active_run
from .openalex import OpenAlexAdapter, OpenAlexConfigurationError, OpenAlexRequestError
from .relation_expansion import RelationExpansionError, build_relation_expansion, write_relation_expansion
from .crossref import CrossrefAdapter, CrossrefRequestError
from .crossref_relation_expansion import CrossrefRelationExpansionError, build_crossref_relation_expansion, write_crossref_relation_expansion
from .paper_structure import PaperStructureError, paper_structure_from_review, write_paper_structure_for_document
from .ui_preview import UiPreviewError, serve_ui_preview
from .relation_reconciliation import RelationReconciliationError, reconciliation_from_review, write_relation_reconciliation
from .condition_normalization import ConditionNormalizationError, condition_normalization_from_review, write_condition_normalization
from .reporting import ReportGateError, build_evidence_manifest, build_structured_research_report, write_mission_report, write_structured_research_report
from .latex_report import LatexReportError, compile_latex_report, export_latex_report
from .potential_benchmark import PotentialBenchmarkError, evaluate_potential_results, generate_potential_boundary_plan, propose_potential_followups, write_potential_evaluation, write_potential_followups, write_potential_plan
from .potential_protocol import PotentialProtocolError, execution_protocol_template, write_potential_execution_protocol
from .ising_benchmark import IsingBenchmarkError, build_ising_benchmark_plan, propose_ising_followups, run_ising_benchmark, write_ising_followups, write_ising_plan, write_ising_result
from .ising_summary import IsingSummaryError, ising_benchmark_summary, write_ising_benchmark_summary
from .sciverse import SciverseAdapter, SciverseConfigurationError, SciverseRequestError
from .ui_export import UiExportError, _evidence_cards_from_payloads, _last_recorded_state, _load_array_if_present, _load_object, _mission_from_payload, _verification_decisions_from_payloads, export_run_to_ui


def _json_print(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _runs_dir() -> Path:
    return data_root() / "runs"


def _run_dir(run_id: str) -> Path:
    return _runs_dir() / safe_run_id(run_id)


def command_check_config(_: argparse.Namespace) -> int:
    _json_print(Settings.load().status())
    return 0


def command_preview_ui(args: argparse.Namespace) -> int:
    try:
        ui_bundle = _run_dir(args.run_id) / "ui.json" if args.run_id else None
        serve_ui_preview(args.port, solid=args.solid, ui_bundle=ui_bundle, api=args.api)
    except (AuditPathError, UiPreviewError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    return 0


def command_serve_mcp(_: argparse.Namespace) -> int:
    """Run the review-gated CosMatter MCP server on standard I/O."""
    return serve_stdio()


def command_create_mission(args: argparse.Namespace) -> int:
    brief = MissionBrief(
        question=args.question,
        material=args.material,
        property_name=args.property_name,
        scope=args.scope,
        **({"mission_id": args.mission_id} if args.mission_id else {}),
    )
    run_id = args.run_id or brief.mission_id.replace("mission_", "run_")
    recorder = FlightRecorder(_runs_dir(), run_id)
    mission_path = recorder.run_dir / "mission.json"
    mission_path.write_text(json.dumps(brief.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    recorder.record(event_type="mission_created", actor="mission_control", state=MissionState.INTAKE, payload=brief.to_dict())
    _json_print({"run_id": run_id, "mission_path": str(mission_path), "state": MissionState.INTAKE.value})
    return 0


def command_assign_fleet(args: argparse.Namespace) -> int:
    brief = MissionBrief(
        question=args.question,
        material=args.material,
        property_name=args.property_name,
        scope=args.scope,
        **({"mission_id": args.mission_id} if args.mission_id else {}),
    )
    assignment = MissionDispatcher.from_project().assign(brief, args.mission_type)
    run_id = args.run_id or brief.mission_id.replace("mission_", "run_")
    recorder = FlightRecorder(_runs_dir(), run_id)
    assignment_path = recorder.run_dir / "fleet_assignment.json"
    assignment_path.write_text(json.dumps(assignment.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    recorder.record(
        event_type="fleet_assigned",
        actor="mission_dispatch",
        state=MissionState.INTAKE,
        payload=assignment.to_dict(),
    )
    _json_print(
        {
            "run_id": run_id,
            "fleet_type": assignment.fleet_type.value,
            "mission_type": assignment.mission_type,
            "reason": assignment.reason,
            "assignment_path": str(assignment_path),
        }
    )
    return 0


def command_cancel_mission(args: argparse.Namespace) -> int:
    """Record cooperative cancellation; in-flight synchronous requests are unaffected."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        state = _last_recorded_state(run_dir / "events.jsonl")
        existing_control = load_run_control(run_dir / "run_control.json", mission.mission_id)
        if existing_control is not None:
            _json_print(build_run_status(args.run_id, mission.mission_id, state, existing_control))
            return 0
        if state in {MissionState.COMPLETE, MissionState.FAILED, MissionState.CANCELLED}:
            raise RunControlError("terminal missions cannot be cancelled")
        control_path = cancel_run(run_dir, mission.mission_id)
    except (UiExportError, RunControlError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="mission_cancelled",
        actor="mission_control",
        state=MissionState.CANCELLED,
        payload={"control_schema_version": "1.0"},
    )
    _json_print({"control_path": str(control_path), **build_run_status(args.run_id, mission.mission_id, state, load_run_control(control_path, mission.mission_id))})
    return 0


def command_run_status(args: argparse.Namespace) -> int:
    """Return an allowlisted status summary suitable for a future local UI."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        state = _last_recorded_state(run_dir / "events.jsonl")
        control = load_run_control(run_dir / "run_control.json", mission.mission_id)
    except (UiExportError, RunControlError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    _json_print(build_run_status(args.run_id, mission.mission_id, state, control))
    return 0

def command_audit_workflow_readiness(args: argparse.Namespace) -> int:
    """Write an artifact-only readiness view; no provider calls are made."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        artifact = workflow_readiness(run_dir, mission)
        path = write_workflow_readiness(run_dir, artifact)
    except (UiExportError, WorkflowReadinessError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    state = _last_recorded_state(run_dir / "events.jsonl")
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="workflow_readiness_audited",
        actor="workflow_orchestrator",
        state=state,
        payload={"next_stage": artifact["next_stage"], "completed_stage_count": sum(item["status"] == "completed" for item in artifact["stages"])},
    )
    _json_print({"run_id": args.run_id, "next_stage": artifact["next_stage"], "workflow_path": str(path)})
    return 0


def command_audit_runtime_invariants(args: argparse.Namespace) -> int:
    """Audit cross-artifact safety relationships without provider calls."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        artifact = audit_runtime_invariants(run_dir, mission.mission_id)
        path = write_runtime_invariant_audit(run_dir, artifact)
    except (OSError, UiExportError, RuntimeInvariantError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="runtime_invariants_audited",
        actor="runtime_invariant_companion",
        state=_last_recorded_state(run_dir / "events.jsonl"),
        payload={"passed": artifact["passed"], "checked_artifact_count": artifact["checked_artifact_count"]},
    )
    _json_print({"run_id": args.run_id, "audit_path": str(path), "passed": artifact["passed"], "trust_status": artifact["trust_status"]})
    return 0


def _decision_memory_dir() -> Path:
    """Keep project operational notes local to the configured runtime data root."""
    return data_root() / "project_decision_memory"


def command_record_decision_memory(args: argparse.Namespace) -> int:
    """Write a human-editable operational note; never accept research evidence."""
    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        path = write_decision_memory_entry(_decision_memory_dir(), payload)
    except (OSError, json.JSONDecodeError, DecisionMemoryError) as error:
        _json_print({"error": str(error)})
        return 2
    _json_print({"entry_path": path.name, "trust_status": "project_operational_memory_not_scientific_evidence_or_report_source"})
    return 0


def command_rebuild_decision_memory(args: argparse.Namespace) -> int:
    """Rebuild index from Markdown source files after a human edit/delete."""
    try:
        index = rebuild_decision_memory_index(_decision_memory_dir())
    except DecisionMemoryError as error:
        _json_print({"error": str(error)})
        return 2
    _json_print({"entry_count": index["entry_count"], "trust_status": index["trust_status"]})
    return 0


def command_list_decision_memory(args: argparse.Namespace) -> int:
    """List compact operational metadata, never Markdown note bodies."""
    try:
        index = load_decision_memory_index(_decision_memory_dir())
    except DecisionMemoryError as error:
        _json_print({"error": str(error)})
        return 2
    _json_print(index)
    return 0


def command_audit_sensitive_artifacts(args: argparse.Namespace) -> int:
    """Write a count-only scan of run artifacts without exposing matches."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        artifact = audit_sensitive_artifacts(run_dir, mission.mission_id)
        path = write_sensitive_artifact_audit(run_dir, artifact)
    except (OSError, UiExportError, SensitiveArtifactAuditError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="sensitive_artifacts_audited",
        actor="redaction_auditor",
        state=_last_recorded_state(run_dir / "events.jsonl"),
        payload={"is_clean": artifact["is_clean"], "finding_category_count": len(artifact["findings"]), "scanned_text_artifact_count": artifact["scanned_text_artifact_count"]},
    )
    _json_print({"run_id": args.run_id, "audit_path": str(path), "is_clean": artifact["is_clean"], "finding_category_count": len(artifact["findings"]), "trust_status": artifact["trust_status"]})
    return 0


def command_build_submission_execution_manifest(args: argparse.Namespace) -> int:
    """Create a secret-safe, artifact-only execution index for a mission run."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        manifest = build_submission_execution_manifest(run_dir=run_dir, mission=mission)
        path = write_submission_execution_manifest(run_dir, manifest)
    except (UiExportError, WorkflowReadinessError, SubmissionManifestError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    state = _last_recorded_state(run_dir / "events.jsonl")
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="submission_execution_manifest_built",
        actor="workflow_orchestrator",
        state=state,
        payload={
            "artifact_present_count": sum(item["exists"] for item in manifest["artifact_inventory"]),
            "event_count": manifest["event_summary"]["event_count"],
            "provider_receipt_count": manifest["provider_receipt_summary"]["receipt_count"],
        },
    )
    _json_print({
        "run_id": args.run_id,
        "submission_manifest_path": str(path),
        "next_stage": manifest["workflow"]["next_stage"],
        "artifact_present_count": sum(item["exists"] for item in manifest["artifact_inventory"]),
    })
    return 0


def command_export_ui(args: argparse.Namespace) -> int:
    output_path = Path(args.output) if args.output else None
    try:
        destination = export_run_to_ui(_runs_dir(), args.run_id, output_path)
    except UiExportError as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    _json_print({"run_id": args.run_id, "ui_path": str(destination), "schema_version": "1.0"})
    return 0


def command_record_evidence_maturity_registry(args: argparse.Namespace) -> int:
    """Record a reviewed registry only when its local source-map links audit cleanly."""
    run_dir = _run_dir(args.run_id)
    registry_path = run_dir / "evidence_maturity_registry.json"
    audit_path = run_dir / "evidence_maturity_registry_audit.json"
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        registry = load_evidence_maturity_registry(Path(args.input))
        if registry["question_id"] != mission.mission_id:
            raise EvidenceMaturityRegistryError("evidence maturity registry question does not match this mission")
        audit = audit_evidence_maturity_registry_against_runs(registry, _runs_dir())
        if not audit["passed"]:
            raise EvidenceMaturityRegistryError("evidence maturity registry source links did not pass audit")
        if not audit_sensitive_artifacts(run_dir, mission.mission_id)["is_clean"]:
            raise EvidenceMaturityRegistryError("evidence maturity registry requires a clean current redaction audit")
        if registry_path.exists() or audit_path.exists():
            raise EvidenceMaturityRegistryError("evidence maturity registry artifacts already exist")
        write_evidence_maturity_registry(registry_path, registry)
        write_evidence_maturity_registry_audit(audit_path, audit)
        write_sensitive_artifact_audit(run_dir, audit_sensitive_artifacts(run_dir, mission.mission_id))
    except (OSError, UiExportError, EvidenceMaturityRegistryError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    state = _last_recorded_state(run_dir / "events.jsonl")
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="evidence_maturity_registry_recorded",
        actor="evidence_maturity_registry",
        state=state,
        payload={"claim_count": audit["claim_count"], "support_record_count": audit["support_record_count"], "link_error_count": audit["link_error_count"]},
    )
    _json_print({"run_id": args.run_id, "claim_count": audit["claim_count"], "support_record_count": audit["support_record_count"], "link_audit": "passed"})
    return 0


def command_approve_plan(args: argparse.Namespace) -> int:
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        plan = approved_flight_plan_from_payload(mission, payload)
        plan_path = write_approved_flight_plan(run_dir, plan)
    except (OSError, json.JSONDecodeError, UiExportError, PlanApprovalError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="flight_plan_approved",
        actor="human_plan_review",
        state=MissionState.PLAN,
        payload={"plan_id": plan.artifact_id, "query_count": len(plan.queries), "counter_query_count": len(plan.counter_queries)},
    )
    _json_print({"run_id": args.run_id, "plan_id": plan.artifact_id, "plan_path": str(plan_path)})
    return 0

def command_draft_plan(args: argparse.Namespace) -> int:
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        require_active_run(run_dir, mission.mission_id)
        system_prompt, user_prompt = research_planning_prompts(mission)
        completion = DeepSeekAdapter(Settings.load()).draft(system_prompt=system_prompt, user_prompt=user_prompt)
        draft_path = write_untrusted_plan_draft(run_dir, completion)
    except (UiExportError, DeepSeekConfigurationError, DeepSeekRequestError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="research_plan_drafted",
        actor="research_planning",
        state=MissionState.PLAN,
        payload={"model": completion.model, "request_id": completion.request_id, "trust_status": "untrusted_draft"},
    )
    _json_print({"run_id": args.run_id, "draft_path": str(draft_path), "trust_status": "untrusted_draft"})
    return 0

def command_build_reading_guide(args: argparse.Namespace) -> int:
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        plan = load_approved_flight_plan(run_dir, mission.mission_id)
        candidate_history = _load_object(run_dir / "retrieval_candidates.json", "candidate history")
        cards = _evidence_cards_from_payloads(_load_array_if_present(run_dir / "evidence_cards.json", "evidence artifacts"))
        decisions = _verification_decisions_from_payloads(
            _load_array_if_present(run_dir / "verification_decisions.json", "verification decision artifacts")
        )
        guide = build_reading_guide(mission, plan, candidate_history, cards, decisions)
        guide_path = write_reading_guide(run_dir, guide)
    except (UiExportError, PlanApprovalError, ReadingGuideError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="reading_guide_built",
        actor="research_guide",
        state=MissionState.SELECT,
        payload={"guide_item_count": len(guide["items"]), "trust_status": guide["trust_status"]},
    )
    _json_print({"run_id": args.run_id, "guide_path": str(guide_path), "item_count": len(guide["items"]), "trust_status": guide["trust_status"]})
    return 0


def command_create_candidate_screening_template(args: argparse.Namespace) -> int:
    """Create one human-review slot for every current retrieval candidate."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        candidate_history = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate history")
        template = candidate_screening_template(mission.mission_id, candidate_history)
        path = write_candidate_screening_template(run_dir, template)
    except (UiExportError, CandidateScreeningError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="candidate_screening_template_created",
        actor="literature_screening",
        state=MissionState.SELECT,
        payload={"candidate_count": len(template["decisions"]), "trust_status": template["trust_status"]},
    )
    _json_print({"run_id": args.run_id, "candidate_count": len(template["decisions"]), "template_path": str(path)})
    return 0


def command_record_candidate_screening(args: argparse.Namespace) -> int:
    """Record complete human inclusion/exclusion decisions for current candidates."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        candidate_history = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate history")
        selection = json.loads(Path(args.input).read_text(encoding="utf-8"))
        artifact = candidate_screening_from_review(mission.mission_id, candidate_history, selection)
        path = write_candidate_screening(run_dir, artifact)
    except (OSError, json.JSONDecodeError, UiExportError, CandidateScreeningError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    counts = {decision: sum(item["decision"] == decision for item in artifact["decisions"]) for decision in ("include_for_fulltext", "exclude", "needs_metadata_review")}
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="candidate_screening_reviewed",
        actor="literature_screening",
        state=MissionState.SELECT,
        payload={"candidate_count": artifact["candidate_count"], "decision_counts": counts},
    )
    _json_print({"run_id": args.run_id, "candidate_count": artifact["candidate_count"], "decision_counts": counts, "screening_path": str(path)})
    return 0


def command_record_automated_trial_screening(args: argparse.Namespace) -> int:
    """Record delegated-agent screening for an explicitly opted-in trial only."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        candidate_history = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate history")
        if args.input:
            selection = json.loads(Path(args.input).read_text(encoding="utf-8"))
        else:
            selection = _automated_trial_screening_selection(candidate_history, args.include_document_id)
        artifact = candidate_screening_from_automated_trial(mission.mission_id, candidate_history, selection)
        path = write_automated_trial_candidate_screening(run_dir, artifact)
    except (OSError, json.JSONDecodeError, UiExportError, CandidateScreeningError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    counts = {decision: sum(item["decision"] == decision for item in artifact["decisions"]) for decision in ("include_for_fulltext", "exclude", "needs_metadata_review")}
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="delegated_automated_trial_candidate_screening_recorded",
        actor="delegated_automated_trial_reviewer",
        state=MissionState.SELECT,
        payload={"candidate_count": artifact["candidate_count"], "decision_counts": counts, "trust_status": artifact["trust_status"]},
    )
    _json_print({"run_id": args.run_id, "candidate_count": artifact["candidate_count"], "decision_counts": counts, "screening_path": str(path), "trust_status": artifact["trust_status"]})
    return 0


def _automated_trial_screening_selection(candidate_history: object, include_document_ids: Sequence[str]) -> dict[str, object]:
    """Build a deliberately conservative complete selection for parser trials.

    Only explicitly named candidates are included. Every other candidate stays
    in ``needs_metadata_review`` rather than being silently excluded or
    treated as scientifically screened.
    """
    if not isinstance(candidate_history, dict) or not isinstance(candidate_history.get("candidates"), list):
        raise CandidateScreeningError("automated trial screening requires retrieval candidates")
    if not isinstance(include_document_ids, list) or not 1 <= len(include_document_ids) <= 3 or any(not isinstance(item, str) or not item.strip() for item in include_document_ids) or len(set(include_document_ids)) != len(include_document_ids):
        raise CandidateScreeningError("automated trial screening requires one to three unique included document IDs")
    included = set(include_document_ids)
    known = [item.get("document_id") for item in candidate_history["candidates"] if isinstance(item, dict)]
    if any(identifier not in known for identifier in included):
        raise CandidateScreeningError("automated trial inclusion document is not a current candidate")
    return {
        "decisions": [
            {
                "document_id": identifier,
                "decision": "include_for_fulltext" if identifier in included else "needs_metadata_review",
                "reason_codes": ["material_match", "property_match", "scope_match"] if identifier in included else ["not_enough_metadata"],
            }
            for identifier in known
        ]
    }


def command_submit_mineru_source(args: argparse.Namespace) -> int:
    """Submit an explicitly authorized public source URL to MinerU.

    The local ledger retains only a hash of the URL and task metadata.  MinerU
    output is not downloaded or exposed to the UI at this stage.
    """
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        candidate_history = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate history")
        delegated_trial = bool(getattr(args, "allow_delegated_automated_trial", False))
        require_document_screened_for_fulltext(run_dir, mission.mission_id, candidate_history, args.document_id, allow_delegated_automated_trial=delegated_trial)
        require_active_run(run_dir, mission.mission_id)
        settings = Settings.load()
        source_url = args.source_url.strip()
        task = MinerUAdapter(settings).submit_remote_source(source_url)
        receipt = mineru_task_receipt(
            operation="source_parse_submit",
            document_id=args.document_id,
            source_url_sha256=hashlib.sha256(source_url.encode("utf-8")).hexdigest(),
            task_id=task.task_id,
            task_state=task.state,
            model_version=settings.mineru_model_version,
            status_code=task.status_code,
            request_id=task.request_id,
        )
        append_provider_receipt(run_dir, receipt)
        task_path = record_source_parse_task(
            run_dir,
            mission_id=mission.mission_id,
            document_id=args.document_id,
            source_url=source_url,
            task=task,
            model_version=settings.mineru_model_version,
        )
    except (UiExportError, EvidenceIngestionError, MinerUConfigurationError, MinerURequestError, SourceParseArtifactError, ProviderReceiptError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id, "document_id": args.document_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="source_parse_submitted",
        actor="document_parser",
        state=MissionState.EXTRACT,
        payload={"document_id": args.document_id, "provider": "mineru", "task_state": task.state, "receipt_id": receipt["receipt_id"], "screening_mode": "delegated_automated_trial" if delegated_trial else "human_reviewed"},
    )
    _json_print({"run_id": args.run_id, "document_id": args.document_id, "task_state": task.state, "task_path": str(task_path)})
    return 0


def command_poll_mineru_source(args: argparse.Namespace) -> int:
    """Refresh one recorded MinerU task without fetching parse output."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        stored_task = task_for_document(run_dir, mission_id=mission.mission_id, document_id=args.document_id)
        require_active_run(run_dir, mission.mission_id)
        settings = Settings.load()
        task = MinerUAdapter(settings).get_task(private_task_id_for_document(run_dir, mission_id=mission.mission_id, document_id=args.document_id))
        receipt = mineru_task_receipt(
            operation="source_parse_poll",
            document_id=args.document_id,
            source_url_sha256=stored_task["source_url_sha256"],
            task_id=task.task_id,
            task_state=task.state,
            model_version=stored_task["model_version"],
            status_code=task.status_code,
            request_id=task.request_id,
        )
        append_provider_receipt(run_dir, receipt)
        task_path = update_source_parse_task(run_dir, mission_id=mission.mission_id, document_id=args.document_id, task=task)
    except (UiExportError, MinerUConfigurationError, MinerURequestError, SourceParseArtifactError, ProviderReceiptError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id, "document_id": args.document_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="source_parse_status_checked",
        actor="document_parser",
        state=MissionState.EXTRACT,
        payload={"document_id": args.document_id, "provider": "mineru", "task_state": task.state, "receipt_id": receipt["receipt_id"]},
    )
    _json_print({"run_id": args.run_id, "document_id": args.document_id, "task_state": task.state, "task_path": str(task_path)})
    return 0


def command_fetch_mineru_markdown(args: argparse.Namespace) -> int:
    """Fetch completed MinerU Markdown to a new private path outside a run.

    The completed archive URL and Markdown body remain process-local except for
    the caller-selected private file. Mission artifacts receive only a
    hash-only provider receipt and a bounded audit event.
    """
    run_dir = _run_dir(args.run_id)
    output_path = Path(args.output).resolve()
    try:
        if (
            output_path.exists()
            or output_path.suffix.casefold() not in {".md", ".markdown"}
            or not output_path.parent.is_dir()
            or _path_is_within(output_path, run_dir)
        ):
            raise MinerULocalReviewError("private Markdown output must be a new .md file outside the mission run with an existing parent")
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        require_active_run(run_dir, mission.mission_id)
        stored_task = task_for_document(run_dir, mission_id=mission.mission_id, document_id=args.document_id)
        if stored_task["state"] != "done":
            raise SourceParseArtifactError("completed MinerU Markdown fetch requires a task in done state")
        task_id = private_task_id_for_document(run_dir, mission_id=mission.mission_id, document_id=args.document_id)
        settings = Settings.load()
        result = MinerUAdapter(settings).download_completed_markdown(task_id)
        with output_path.open("xb") as handle:
            handle.write(result.content)
        receipt = mineru_output_receipt(
            document_id=args.document_id,
            source_url_sha256=stored_task["source_url_sha256"],
            task_id=task_id,
            model_version=stored_task["model_version"],
            content=result.content,
            status_code=result.status_code,
            request_id=result.request_id,
        )
        append_provider_receipt(run_dir, receipt)
    except (OSError, UiExportError, RunControlError, MinerUConfigurationError, MinerURequestError, MinerULocalReviewError, SourceParseArtifactError, ProviderReceiptError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id, "document_id": args.document_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="private_mineru_markdown_fetched",
        actor="document_parser",
        state=MissionState.EXTRACT,
        payload={"document_id": args.document_id, "provider": "mineru", "markdown_byte_count": len(result.content), "receipt_id": receipt["receipt_id"]},
    )
    _json_print({"run_id": args.run_id, "document_id": args.document_id, "markdown_byte_count": len(result.content), "private_markdown_written": True})
    return 0

def command_audit_source_parse_receipts(args: argparse.Namespace) -> int:
    """Verify MinerU task-ledger entries against hash-only provider receipts."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        ledger = load_source_parse_tasks(run_dir / "source_parse_tasks.json", mission.mission_id)
        if ledger is None:
            raise SourceParseArtifactError("source parse task ledger does not exist")
        result = audit_source_parse_receipt_links(ledger, run_dir / "provider_receipts.jsonl")
        audit_path = write_source_parse_receipt_audit(run_dir, result)
    except (OSError, UiExportError, SourceParseArtifactError, ProviderReceiptError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="source_parse_receipt_links_audited",
        actor="document_parser_auditor",
        state=MissionState.EXTRACT,
        payload={"source_parse_task_count": result["source_parse_task_count"], "receipt_linked_task_count": result["receipt_linked_task_count"], "stale_task_state_count": result["stale_task_state_count"]},
    )
    _json_print({"run_id": args.run_id, "audit_path": str(audit_path), **result})
    return 0


def command_migrate_source_parse_task_identifiers(args: argparse.Namespace) -> int:
    """Move a legacy raw MinerU task identifier into private local storage."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        migrated_count = migrate_legacy_source_parse_task_ids(run_dir, mission_id=mission.mission_id)
    except (OSError, UiExportError, SourceParseArtifactError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="source_parse_task_identifiers_migrated",
        actor="redaction_migration",
        state=MissionState.EXTRACT,
        payload={"migrated_task_count": migrated_count},
    )
    _json_print({"run_id": args.run_id, "migrated_task_count": migrated_count, "trust_status": "private_task_identifier_migration_not_scientific_evidence"})
    return 0



def _path_is_within(path: Path, directory: Path) -> bool:
    """Return whether a resolved local path sits under one run directory."""
    try:
        path.resolve().relative_to(directory.resolve())
    except ValueError:
        return False
    return True


def command_prepare_mineru_markdown_review(args: argparse.Namespace) -> int:
    """Build a private candidate pool from an already downloaded MinerU Markdown result.

    The pool remains outside the run. It is an operator convenience only:
    reviewers still make a new, bounded Source Map selection themselves.
    """
    run_dir = _run_dir(args.run_id)
    input_path = Path(args.input)
    output_path = Path(args.output)
    try:
        if _path_is_within(input_path, run_dir) or _path_is_within(output_path, run_dir):
            raise MinerULocalReviewError("local MinerU Markdown input and review-pool output must remain outside the mission run")
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        task = task_for_document(run_dir, mission_id=mission.mission_id, document_id=args.document_id)
        pool = prepare_mineru_markdown_review_pool(
            mission_id=mission.mission_id,
            document_id=args.document_id,
            source_task=task,
            input_path=input_path,
            output_path=output_path,
        )
    except (OSError, UiExportError, SourceParseArtifactError, MinerULocalReviewError) as error:
        _json_print({"error": str(error), "run_id": args.run_id, "document_id": args.document_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="private_mineru_markdown_review_pool_prepared",
        actor="source_reviewer",
        state=MissionState.EXTRACT,
        payload={"document_id": args.document_id, "candidate_segment_count": len(pool["candidate_segments"])},
    )
    _json_print(
        {
            "run_id": args.run_id,
            "document_id": args.document_id,
            "candidate_segment_count": len(pool["candidate_segments"]),
            "trust_status": pool["trust_status"],
        }
    )
    return 0


def command_create_mineru_source_map_review_template(args: argparse.Namespace) -> int:
    """Create an excerpt-free local review template bound to one private candidate pool."""
    run_dir = _run_dir(args.run_id)
    pool_path = Path(args.review_pool)
    output_path = Path(args.output)
    try:
        if _path_is_within(pool_path, run_dir) or _path_is_within(output_path, run_dir):
            raise MinerULocalReviewError("private review-pool input and review template output must remain outside the mission run")
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        task = task_for_document(run_dir, mission_id=mission.mission_id, document_id=args.document_id)
        pool = load_mineru_markdown_review_pool(
            path=pool_path,
            mission_id=mission.mission_id,
            document_id=args.document_id,
            source_task=task,
        )
        template = source_map_pool_review_template(pool)
        write_source_map_pool_review_template(output_path, template)
    except (OSError, UiExportError, SourceParseArtifactError, MinerULocalReviewError) as error:
        _json_print({"error": str(error), "run_id": args.run_id, "document_id": args.document_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="private_mineru_source_map_review_template_created",
        actor="source_reviewer",
        state=MissionState.EXTRACT,
        payload={"document_id": args.document_id, "candidate_segment_count": len(template["segments"])},
    )
    _json_print({"run_id": args.run_id, "document_id": args.document_id, "candidate_segment_count": len(template["segments"]), "trust_status": template["trust_status"]})
    return 0


def command_create_automated_trial_source_map_selection(args: argparse.Namespace) -> int:
    """Create a hash-bound delegated-agent trial selection from a private pool."""
    run_dir = _run_dir(args.run_id)
    pool_path = Path(args.review_pool)
    output_path = Path(args.output)
    try:
        if _path_is_within(pool_path, run_dir) or _path_is_within(output_path, run_dir):
            raise MinerULocalReviewError("private review-pool and automated trial selection must remain outside the mission run")
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        task = task_for_document(run_dir, mission_id=mission.mission_id, document_id=args.document_id)
        pool = load_mineru_markdown_review_pool(
            path=pool_path,
            mission_id=mission.mission_id,
            document_id=args.document_id,
            source_task=task,
        )
        selected_ids = args.segment_id
        if not isinstance(selected_ids, list) or not 1 <= len(selected_ids) <= 12 or len(set(selected_ids)) != len(selected_ids):
            raise MinerULocalReviewError("automated trial Source Map selection requires one to twelve unique segment IDs")
        selection = source_map_pool_review_template(pool, delegated_automated_trial=True)
        known_ids = {item["segment_id"] for item in selection["segments"]}
        if any(identifier not in known_ids for identifier in selected_ids):
            raise MinerULocalReviewError("automated trial Source Map selection contains an unknown pool segment")
        selected = set(selected_ids)
        for item in selection["segments"]:
            if item["segment_id"] in selected:
                item["selected"] = True
                item["reason"] = "direct_support_for_authorized_trial_question"
        selection["trust_status"] = "delegated_automated_trial_source_map_pool_selection"
        write_source_map_pool_review_selection(output_path, selection, delegated_automated_trial=True)
    except (OSError, UiExportError, SourceParseArtifactError, MinerULocalReviewError) as error:
        _json_print({"error": str(error), "run_id": args.run_id, "document_id": args.document_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="delegated_automated_trial_source_map_selection_created",
        actor="delegated_automated_trial_reviewer",
        state=MissionState.EXTRACT,
        payload={"document_id": args.document_id, "selected_segment_count": len(selected_ids), "trust_status": selection["trust_status"]},
    )
    _json_print({"run_id": args.run_id, "document_id": args.document_id, "selected_segment_count": len(selected_ids), "selection_path": str(output_path), "trust_status": selection["trust_status"]})
    return 0

def command_record_source_map(args: argparse.Namespace) -> int:
    """Persist only reviewer-selected excerpts from a completed parse task."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        candidate_history = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate history")
        delegated_trial = bool(getattr(args, "allow_delegated_automated_trial", False))
        require_document_screened_for_fulltext(run_dir, mission.mission_id, candidate_history, args.document_id, allow_delegated_automated_trial=delegated_trial)
        task = task_for_document(run_dir, mission_id=mission.mission_id, document_id=args.document_id)
        selection = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if args.review_pool:
            review_pool_path = Path(args.review_pool)
            if _path_is_within(review_pool_path, run_dir) or _path_is_within(Path(args.input), run_dir):
                raise MinerULocalReviewError("private review-pool and its reviewed selection must remain outside the mission run")
            review_pool = load_mineru_markdown_review_pool(
                path=review_pool_path,
                mission_id=mission.mission_id,
                document_id=args.document_id,
                source_task=task,
            )
            resolved_selection, markdown_sha256 = source_map_selection_from_pool_review(pool=review_pool, review=selection, delegated_automated_trial=delegated_trial)
            source_map = source_map_from_pool_review(
                mission_id=mission.mission_id,
                document_id=args.document_id,
                source_task=task,
                selection=resolved_selection,
                source_markdown_sha256=markdown_sha256,
                trust_status=AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS if delegated_trial else "human_reviewed_parser_selection",
            )
        else:
            source_map = source_map_from_review(
                mission_id=mission.mission_id,
                document_id=args.document_id,
                source_task=task,
                selection=selection,
                trust_status=AUTOMATED_TRIAL_SOURCE_MAP_TRUST_STATUS if delegated_trial else "human_reviewed_parser_selection",
            )
        source_map_path = write_source_map_for_document(run_dir, source_map)
    except (OSError, json.JSONDecodeError, UiExportError, CandidateScreeningError, EvidenceIngestionError, SourceParseArtifactError, SourceMapError, MinerULocalReviewError) as error:
        _json_print({"error": str(error), "run_id": args.run_id, "document_id": args.document_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="delegated_automated_trial_source_map_recorded" if delegated_trial else "source_map_reviewed",
        actor="delegated_automated_trial_reviewer" if delegated_trial else "source_reviewer",
        state=MissionState.EXTRACT,
        payload={"document_id": args.document_id, "segment_count": len(source_map["segments"]), "trust_status": source_map["trust_status"]},
    )
    _json_print({"run_id": args.run_id, "document_id": args.document_id, "segment_count": len(source_map["segments"]), "source_map_path": str(source_map_path)})
    return 0


def command_record_automated_trial_fact_audit(args: argparse.Namespace) -> int:
    """Record source-map-bound delegated-agent checks without creating facts."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        source_map = load_source_map_for_document(run_dir, mission.mission_id, args.document_id)
        if source_map is None:
            raise AutomatedTrialFactAuditError("automated trial fact audit requires a current Source Map")
        review = json.loads(Path(args.input).read_text(encoding="utf-8"))
        artifact = automated_trial_fact_audit_from_review(mission_id=mission.mission_id, source_map=source_map, review=review)
        path = write_automated_trial_fact_audit(run_dir, artifact)
    except (OSError, json.JSONDecodeError, UiExportError, SourceMapError, AutomatedTrialFactAuditError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id, "document_id": args.document_id})
        return 2
    counts = {status: sum(item["determination"] == status for item in artifact["claims"]) for status in ("directly_supported", "qualified_by_source", "not_supported")}
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="delegated_automated_trial_fact_audit_recorded",
        actor="delegated_automated_trial_fact_auditor",
        state=MissionState.EXTRACT,
        payload={"document_id": args.document_id, "claim_count": len(artifact["claims"]), "determination_counts": counts, "trust_status": artifact["trust_status"]},
    )
    _json_print({"run_id": args.run_id, "document_id": args.document_id, "claim_count": len(artifact["claims"]), "determination_counts": counts, "audit_path": str(path), "trust_status": artifact["trust_status"]})
    return 0


def command_draft_material_extraction(args: argparse.Namespace) -> int:
    """Ask DeepSeek for an untrusted fact draft from reviewed short source-map excerpts."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        require_active_run(run_dir, mission.mission_id)
        source_map = load_source_map_for_document(run_dir, mission.mission_id, args.document_id)
        if source_map is None:
            raise MaterialExtractionError("material extraction requires a reviewed source map")
        system_prompt, user_prompt = material_extraction_prompts(mission, source_map)
        completion = DeepSeekAdapter(Settings.load()).draft(system_prompt=system_prompt, user_prompt=user_prompt)
        path = write_untrusted_material_extraction_draft(run_dir, completion, source_map)
        try:
            preview_path, preview_fact_count = preview_untrusted_material_draft(run_dir, mission.mission_id, source_map, completion.content)
        except MaterialDraftPreviewError:
            preview_path, preview_fact_count = None, 0
    except (UiExportError, RunControlError, SourceMapError, MaterialExtractionError, DeepSeekConfigurationError, DeepSeekRequestError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="material_extraction_drafted", actor="material_extractor", state=MissionState.EXTRACT,
        payload={"document_id": source_map["document_id"], "segment_count": len(source_map["segments"]), "model": completion.model, "trust_status": "untrusted_draft", "structured_candidate_fact_count": preview_fact_count},
    )
    _json_print({"run_id": args.run_id, "document_id": source_map["document_id"], "draft_path": str(path), "structured_candidate_path": str(preview_path) if preview_path is not None else None, "structured_candidate_fact_count": preview_fact_count, "trust_status": "untrusted_draft"})
    return 0


def command_create_material_fact_review_template(args: argparse.Namespace) -> int:
    """Create a quote-free human fact-review form tied to one reviewed source map."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        source_map = load_source_map_for_document(run_dir, mission.mission_id, args.document_id)
        if source_map is None:
            raise MaterialExtractionError("material fact review template requires a reviewed source map")
        template = material_fact_review_template(mission_id=mission.mission_id, source_map=source_map)
        path = write_material_fact_review_template(run_dir, template)
    except (UiExportError, SourceMapError, MaterialExtractionError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="material_fact_review_template_created",
        actor="material_reviewer",
        state=MissionState.EXTRACT,
        payload={"document_id": template["document_id"], "segment_count": len(template["segments"]), "trust_status": template["trust_status"]},
    )
    _json_print({
        "run_id": args.run_id,
        "document_id": template["document_id"],
        "segment_count": len(template["segments"]),
        "material_fact_review_template_path": str(path),
        "next_step": "Complete facts, change trust_status to human_reviewed_material_facts_for_recording, then use record-material-facts.",
    })
    return 0


def command_audit_material_draft_traceability(args: argparse.Namespace) -> int:
    """Write a count-only mechanical check for an explicitly untrusted draft."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        source_map = load_source_map_for_document(run_dir, mission.mission_id, args.document_id)
        if source_map is None:
            raise MaterialDraftTraceabilityAuditError("material draft audit requires a reviewed source map")
        document_id = source_map["document_id"]
        candidate_path = run_dir / "material_extraction_candidates" / f"{hashlib.sha256(document_id.encode('utf-8')).hexdigest()}.json"
        candidates = _load_object(candidate_path, "structured material draft candidate")
        audit = audit_untrusted_material_draft(mission_id=mission.mission_id, source_map=source_map, candidates=candidates)
        path = write_material_draft_traceability_audit(run_dir, audit)
    except (UiExportError, SourceMapError, MaterialDraftTraceabilityAuditError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="material_draft_traceability_audited", actor="material_reviewer", state=MissionState.EXTRACT,
        payload={key: audit[key] for key in ("candidate_fact_count", "source_linked_fact_count", "reported_value_verbatim_fact_count", "automatically_accepted_fact_count")},
    )
    _json_print({"run_id": args.run_id, "audit_path": str(path), "candidate_fact_count": audit["candidate_fact_count"], "automatically_accepted_fact_count": 0, "review_gate": audit["review_gate"]})
    return 0


def command_record_material_facts(args: argparse.Namespace) -> int:
    """Persist reviewer-approved structured facts linked to source-map segments."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        source_map = load_source_map_for_document(run_dir, mission.mission_id, args.document_id)
        if source_map is None:
            raise MaterialExtractionError("material facts require a reviewed source map")
        selection = json.loads(Path(args.input).read_text(encoding="utf-8"))
        artifact = material_facts_from_review(mission_id=mission.mission_id, source_map=source_map, selection=selection)
        path = write_material_facts_for_document(run_dir, artifact)
    except (OSError, json.JSONDecodeError, UiExportError, SourceMapError, MaterialExtractionError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    categories = sorted({fact["category"] for fact in artifact["facts"]})
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="material_facts_reviewed", actor="material_reviewer", state=MissionState.EXTRACT,
        payload={"document_id": artifact["document_id"], "fact_count": len(artifact["facts"]), "categories": categories},
    )
    _json_print({"run_id": args.run_id, "document_id": artifact["document_id"], "fact_count": len(artifact["facts"]), "material_facts_path": str(path)})
    return 0


def command_fuse_material_facts(args: argparse.Namespace) -> int:
    """Compare only reviewed facts across documents; do not infer a scientific conclusion."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        material_fact_artifacts = iter_material_facts(run_dir, mission.mission_id)
        validate_material_fact_source_links(
            mission_id=mission.mission_id,
            artifacts=material_fact_artifacts,
            source_maps=iter_source_maps(run_dir, mission.mission_id),
        )
        artifact = fuse_reviewed_material_facts(mission.mission_id, material_fact_artifacts)
        path = write_material_fact_fusion(run_dir, artifact)
    except (UiExportError, MaterialExtractionError, KnowledgeFusionError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    flagged = sum(item["comparison_status"] == "value_disagreement_under_matching_qualifiers_requires_human_review" for item in artifact["comparisons"])
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="material_facts_fused", actor="knowledge_fusion", state=MissionState.HAZARD_SCAN,
        payload={"comparison_count": len(artifact["comparisons"]), "human_review_disagreement_count": flagged},
    )
    _json_print({"run_id": args.run_id, "comparison_count": len(artifact["comparisons"]), "fusion_path": str(path)})
    return 0

def command_expand_openalex_relations(args: argparse.Namespace) -> int:
    """Expand only public relation metadata for one accepted DOI-bearing card."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        require_active_run(run_dir, mission.mission_id)
        cards = _evidence_cards_from_payloads(_load_array_if_present(run_dir / "evidence_cards.json", "evidence artifacts"))
        decisions = _verification_decisions_from_payloads(_load_array_if_present(run_dir / "verification_decisions.json", "verification decision artifacts"))
        card = next((item for item in cards if item.evidence_id == args.evidence_id), None)
        decision = next((item for item in decisions if item.evidence_id == args.evidence_id and item.mission_id == mission.mission_id), None)
        if card is None or decision is None:
            raise RelationExpansionError("evidence_id must have a recorded card and review decision in this mission")
        work = OpenAlexAdapter(Settings.load()).work_relations_by_doi(card.provenance.doi or "")
        expansion = build_relation_expansion(mission, card, decision, work)
        path = write_relation_expansion(run_dir, expansion)
    except (UiExportError, RunControlError, OpenAlexConfigurationError, OpenAlexRequestError, RelationExpansionError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id, "evidence_id": args.evidence_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="public_relations_expanded",
        actor="citation_array",
        state=MissionState.MAP,
        payload={"evidence_id": args.evidence_id, "provider": "openalex", "edge_count": len(expansion["edges"])},
    )
    _json_print({"run_id": args.run_id, "evidence_id": args.evidence_id, "edge_count": len(expansion["edges"]), "relation_path": str(path)})
    return 0

def command_expand_crossref_references(args: argparse.Namespace) -> int:
    """Expand deposited Crossref reference metadata for one accepted evidence card."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        require_active_run(run_dir, mission.mission_id)
        cards = _evidence_cards_from_payloads(_load_array_if_present(run_dir / "evidence_cards.json", "evidence artifacts"))
        decisions = _verification_decisions_from_payloads(_load_array_if_present(run_dir / "verification_decisions.json", "verification decision artifacts"))
        card = next((item for item in cards if item.evidence_id == args.evidence_id), None)
        decision = next((item for item in decisions if item.evidence_id == args.evidence_id and item.mission_id == mission.mission_id), None)
        if card is None or decision is None:
            raise CrossrefRelationExpansionError("evidence_id must have a recorded card and review decision in this mission")
        work = CrossrefAdapter(Settings.load()).work_references_by_doi(card.provenance.doi or "")
        expansion = build_crossref_relation_expansion(mission, card, decision, work)
        path = write_crossref_relation_expansion(run_dir, expansion)
    except (UiExportError, RunControlError, CrossrefRequestError, CrossrefRelationExpansionError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id, "evidence_id": args.evidence_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="crossref_references_expanded",
        actor="citation_array",
        state=MissionState.MAP,
        payload={"evidence_id": args.evidence_id, "provider": "crossref", "edge_count": len(expansion["edges"]), "reference_field_present": expansion["reference_field_present"]},
    )
    _json_print({"run_id": args.run_id, "evidence_id": args.evidence_id, "edge_count": len(expansion["edges"]), "reference_field_present": expansion["reference_field_present"], "relation_path": str(path)})
    return 0
def command_record_condition_normalization(args: argparse.Namespace) -> int:
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        cards = _evidence_cards_from_payloads(_load_array_if_present(run_dir / "evidence_cards.json", "evidence artifacts"))
        decisions = _verification_decisions_from_payloads(_load_array_if_present(run_dir / "verification_decisions.json", "verification decision artifacts"))
        selection = json.loads(Path(args.input).read_text(encoding="utf-8"))
        artifact = condition_normalization_from_review(mission, cards, decisions, selection)
        path = write_condition_normalization(run_dir, artifact)
    except (OSError, json.JSONDecodeError, UiExportError, ConditionNormalizationError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(event_type="condition_normalization_reviewed", actor="source_reviewer", state=MissionState.MAP, payload={"mapping_count": len(artifact["mappings"])})
    _json_print({"run_id": args.run_id, "mapping_count": len(artifact["mappings"]), "normalization_path": str(path)})
    return 0
def command_reconcile_relations(args: argparse.Namespace) -> int:
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        selection = json.loads(Path(args.input).read_text(encoding="utf-8"))
        artifact = reconciliation_from_review(mission_id=mission.mission_id, openalex=_load_object(run_dir / "relation_expansion.json", "OpenAlex relation artifact"), crossref=_load_object(run_dir / "crossref_relation_expansion.json", "Crossref relation artifact"), selection=selection)
        path = write_relation_reconciliation(run_dir, artifact)
    except (OSError, json.JSONDecodeError, UiExportError, RelationReconciliationError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(event_type="cross_source_identity_reviewed", actor="source_reviewer", state=MissionState.MAP, payload={"mapping_count": len(artifact["mappings"]), "statuses": sorted({item["status"] for item in artifact["mappings"]})})
    _json_print({"run_id": args.run_id, "mapping_count": len(artifact["mappings"]), "reconciliation_path": str(path)})
    return 0
def command_record_paper_structure(args: argparse.Namespace) -> int:
    """Record reviewer-approved paper-scoped entities and internal relations."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        selection = json.loads(Path(args.input).read_text(encoding="utf-8"))
        document_id = selection.get("document_id") if isinstance(selection, dict) else None
        if not isinstance(document_id, str) or not document_id.strip():
            raise PaperStructureError("paper structure selection requires a document_id")
        source_map = load_source_map_for_document(run_dir, mission.mission_id, document_id)
        if source_map is None:
            raise PaperStructureError("paper structure requires a reviewed source map for the selected document")
        structure = paper_structure_from_review(mission_id=mission.mission_id, source_map=source_map, selection=selection)
        path = write_paper_structure_for_document(run_dir, structure)
    except (OSError, json.JSONDecodeError, UiExportError, PaperStructureError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(event_type="paper_structure_reviewed", actor="source_reviewer", state=MissionState.MAP, payload={"document_id": structure["document_id"], "entity_count": len(structure["entities"]), "relation_count": len(structure["relations"])})
    _json_print({"run_id": args.run_id, "document_id": structure["document_id"], "entity_count": len(structure["entities"]), "relation_count": len(structure["relations"]), "paper_structure_path": str(path)})
    return 0

def command_generate_gap_candidates(args: argparse.Namespace) -> int:
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        plan = load_approved_flight_plan(run_dir, mission.mission_id)
        candidate_history = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate history")
        counterevidence = require_executed_counterevidence(plan, candidate_history)
        cards = _evidence_cards_from_payloads(_load_array_if_present(run_dir / "evidence_cards.json", "evidence artifacts"))
        decisions = _verification_decisions_from_payloads(_load_array_if_present(run_dir / "verification_decisions.json", "verification decision artifacts"))
        payload = _load_array_if_present(run_dir / "condition_matrix.json", "condition matrix")
        rows = tuple(DiscrepancyRow(str(row["condition_cluster"]), tuple(str(x) for x in row["supporting_evidence_ids"]), tuple(str(x) for x in row["contradicting_evidence_ids"]), tuple(str(x) for x in row["differing_fields"]), tuple(str(x) for x in row["unknowns"])) for row in payload)
        candidates = candidates_from_discrepancies(
            mission.mission_id, mission.material, mission.property_name, cards, decisions,
            DiscrepancyMatrix(rows, plan.counter_queries), counterevidence,
        )
        path = write_gap_candidates(run_dir, candidates)
    except (UiExportError, PlanApprovalError, CounterevidenceGateError, GapAnalysisError, KeyError, TypeError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(event_type="research_gap_candidates_generated", actor="gap_analysis", state=MissionState.HAZARD_SCAN, payload={"candidate_count": len(candidates), "evidence_bound": True, "planned_counter_query_count": counterevidence.planned_query_count, "executed_counter_query_count": counterevidence.executed_query_count})
    _json_print({"run_id": args.run_id, "candidate_count": len(candidates), "gap_path": str(path)})
    return 0


def command_draft_gap_hypotheses(args: argparse.Namespace) -> int:
    """Ask DeepSeek for an untrusted, structural-only Gap brainstorming draft."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        require_active_run(run_dir, mission.mission_id)
        plan = load_approved_flight_plan(run_dir, mission.mission_id)
        candidate_history = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate history")
        counterevidence = require_executed_counterevidence(plan, candidate_history)
        payload = _load_array_if_present(run_dir / "condition_matrix.json", "condition matrix")
        rows = tuple(
            DiscrepancyRow(
                str(row["condition_cluster"]),
                tuple(str(item) for item in row["supporting_evidence_ids"]),
                tuple(str(item) for item in row["contradicting_evidence_ids"]),
                tuple(str(item) for item in row["differing_fields"]),
                tuple(str(item) for item in row["unknowns"]),
            )
            for row in payload
        )
        system_prompt, user_prompt = research_gap_drafting_prompts(mission, rows)
        completion = DeepSeekAdapter(Settings.load()).draft(system_prompt=system_prompt, user_prompt=user_prompt)
        path = write_untrusted_research_gap_draft(run_dir, mission, completion, rows)
    except (UiExportError, PlanApprovalError, CounterevidenceGateError, GapDraftingError, DeepSeekConfigurationError, DeepSeekRequestError, KeyError, TypeError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="research_gap_hypotheses_drafted",
        actor="gap_drafting",
        state=MissionState.HAZARD_SCAN,
        payload={
            "model": completion.model,
            "condition_row_count": len(rows),
            "planned_counter_query_count": counterevidence.planned_query_count,
            "executed_counter_query_count": counterevidence.executed_query_count,
            "trust_status": "untrusted_draft_not_candidate_or_finding",
        },
    )
    _json_print({"run_id": args.run_id, "draft_path": str(path), "trust_status": "untrusted_draft_not_candidate_or_finding"})
    return 0


def command_build_report(args: argparse.Namespace) -> int:
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        cards = _evidence_cards_from_payloads(_load_array_if_present(run_dir / "evidence_cards.json", "evidence artifacts"))
        decisions = _verification_decisions_from_payloads(
            _load_array_if_present(run_dir / "verification_decisions.json", "verification decision artifacts")
        )
        gap_path = run_dir / "research_gap_candidates.json"
        gap_candidates = load_gap_candidates(gap_path) if gap_path.exists() else ()
        audit_accepted_evidence_provenance(
            mission=mission,
            cards=cards,
            decisions=decisions,
            source_maps=iter_source_maps(run_dir, mission.mission_id),
        )
        report = build_evidence_manifest(mission, cards, decisions, gap_candidates)
        report_path = write_mission_report(run_dir, report)
        material_fact_artifacts = iter_material_facts(run_dir, mission.mission_id)
        validate_material_fact_source_links(
            mission_id=mission.mission_id,
            artifacts=material_fact_artifacts,
            source_maps=iter_source_maps(run_dir, mission.mission_id),
        )
        fusion = load_material_fact_fusion(run_dir / "material_fact_fusion.json", mission.mission_id)
        structured_report_path = write_structured_research_report(
            run_dir, build_structured_research_report(mission, cards, decisions, gap_candidates, material_fact_artifacts, fusion)
        )
    except (UiExportError, GapAnalysisError, MaterialExtractionError, KnowledgeFusionError, ProvenanceAuditError, ReportGateError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="mission_report_built",
        actor="report_delivery",
        state=MissionState.REPORT,
        payload={"report_id": report.report_id, "accepted_evidence_count": len(report.evidence_ids), "research_gap_candidate_count": len(report.research_gap_candidate_ids), "structured_report_generated": True},
    )
    _json_print({"run_id": args.run_id, "report_id": report.report_id, "report_path": str(report_path), "structured_report_path": str(structured_report_path)})
    return 0




def command_audit_frozen_corpus_readiness(args: argparse.Namespace) -> int:
    """Write a count-only audit for an already human-reviewed frozen corpus."""
    if not 1 <= args.expected_count <= 250:
        _json_print({"error": "expected document count must be between 1 and 250", "run_id": args.run_id})
        return 2
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        payload = frozen_corpus_readiness(run_dir=run_dir, mission_id=mission.mission_id, expected_document_count=args.expected_count)
        path = write_frozen_corpus_readiness(run_dir, payload)
    except (UiExportError, CorpusReadinessError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="frozen_corpus_readiness_audited", actor="corpus_review", state=MissionState.HUMAN_REVIEW,
        payload={"frozen_document_count": payload["frozen_document_count"], "expected_count_matched": payload["expected_count_matched"]},
    )
    _json_print({"run_id": args.run_id, "readiness_path": str(path), "evaluation_gate": payload["evaluation_gate"]})
    return 0


def command_audit_human_annotation_coverage(args: argparse.Namespace) -> int:
    """Write count-only coverage of an authorized human annotation file."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        payload = annotation_coverage_audit(run_dir=run_dir, mission_id=mission.mission_id, annotation_path=Path(args.input))
        path = write_annotation_coverage_audit(run_dir, payload)
    except (OSError, UiExportError, AnnotationCoverageError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="human_annotation_coverage_audited", actor="evaluation_reviewer", state=MissionState.HUMAN_REVIEW,
        payload={"frozen_document_count": payload["frozen_document_count"], "relevance_gate": payload["relevance_evaluation_gate"]},
    )
    _json_print({"run_id": args.run_id, "coverage_path": str(path), "relevance_evaluation_gate": payload["relevance_evaluation_gate"]})
    return 0


def command_create_bibliographic_source_template(args: argparse.Namespace) -> int:
    """Create private, blank metadata-source review slots for one frozen corpus."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        manifest = load_corpus_manifest(run_dir / "corpus_manifest.json", mission.mission_id)
        if manifest is None:
            raise CorpusPreparationError("bibliographic source template requires a recorded corpus manifest")
        payload = bibliographic_source_template_from_manifest(manifest)
        path = write_bibliographic_source_template(run_dir, payload)
    except (UiExportError, CorpusPreparationError, BibliographicSourceCoverageError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="bibliographic_source_registry_template_created", actor="corpus_reviewer", state=MissionState.HUMAN_REVIEW,
        payload={"corpus_id": payload["corpus_id"], "frozen_document_count": len(payload["documents"])},
    )
    _json_print({"run_id": args.run_id, "template_path": str(path), "frozen_document_count": len(payload["documents"]), "trust_status": payload["trust_status"]})
    return 0


def command_prepare_real_evaluation(args: argparse.Namespace) -> int:
    """Create the blank, path-free review pack for one frozen corpus.

    This command intentionally creates preparation artifacts only. It cannot
    create a human judgment or evaluation metric, and it never opens local
    paper files, annotations, provider records, or environment secrets.
    """
    if not 1 <= args.expected_count <= 250:
        _json_print({"error": "expected document count must be between 1 and 250", "run_id": args.run_id})
        return 2
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        manifest = load_corpus_manifest(run_dir / "corpus_manifest.json", mission.mission_id)
        if manifest is None:
            raise CorpusPreparationError("real evaluation preparation requires a recorded corpus manifest")
        readiness = frozen_corpus_readiness(
            run_dir=run_dir, mission_id=mission.mission_id, expected_document_count=args.expected_count
        )
        readiness_path = write_frozen_corpus_readiness(run_dir, readiness)
        gold_standard = gold_standard_template_from_manifest(manifest)
        gold_standard_path = write_gold_standard_template(run_dir, gold_standard)
        bibliographic_source = bibliographic_source_template_from_manifest(manifest)
        bibliographic_source_path = write_bibliographic_source_template(run_dir, bibliographic_source)
        run_record = evaluation_run_record_template(manifest=manifest, mission_id=mission.mission_id)
        run_record_path = write_evaluation_run_record_template(run_dir, run_record)
        candidate_path = None
        if args.seed_candidates:
            candidates = candidates_from_authorized_corpus_manifest(manifest, mission.question)
            candidate_path = write_candidate_artifact(run_dir, mission.question, candidates)
    except (UiExportError, CorpusReadinessError, CorpusPreparationError, BibliographicSourceCoverageError, EvaluationRunRecordError, RetrievalArtifactError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="real_corpus_evaluation_preparation_created",
        actor="evaluation_reviewer",
        state=MissionState.HUMAN_REVIEW,
        payload={
            "corpus_id": manifest["corpus_id"],
            "frozen_document_count": len(manifest["documents"]),
            "expected_count_matched": readiness["expected_count_matched"],
            "candidate_seeding_requested": bool(args.seed_candidates),
        },
    )
    _json_print({
        "run_id": args.run_id,
        "corpus_id": manifest["corpus_id"],
        "frozen_document_count": len(manifest["documents"]),
        "evaluation_gate": readiness["evaluation_gate"],
        "candidate_seeding_requested": bool(args.seed_candidates),
        "frozen_corpus_readiness_path": str(readiness_path),
        "gold_standard_template_path": str(gold_standard_path),
        "bibliographic_source_template_path": str(bibliographic_source_path),
        "evaluation_run_record_template_path": str(run_record_path),
        "candidates_path": str(candidate_path) if candidate_path else None,
    })
    return 0


def command_audit_bibliographic_source_coverage(args: argparse.Namespace) -> int:
    """Write a count-only audit for a private, human-reviewed source registry."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        payload = bibliographic_source_coverage_audit(run_dir=run_dir, mission_id=mission.mission_id, registry_path=Path(args.input))
        path = write_bibliographic_source_coverage_audit(run_dir, payload)
    except (OSError, UiExportError, BibliographicSourceCoverageError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="bibliographic_source_coverage_audited", actor="corpus_reviewer", state=MissionState.HUMAN_REVIEW,
        payload={"frozen_document_count": payload["frozen_document_count"], "source_coverage_gate": payload["bibliographic_source_coverage_gate"]},
    )
    _json_print({"run_id": args.run_id, "coverage_path": str(path), "source_coverage_gate": payload["bibliographic_source_coverage_gate"]})
    return 0

def command_compare_human_retrieval_routes(args: argparse.Namespace) -> int:
    """Compare reviewed aggregate retrieval metrics from one frozen corpus only."""
    run_dir = _run_dir(args.run_id)
    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or set(payload) != {"baseline_route_id", "routes"}:
            raise RetrievalRouteComparisonError("route comparison input must contain only baseline_route_id and routes")
        comparison = compare_human_retrieval_routes(
            routes=payload["routes"], baseline_route_id=payload["baseline_route_id"],
        )
        path = write_retrieval_route_comparison(run_dir, comparison)
    except (OSError, json.JSONDecodeError, RetrievalRouteComparisonError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="human_retrieval_routes_compared", actor="evaluation_reviewer", state=MissionState.HUMAN_REVIEW,
        payload={"route_count": len(comparison["route_metrics"]), "k": comparison["k"], "baseline_route_id": comparison["baseline_route_id"]},
    )
    _json_print({"run_id": args.run_id, "comparison_path": str(path), "trust_status": comparison["trust_status"]})
    return 0

def command_create_ising_benchmark_plan(args: argparse.Namespace) -> int:
    """Create a finite seeded classical-MC plan; it does not execute samples."""
    try:
        plan = build_ising_benchmark_plan(
            lattice_size=args.lattice_size,
            temperatures=tuple(args.temperature),
            burn_in_sweeps=args.burn_in_sweeps,
            measurement_sweeps=args.measurement_sweeps,
            seed=args.seed,
            repetitions=args.repetitions,
        )
        path = write_ising_plan(_run_dir(args.run_id), plan)
    except IsingBenchmarkError as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="ising_benchmark_plan_created", actor="classical_mc_benchmark", state=MissionState.PLAN,
        payload={"lattice_size": plan["lattice_size"], "temperature_count": len(plan["temperatures"]), "seed": plan["seed"], "repetitions": plan["repetitions"], "not_run": True},
    )
    _json_print({"run_id": args.run_id, "plan_path": str(path), "trust_status": plan["trust_status"]})
    return 0


def command_run_ising_benchmark(args: argparse.Namespace) -> int:
    """Run a bounded local classical-MC benchmark already fixed by its plan."""
    run_dir = _run_dir(args.run_id)
    try:
        plan = _load_object(run_dir / "ising_benchmark_plan.json", "Ising benchmark plan")
        result = run_ising_benchmark(plan=plan)
        path = write_ising_result(run_dir, result)
    except (UiExportError, IsingBenchmarkError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="ising_benchmark_executed", actor="classical_mc_benchmark", state=MissionState.HUMAN_REVIEW,
        payload={"lattice_size": result["lattice_size"], "temperature_count": len(result["temperatures"]), "seed": result["seed"], "repetitions": result["repetitions"], "scope_limited": True},
    )
    _json_print({"run_id": args.run_id, "result_path": str(path), "trust_status": result["trust_status"]})
    return 0


def command_propose_ising_followups(args: argparse.Namespace) -> int:
    """Create a non-executing, approval-required MC refinement proposal."""
    run_dir = _run_dir(args.run_id)
    try:
        plan = _load_object(run_dir / "ising_benchmark_plan.json", "Ising benchmark plan")
        result = _load_object(run_dir / "ising_benchmark_result.json", "Ising benchmark result")
        followups = propose_ising_followups(plan=plan, result=result)
        path = write_ising_followups(run_dir, followups)
    except (UiExportError, IsingBenchmarkError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="ising_benchmark_followups_proposed", actor="classical_mc_benchmark", state=MissionState.HUMAN_REVIEW,
        payload={"approval_required": True, "trigger_algorithm": followups["trigger"]["algorithm"]},
    )
    _json_print({"run_id": args.run_id, "followups_path": str(path), "trust_status": followups["trust_status"]})
    return 0


def command_export_ising_benchmark_summary(args: argparse.Namespace) -> int:
    """Export a compact, scope-limited aggregate from an executed local run."""
    run_dir = _run_dir(args.run_id)
    try:
        plan = _load_object(run_dir / "ising_benchmark_plan.json", "Ising benchmark plan")
        result = _load_object(run_dir / "ising_benchmark_result.json", "Ising benchmark result")
        followup_path = run_dir / "ising_benchmark_followups.json"
        followups = _load_object(followup_path, "Ising benchmark followups") if followup_path.is_file() else None
        payload = ising_benchmark_summary(plan=plan, result=result, followups=followups)
        path = write_ising_benchmark_summary(run_dir, payload)
    except (UiExportError, IsingSummaryError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="ising_benchmark_summary_exported", actor="classical_mc_benchmark", state=MissionState.HUMAN_REVIEW,
        payload={"metric_count": len(payload["metrics"]), "scope_limited": True, "followup_included": payload["followup_proposal"] is not None},
    )
    _json_print({"run_id": args.run_id, "summary_path": str(path), "trust_status": payload["trust_status"]})
    return 0

def command_create_potential_benchmark_plan(args: argparse.Namespace) -> int:
    """Create a deterministic, framework-only potential comparison plan."""
    try:
        controls_payload = json.loads(Path(args.controls).read_text(encoding="utf-8-sig"))
        if not isinstance(controls_payload, dict):
            raise PotentialBenchmarkError("controls JSON must be an object")
        controls = {
            name: (values[0], values[1])
            for name, values in controls_payload.items()
            if isinstance(name, str) and isinstance(values, list) and len(values) == 2
        }
        if len(controls) != len(controls_payload):
            raise PotentialBenchmarkError("controls JSON values must all be [min, max] arrays")
        plan = generate_potential_boundary_plan(
            system_label=args.system, potential_models=tuple(args.model), reference_method=args.reference_method,
            baseline_model_id=args.baseline_model, seed=args.seed, controls=controls, samples_per_regime=args.samples_per_regime,
        )
        path = write_potential_plan(_run_dir(args.run_id), plan)
    except (OSError, json.JSONDecodeError, PotentialBenchmarkError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="potential_benchmark_plan_created", actor="potential_benchmark", state=MissionState.PLAN,
        payload={"model_count": len(plan["potential_models"]), "task_count": len(plan["tasks"]), "seed": args.seed, "framework_only": True},
    )
    _json_print({"run_id": args.run_id, "plan_path": str(path), "trust_status": plan["trust_status"]})
    return 0


def command_evaluate_potential_benchmark(args: argparse.Namespace) -> int:
    """Evaluate a complete result summary from an approved external calculation."""
    run_dir = _run_dir(args.run_id)
    try:
        plan = _load_object(run_dir / "potential_benchmark_plan.json", "potential benchmark plan")
        results = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if not isinstance(results, list):
            raise PotentialBenchmarkError("potential benchmark results must be a JSON array")
        protocol_path = run_dir / "potential_execution_protocol.json"
        protocol = _load_object(protocol_path, "potential execution protocol") if protocol_path.is_file() else None
        report = evaluate_potential_results(plan=plan, results=results, execution_protocol=protocol)
        path = write_potential_evaluation(run_dir, report)
    except (OSError, json.JSONDecodeError, UiExportError, PotentialBenchmarkError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="potential_benchmark_external_results_imported", actor="potential_benchmark", state=MissionState.HUMAN_REVIEW,
        payload={"model_count": len(report["model_summaries"]), "external_execution_confirmed_by_import_only": True, "execution_protocol_status": report["execution_protocol_status"]},
    )
    _json_print({"run_id": args.run_id, "evaluation_path": str(path), "trust_status": report["trust_status"]})
    return 0


def command_propose_potential_followups(args: argparse.Namespace) -> int:
    """Create approval-required followup tasks from imported benchmark results."""
    run_dir = _run_dir(args.run_id)
    try:
        plan = _load_object(run_dir / "potential_benchmark_plan.json", "potential benchmark plan")
        evaluation = _load_object(run_dir / "potential_benchmark_evaluation.json", "potential benchmark evaluation")
        payload = propose_potential_followups(plan=plan, evaluation=evaluation)
        path = write_potential_followups(run_dir, payload)
    except (OSError, UiExportError, PotentialBenchmarkError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="potential_benchmark_followups_proposed", actor="potential_benchmark", state=MissionState.PLAN,
        payload={"followup_task_count": len(payload["followup_tasks"]), "approval_required": True},
    )
    _json_print({"run_id": args.run_id, "followup_path": str(path), "trust_status": payload["trust_status"]})
    return 0


def command_record_external_resource_disclosure(args: argparse.Namespace) -> int:
    """Record a human-completed, secret-safe external-resource disclosure for one run."""
    run_dir = _run_dir(args.run_id)
    try:
        payload = load_external_resource_disclosure(Path(args.input))
        path = write_external_resource_disclosure(run_dir, payload)
    except (ExternalResourceDisclosureError, OSError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="external_resource_disclosure_recorded",
        actor="human_submission_review",
        state=_last_recorded_state(run_dir / "events.jsonl"),
        payload={
            "resource_count": len(payload["resources"]),
            "used_in_final_result_count": sum(item["used_in_final_result"] for item in payload["resources"]),
        },
    )
    _json_print({"run_id": args.run_id, "disclosure_path": str(path), "resource_count": len(payload["resources"])})
    return 0

def command_create_potential_execution_protocol_template(args: argparse.Namespace) -> int:
    """Write a plan-bound, non-executing protocol template for external calculations."""
    try:
        plan = _load_object(_run_dir(args.run_id) / "potential_benchmark_plan.json", "potential benchmark plan")
        payload = execution_protocol_template(plan=plan)
        path = _run_dir(args.run_id) / "potential_execution_protocol_template.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, UiExportError, PotentialProtocolError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    _json_print({"run_id": args.run_id, "template_path": str(path), "trust_status": payload["trust_status"]})
    return 0


def command_record_potential_execution_protocol(args: argparse.Namespace) -> int:
    """Record a human-authored external-calculation protocol without executing it."""
    run_dir = _run_dir(args.run_id)
    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        path = write_potential_execution_protocol(run_dir, payload)
    except (OSError, json.JSONDecodeError, PotentialProtocolError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="potential_execution_protocol_recorded", actor="human_potential_review", state=MissionState.PLAN,
        payload={"approval_status": payload["approval"]["status"], "model_count": len(payload["potential_models"]), "not_executed": True},
    )
    _json_print({"run_id": args.run_id, "protocol_path": str(path), "approval_status": payload["approval"]["status"]})
    return 0


def command_check_submission_readiness(args: argparse.Namespace) -> int:
    """Check source, disclosure, and optional LaTeX submission package presence."""
    try:
        run_dir = _run_dir(args.run_id) if args.run_id else None
        result = submission_readiness(repository_root=AGENT_ROOT, run_dir=run_dir)
    except SubmissionReadinessError as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    _json_print(result)
    return 0 if result["ready"] else 1


def command_build_submission_source_bundle(args: argparse.Namespace) -> int:
    """Build an allowlisted source ZIP for the preliminary submission."""
    try:
        output = Path(args.output).expanduser().resolve() if args.output else AGENT_ROOT / "submission" / "cosmatter_preliminary_source.zip"
        payload = build_source_bundle(repository_root=AGENT_ROOT, output_path=output)
    except SubmissionBundleError as error:
        _json_print({"error": str(error)})
        return 2
    _json_print(payload)
    return 0

def command_build_final_submission_package(args: argparse.Namespace) -> int:
    """Package only source plus a readiness-checked reviewed report for submission."""
    try:
        output = Path(args.output).expanduser().resolve() if args.output else AGENT_ROOT / "submission" / f"cosmatter_preliminary_{args.run_id}.zip"
        payload = build_final_submission_package(
            repository_root=AGENT_ROOT, run_dir=_run_dir(args.run_id), output_path=output,
        )
    except (FinalSubmissionError, SubmissionReadinessError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    _json_print(payload)
    return 0

def command_export_latex_report(args: argparse.Namespace) -> int:
    """Export a competition-submission LaTeX source package from reviewed work."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        cards = _evidence_cards_from_payloads(_load_array_if_present(run_dir / "evidence_cards.json", "evidence artifacts"))
        decisions = _verification_decisions_from_payloads(
            _load_array_if_present(run_dir / "verification_decisions.json", "verification decision artifacts")
        )
        candidate_payload = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate artifact")
        candidates = candidate_payload.get("candidates")
        if not isinstance(candidates, list) or not all(isinstance(item, dict) for item in candidates):
            raise LatexReportError("retrieval candidate artifact lacks bibliographic candidate records")
        gap_path = run_dir / "research_gap_candidates.json"
        gap_candidates = load_gap_candidates(gap_path) if gap_path.exists() else ()
        output_dir = Path(args.output).expanduser().resolve() if args.output else run_dir / "latex_submission"
        export = export_latex_report(
            output_dir=output_dir,
            mission=mission,
            cards=cards,
            decisions=decisions,
            document_metadata=tuple(candidates),
            research_gap_candidates=gap_candidates,
        )
        pdf_path = compile_latex_report(export) if args.compile else None
    except (OSError, UiExportError, GapAnalysisError, LatexReportError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="latex_submission_report_exported",
        actor="submission_reporting",
        state=MissionState.REPORT,
        payload={
            "accepted_evidence_count": json.loads(export.manifest_path.read_text(encoding="utf-8"))["accepted_evidence_count"],
            "research_gap_candidate_count": json.loads(export.manifest_path.read_text(encoding="utf-8"))["research_gap_candidate_count"],
            "pdf_compiled": pdf_path is not None,
        },
    )
    _json_print({
        "run_id": args.run_id,
        "output_dir": str(export.output_dir),
        "tex_path": str(export.tex_path),
        "bib_path": str(export.bib_path),
        "citation_audit_path": str(export.citation_audit_path),
        "pdf_path": str(pdf_path) if pdf_path is not None else None,
        "trust_status": "review_gated_latex_source_not_scientific_validity_assessment",
    })
    return 0

def command_audit_report_evidence(args: argparse.Namespace) -> int:
    """Audit persisted identifier coverage; it does not validate scientific truth."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        cards = _evidence_cards_from_payloads(_load_array_if_present(run_dir / "evidence_cards.json", "evidence artifacts"))
        decisions = _verification_decisions_from_payloads(
            _load_array_if_present(run_dir / "verification_decisions.json", "verification decision artifacts")
        )
        gap_path = run_dir / "research_gap_candidates.json"
        gap_candidates = load_gap_candidates(gap_path) if gap_path.exists() else ()
        audit_accepted_evidence_provenance(
            mission=mission,
            cards=cards,
            decisions=decisions,
            source_maps=iter_source_maps(run_dir, mission.mission_id),
        )
        report_payload = _load_object(run_dir / "mission_report.json", "mission report artifact")
        structured_report = (run_dir / "research_report.md").read_text(encoding="utf-8")
        material_fact_artifacts = iter_material_facts(run_dir, mission.mission_id)
        validate_material_fact_source_links(
            mission_id=mission.mission_id,
            artifacts=material_fact_artifacts,
            source_maps=iter_source_maps(run_dir, mission.mission_id),
        )
        fusion = load_material_fact_fusion(run_dir / "material_fact_fusion.json", mission.mission_id)
        result = audit_report_evidence(
            mission=mission,
            cards=cards,
            decisions=decisions,
            research_gap_candidates=gap_candidates,
            report_payload=report_payload,
            structured_report=structured_report,
            material_fact_artifacts=material_fact_artifacts,
            material_fact_fusion=fusion,
        )
        audit_path = write_report_evidence_audit(run_dir, result)
    except (OSError, UiExportError, GapAnalysisError, MaterialExtractionError, KnowledgeFusionError, ProvenanceAuditError, ReportAuditError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="report_evidence_audited",
        actor="report_audit",
        state=MissionState.REPORT,
        payload={
            "accepted_evidence_count": result["accepted_evidence_count"],
            "research_gap_candidate_count": result["research_gap_candidate_count"],
            "reviewed_material_fact_count": result["reviewed_material_fact_count"],
            "cross_document_comparison_count": result["cross_document_comparison_count"],
            "artifact_level_identifier_audit": True,
        },
    )
    _json_print({"run_id": args.run_id, "audit_path": str(audit_path), "trust_status": result["trust_status"]})
    return 0


def command_audit_evidence_provenance(args: argparse.Namespace) -> int:
    """Audit accepted EvidenceCards against reviewed source-map segments."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        cards = _evidence_cards_from_payloads(_load_array_if_present(run_dir / "evidence_cards.json", "evidence artifacts"))
        decisions = _verification_decisions_from_payloads(
            _load_array_if_present(run_dir / "verification_decisions.json", "verification decision artifacts")
        )
        result = audit_accepted_evidence_provenance(
            mission=mission,
            cards=cards,
            decisions=decisions,
            source_maps=iter_source_maps(run_dir, mission.mission_id),
        )
        audit_path = write_evidence_provenance_audit(run_dir, result)
    except (UiExportError, SourceMapError, ProvenanceAuditError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="accepted_evidence_provenance_audited",
        actor="evidence_provenance_audit",
        state=MissionState.VERIFY,
        payload={
            "accepted_evidence_count": result["accepted_evidence_count"],
            "exact_reviewed_source_map_match_count": result["exact_reviewed_source_map_match_count"],
            "manual_locator_only_count": result["manual_locator_only_count"],
        },
    )
    _json_print({"run_id": args.run_id, "audit_path": str(audit_path), "exact_source_map_match_rate": result["exact_source_map_match_rate"]})
    return 0


def command_evaluate_agent_benchmark(args: argparse.Namespace) -> int:
    try:
        report = evaluate_frozen_agent_benchmark(Path(args.fixture), f"benchmark_{args.run_id}")
    except AgentBenchmarkError as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    path = write_agent_benchmark_record(recorder.run_dir, report)
    recorder.record(event_type="synthetic_agent_benchmark_evaluated", actor="evaluation", state=MissionState.REPORT, payload={"fixture_id": report.fixture_id, "fixture_sha256": report.fixture_sha256, "synthetic": True, "metric_names": sorted(report.to_dict().keys())})
    _json_print({"run_id": args.run_id, "fixture_id": report.fixture_id, "fixture_sha256": report.fixture_sha256, "benchmark_path": str(path), "synthetic": True})
    return 0

def command_ingest_evidence(args: argparse.Namespace) -> int:
    run_dir = _run_dir(args.run_id)
    try:
        draft = json.loads(Path(args.input).read_text(encoding="utf-8"))
        decision = ingest_evidence_draft(run_dir, draft)
    except (OSError, json.JSONDecodeError, EvidenceIngestionError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="evidence_ingested",
        actor="source_locator",
        state=MissionState.EXTRACT,
        payload={"evidence_id": decision.evidence_id, "status": decision.status.value, "decision_id": decision.decision_id},
    )
    _json_print({"run_id": args.run_id, "evidence_id": decision.evidence_id, "status": decision.status.value})
    return 0

def _accepted_evidence_for_quality_review(run_dir: Path, mission_id: str):
    cards = _evidence_cards_from_payloads(_load_array_if_present(run_dir / "evidence_cards.json", "evidence artifacts"))
    decisions = _verification_decisions_from_payloads(
        _load_array_if_present(run_dir / "verification_decisions.json", "verification decision artifacts")
    )
    accepted_ids = {
        decision.evidence_id
        for decision in decisions
        if decision.mission_id == mission_id and decision.status.value == "accepted"
    }
    accepted = tuple(card for card in cards if card.evidence_id in accepted_ids)
    if not accepted:
        raise EvidenceQualityEvaluationError("evidence-quality review requires at least one accepted EvidenceCard")
    return accepted


def command_create_evidence_quality_review_template(args: argparse.Namespace) -> int:
    """Create narrow human-review slots for the current accepted evidence set."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        cards = _accepted_evidence_for_quality_review(run_dir, mission.mission_id)
        template = evidence_quality_review_template(mission_id=mission.mission_id, cards=cards)
        path = write_evidence_quality_review_template(run_dir, template)
    except (UiExportError, EvidenceQualityEvaluationError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="human_evidence_quality_review_template_created",
        actor="evaluation_reviewer",
        state=MissionState.HUMAN_REVIEW,
        payload={"accepted_evidence_count": len(template["assessments"])},
    )
    _json_print({"run_id": args.run_id, "accepted_evidence_count": len(template["assessments"]), "template_path": str(path)})
    return 0


def command_evaluate_human_evidence_quality(args: argparse.Namespace) -> int:
    """Summarize independent review of current evidence locators and conditions."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        cards = _accepted_evidence_for_quality_review(run_dir, mission.mission_id)
        assessments = load_reviewed_evidence_quality_assessment(
            Path(args.input), mission_id=mission.mission_id, cards=cards
        )
        result = evidence_quality_evaluation_from_assessments(
            mission_id=mission.mission_id, assessments=assessments
        )
        path = write_evidence_quality_evaluation(run_dir, result)
    except (UiExportError, EvidenceQualityEvaluationError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="human_evidence_quality_evaluated",
        actor="evaluation_reviewer",
        state=MissionState.HUMAN_REVIEW,
        payload={
            "evidence_count": result["evidence_count"],
            "predicted_contradiction_count": result["predicted_contradiction_count"],
        },
    )
    _json_print({"run_id": args.run_id, "evaluation_path": str(path), "trust_status": result["trust_status"]})
    return 0


def command_create_gap_review_template(args: argparse.Namespace) -> int:
    """Create blank expert-review slots for exactly the current Gap candidates."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        candidates = load_gap_candidates(run_dir / "research_gap_candidates.json")
        template = gap_review_template(
            mission_id=mission.mission_id,
            gap_ids=tuple(candidate.gap_id for candidate in candidates),
        )
        path = write_gap_review_template(run_dir, template)
    except (UiExportError, GapAnalysisError, GapReviewEvaluationError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="human_gap_review_template_created",
        actor="evaluation_reviewer",
        state=MissionState.HUMAN_REVIEW,
        payload={"candidate_count": len(template["assessments"])},
    )
    _json_print({"run_id": args.run_id, "candidate_count": len(template["assessments"]), "template_path": str(path)})
    return 0


def command_evaluate_human_gaps(args: argparse.Namespace) -> int:
    """Summarize independent expert review of all current evidence-bound Gap IDs."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        candidates = load_gap_candidates(run_dir / "research_gap_candidates.json")
        assessments = load_reviewed_gap_assessment(
            Path(args.input),
            mission_id=mission.mission_id,
            gap_ids=tuple(candidate.gap_id for candidate in candidates),
        )
        result = gap_evaluation_from_assessments(
            mission_id=mission.mission_id,
            assessments=assessments,
        )
        path = write_gap_evaluation(run_dir, result)
    except (UiExportError, GapAnalysisError, GapReviewEvaluationError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="human_gap_candidates_evaluated",
        actor="evaluation_reviewer",
        state=MissionState.HUMAN_REVIEW,
        payload={"candidate_count": result["candidate_count"]},
    )
    _json_print({"run_id": args.run_id, "evaluation_path": str(path), "trust_status": result["trust_status"]})
    return 0


def command_evaluate_human_material_facts(args: argparse.Namespace) -> int:
    """Evaluate review-gated material facts against an independent human gold file."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        manifest = load_corpus_manifest(run_dir / "corpus_manifest.json", mission.mission_id)
        if manifest is None:
            raise CorpusPreparationError("material-fact evaluation requires a recorded corpus manifest")
        corpus_ids = {item["document_id"] for item in manifest["documents"]}
        gold = load_reviewed_material_fact_gold(
            Path(args.input),
            mission_id=mission.mission_id,
            corpus_id=manifest["corpus_id"],
            corpus_document_ids=corpus_ids,
        )
        result = material_fact_evaluation_from_gold(
            mission_id=mission.mission_id,
            corpus_id=manifest["corpus_id"],
            gold=gold,
            reviewed_artifacts=iter_material_facts(run_dir, mission.mission_id),
        )
        path = write_material_fact_evaluation(run_dir, result)
    except (UiExportError, CorpusPreparationError, MaterialFactEvaluationError, MaterialExtractionError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="human_gold_material_facts_evaluated",
        actor="evaluation_reviewer",
        state=MissionState.HUMAN_REVIEW,
        payload={"gold_fact_count": result["gold_fact_count"], "reviewed_fact_count": result["reviewed_fact_count"], "exact_match_count": result["exact_match_count"], "unit_match_denominator": result["unit_match_denominator"]},
    )
    _json_print({"run_id": args.run_id, "evaluation_path": str(path), "trust_status": result["trust_status"]})
    return 0


def command_evaluate_human_retrieval(args: argparse.Namespace) -> int:
    """Evaluate one recorded retrieval search against a fully reviewed gold file."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        manifest = load_corpus_manifest(run_dir / "corpus_manifest.json", mission.mission_id)
        if manifest is None:
            raise CorpusPreparationError("human retrieval evaluation requires a recorded corpus manifest")
        corpus_ids = {item["document_id"] for item in manifest["documents"]}
        gold = load_reviewed_retrieval_gold(
            Path(args.input),
            mission_id=mission.mission_id,
            corpus_id=manifest["corpus_id"],
            corpus_document_ids=corpus_ids,
        )
        candidates = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate artifact")
        result = retrieval_evaluation_from_gold(
            mission_id=mission.mission_id,
            corpus_id=manifest["corpus_id"],
            gold=gold,
            candidate_artifact=candidates,
            search_index=args.search_index,
            k=args.k,
            corpus_document_dois={item["document_id"]: item.get("doi") for item in manifest["documents"]},
        )
        path = write_human_retrieval_evaluation(run_dir, result)
    except (UiExportError, CorpusPreparationError, HumanEvaluationError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="human_gold_retrieval_evaluated",
        actor="evaluation_reviewer",
        state=MissionState.HUMAN_REVIEW,
        payload={"search_index": result["search_index"], "k": result["k"], "retrieved_count": result["retrieved_count"], "gold_relevant_count": result["gold_relevant_count"]},
    )
    _json_print({"run_id": args.run_id, "evaluation_path": str(path), "k": result["k"], "trust_status": result["trust_status"]})
    return 0


def command_evaluate_fixture(args: argparse.Namespace) -> int:
    fixture_path = Path(args.fixture)
    try:
        report = evaluate_frozen_route_fixture(fixture_path, f"evaluation_{args.run_id}")
    except EvaluationError as error:
        _json_print({"error": str(error), "fixture": str(fixture_path)})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    record_path = write_evaluation_record(recorder.run_dir, report)
    recorder.record(
        event_type="frozen_fixture_evaluated",
        actor="evaluation_lab",
        state=MissionState.VERIFY,
        payload={
            "fixture_id": report.fixture_id,
            "fixture_sha256": report.fixture_sha256,
            "citation_precision": report.citation_precision,
            "condition_completeness": report.condition_completeness,
            "contradiction_precision": report.contradiction_precision,
            "reproducibility_consistency": report.reproducibility_consistency,
        },
    )
    _json_print({"run_id": args.run_id, "fixture_id": report.fixture_id, "fixture_sha256": report.fixture_sha256, "evaluation_path": str(record_path)})
    return 0

def command_demo_flow(args: argparse.Namespace) -> int:
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    machine = MissionMachine()
    for target in (
        MissionState.PLAN,
        MissionState.RETRIEVE,
        MissionState.SELECT,
        MissionState.EXTRACT,
        MissionState.MAP,
        MissionState.HAZARD_SCAN,
        MissionState.VERIFY,
        MissionState.REPORT,
        MissionState.COMPLETE,
    ):
        previous = machine.state
        machine.transition(target)
        recorder.record(
            event_type="state_transition",
            actor="orchestrator",
            state=machine.state,
            payload={"from": previous.value, "to": machine.state.value, "mode": "offline_demo"},
        )
    _json_print({"run_id": args.run_id, "state": machine.state.value, "events_path": str(recorder.path)})
    return 0


def command_diagnose_conditions(args: argparse.Namespace) -> int:
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        plan = load_approved_flight_plan(run_dir, mission.mission_id)
        candidate_history = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate history")
        counterevidence = require_executed_counterevidence(plan, candidate_history)
        cards = _evidence_cards_from_payloads(_load_array_if_present(run_dir / "evidence_cards.json", "evidence artifacts"))
        decisions = _verification_decisions_from_payloads(
            _load_array_if_present(run_dir / "verification_decisions.json", "verification decision artifacts")
        )
        accepted_ids = {
            decision.evidence_id
            for decision in decisions
            if decision.mission_id == mission.mission_id and decision.status.value == "accepted"
        }
        matrix = condition_differential(
            tuple(card for card in cards if card.evidence_id in accepted_ids),
            plan.counter_queries,
        )
        matrix_path = write_condition_matrix(run_dir, matrix)
    except (UiExportError, PlanApprovalError, CounterevidenceGateError, FacilityGateError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="condition_diagnostics_completed",
        actor="condition_differential",
        state=MissionState.MAP,
        payload={"matrix_row_count": len(matrix.rows), "differing_field_count": sum(len(row.differing_fields) for row in matrix.rows), "planned_counter_query_count": counterevidence.planned_query_count, "executed_counter_query_count": counterevidence.executed_query_count},
    )
    _json_print({"run_id": args.run_id, "matrix_path": str(matrix_path), "matrix_row_count": len(matrix.rows)})
    return 0

def command_execute_plan_local_corpus_query(args: argparse.Namespace) -> int:
    """Execute one approved query against an explicit authorized local corpus index.

    The index path and parsed text stay process-local. Persisted artifacts carry
    only candidate metadata, query digests derived by the standard history, and
    a source label; no external provider receipt is fabricated for local work.
    """
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        require_active_run(run_dir, mission.mission_id)
        plan = load_approved_flight_plan(run_dir, mission.mission_id)
        query_kind = "counter" if args.counter else "primary"
        approved_queries = plan.counter_queries if args.counter else plan.queries
        if not 0 <= args.query_index < len(approved_queries):
            raise PlanApprovalError("query_index is outside the approved query list")
        manifest = load_corpus_manifest(run_dir / "corpus_manifest.json", mission.mission_id)
        if manifest is None:
            raise CorpusPreparationError("approved local corpus query requires a recorded corpus manifest")
        query = approved_queries[args.query_index]
        candidates = candidates_from_local_source_index(
            manifest=manifest,
            index_path=Path(args.index),
            query=query,
            top_k=plan.max_papers,
        )
        artifact_path = write_candidate_artifact(run_dir, query, candidates)
    except (UiExportError, RunControlError, PlanApprovalError, CorpusPreparationError, LocalCorpusSearchError, RetrievalArtifactError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="approved_plan_local_corpus_query_executed",
        actor="local_corpus_retriever",
        state=MissionState.RETRIEVE,
        payload={
            "plan_id": plan.artifact_id,
            "query_kind": query_kind,
            "query_index": args.query_index,
            "candidate_count": len(candidates),
            "source": "authorized_local_parsed_corpus",
        },
    )
    _json_print({
        "run_id": args.run_id,
        "query_kind": query_kind,
        "query_index": args.query_index,
        "candidate_count": len(candidates),
        "source": "authorized_local_parsed_corpus",
        "candidates_path": str(artifact_path),
    })
    return 0


def command_execute_plan_query(args: argparse.Namespace) -> int:
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        plan = load_approved_flight_plan(run_dir, mission.mission_id)
        require_active_run(run_dir, mission.mission_id)
        query_kind = "counter" if args.counter else "primary"
        approved_queries = plan.counter_queries if args.counter else plan.queries
        if not 0 <= args.query_index < len(approved_queries):
            raise PlanApprovalError("query_index is outside the approved query list")
        query = approved_queries[args.query_index]
        response = SciverseAdapter(Settings.load()).agentic_search(query, top_k=plan.max_papers)
        candidates = candidates_from_sciverse(response.payload, query, plan.max_papers)
        receipt = sciverse_search_receipt(query=query, top_k=plan.max_papers, status_code=response.status_code, request_id=response.request_id, candidate_count=len(candidates))
        append_provider_receipt(run_dir, receipt)
        artifact_path = write_candidate_artifact(
            run_dir, query, candidates,
            source_provenance={"Sciverse": {"provider": "sciverse", "operation": "agentic_search", "receipt_id": receipt["receipt_id"], "query_sha256": receipt["query_sha256"]}},
        )
    except (UiExportError, PlanApprovalError, RetrievalArtifactError, ProviderReceiptError, SciverseConfigurationError, SciverseRequestError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="approved_plan_query_executed",
        actor="search_selection",
        state=MissionState.RETRIEVE,
        payload={"plan_id": plan.artifact_id, "query_kind": query_kind, "query_index": args.query_index, "candidate_count": len(candidates), "provider": "sciverse", "receipt_id": receipt["receipt_id"], "request_id": response.request_id},
    )
    _json_print({"run_id": args.run_id, "query_kind": query_kind, "query_index": args.query_index, "candidate_count": len(candidates), "candidates_path": str(artifact_path)})
    return 0

def command_register_public_pdf_candidate(args: argparse.Namespace) -> int:
    """Register one policy-probed public PDF as a metadata-only candidate.

    This is intentionally not a download, parsing, or evidence-ingestion path.
    The plain source URL is used only for the live probe and is not retained in
    mission artifacts, output, events, or receipts.
    """
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        plan = load_approved_flight_plan(run_dir, mission.mission_id)
        require_active_run(run_dir, mission.mission_id)
        query_kind = "counter" if args.counter else "primary"
        approved_queries = plan.counter_queries if args.counter else plan.queries
        if not 0 <= args.query_index < len(approved_queries):
            raise PlanApprovalError("query_index is outside the approved query list")
        probe = probe_public_pdf(args.source_url)
        candidate = PaperCandidate(
            document_id=args.document_id.strip(),
            title=args.title.strip(),
            query=approved_queries[args.query_index],
            source="PublicOpenAccess",
            publication_year=args.publication_year,
            is_content_accessible=True,
            doi=args.doi.strip() if args.doi else None,
        )
        artifact_path = write_candidate_artifact(run_dir, candidate.query, (candidate,))
        receipt_path = run_dir / "public_pdf_probe_receipts.jsonl"
        with receipt_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(probe, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    except (OSError, UiExportError, PlanApprovalError, RetrievalArtifactError, PublicDiscoveryError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="public_pdf_candidate_registered",
        actor="public_candidate_discovery",
        state=MissionState.RETRIEVE,
        payload={
            "plan_id": plan.artifact_id,
            "query_kind": query_kind,
            "query_index": args.query_index,
            "document_id": candidate.document_id,
            "final_host": probe["final_host"],
            "redirect_count": probe["redirect_count"],
            "status_class": probe["status_class"],
            "trust_status": probe["trust_status"],
        },
    )
    _json_print({
        "run_id": args.run_id,
        "document_id": candidate.document_id,
        "candidate_count": 1,
        "source_access": probe["trust_status"],
        "candidates_path": str(artifact_path),
    })
    return 0


def command_execute_plan_public_arxiv_discovery(args: argparse.Namespace) -> int:
    """Discover arXiv metadata for one approved query without downloading PDFs."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        plan = load_approved_flight_plan(run_dir, mission.mission_id)
        require_active_run(run_dir, mission.mission_id)
        query_kind = "counter" if args.counter else "primary"
        approved_queries = plan.counter_queries if args.counter else plan.queries
        if not 0 <= args.query_index < len(approved_queries):
            raise PlanApprovalError("query_index is outside the approved query list")
        top_k = min(args.top_k, plan.max_papers)
        raw_candidates, receipt = discover_arxiv_candidates(approved_queries[args.query_index], top_k=top_k)
        candidates = tuple(
            PaperCandidate(
                document_id=item["document_id"], title=item["title"], query=item["query"], source=item["source"],
                publication_year=item["publication_year"], is_content_accessible=False,
            )
            for item in raw_candidates
        )
        artifact_path = write_candidate_artifact(run_dir, approved_queries[args.query_index], candidates)
        receipt_path = run_dir / "public_candidate_discovery_receipts.jsonl"
        with receipt_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    except (OSError, UiExportError, PlanApprovalError, RetrievalArtifactError, PublicDiscoveryError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="approved_plan_public_arxiv_discovery_executed",
        actor="public_candidate_discovery",
        state=MissionState.RETRIEVE,
        payload={
            "plan_id": plan.artifact_id,
            "query_kind": query_kind,
            "query_index": args.query_index,
            "candidate_count": len(candidates),
            "final_host": receipt["final_host"],
            "redirect_count": receipt["redirect_count"],
            "status_class": receipt["status_class"],
            "trust_status": receipt["trust_status"],
        },
    )
    _json_print({"run_id": args.run_id, "query_kind": query_kind, "query_index": args.query_index, "candidate_count": len(candidates), "source": "PublicArXiv", "candidates_path": str(artifact_path)})
    return 0


def command_sciverse_read_context(args: argparse.Namespace) -> int:
    """Fetch one screened candidate's bounded context into an explicit local review file."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        candidate_history = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate history")
        delegated_trial = bool(getattr(args, "allow_delegated_automated_trial", False))
        require_document_screened_for_fulltext(run_dir, mission.mission_id, candidate_history, args.document_id, allow_delegated_automated_trial=delegated_trial)
        output_path = Path(args.output).resolve()
        run_path = run_dir.resolve()
        if output_path.exists() or output_path.suffix.casefold() not in {".txt", ".md"} or not output_path.parent.is_dir() or output_path.is_relative_to(run_path):
            raise ValueError("review output must be a new .txt or .md file outside the run directory with an existing parent")
        response = SciverseAdapter(Settings.load()).read_content(args.document_id, offset=args.offset, limit=args.limit)
        receipt = sciverse_content_receipt(document_id=args.document_id, offset=args.offset, limit=args.limit, content=response.text, next_offset=response.next_offset, more=response.more, status_code=response.status_code, request_id=response.request_id)
        append_provider_receipt(run_dir, receipt)
        confirmation_path = record_sciverse_content_access(
            run_dir,
            mission_id=mission.mission_id,
            candidate_payload=candidate_history,
            document_id=args.document_id,
            receipt=receipt,
            delegated_automated_trial=delegated_trial,
        )
        output_path.write_text(response.text, encoding="utf-8")
    except (OSError, UiExportError, CandidateScreeningError, ContentAccessError, EvidenceIngestionError, ProviderReceiptError, SciverseConfigurationError, SciverseRequestError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(event_type="delegated_automated_trial_sciverse_content_context_fetched" if delegated_trial else "sciverse_content_context_fetched", actor="delegated_automated_trial_reviewer" if delegated_trial else "evidence_context_reader", state=MissionState.RETRIEVE, payload={"offset": args.offset, "limit": args.limit, "content_char_count": receipt["content_char_count"], "more": response.more, "receipt_id": receipt["receipt_id"], "trust_status": "delegated_automated_trial_content_access_probe_not_evidence" if delegated_trial else "explicit_human_requested_content_access_probe_not_evidence"})
    _json_print({"run_id": args.run_id, "document_id": args.document_id, "offset": args.offset, "content_char_count": receipt["content_char_count"], "next_offset": response.next_offset, "more": response.more, "review_output": str(output_path), "content_access_confirmation": str(confirmation_path)})
    return 0


def command_audit_candidate_receipts(args: argparse.Namespace) -> int:
    """Verify that persisted provider-linked candidate origins retain real receipts."""
    run_dir = _run_dir(args.run_id)
    try:
        candidates = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate artifact")
        result = audit_candidate_receipt_links(candidates, run_dir / "provider_receipts.jsonl")
        audit_path = write_candidate_receipt_audit(run_dir, result)
    except (OSError, UiExportError, ProviderReceiptError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="candidate_receipt_links_audited",
        actor="retrieval_audit",
        state=MissionState.RETRIEVE,
        payload={"candidate_count": result["candidate_count"], "provider_linked_origin_count": result["provider_linked_origin_count"], "provider_receipt_count": result["provider_receipt_count"]},
    )
    _json_print({"run_id": args.run_id, "audit_path": str(audit_path), "trust_status": result["trust_status"]})
    return 0


def command_sciverse_search(args: argparse.Namespace) -> int:
    try:
        response = SciverseAdapter(Settings.load()).agentic_search(args.query, top_k=args.top_k)
        candidates = candidates_from_sciverse(response.payload, args.query, args.top_k)
        recorder = FlightRecorder(_runs_dir(), args.run_id)
        receipt = sciverse_search_receipt(query=args.query, top_k=args.top_k, status_code=response.status_code, request_id=response.request_id, candidate_count=len(candidates))
        append_provider_receipt(recorder.run_dir, receipt)
        artifact_path = write_candidate_artifact(
            recorder.run_dir, args.query, candidates,
            source_provenance={"Sciverse": {"provider": "sciverse", "operation": "agentic_search", "receipt_id": receipt["receipt_id"], "query_sha256": receipt["query_sha256"]}},
        )
    except (ProviderReceiptError, RetrievalArtifactError, SciverseConfigurationError, SciverseRequestError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    recorder.record(
        event_type="sciverse_agentic_search",
        actor="radar_retriever",
        state=MissionState.RETRIEVE,
        payload={
            "top_k": args.top_k,
            "status_code": response.status_code,
            "request_id": response.request_id,
            "candidate_count": len(candidates),
            "provider": "sciverse",
            "receipt_id": receipt["receipt_id"],
        },
    )
    _json_print(
        {
            "status_code": response.status_code,
            "request_id": response.request_id,
            "code": response.payload.get("code"),
            "message": response.payload.get("message"),
            "candidate_count": len(candidates),
            "candidates_path": str(artifact_path),
            "candidates": [candidate.to_dict() for candidate in candidates],
        }
    )
    return 0


def command_prepare_scibase_local_index(args: argparse.Namespace) -> int:
    """Prepare a private local BM25 index from one bounded Sci-Base Parquet subset."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        manifest = load_corpus_manifest(run_dir / "corpus_manifest.json", mission.mission_id)
        if manifest is None:
            raise CorpusPreparationError("Sci-Base local-index preparation requires a recorded corpus manifest")
        output_dir = Path(args.output_dir).resolve()
        resolved_run = run_dir.resolve()
        if output_dir == resolved_run or resolved_run in output_dir.parents:
            raise SciBaseLocalError("Sci-Base private index output_dir must stay outside the mission run directory")
        result = build_scibase_local_index(
            manifest=manifest,
            rows=rows_from_scibase_parquet(Path(args.input), max_rows=args.max_rows),
            output_dir=output_dir,
            dataset_id=args.dataset_id,
            dataset_revision=args.dataset_revision,
            require_all_doi_matched=args.require_all_doi_matched,
        )
    except (OSError, UiExportError, CorpusPreparationError, SciBaseLocalError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="private_scibase_local_index_prepared",
        actor="local_scibase_preparer",
        state=MissionState.SELECT,
        payload={
            "dataset_id": args.dataset_id,
            "dataset_revision_supplied": bool(args.dataset_revision),
            "matched_document_count": result.matched_document_count,
            "manifest_document_count": result.manifest_document_count,
            "manifest_documents_without_doi": result.manifest_documents_without_doi,
            "source": "local_scibase_parquet_exact_doi_match",
            "run_artifact_boundary": "private_index_paths_and_markdown_not_persisted",
        },
    )
    _json_print({
        "run_id": args.run_id,
        **result.to_dict(),
        "next_step": "Use index_path with execute-plan-local-corpus-query after approving the FlightPlan.",
    })
    return 0



def command_search_local_parsed_corpus(args: argparse.Namespace) -> int:
    """Run deterministic local retrieval over an explicit reviewed Markdown index."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        manifest = load_corpus_manifest(run_dir / "corpus_manifest.json", mission.mission_id)
        if manifest is None:
            raise CorpusPreparationError("local parsed search requires a recorded corpus manifest")
        candidates = candidates_from_local_source_index(
            manifest=manifest,
            index_path=Path(args.index),
            query=args.query,
            top_k=args.top_k,
        )
        path = write_candidate_artifact(run_dir, args.query, candidates)
    except (UiExportError, CorpusPreparationError, LocalCorpusSearchError, RetrievalArtifactError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="local_parsed_corpus_search",
        actor="local_corpus_retriever",
        state=MissionState.RETRIEVE,
        payload={"source": "authorized_local_parsed_corpus", "top_k": args.top_k, "candidate_count": len(candidates)},
    )
    _json_print({"run_id": args.run_id, "candidate_count": len(candidates), "candidates_path": str(path), "source": "authorized_local_parsed_corpus"})
    return 0



def command_create_corpus_selection_template_from_zotero(args: argparse.Namespace) -> int:
    """Create a blank human corpus-selection form from metadata-only Zotero matches."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        candidates = candidates_from_zotero_export(Path(args.input), args.query, args.top_k)
        template = corpus_selection_template_from_zotero_candidates(
            mission_id=mission.mission_id,
            material=mission.material,
            corpus_id=args.corpus_id,
            query=args.query,
            candidates=candidates,
        )
        path = write_corpus_selection_template(run_dir, template)
    except (OSError, UiExportError, LocalLibraryError, CorpusPreparationError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="blank_zotero_corpus_selection_template_created",
        actor="corpus_reviewer",
        state=MissionState.SELECT,
        payload={
            "corpus_id": template["corpus_id"],
            "candidate_count": len(template["candidates"]),
            "trust_status": template["trust_status"],
            "source": "local_zotero_metadata_no_attachments_or_fulltext",
        },
    )
    _json_print({
        "run_id": args.run_id,
        "corpus_id": template["corpus_id"],
        "candidate_count": len(template["candidates"]),
        "corpus_selection_template_path": str(path),
        "next_step": "Human reviewer must mark every candidate true or false, add a reason, and set trust_status to human_reviewed_corpus_selection_for_manifest.",
    })
    return 0


def command_record_corpus_manifest(args: argparse.Namespace) -> int:
    """Record an explicit, path-free list of institutionally authorized papers."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        selection = json.loads(Path(args.input).read_text(encoding="utf-8"))
        manifest = corpus_manifest_from_review(
            mission_id=mission.mission_id,
            material=mission.material,
            selection=selection,
        )
        path = write_corpus_manifest(run_dir, manifest)
    except (OSError, json.JSONDecodeError, UiExportError, CorpusPreparationError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="authorized_corpus_manifest_recorded",
        actor="corpus_reviewer",
        state=MissionState.SELECT,
        payload={"corpus_id": manifest["corpus_id"], "document_count": len(manifest["documents"]), "access_boundary": manifest["access_boundary"]},
    )
    _json_print({"run_id": args.run_id, "corpus_id": manifest["corpus_id"], "document_count": len(manifest["documents"]), "corpus_manifest_path": str(path)})
    return 0


def command_record_corpus_manifest_from_selection_review(args: argparse.Namespace) -> int:
    """Record a frozen manifest only after the candidate template was reviewed."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        review = json.loads(Path(args.input).read_text(encoding="utf-8"))
        manifest = corpus_manifest_from_selection_review(
            mission_id=mission.mission_id,
            material=mission.material,
            review=review,
        )
        path = write_corpus_manifest(run_dir, manifest)
    except (OSError, json.JSONDecodeError, UiExportError, CorpusPreparationError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="authorized_corpus_manifest_recorded_from_human_selection",
        actor="corpus_reviewer",
        state=MissionState.SELECT,
        payload={
            "corpus_id": manifest["corpus_id"],
            "document_count": len(manifest["documents"]),
            "access_boundary": manifest["access_boundary"],
            "source": "human_reviewed_zotero_metadata_selection",
        },
    )
    _json_print({
        "run_id": args.run_id,
        "corpus_id": manifest["corpus_id"],
        "document_count": len(manifest["documents"]),
        "corpus_manifest_path": str(path),
    })
    return 0


def command_seed_authorized_corpus_candidates(args: argparse.Namespace) -> int:
    """Make manifest papers eligible for reviewed local full-text processing."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        manifest = load_corpus_manifest(run_dir / "corpus_manifest.json", mission.mission_id)
        if manifest is None:
            raise CorpusPreparationError("candidate seeding requires a recorded corpus manifest")
        candidates = candidates_from_authorized_corpus_manifest(manifest, mission.question)
        path = write_candidate_artifact(run_dir, mission.question, candidates)
    except (UiExportError, CorpusPreparationError, RetrievalArtifactError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="authorized_corpus_candidates_seeded",
        actor="corpus_reviewer",
        state=MissionState.SELECT,
        payload={"corpus_id": manifest["corpus_id"], "candidate_count": len(candidates), "source": "authorized_local_corpus_manifest_not_ranked_retrieval"},
    )
    _json_print({"run_id": args.run_id, "candidate_count": len(candidates), "candidates_path": str(path), "source": "authorized_local_corpus_manifest_not_ranked_retrieval"})
    return 0


def command_record_evaluation_failure_case_log(args: argparse.Namespace) -> int:
    """Validate and store a human-reviewed aggregate failure-case disclosure."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        manifest = load_corpus_manifest(run_dir / "corpus_manifest.json", mission.mission_id)
        if manifest is None:
            raise CorpusPreparationError("evaluation failure-case log requires a recorded corpus manifest")
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        record = failure_case_log_from_review(
            mission_id=mission.mission_id, corpus_id=manifest["corpus_id"], payload=payload
        )
        path = write_failure_case_log(run_dir, record)
    except (OSError, json.JSONDecodeError, UiExportError, CorpusPreparationError, EvaluationOperationalDisclosureError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    category_count = len(record["categories"])
    occurrence_count = sum(item["occurrence_count"] for item in record["categories"])
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="human_reviewed_evaluation_failure_case_log_recorded",
        actor="evaluation_reviewer",
        state=MissionState.HUMAN_REVIEW,
        payload={"corpus_id": record["corpus_id"], "category_count": category_count, "occurrence_count": occurrence_count},
    )
    _json_print({"run_id": args.run_id, "category_count": category_count, "occurrence_count": occurrence_count, "failure_case_log_path": str(path)})
    return 0


def command_record_evaluation_api_cost_latency(args: argparse.Namespace) -> int:
    """Validate and store a human-reviewed aggregate API cost/latency disclosure."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        manifest = load_corpus_manifest(run_dir / "corpus_manifest.json", mission.mission_id)
        if manifest is None:
            raise CorpusPreparationError("evaluation API cost/latency disclosure requires a recorded corpus manifest")
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        record = api_cost_latency_from_review(
            mission_id=mission.mission_id, corpus_id=manifest["corpus_id"], payload=payload
        )
        path = write_api_cost_latency(run_dir, record)
    except (OSError, json.JSONDecodeError, UiExportError, CorpusPreparationError, EvaluationOperationalDisclosureError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    request_count = sum(item["request_count"] for item in record["providers"])
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="human_reviewed_evaluation_api_cost_latency_recorded",
        actor="evaluation_reviewer",
        state=MissionState.HUMAN_REVIEW,
        payload={"corpus_id": record["corpus_id"], "provider_count": len(record["providers"]), "request_count": request_count},
    )
    _json_print({"run_id": args.run_id, "provider_count": len(record["providers"]), "request_count": request_count, "api_cost_latency_path": str(path)})
    return 0

def command_create_evaluation_run_record_template(args: argparse.Namespace) -> int:
    """Bind a blank real-corpus disclosure record to the current frozen manifest."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        manifest = load_corpus_manifest(run_dir / "corpus_manifest.json", mission.mission_id)
        if manifest is None:
            raise CorpusPreparationError("evaluation run record requires a recorded corpus manifest")
        template = evaluation_run_record_template(manifest=manifest, mission_id=mission.mission_id)
        path = write_evaluation_run_record_template(run_dir, template)
    except (UiExportError, CorpusPreparationError, EvaluationRunRecordError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="evaluation_run_record_template_created",
        actor="evaluation_reviewer",
        state=MissionState.HUMAN_REVIEW,
        payload={
            "corpus_id": template["corpus_id"],
            "document_count": template["frozen_corpus_document_count"],
            "trust_status": template["trust_status"],
        },
    )
    _json_print({
        "run_id": args.run_id,
        "corpus_id": template["corpus_id"],
        "document_count": template["frozen_corpus_document_count"],
        "trust_status": template["trust_status"],
        "evaluation_run_record_template_path": str(path),
    })
    return 0


def command_record_evaluation_run_record(args: argparse.Namespace) -> int:
    """Validate and save a human-completed real-corpus disclosure record."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        manifest = load_corpus_manifest(run_dir / "corpus_manifest.json", mission.mission_id)
        if manifest is None:
            raise CorpusPreparationError("evaluation run record requires a recorded corpus manifest")
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        record = reviewed_evaluation_run_record(
            run_dir=run_dir, manifest=manifest, mission_id=mission.mission_id, payload=payload
        )
        path = write_reviewed_evaluation_run_record(run_dir, record)
    except (OSError, json.JSONDecodeError, UiExportError, CorpusPreparationError, EvaluationRunRecordError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    generated_metric_count = sum(value == "generated" for value in record["metric_artifacts"].values())
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="human_real_corpus_evaluation_run_recorded",
        actor="evaluation_reviewer",
        state=MissionState.HUMAN_REVIEW,
        payload={
            "corpus_id": record["corpus_id"],
            "document_count": record["frozen_corpus_document_count"],
            "generated_metric_count": generated_metric_count,
            "submission_truth_check": record["submission_truth_check"],
        },
    )
    _json_print({
        "run_id": args.run_id,
        "corpus_id": record["corpus_id"],
        "document_count": record["frozen_corpus_document_count"],
        "generated_metric_count": generated_metric_count,
        "submission_truth_check": record["submission_truth_check"],
        "evaluation_run_record_path": str(path),
    })
    return 0


def command_create_gold_standard_template(args: argparse.Namespace) -> int:
    """Create blank reviewer slots from a recorded corpus, not evaluation claims."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        manifest = load_corpus_manifest(run_dir / "corpus_manifest.json", mission.mission_id)
        if manifest is None:
            raise CorpusPreparationError("human gold-standard template requires a recorded corpus manifest")
        template = gold_standard_template_from_manifest(manifest)
        path = write_gold_standard_template(run_dir, template)
    except (UiExportError, CorpusPreparationError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    FlightRecorder(_runs_dir(), args.run_id).record(
        event_type="human_gold_standard_template_created",
        actor="corpus_reviewer",
        state=MissionState.HUMAN_REVIEW,
        payload={"corpus_id": template["corpus_id"], "document_count": len(template["documents"]), "trust_status": template["trust_status"]},
    )
    _json_print({"run_id": args.run_id, "corpus_id": template["corpus_id"], "document_count": len(template["documents"]), "gold_standard_template_path": str(path)})
    return 0


def command_local_zotero_search(args: argparse.Namespace) -> int:
    try:
        candidates = candidates_from_zotero_export(Path(args.input), args.query, args.top_k)
        recorder = FlightRecorder(_runs_dir(), args.run_id)
        artifact_path = write_candidate_artifact(recorder.run_dir, args.query, candidates)
    except (LocalLibraryError, RetrievalArtifactError, AuditPathError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    recorder.record(event_type="local_zotero_metadata_search", actor="local_library_retriever", state=MissionState.RETRIEVE, payload={"source": "local_zotero_metadata", "top_k": args.top_k, "candidate_count": len(candidates)})
    _json_print({"run_id": args.run_id, "candidate_count": len(candidates), "candidates_path": str(artifact_path)})
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cosmatter", description="CosMatter material-literature navigation agent")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check-config", help="report configuration presence without revealing secrets")
    check.set_defaults(handler=command_check_config)

    preview = commands.add_parser("preview-ui", help="serve a loopback-only UI; credentials and unselected run artifacts are never exposed")
    preview.add_argument("--port", type=int, default=8765)
    preview.add_argument("--solid", action="store_true", help="serve frontend/dist instead of the legacy static web UI")
    preview.add_argument("--run-id", help="explicit run whose already-exported ui.json is exposed only at /ui.json")
    preview.add_argument("--api", action="store_true", help="enable the allowlisted loopback task API; provider credentials remain server-side")
    preview.set_defaults(handler=command_preview_ui)
    mcp = commands.add_parser("serve-mcp", help="serve review-gated CosMatter tools through stdio MCP")
    mcp.set_defaults(handler=command_serve_mcp)
    create = commands.add_parser("create-mission", help="write a validated MissionBrief and an audit event")
    create.add_argument("--question", required=True)
    create.add_argument("--material", required=True)
    create.add_argument("--property", dest="property_name", required=True)
    create.add_argument("--scope", required=True)
    create.add_argument("--run-id")
    create.add_argument("--mission-id", help="optional stable ID for linking later run artifacts")
    create.set_defaults(handler=command_create_mission)

    assign = commands.add_parser("assign-fleet", help="select one configured primary fleet and record its reason")
    assign.add_argument("--question", required=True)
    assign.add_argument("--material", required=True)
    assign.add_argument("--property", dest="property_name", required=True)
    assign.add_argument("--scope", required=True)
    assign.add_argument("--mission-type", help="optional explicit mission type, such as literature_discrepancy")
    assign.add_argument("--run-id")
    assign.add_argument("--mission-id", help="must match create-mission when both artifacts share a run")
    assign.set_defaults(handler=command_assign_fleet)
    cancel = commands.add_parser("cancel-mission", help="write a cooperative cancellation marker for a nonterminal run")
    cancel.add_argument("--run-id", required=True)
    cancel.set_defaults(handler=command_cancel_mission)
    run_status = commands.add_parser("run-status", help="emit an allowlisted state summary without audit payloads")
    run_status.add_argument("--run-id", required=True)
    run_status.set_defaults(handler=command_run_status)
    readiness = commands.add_parser("audit-workflow-readiness", help="audit plan, retrieval, screening, parsing, extraction, Gap, and report artifact readiness without provider calls")
    readiness.add_argument("--run-id", required=True)
    readiness.set_defaults(handler=command_audit_workflow_readiness)
    invariants = commands.add_parser("audit-runtime-invariants", help="audit state, authorization, receipt/result, artifact-hash, and evidence-decision relationships without provider calls")
    invariants.add_argument("--run-id", required=True)
    invariants.set_defaults(handler=command_audit_runtime_invariants)
    decision_memory = commands.add_parser("record-decision-memory", help="record one human-editable local operational note; research evidence and source text are rejected")
    decision_memory.add_argument("--input", required=True, help="strict operational-memory JSON; it remains outside mission reports")
    decision_memory.set_defaults(handler=command_record_decision_memory)
    rebuild_memory = commands.add_parser("rebuild-decision-memory", help="rebuild local operational-memory index from editable Markdown notes")
    rebuild_memory.set_defaults(handler=command_rebuild_decision_memory)
    list_memory = commands.add_parser("list-decision-memory", help="list local operational-memory metadata without note bodies")
    list_memory.set_defaults(handler=command_list_decision_memory)
    sensitive_audit = commands.add_parser("audit-sensitive-artifacts", help="scan persisted run text for forbidden URL, credential, and private-path patterns without outputting matches")
    sensitive_audit.add_argument("--run-id", required=True)
    sensitive_audit.set_defaults(handler=command_audit_sensitive_artifacts)
    submission_manifest = commands.add_parser("build-submission-execution-manifest", help="build a secret-safe execution index from current run artifacts; it makes no provider calls")
    submission_manifest.add_argument("--run-id", required=True)
    submission_manifest.set_defaults(handler=command_build_submission_execution_manifest)
    export_ui = commands.add_parser("export-ui", help="export a redacted, browser-safe JSON bundle for one run")
    export_ui.add_argument("--run-id", required=True)
    export_ui.add_argument("--output", help="optional JSON destination; defaults to runs/<run_id>/ui.json")
    export_ui.set_defaults(handler=command_export_ui)
    maturity_registry = commands.add_parser("record-evidence-maturity-registry", help="bind a reviewed evidence-maturity registry to one mission only after its local Source Map links pass")
    maturity_registry.add_argument("--run-id", required=True)
    maturity_registry.add_argument("--input", required=True, help="reviewed evidence-maturity registry JSON; the source file is not modified")
    maturity_registry.set_defaults(handler=command_record_evidence_maturity_registry)
    approve_plan = commands.add_parser("approve-plan", help="persist a human-reviewed bounded FlightPlan JSON")
    approve_plan.add_argument("--run-id", required=True)
    approve_plan.add_argument("--input", required=True, help="path to reviewed FlightPlan JSON; never reads LLM draft implicitly")
    approve_plan.set_defaults(handler=command_approve_plan)
    draft_plan = commands.add_parser("draft-plan", help="generate an untrusted DeepSeek research-planning draft")
    draft_plan.add_argument("--run-id", required=True)
    draft_plan.set_defaults(handler=command_draft_plan)
    public_pdf = commands.add_parser("register-public-pdf-candidate", help="probe an allowlisted public PDF and register its metadata-only candidate without retaining the URL")
    public_pdf.add_argument("--run-id", required=True)
    public_pdf.add_argument("--query-index", required=True, type=int)
    public_pdf.add_argument("--counter", action="store_true", help="select an approved counter-evidence query")
    public_pdf.add_argument("--document-id", required=True, help="stable public metadata identifier, not a URL")
    public_pdf.add_argument("--title", required=True, help="public bibliographic title")
    public_pdf.add_argument("--publication-year", type=int)
    public_pdf.add_argument("--doi", help="optional normalized DOI")
    public_pdf.add_argument("--source-url", required=True, help="allowlisted HTTPS PDF URL; used only for this bounded probe and not stored")
    public_pdf.set_defaults(handler=command_register_public_pdf_candidate)
    public_arxiv = commands.add_parser("execute-plan-public-arxiv-discovery", help="execute one approved query against allowlisted arXiv Atom metadata without downloading PDFs")
    public_arxiv.add_argument("--run-id", required=True)
    public_arxiv.add_argument("--query-index", required=True, type=int)
    public_arxiv.add_argument("--counter", action="store_true", help="select an approved counter-evidence query")
    public_arxiv.add_argument("--top-k", type=int, default=10, choices=range(1, 51), metavar="1..50")
    public_arxiv.set_defaults(handler=command_execute_plan_public_arxiv_discovery)
    reading_guide = commands.add_parser("build-reading-guide", help="build a bounded route from approved candidates and reviewed evidence")
    reading_guide.add_argument("--run-id", required=True)
    reading_guide.set_defaults(handler=command_build_reading_guide)
    screening_template = commands.add_parser("create-candidate-screening-template", help="create blank inclusion/exclusion review slots for every current retrieval candidate")
    screening_template.add_argument("--run-id", required=True)
    screening_template.set_defaults(handler=command_create_candidate_screening_template)
    screening = commands.add_parser("record-candidate-screening", help="record complete human-reviewed inclusion/exclusion decisions before full-text parsing")
    screening.add_argument("--run-id", required=True)
    screening.add_argument("--input", required=True, help="complete reviewed candidate decision JSON from the current template")
    screening.set_defaults(handler=command_record_candidate_screening)
    automated_screening = commands.add_parser("record-automated-trial-screening", help="record delegated-agent screening for an explicitly opted-in trial; it is not human review or scientific evidence")
    automated_screening.add_argument("--run-id", required=True)
    automated_screening_choice = automated_screening.add_mutually_exclusive_group(required=True)
    automated_screening_choice.add_argument("--input", help="complete automated trial decision JSON from the current candidate set")
    automated_screening_choice.add_argument("--include-document-id", action="append", help="include one to three exact candidate IDs; every other candidate remains needs_metadata_review")
    automated_screening.set_defaults(handler=command_record_automated_trial_screening)
    mineru_submit = commands.add_parser("mineru-submit-url", help="submit one candidate-screened authorized HTTPS source URL to MinerU without downloading output")
    mineru_submit.add_argument("--run-id", required=True)
    mineru_submit.add_argument("--document-id", required=True)
    mineru_submit.add_argument("--source-url", required=True, help="explicit HTTPS remote source; its plain URL is not stored in run artifacts")
    mineru_submit.add_argument("--allow-delegated-automated-trial", action="store_true", help="permit only a separately recorded delegated automated trial screening; never substitutes for human evidence review")
    mineru_submit.set_defaults(handler=command_submit_mineru_source)
    mineru_poll = commands.add_parser("mineru-poll", help="refresh a recorded MinerU task state without fetching parser output")
    mineru_poll.add_argument("--run-id", required=True)
    mineru_poll.add_argument("--document-id", required=True)
    mineru_poll.set_defaults(handler=command_poll_mineru_source)
    mineru_fetch = commands.add_parser("mineru-fetch-markdown", help="fetch exactly one completed MinerU Markdown result to a new private path outside the mission run")
    mineru_fetch.add_argument("--run-id", required=True)
    mineru_fetch.add_argument("--document-id", required=True)
    mineru_fetch.add_argument("--output", required=True, help="new private .md output outside the mission run; URL, ZIP and Markdown are never stored in run artifacts")
    mineru_fetch.set_defaults(handler=command_fetch_mineru_markdown)
    mineru_receipt_audit = commands.add_parser("audit-source-parse-receipts", help="verify MinerU parse-task receipt links without reading URLs or parser output")
    mineru_receipt_audit.add_argument("--run-id", required=True)
    mineru_receipt_audit.set_defaults(handler=command_audit_source_parse_receipts)
    mineru_task_migration = commands.add_parser("migrate-source-parse-task-identifiers", help="move legacy raw MinerU task IDs from a run ledger into private local storage")
    mineru_task_migration.add_argument("--run-id", required=True)
    mineru_task_migration.set_defaults(handler=command_migrate_source_parse_task_identifiers)
    mineru_review = commands.add_parser("prepare-mineru-markdown-review", help="make a private local candidate pool from a completed MinerU Markdown result; it never writes parser output into a run")
    mineru_review.add_argument("--run-id", required=True)
    mineru_review.add_argument("--document-id", required=True)
    mineru_review.add_argument("--input", required=True, help="explicit UTF-8 MinerU Markdown outside the mission run")
    mineru_review.add_argument("--output", required=True, help="new private .json review-pool path outside the mission run")
    mineru_review.set_defaults(handler=command_prepare_mineru_markdown_review)
    mineru_map_template = commands.add_parser("create-mineru-source-map-review-template", help="create a quote-free reviewer template bound to one private MinerU candidate pool")
    mineru_map_template.add_argument("--run-id", required=True)
    mineru_map_template.add_argument("--document-id", required=True)
    mineru_map_template.add_argument("--review-pool", required=True, help="private candidate-pool JSON outside the mission run")
    mineru_map_template.add_argument("--output", required=True, help="new private quote-free reviewer template JSON outside the mission run")
    mineru_map_template.set_defaults(handler=command_create_mineru_source_map_review_template)
    automated_mineru_selection = commands.add_parser("create-automated-trial-source-map-selection", help="create a hash-bound delegated automated trial selection from exact private-pool segment IDs")
    automated_mineru_selection.add_argument("--run-id", required=True)
    automated_mineru_selection.add_argument("--document-id", required=True)
    automated_mineru_selection.add_argument("--review-pool", required=True, help="private MinerU candidate-pool JSON outside the mission run")
    automated_mineru_selection.add_argument("--output", required=True, help="new private automated trial selection JSON outside the mission run")
    automated_mineru_selection.add_argument("--segment-id", action="append", required=True, help="exact private-pool segment ID to select; repeat at most 12 times")
    automated_mineru_selection.set_defaults(handler=command_create_automated_trial_source_map_selection)
    source_map = commands.add_parser("record-source-map", help="record reviewer-selected bounded excerpts for one completed MinerU task")
    source_map.add_argument("--run-id", required=True)
    source_map.add_argument("--document-id", required=True)
    source_map.add_argument("--input", required=True, help="reviewed bounded JSON selection; parser output files are never read directly")
    source_map.add_argument("--review-pool", help="optional private MinerU candidate-pool JSON; requires its hash-bound selection template and both files outside the run")
    source_map.add_argument("--allow-delegated-automated-trial", action="store_true", help="record a separately labelled delegated automated trial Source Map; it cannot enter human-reviewed evidence flows")
    source_map.set_defaults(handler=command_record_source_map)
    automated_fact_audit = commands.add_parser("record-automated-trial-fact-audit", help="record segment-bound delegated-agent fact checks; it never creates human-reviewed material facts or evidence")
    automated_fact_audit.add_argument("--run-id", required=True)
    automated_fact_audit.add_argument("--document-id", required=True)
    automated_fact_audit.add_argument("--input", required=True, help="private claim review JSON bound to the delegated automated trial Source Map")
    automated_fact_audit.set_defaults(handler=command_record_automated_trial_fact_audit)
    material_draft = commands.add_parser("draft-material-extraction", help="generate an untrusted DeepSeek material-fact draft from reviewer-selected source-map excerpts")
    material_draft.add_argument("--run-id", required=True)
    material_draft.add_argument("--document-id", help="document-scoped source map; defaults to the legacy single map")
    material_draft.set_defaults(handler=command_draft_material_extraction)
    material_review_template = commands.add_parser("create-material-fact-review-template", help="create a quote-free human review template tied to one reviewed Source Map")
    material_review_template.add_argument("--run-id", required=True)
    material_review_template.add_argument("--document-id", help="document-scoped source map; defaults to the legacy single map")
    material_review_template.set_defaults(handler=command_create_material_fact_review_template)
    material_draft_audit = commands.add_parser("audit-material-draft-traceability", help="write a count-only, non-scientific traceability audit for untrusted material candidates")
    material_draft_audit.add_argument("--run-id", required=True)
    material_draft_audit.add_argument("--document-id", help="document-scoped source map; defaults to the legacy single map")
    material_draft_audit.set_defaults(handler=command_audit_material_draft_traceability)
    material_facts = commands.add_parser("record-material-facts", help="record reviewer-approved composition, structure, property, process, condition, and simulation facts")
    material_facts.add_argument("--run-id", required=True)
    material_facts.add_argument("--document-id", help="document-scoped source map; defaults to the legacy single map")
    material_facts.add_argument("--input", required=True, help="reviewed fact JSON tied to source-map segment identifiers")
    material_facts.set_defaults(handler=command_record_material_facts)
    material_fusion = commands.add_parser("fuse-material-facts", help="compare reviewed material facts across documents with qualifier-aware conflict boundaries")
    material_fusion.add_argument("--run-id", required=True)
    material_fusion.set_defaults(handler=command_fuse_material_facts)
    normalization = commands.add_parser("record-condition-normalization", help="record reviewer-approved condition names and units without conversion")
    normalization.add_argument("--run-id", required=True)
    normalization.add_argument("--input", required=True, help="reviewed mappings from existing accepted condition fields")
    normalization.set_defaults(handler=command_record_condition_normalization)
    reconcile = commands.add_parser("reconcile-relations", help="record reviewer-approved identity mappings between existing OpenAlex and Crossref targets")
    reconcile.add_argument("--run-id", required=True)
    reconcile.add_argument("--input", required=True, help="reviewed bounded mapping JSON; no automatic identity inference")
    reconcile.set_defaults(handler=command_reconcile_relations)
    structure = commands.add_parser("record-paper-structure", help="record reviewer-approved paper-scoped material entities and relations")
    structure.add_argument("--run-id", required=True)
    structure.add_argument("--input", required=True, help="reviewed bounded structure JSON tied to source-map segments")
    structure.set_defaults(handler=command_record_paper_structure)
    openalex_expand = commands.add_parser("expand-openalex-relations", help="expand bounded public metadata relations for one accepted DOI-bearing evidence card")
    openalex_expand.add_argument("--run-id", required=True)
    openalex_expand.add_argument("--evidence-id", required=True)
    openalex_expand.set_defaults(handler=command_expand_openalex_relations)
    crossref_expand = commands.add_parser("expand-crossref-references", help="expand bounded deposited Crossref reference metadata for one accepted DOI-bearing evidence card")
    crossref_expand.add_argument("--run-id", required=True)
    crossref_expand.add_argument("--evidence-id", required=True)
    crossref_expand.set_defaults(handler=command_expand_crossref_references)
    gaps = commands.add_parser("generate-gap-candidates", help="generate evidence-bound, human-review-required Research Gap candidates from a condition matrix")
    gaps.add_argument("--run-id", required=True)
    gaps.set_defaults(handler=command_generate_gap_candidates)
    gap_draft = commands.add_parser("draft-gap-hypotheses", help="generate an untrusted DeepSeek hypothesis draft from structural condition discrepancies; it cannot enter reports")
    gap_draft.add_argument("--run-id", required=True)
    gap_draft.set_defaults(handler=command_draft_gap_hypotheses)
    report = commands.add_parser("build-report", help="build a review-gated evidence-manifest report for an existing run")
    report.add_argument("--run-id", required=True)
    report.set_defaults(handler=command_build_report)
    corpus_readiness = commands.add_parser("audit-frozen-corpus-readiness", help="write a count-only authorization and DOI-coverage audit for a frozen corpus")
    corpus_readiness.add_argument("--run-id", required=True)
    corpus_readiness.add_argument("--expected-count", type=int, default=90)
    corpus_readiness.set_defaults(handler=command_audit_frozen_corpus_readiness)
    annotation_coverage = commands.add_parser("audit-human-annotation-coverage", help="write a count-only annotation coverage audit for a frozen corpus")
    annotation_coverage.add_argument("--run-id", required=True)
    annotation_coverage.add_argument("--input", required=True, help="private blank or reviewed human_gold_standard JSON; it is read locally and not copied into the audit")
    annotation_coverage.set_defaults(handler=command_audit_human_annotation_coverage)
    source_template = commands.add_parser("create-bibliographic-source-template", help="create blank private bibliographic-source review slots from a frozen corpus")
    source_template.add_argument("--run-id", required=True)
    source_template.set_defaults(handler=command_create_bibliographic_source_template)
    source_coverage = commands.add_parser("audit-bibliographic-source-coverage", help="write a count-only audit for a private human-reviewed bibliographic-source registry")
    source_coverage.add_argument("--run-id", required=True)
    source_coverage.add_argument("--input", required=True, help="private reviewed source registry JSON; it is read locally and not copied into the audit")
    source_coverage.set_defaults(handler=command_audit_bibliographic_source_coverage)
    retrieval_compare = commands.add_parser("compare-human-retrieval-routes", help="compare aggregate human-reviewed retrieval metrics from one frozen corpus")
    retrieval_compare.add_argument("--run-id", required=True)
    retrieval_compare.add_argument("--input", required=True, help="JSON containing baseline_route_id and aggregate human retrieval evaluation payloads; no labels or queries")
    retrieval_compare.set_defaults(handler=command_compare_human_retrieval_routes)
    ising_plan = commands.add_parser("create-ising-benchmark-plan", help="create a seeded bounded 2-D Ising Metropolis/Wolff/Swendsen-Wang comparison plan")
    ising_plan.add_argument("--run-id", required=True)
    ising_plan.add_argument("--lattice-size", type=int, default=32)
    ising_plan.add_argument("--temperature", type=float, action="append", required=True, help="temperature; repeat for each evaluated point")
    ising_plan.add_argument("--burn-in-sweeps", type=int, default=200)
    ising_plan.add_argument("--measurement-sweeps", type=int, default=1000)
    ising_plan.add_argument("--seed", type=int, required=True)
    ising_plan.add_argument("--repetitions", type=int, default=3, help="independently seeded local repeats per temperature and algorithm (1-20)")
    ising_plan.set_defaults(handler=command_create_ising_benchmark_plan)
    ising_run = commands.add_parser("run-ising-benchmark", help="execute the already fixed local classical-MC benchmark")
    ising_run.add_argument("--run-id", required=True)
    ising_run.set_defaults(handler=command_run_ising_benchmark)
    ising_followups = commands.add_parser("propose-ising-followups", help="propose approval-required local MC refinements without executing them")
    ising_followups.add_argument("--run-id", required=True)
    ising_followups.set_defaults(handler=command_propose_ising_followups)
    ising_summary = commands.add_parser("export-ising-benchmark-summary", help="export an aggregate, scope-limited summary of an executed local Ising benchmark")
    ising_summary.add_argument("--run-id", required=True)
    ising_summary.set_defaults(handler=command_export_ising_benchmark_summary)
    potential_plan = commands.add_parser("create-potential-benchmark-plan", help="create a seeded framework-only potential comparison and boundary task plan")
    potential_plan.add_argument("--run-id", required=True)
    potential_plan.add_argument("--system", required=True)
    potential_plan.add_argument("--model", required=True, action="append", help="model identifier; specify at least twice")
    potential_plan.add_argument("--baseline-model", help="declared comparison baseline; defaults to the first --model")
    potential_plan.add_argument("--reference-method", required=True)
    potential_plan.add_argument("--controls", required=True, help="JSON object mapping control names to [train_min, train_max]")
    potential_plan.add_argument("--seed", required=True, type=int)
    potential_plan.add_argument("--samples-per-regime", type=int, default=3, help="seeded task coordinates per in-domain, near-boundary, and out-of-domain regime (1-32)")
    potential_plan.set_defaults(handler=command_create_potential_benchmark_plan)
    potential_protocol_template = commands.add_parser("create-potential-execution-protocol-template", help="write a human-completed external execution protocol template bound to a potential benchmark plan")
    potential_protocol_template.add_argument("--run-id", required=True)
    potential_protocol_template.set_defaults(handler=command_create_potential_execution_protocol_template)
    potential_protocol = commands.add_parser("record-potential-execution-protocol", help="validate and record a human-authored potential execution protocol; it never runs calculations")
    potential_protocol.add_argument("--run-id", required=True)
    potential_protocol.add_argument("--input", required=True, help="completed protocol JSON without structures, trajectories, credentials, or private paths")
    potential_protocol.set_defaults(handler=command_record_potential_execution_protocol)
    potential_evaluate = commands.add_parser("evaluate-potential-benchmark", help="compare complete imported external potential result summaries")
    potential_evaluate.add_argument("--run-id", required=True)
    potential_evaluate.add_argument("--input", required=True, help="JSON array of external result summaries; no raw trajectories or structures")
    potential_evaluate.set_defaults(handler=command_evaluate_potential_benchmark)
    potential_followups = commands.add_parser("propose-potential-followups", help="propose approval-required boundary followups from imported benchmark results")
    potential_followups.add_argument("--run-id", required=True)
    potential_followups.set_defaults(handler=command_propose_potential_followups)
    resource_disclosure = commands.add_parser("record-external-resource-disclosure", help="validate and record a human-completed database/API/model disclosure for one run")
    resource_disclosure.add_argument("--run-id", required=True)
    resource_disclosure.add_argument("--input", required=True, help="human-completed disclosure JSON; it must not contain credentials or private paths")
    resource_disclosure.set_defaults(handler=command_record_external_resource_disclosure)
    submission_ready = commands.add_parser("check-submission-readiness", help="check source, disclosure, and optional report package readiness for preliminary submission")
    submission_ready.add_argument("--run-id", help="also require the run's compiled LaTeX source package")
    submission_ready.set_defaults(handler=command_check_submission_readiness)
    source_bundle = commands.add_parser("build-submission-source-bundle", help="create an allowlisted preliminary source ZIP without runs, secrets, or full text")
    source_bundle.add_argument("--output", help="ZIP output inside the repository; defaults to submission/cosmatter_preliminary_source.zip")
    source_bundle.set_defaults(handler=command_build_submission_source_bundle)
    final_package = commands.add_parser("build-final-submission-package", help="package reviewed report, disclosure, and allowlisted source only when all readiness checks pass")
    final_package.add_argument("--run-id", required=True)
    final_package.add_argument("--output", help="ZIP output inside the repository; defaults to submission/cosmatter_preliminary_RUN_ID.zip")
    final_package.set_defaults(handler=command_build_final_submission_package)
    latex_report = commands.add_parser("export-latex-report", help="export review-gated LaTeX and BibTeX submission sources from an existing run")
    latex_report.add_argument("--run-id", required=True)
    latex_report.add_argument("--output", help="output directory for main.tex, references.bib, and citation audit; defaults inside the run")
    latex_report.add_argument("--compile", action="store_true", help="compile main.tex to PDF with local XeLaTeX and BibTeX")
    latex_report.set_defaults(handler=command_export_latex_report)
    report_audit = commands.add_parser("audit-report-evidence", help="verify manifest, Gap, and structured-report identifier coverage without assessing scientific validity")
    report_audit.add_argument("--run-id", required=True)
    report_audit.set_defaults(handler=command_audit_report_evidence)
    provenance_audit = commands.add_parser("audit-evidence-provenance", help="audit accepted EvidenceCard linkage to reviewed source maps without assessing source authenticity")
    provenance_audit.add_argument("--run-id", required=True)
    provenance_audit.set_defaults(handler=command_audit_evidence_provenance)
    ingest = commands.add_parser("ingest-evidence", help="validate and record one extracted evidence draft for an existing run")
    ingest.add_argument("--run-id", required=True)
    ingest.add_argument("--input", required=True, help="path to a narrow evidence-draft JSON file")
    ingest.set_defaults(handler=command_ingest_evidence)
    evaluate = commands.add_parser("evaluate-fixture", help="evaluate an explicitly synthetic frozen route-diagnostics fixture")
    evaluate.add_argument("--fixture", required=True)
    evaluate.add_argument("--run-id", default="frozen_evaluation")
    evaluate.set_defaults(handler=command_evaluate_fixture)
    human_retrieval = commands.add_parser("evaluate-human-retrieval", help="calculate P@K, Recall@K, and nDCG@K from a complete human-reviewed frozen-corpus gold file")
    human_retrieval.add_argument("--run-id", required=True)
    human_retrieval.add_argument("--input", required=True, help="fully reviewed gold JSON; the blank template is rejected")
    human_retrieval.add_argument("--search-index", type=int, required=True, help="zero-based retrieval search history index")
    human_retrieval.add_argument("--k", type=int, default=10)
    human_retrieval.set_defaults(handler=command_evaluate_human_retrieval)
    human_material = commands.add_parser("evaluate-human-material-facts", help="calculate end-to-end review-gated material fact P/R/F1 and unit-match accuracy from an independent human gold file")
    human_material.add_argument("--run-id", required=True)
    human_material.add_argument("--input", required=True, help="complete independent human material-fact gold JSON")
    human_material.set_defaults(handler=command_evaluate_human_material_facts)
    evidence_quality_template = commands.add_parser("create-evidence-quality-review-template", help="create blank human-review fields for accepted evidence citation locators and conditions")
    evidence_quality_template.add_argument("--run-id", required=True)
    evidence_quality_template.set_defaults(handler=command_create_evidence_quality_review_template)
    evidence_quality = commands.add_parser("evaluate-human-evidence-quality", help="summarize independent human review of evidence citation locators, condition completeness, and contradiction labels")
    evidence_quality.add_argument("--run-id", required=True)
    evidence_quality.add_argument("--input", required=True, help="complete independent human evidence-quality assessment JSON")
    evidence_quality.set_defaults(handler=command_evaluate_human_evidence_quality)
    gap_template = commands.add_parser("create-gap-review-template", help="create blank expert-review fields for every current Research Gap candidate")
    gap_template.add_argument("--run-id", required=True)
    gap_template.set_defaults(handler=command_create_gap_review_template)
    human_gaps = commands.add_parser("evaluate-human-gaps", help="summarize human-expert approval, novelty, actionability, and evidence-completeness of current Gap candidates")
    human_gaps.add_argument("--run-id", required=True)
    human_gaps.add_argument("--input", required=True, help="complete independent human-expert Gap assessment JSON")
    human_gaps.set_defaults(handler=command_evaluate_human_gaps)
    benchmark = commands.add_parser("evaluate-agent-benchmark", help="run an explicitly synthetic end-to-end retrieval/extraction/Gap benchmark")
    benchmark.add_argument("--fixture", required=True)
    benchmark.add_argument("--run-id", default="synthetic_agent_benchmark")
    benchmark.set_defaults(handler=command_evaluate_agent_benchmark)
    demo = commands.add_parser("demo-flow", help="run the offline happy-path state-machine demo")
    demo.add_argument("--run-id", default="demo_cosmatter_001")
    demo.set_defaults(handler=command_demo_flow)

    diagnose = commands.add_parser("diagnose-conditions", help="build a condition-differential matrix from accepted evidence")
    diagnose.add_argument("--run-id", required=True)
    diagnose.set_defaults(handler=command_diagnose_conditions)
    execute_local_plan_query = commands.add_parser("execute-plan-local-corpus-query", help="execute one approved FlightPlan query against an explicit authorized local parsed-corpus index")
    execute_local_plan_query.add_argument("--run-id", required=True)
    execute_local_plan_query.add_argument("--index", required=True, help="path-bearing local Markdown index; paths and text are never persisted")
    execute_local_plan_query.add_argument("--query-index", type=int, required=True)
    execute_local_plan_query.add_argument("--counter", action="store_true", help="use the approved counterevidence query list")
    execute_local_plan_query.set_defaults(handler=command_execute_plan_local_corpus_query)
    execute_plan_query = commands.add_parser("execute-plan-query", help="execute one query from an approved FlightPlan")
    execute_plan_query.add_argument("--run-id", required=True)
    execute_plan_query.add_argument("--query-index", type=int, required=True)
    execute_plan_query.add_argument("--counter", action="store_true", help="use the approved counterevidence query list")
    execute_plan_query.set_defaults(handler=command_execute_plan_query)
    content = commands.add_parser("sciverse-read-context", help="fetch one screened candidate's bounded Sciverse context into an explicit local review file")
    content.add_argument("--run-id", required=True)
    content.add_argument("--document-id", required=True)
    content.add_argument("--offset", type=int, default=0)
    content.add_argument("--limit", type=int, default=2000)
    content.add_argument("--output", required=True, help="new local .txt/.md review file outside the run directory; content is never stored in run artifacts")
    content.add_argument("--allow-delegated-automated-trial", action="store_true", help="permit separately recorded delegated automated trial screening; preserves a non-human content-access trust status")
    content.set_defaults(handler=command_sciverse_read_context)
    receipt_audit = commands.add_parser("audit-candidate-receipts", help="verify provider receipt links retained by retrieval candidates without reading provider payloads")
    receipt_audit.add_argument("--run-id", required=True)
    receipt_audit.set_defaults(handler=command_audit_candidate_receipts)
    search = commands.add_parser("sciverse-search", help="run a bounded Sciverse agentic-search request")
    search.add_argument("--query", required=True)
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--run-id", default="live_sciverse_search")
    search.set_defaults(handler=command_sciverse_search)
    local_search = commands.add_parser("local-zotero-search", help="search an explicit local Zotero JSON export without reading attachments or full text")
    local_search.add_argument("--input", required=True, help="explicit Zotero JSON export; attachment paths and notes are ignored")
    local_search.add_argument("--query", required=True)
    local_search.add_argument("--top-k", type=int, default=10)
    local_search.add_argument("--run-id", default="local_zotero_search")
    local_search.set_defaults(handler=command_local_zotero_search)
    scibase_index = commands.add_parser("prepare-scibase-local-index", help="build a private DOI-bound Markdown index from one local Sci-Base Parquet subset; no dataset download or API call")
    scibase_index.add_argument("--run-id", required=True)
    scibase_index.add_argument("--input", required=True, help="one prefiltered local Sci-Base .parquet file")
    scibase_index.add_argument("--output-dir", required=True, help="new or empty private directory outside the mission run")
    scibase_index.add_argument("--max-rows", type=int, default=500000, help="maximum Parquet rows to scan, 1 through 5000000")
    scibase_index.add_argument("--dataset-id", default="opendatalab/Sci-Base")
    scibase_index.add_argument("--dataset-revision", help="optional local dataset revision or commit recorded in the private receipt")
    scibase_index.add_argument("--require-all-doi-matched", action="store_true", help="fail unless the supplied subset covers every DOI-bearing reviewed manifest document")
    scibase_index.set_defaults(handler=command_prepare_scibase_local_index)
    local_parsed_search = commands.add_parser("local-parsed-corpus-search", help="run deterministic local retrieval over an explicit authorized Markdown index; paths and text are not persisted")
    local_parsed_search.add_argument("--run-id", required=True)
    local_parsed_search.add_argument("--index", required=True, help="explicit private Markdown index; its paths and source text are process-local")
    local_parsed_search.add_argument("--query", required=True)
    local_parsed_search.add_argument("--top-k", type=int, default=10)
    local_parsed_search.set_defaults(handler=command_search_local_parsed_corpus)
    zotero_selection = commands.add_parser("create-corpus-selection-template-from-zotero", help="make a blank metadata-only human corpus-selection template from a Zotero JSON export")
    zotero_selection.add_argument("--run-id", required=True)
    zotero_selection.add_argument("--input", required=True, help="explicit Zotero JSON export; paths, attachments, notes, and full text are ignored")
    zotero_selection.add_argument("--query", required=True, help="metadata query used only to prepare a human review queue")
    zotero_selection.add_argument("--corpus-id", required=True, help="stable name for the corpus to be frozen after review")
    zotero_selection.add_argument("--top-k", type=int, default=90, help="number of metadata candidates to present, 1 through 250")
    zotero_selection.set_defaults(handler=command_create_corpus_selection_template_from_zotero)
    reviewed_manifest = commands.add_parser("record-corpus-manifest-from-selection-review", help="freeze a path-free manifest only from a fully human-reviewed Zotero selection template")
    reviewed_manifest.add_argument("--run-id", required=True)
    reviewed_manifest.add_argument("--input", required=True, help="reviewed template JSON; every candidate needs a boolean decision and a reason")
    reviewed_manifest.set_defaults(handler=command_record_corpus_manifest_from_selection_review)
    corpus_manifest = commands.add_parser("record-corpus-manifest", help="record an explicit path-free manifest of institutionally authorized local-review papers")
    corpus_manifest.add_argument("--run-id", required=True)
    corpus_manifest.add_argument("--input", required=True, help="reviewed bibliography JSON; document paths, attachments, and full text are prohibited")
    corpus_manifest.set_defaults(handler=command_record_corpus_manifest)
    gold_template = commands.add_parser("create-gold-standard-template", help="create blank human annotation slots from an authorized corpus manifest")
    gold_template.add_argument("--run-id", required=True)
    gold_template.set_defaults(handler=command_create_gold_standard_template)
    evaluation_prep = commands.add_parser("prepare-real-evaluation", help="create count-only frozen-corpus audit and blank human-review templates from an existing manifest")
    evaluation_prep.add_argument("--run-id", required=True)
    evaluation_prep.add_argument("--expected-count", type=int, default=90)
    evaluation_prep.add_argument("--seed-candidates", action="store_true", help="also seed manifest papers as unranked authorized local candidates")
    evaluation_prep.set_defaults(handler=command_prepare_real_evaluation)
    evaluation_run_template = commands.add_parser("create-evaluation-run-record-template", help="bind a blank human real-corpus evaluation disclosure record to the frozen manifest")
    evaluation_run_template.add_argument("--run-id", required=True)
    evaluation_run_template.set_defaults(handler=command_create_evaluation_run_record_template)
    evaluation_run_record = commands.add_parser("record-evaluation-run-record", help="validate and save a human-completed real-corpus evaluation disclosure record")
    evaluation_run_record.add_argument("--run-id", required=True)
    evaluation_run_record.add_argument("--input", required=True, help="human-completed disclosure JSON; paths, full text, and provider payloads are prohibited")
    evaluation_run_record.set_defaults(handler=command_record_evaluation_run_record)
    failure_case_log = commands.add_parser("record-evaluation-failure-case-log", help="validate and save a human-reviewed aggregate failure-case disclosure without document data")
    failure_case_log.add_argument("--run-id", required=True)
    failure_case_log.add_argument("--input", required=True, help="aggregate human-reviewed JSON; full text, document identifiers, paths, and provider payloads are prohibited")
    failure_case_log.set_defaults(handler=command_record_evaluation_failure_case_log)
    api_cost_latency = commands.add_parser("record-evaluation-api-cost-latency", help="validate and save aggregate API cost and latency without provider payloads")
    api_cost_latency.add_argument("--run-id", required=True)
    api_cost_latency.add_argument("--input", required=True, help="aggregate human-reviewed JSON; credentials, request IDs, URLs, paths, and provider payloads are prohibited")
    api_cost_latency.set_defaults(handler=command_record_evaluation_api_cost_latency)
    corpus_candidates = commands.add_parser("seed-authorized-corpus-candidates", help="make reviewed corpus-manifest papers eligible local candidates without claiming a ranked retrieval result")
    corpus_candidates.add_argument("--run-id", required=True)
    corpus_candidates.set_defaults(handler=command_seed_authorized_corpus_candidates)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except AuditPathError as error:
        _json_print({"error": str(error), "run_id": getattr(args, "run_id", None)})
        return 2
