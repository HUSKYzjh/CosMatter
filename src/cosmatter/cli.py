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
from .sciverse import SciverseAdapter
from .ui_export import UiExportError, export_run_to_ui


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
    recorder = FlightRecorder(_runs_dir(), args.run_id)
    recorder.record(
        event_type="sciverse_agentic_search",
        actor="radar_retriever",
        state=MissionState.RETRIEVE,
        payload={"query": args.query, "top_k": args.top_k, "status_code": response.status_code, "request_id": response.request_id},
    )
    raw_hits = response.payload.get("hits", [])
    if not isinstance(raw_hits, list):
        raw_hits = []
    candidates = [
        {
            "doc_id": hit.get("doc_id"),
            "title": hit.get("title"),
            "year": hit.get("publication_published_year"),
            "page_no": hit.get("page_no"),
            "offset": hit.get("offset"),
            "score": hit.get("score"),
            "is_content_accessible": hit.get("is_content_accessible"),
        }
        for hit in raw_hits[: args.top_k]
        if isinstance(hit, dict)
    ]
    _json_print(
        {
            "status_code": response.status_code,
            "request_id": response.request_id,
            "code": response.payload.get("code"),
            "message": response.payload.get("message"),
            "candidate_count": len(raw_hits),
            "candidates": candidates,
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
