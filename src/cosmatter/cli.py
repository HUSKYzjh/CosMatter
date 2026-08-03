"""Small command-line surface for the CosMatter M1.1 baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from cosmatter.audit import FlightRecorder
from cosmatter.models import MissionBrief, MissionState
from cosmatter.state_machine import MissionMachine

from .config import AGENT_ROOT, Settings
from .dispatch import MissionDispatcher
from .deepseek import DeepSeekAdapter, DeepSeekConfigurationError, DeepSeekRequestError
from .evaluation import EvaluationError, evaluate_frozen_route_fixture, write_evaluation_record
from .ingestion import EvidenceIngestionError, ingest_evidence_draft
from .planning import PlanApprovalError, approved_flight_plan_from_payload, research_planning_prompts, write_approved_flight_plan, write_untrusted_plan_draft
from .retrieval import candidates_from_sciverse, write_candidate_artifact
from .reporting import ReportGateError, build_evidence_manifest, write_mission_report
from .sciverse import SciverseAdapter
from .ui_export import UiExportError, _evidence_cards_from_payloads, _load_array_if_present, _load_object, _mission_from_payload, _verification_decisions_from_payloads, export_run_to_ui


def _json_print(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _runs_dir() -> Path:
    return AGENT_ROOT / "runs"


def command_check_config(_: argparse.Namespace) -> int:
    _json_print(Settings.load().status())
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
    run_dir = _runs_dir() / args.run_id
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
    run_dir = _runs_dir() / args.run_id
    try:
        mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
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

def command_build_report(args: argparse.Namespace) -> int:
    run_dir = _runs_dir() / args.run_id
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
    run_dir = _runs_dir() / args.run_id
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

    search = commands.add_parser("sciverse-search", help="run a bounded Sciverse agentic-search request")
    search.add_argument("--query", required=True)
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--run-id", default="live_sciverse_search")
    search.set_defaults(handler=command_sciverse_search)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)
