"""Safe, read-only JSON bundles consumed by the static CosMatter UI.

This module is intentionally an export boundary.  It does not start a web
server, read provider credentials, or pass audit-event payloads through to a
browser.  The only runtime inputs are a MissionBrief and FleetAssignment that
were already written for a local run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cosmatter.audit import FlightRecorder
from cosmatter.models import (
    AccessPolicy,
    FacilityType,
    FleetAssignment,
    FleetType,
    MissionBrief,
    MissionState,
    StationType,
    utc_now,
)

from .dispatch import MissionDispatcher


UI_SCHEMA_VERSION = "1.0"


class UiExportError(ValueError):
    """Raised when a run cannot safely be converted into a UI bundle."""


def _safe_run_id(run_id: str) -> str:
    candidate = run_id.strip()
    if not candidate or candidate in {".", ".."} or Path(candidate).name != candidate:
        raise UiExportError("run_id must be a single directory name")
    return candidate


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise UiExportError(f"missing {label}: {path.name}") from error
    except json.JSONDecodeError as error:
        raise UiExportError(f"invalid {label}: {path.name}") from error
    if not isinstance(payload, dict):
        raise UiExportError(f"{label} must be a JSON object")
    return payload


def _mission_from_payload(payload: dict[str, Any]) -> MissionBrief:
    try:
        return MissionBrief(
            question=str(payload["question"]),
            material=str(payload["material"]),
            property_name=str(payload["property_name"]),
            scope=str(payload["scope"]),
            source_policy=AccessPolicy(str(payload.get("source_policy", AccessPolicy.AUTHORIZED.value))),
            output_request=str(payload.get("output_request", "evidence-backed research report")),
            mission_id=str(payload["mission_id"]),
            created_at=str(payload.get("created_at", utc_now())),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise UiExportError("mission.json does not satisfy MissionBrief") from error


def _assignment_from_payload(payload: dict[str, Any]) -> FleetAssignment:
    try:
        return FleetAssignment(
            mission_id=str(payload["mission_id"]),
            fleet_type=FleetType(str(payload["fleet_type"])),
            mission_type=str(payload["mission_type"]),
            reason=str(payload["reason"]),
            required_stations=tuple(StationType(str(item)) for item in payload["required_stations"]),
            required_facilities=tuple(FacilityType(str(item)) for item in payload["required_facilities"]),
            release_gate=StationType(str(payload["release_gate"])),
            assignment_id=str(payload.get("assignment_id", "assignment_export")),
            created_at=str(payload.get("created_at", utc_now())),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise UiExportError("fleet_assignment.json does not satisfy FleetAssignment") from error


def _last_recorded_state(path: Path) -> MissionState:
    """Read only event state labels; never export event actors or payloads."""
    if not path.exists():
        return MissionState.INTAKE
    latest = MissionState.INTAKE
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(raw_line)
            latest = MissionState(str(event.get("state", latest.value)))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return latest


def build_ui_bundle(
    mission: MissionBrief,
    assignment: FleetAssignment,
    state: MissionState = MissionState.INTAKE,
) -> dict[str, Any]:
    """Produce the minimal browser-safe projection of a mission assignment."""
    if mission.mission_id != assignment.mission_id:
        raise UiExportError("mission and fleet assignment identifiers do not match")
    spec = MissionDispatcher.from_project().specs.get(assignment.fleet_type)
    if spec is None:
        raise UiExportError(f"missing configured fleet: {assignment.fleet_type.value}")
    stations = [
        {
            "station_type": station.value,
            "status": "active" if index == 0 else "waiting",
        }
        for index, station in enumerate(assignment.required_stations)
    ]
    facilities = [
        {"facility_type": facility.value, "status": "queued"}
        for facility in assignment.required_facilities
    ]
    return {
        "schema_version": UI_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "mission": {
            "mission_id": mission.mission_id,
            "question": mission.question,
            "material": mission.material,
            "property_name": mission.property_name,
            "scope": mission.scope,
            "source_policy": mission.source_policy.value,
        },
        "fleet_assignment": {
            "assignment_id": assignment.assignment_id,
            "fleet_type": assignment.fleet_type.value,
            "display_name_zh": spec.display_name_zh,
            "display_name_en": spec.display_name_en,
            "mission_type": assignment.mission_type,
            "reason": assignment.reason,
            "release_gate": assignment.release_gate.value,
        },
        "status": {
            "mission_state": state.value,
            "retry_count": 0,
            "retry_budget": spec.max_facility_attempts,
            "return_reason": None,
        },
        "stations": stations,
        "facilities": facilities,
        "evidence_cards": [],
        "verification_decisions": [],
        "condition_matrix": [],
        "mission_report": None,
    }


def export_run_to_ui(runs_dir: Path, run_id: str, output_path: Path | None = None) -> Path:
    """Export one local run as a browser-safe JSON file and record only a summary."""
    safe_run_id = _safe_run_id(run_id)
    run_dir = runs_dir / safe_run_id
    mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
    assignment = _assignment_from_payload(_load_object(run_dir / "fleet_assignment.json", "fleet assignment artifact"))
    state = _last_recorded_state(run_dir / "events.jsonl")
    bundle = build_ui_bundle(mission, assignment, state)
    destination = output_path or run_dir / "ui.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    FlightRecorder(runs_dir, safe_run_id).record(
        event_type="ui_bundle_exported",
        actor="ui_export",
        state=state,
        payload={"schema_version": UI_SCHEMA_VERSION, "evidence_card_count": 0},
    )
    return destination
