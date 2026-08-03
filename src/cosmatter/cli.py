"""Small command-line surface for the CosMatter M1.1 baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from cosmatter.audit import AuditPathError, FlightRecorder, safe_run_id
from cosmatter.models import MissionBrief, MissionState
from cosmatter.state_machine import MissionMachine

from .config import AGENT_ROOT, Settings
from .dispatch import MissionDispatcher
from .deepseek import DeepSeekAdapter, DeepSeekConfigurationError, DeepSeekRequestError
from .evaluation import EvaluationError, evaluate_frozen_route_fixture, write_evaluation_record
from .facilities import FacilityGateError, condition_differential, write_condition_matrix
from .ingestion import EvidenceIngestionError, ingest_evidence_draft, require_eligible_candidate
from .planning import PlanApprovalError, approved_flight_plan_from_payload, load_approved_flight_plan, research_planning_prompts, write_approved_flight_plan, write_untrusted_plan_draft
from .retrieval import RetrievalArtifactError, candidates_from_sciverse, write_candidate_artifact
from .reading_guide import ReadingGuideError, build_reading_guide, write_reading_guide
from .mineru import MinerUAdapter, MinerUConfigurationError, MinerURequestError
from .source_parse import SourceParseArtifactError, record_source_parse_task, task_for_document, update_source_parse_task
from .source_map import SourceMapError, source_map_from_review, write_source_map
from .run_control import RunControlError, build_run_status, cancel_run, load_run_control, require_active_run
from .openalex import OpenAlexAdapter, OpenAlexConfigurationError, OpenAlexRequestError
from .relation_expansion import RelationExpansionError, build_relation_expansion, write_relation_expansion
from .crossref import CrossrefAdapter, CrossrefRequestError
from .crossref_relation_expansion import CrossrefRelationExpansionError, build_crossref_relation_expansion, write_crossref_relation_expansion
from .paper_structure import PaperStructureError, paper_structure_from_review, write_paper_structure
from .ui_preview import UiPreviewError, serve_ui_preview
from .relation_reconciliation import RelationReconciliationError, reconciliation_from_review, write_relation_reconciliation
from .source_map import load_source_map
from .reporting import ReportGateError, build_evidence_manifest, write_mission_report
from .sciverse import SciverseAdapter, SciverseConfigurationError, SciverseRequestError
from .ui_export import UiExportError, _evidence_cards_from_payloads, _last_recorded_state, _load_array_if_present, _load_object, _mission_from_payload, _verification_decisions_from_payloads, export_run_to_ui


def _json_print(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _runs_dir() -> Path:
    return AGENT_ROOT / "runs"


def _run_dir(run_id: str) -> Path:
    return _runs_dir() / safe_run_id(run_id)


def command_check_config(_: argparse.Namespace) -> int:
    _json_print(Settings.load().status())
    return 0


def command_preview_ui(args: argparse.Namespace) -> int:
    try:
        serve_ui_preview(args.port)
    except UiPreviewError as error:
        _json_print({"error": str(error)})
        return 2
    return 0
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

def command_export_ui(args: argparse.Namespace) -> int:
    output_path = Path(args.output) if args.output else None
    try:
        destination = export_run_to_ui(_runs_dir(), args.run_id, output_path)
    except UiExportError as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    _json_print({"run_id": args.run_id, "ui_path": str(destination), "schema_version": "1.0"})
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


def command_submit_mineru_source(args: argparse.Namespace) -> int:
    """Submit an explicitly authorized public source URL to MinerU.

    The local ledger retains only a hash of the URL and task metadata.  MinerU
    output is not downloaded or exposed to the UI at this stage.
    """
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        require_eligible_candidate(run_dir, args.document_id)
        require_active_run(run_dir, mission.mission_id)
        settings = Settings.load()
        task = MinerUAdapter(settings).submit_remote_source(args.source_url)
        task_path = record_source_parse_task(
            run_dir,
            mission_id=mission.mission_id,
            document_id=args.document_id,
            source_url=args.source_url.strip(),
            task=task,
            model_version=settings.mineru_model_version,
        )
    except (UiExportError, EvidenceIngestionError, MinerUConfigurationError, MinerURequestError, SourceParseArtifactError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id, "document_id": args.document_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="source_parse_submitted",
        actor="document_parser",
        state=MissionState.EXTRACT,
        payload={"document_id": args.document_id, "provider": "mineru", "task_state": task.state},
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
        task = MinerUAdapter(settings).get_task(stored_task["task_id"])
        task_path = update_source_parse_task(run_dir, mission_id=mission.mission_id, document_id=args.document_id, task=task)
    except (UiExportError, MinerUConfigurationError, MinerURequestError, SourceParseArtifactError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id, "document_id": args.document_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="source_parse_status_checked",
        actor="document_parser",
        state=MissionState.EXTRACT,
        payload={"document_id": args.document_id, "provider": "mineru", "task_state": task.state},
    )
    _json_print({"run_id": args.run_id, "document_id": args.document_id, "task_state": task.state, "task_path": str(task_path)})
    return 0

def command_record_source_map(args: argparse.Namespace) -> int:
    """Persist only reviewer-selected excerpts from a completed parse task."""
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        require_eligible_candidate(run_dir, args.document_id)
        task = task_for_document(run_dir, mission_id=mission.mission_id, document_id=args.document_id)
        selection = json.loads(Path(args.input).read_text(encoding="utf-8"))
        source_map = source_map_from_review(
            mission_id=mission.mission_id,
            document_id=args.document_id,
            source_task=task,
            selection=selection,
        )
        source_map_path = write_source_map(run_dir, source_map)
    except (OSError, json.JSONDecodeError, UiExportError, EvidenceIngestionError, SourceParseArtifactError, SourceMapError) as error:
        _json_print({"error": str(error), "run_id": args.run_id, "document_id": args.document_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="source_map_reviewed",
        actor="source_reviewer",
        state=MissionState.EXTRACT,
        payload={"document_id": args.document_id, "segment_count": len(source_map["segments"])},
    )
    _json_print({"run_id": args.run_id, "document_id": args.document_id, "segment_count": len(source_map["segments"]), "source_map_path": str(source_map_path)})
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
        source_map = load_source_map(run_dir / "source_map.json", mission.mission_id)
        if source_map is None:
            raise PaperStructureError("paper structure requires a reviewed source map")
        selection = json.loads(Path(args.input).read_text(encoding="utf-8"))
        structure = paper_structure_from_review(mission_id=mission.mission_id, source_map=source_map, selection=selection)
        path = write_paper_structure(run_dir, structure)
    except (OSError, json.JSONDecodeError, UiExportError, PaperStructureError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(event_type="paper_structure_reviewed", actor="source_reviewer", state=MissionState.MAP, payload={"document_id": structure["document_id"], "entity_count": len(structure["entities"]), "relation_count": len(structure["relations"])})
    _json_print({"run_id": args.run_id, "document_id": structure["document_id"], "entity_count": len(structure["entities"]), "relation_count": len(structure["relations"]), "paper_structure_path": str(path)})
    return 0
def command_build_report(args: argparse.Namespace) -> int:
    run_dir = _run_dir(args.run_id)
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
        cards = _evidence_cards_from_payloads(_load_array_if_present(run_dir / "evidence_cards.json", "evidence artifacts"))
        decisions = _verification_decisions_from_payloads(
            _load_array_if_present(run_dir / "verification_decisions.json", "verification decision artifacts")
        )
        report = build_evidence_manifest(mission, cards, decisions)
        report_path = write_mission_report(run_dir, report)
    except (UiExportError, ReportGateError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="mission_report_built",
        actor="report_delivery",
        state=MissionState.REPORT,
        payload={"report_id": report.report_id, "accepted_evidence_count": len(report.evidence_ids)},
    )
    _json_print({"run_id": args.run_id, "report_id": report.report_id, "report_path": str(report_path)})
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
            "citation_precision": report.citation_precision,
            "condition_completeness": report.condition_completeness,
            "contradiction_precision": report.contradiction_precision,
            "reproducibility_consistency": report.reproducibility_consistency,
        },
    )
    _json_print({"run_id": args.run_id, "fixture_id": report.fixture_id, "evaluation_path": str(record_path)})
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
    except (UiExportError, PlanApprovalError, FacilityGateError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="condition_diagnostics_completed",
        actor="condition_differential",
        state=MissionState.MAP,
        payload={"matrix_row_count": len(matrix.rows), "differing_field_count": sum(len(row.differing_fields) for row in matrix.rows)},
    )
    _json_print({"run_id": args.run_id, "matrix_path": str(matrix_path), "matrix_row_count": len(matrix.rows)})
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
        artifact_path = write_candidate_artifact(run_dir, query, candidates)
    except (UiExportError, PlanApprovalError, RetrievalArtifactError, SciverseConfigurationError, SciverseRequestError, ValueError) as error:
        _json_print({"error": str(error), "run_id": args.run_id})
        return 2
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="approved_plan_query_executed",
        actor="search_selection",
        state=MissionState.RETRIEVE,
        payload={"plan_id": plan.artifact_id, "query_kind": query_kind, "query_index": args.query_index, "candidate_count": len(candidates), "request_id": response.request_id},
    )
    _json_print({"run_id": args.run_id, "query_kind": query_kind, "query_index": args.query_index, "candidate_count": len(candidates), "candidates_path": str(artifact_path)})
    return 0

def command_sciverse_search(args: argparse.Namespace) -> int:
    response = SciverseAdapter(Settings.load()).agentic_search(args.query, top_k=args.top_k)
    candidates = candidates_from_sciverse(response.payload, args.query, args.top_k)
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    artifact_path = write_candidate_artifact(recorder.run_dir, args.query, candidates)
    recorder.record(
        event_type="sciverse_agentic_search",
        actor="radar_retriever",
        state=MissionState.RETRIEVE,
        payload={
            "query": args.query,
            "top_k": args.top_k,
            "status_code": response.status_code,
            "request_id": response.request_id,
            "candidate_count": len(candidates),
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

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cosmatter", description="CosMatter material-literature navigation agent")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check-config", help="report configuration presence without revealing secrets")
    check.set_defaults(handler=command_check_config)

    preview = commands.add_parser("preview-ui", help="serve only static web UI on 127.0.0.1; no credentials or run artifacts are exposed")
    preview.add_argument("--port", type=int, default=8765)
    preview.set_defaults(handler=command_preview_ui)
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
    export_ui = commands.add_parser("export-ui", help="export a redacted, browser-safe JSON bundle for one run")
    export_ui.add_argument("--run-id", required=True)
    export_ui.add_argument("--output", help="optional JSON destination; defaults to runs/<run_id>/ui.json")
    export_ui.set_defaults(handler=command_export_ui)
    approve_plan = commands.add_parser("approve-plan", help="persist a human-reviewed bounded FlightPlan JSON")
    approve_plan.add_argument("--run-id", required=True)
    approve_plan.add_argument("--input", required=True, help="path to reviewed FlightPlan JSON; never reads LLM draft implicitly")
    approve_plan.set_defaults(handler=command_approve_plan)
    draft_plan = commands.add_parser("draft-plan", help="generate an untrusted DeepSeek research-planning draft")
    draft_plan.add_argument("--run-id", required=True)
    draft_plan.set_defaults(handler=command_draft_plan)
    reading_guide = commands.add_parser("build-reading-guide", help="build a bounded route from approved candidates and reviewed evidence")
    reading_guide.add_argument("--run-id", required=True)
    reading_guide.set_defaults(handler=command_build_reading_guide)
    mineru_submit = commands.add_parser("mineru-submit-url", help="submit one authorized HTTPS source URL to MinerU without downloading output")
    mineru_submit.add_argument("--run-id", required=True)
    mineru_submit.add_argument("--document-id", required=True)
    mineru_submit.add_argument("--source-url", required=True, help="explicit HTTPS remote source; its plain URL is not stored in run artifacts")
    mineru_submit.set_defaults(handler=command_submit_mineru_source)
    mineru_poll = commands.add_parser("mineru-poll", help="refresh a recorded MinerU task state without fetching parser output")
    mineru_poll.add_argument("--run-id", required=True)
    mineru_poll.add_argument("--document-id", required=True)
    mineru_poll.set_defaults(handler=command_poll_mineru_source)
    source_map = commands.add_parser("record-source-map", help="record reviewer-selected bounded excerpts for one completed MinerU task")
    source_map.add_argument("--run-id", required=True)
    source_map.add_argument("--document-id", required=True)
    source_map.add_argument("--input", required=True, help="reviewed bounded JSON selection; parser output files are never read directly")
    source_map.set_defaults(handler=command_record_source_map)
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
    report = commands.add_parser("build-report", help="build a review-gated evidence-manifest report for an existing run")
    report.add_argument("--run-id", required=True)
    report.set_defaults(handler=command_build_report)
    ingest = commands.add_parser("ingest-evidence", help="validate and record one extracted evidence draft for an existing run")
    ingest.add_argument("--run-id", required=True)
    ingest.add_argument("--input", required=True, help="path to a narrow evidence-draft JSON file")
    ingest.set_defaults(handler=command_ingest_evidence)
    evaluate = commands.add_parser("evaluate-fixture", help="evaluate an explicitly synthetic frozen route-diagnostics fixture")
    evaluate.add_argument("--fixture", required=True)
    evaluate.add_argument("--run-id", default="frozen_evaluation")
    evaluate.set_defaults(handler=command_evaluate_fixture)
    demo = commands.add_parser("demo-flow", help="run the offline happy-path state-machine demo")
    demo.add_argument("--run-id", default="demo_cosmatter_001")
    demo.set_defaults(handler=command_demo_flow)

    diagnose = commands.add_parser("diagnose-conditions", help="build a condition-differential matrix from accepted evidence")
    diagnose.add_argument("--run-id", required=True)
    diagnose.set_defaults(handler=command_diagnose_conditions)
    execute_plan_query = commands.add_parser("execute-plan-query", help="execute one query from an approved FlightPlan")
    execute_plan_query.add_argument("--run-id", required=True)
    execute_plan_query.add_argument("--query-index", type=int, required=True)
    execute_plan_query.add_argument("--counter", action="store_true", help="use the approved counterevidence query list")
    execute_plan_query.set_defaults(handler=command_execute_plan_query)
    search = commands.add_parser("sciverse-search", help="run a bounded Sciverse agentic-search request")
    search.add_argument("--query", required=True)
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--run-id", default="live_sciverse_search")
    search.set_defaults(handler=command_sciverse_search)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except AuditPathError as error:
        _json_print({"error": str(error), "run_id": getattr(args, "run_id", None)})
        return 2
