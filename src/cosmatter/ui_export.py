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
    EvidenceCard,
    FacilityType,
    FleetAssignment,
    FleetType,
    MissionBrief,
    MissionReport,
    MissionState,
    Provenance,
    ReviewStatus,
    Stance,
    StationType,
    utc_now,
)

from .dispatch import MissionDispatcher
from .reading_guide import ReadingGuideError, load_reading_guide
from .source_map import SourceMapError, load_source_map
from .verification import VerificationDecision


UI_SCHEMA_VERSION = "1.0"
_MAX_UI_QUOTE_CHARS = 500
_MAX_TIMELINE_ENTRIES = 40
_MAX_PAPER_SOURCE_SEGMENTS = 3
_MAX_PAPER_SOURCE_CHARS = 1_000

# These are presentation labels, not raw audit events.  The browser receives no
# actor, event ID, payload, request ID, query text, exception, or review reason.
_TIMELINE_ACTIONS = {
    "mission_created": ("question_intake", "任务已创建"),
    "mission_cancelled": ("question_intake", "任务已取消；未启动后续外部请求"),
    "fleet_assigned": ("question_intake", "主舰队已分派"),
    "research_plan_drafted": ("research_planning", "研究计划草案已生成（待人工审批）"),
    "flight_plan_approved": ("research_planning", "研究计划已批准"),
    "reading_guide_built": ("search_selection", "有界阅读路线已生成"),
    "source_parse_submitted": ("evidence_extraction", "授权结构解析任务已提交"),
    "source_parse_status_checked": ("evidence_extraction", "授权结构解析状态已刷新"),
    "source_map_reviewed": ("evidence_extraction", "定位片段已人工复核"),
    "evidence_ingested": ("evidence_extraction", "证据卡已进入审核流程"),
    "condition_diagnostics_completed": ("cross_check_review", "条件差分已完成"),
    "mission_report_built": ("report_delivery", "审核后报告已生成"),
}


class UiExportError(ValueError):
    """Raised when a run cannot safely be converted into a UI bundle."""


def approved_evidence_projection(
    mission_id: str,
    cards: tuple[EvidenceCard, ...],
    decisions: tuple[VerificationDecision, ...],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Project only accepted, browser-safe evidence cards.

    Decisions are authoritative: an ``EvidenceCard.review_status`` is not
    trusted as a release signal. The projection deliberately excludes review
    reasons and missing-condition details, which remain local audit material.
    """
    decisions_by_evidence: dict[str, VerificationDecision] = {}
    for decision in decisions:
        if decision.mission_id != mission_id:
            continue
        if decision.evidence_id in decisions_by_evidence:
            raise UiExportError("multiple verification decisions for one evidence card")
        decisions_by_evidence[decision.evidence_id] = decision
    accepted: list[dict[str, Any]] = []
    rejected_count = 0
    withheld_count = 0
    for card in cards:
        decision = decisions_by_evidence.get(card.evidence_id)
        if decision is None:
            withheld_count += 1
            continue
        if decision.status is not ReviewStatus.ACCEPTED:
            rejected_count += 1
            continue
        if (
            card.provenance.access_policy is AccessPolicy.METADATA_ONLY
            or len(card.quote) > _MAX_UI_QUOTE_CHARS
        ):
            withheld_count += 1
            continue
        accepted.append(
            {
                "evidence_id": card.evidence_id,
                "claim": card.claim,
                "stance": card.stance.value,
                "material": card.material,
                "property_name": card.property_name,
                "conditions": card.conditions,
                "quote": card.quote,
                "review_status": ReviewStatus.ACCEPTED.value,
                "provenance": {
                    "document_id": card.provenance.document_id,
                    "locator": card.provenance.locator,
                    "source": card.provenance.source,
                    "doi": card.provenance.doi,
                    "access_policy": card.provenance.access_policy.value,
                },
            }
        )
    return accepted, {
        "accepted_count": len(accepted),
        "rejected_count": rejected_count,
        "withheld_count": withheld_count,
    }


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


def _load_array_if_present(path: Path, label: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise UiExportError(f"invalid {label}: {path.name}") from error
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise UiExportError(f"{label} must be a JSON array of objects")
    return payload


def _evidence_cards_from_payloads(payloads: list[dict[str, Any]]) -> tuple[EvidenceCard, ...]:
    cards: list[EvidenceCard] = []
    for payload in payloads:
        try:
            provenance_payload = payload["provenance"]
            if not isinstance(provenance_payload, dict) or not isinstance(payload["conditions"], dict):
                raise TypeError("invalid nested artifact")
            cards.append(
                EvidenceCard(
                    claim=str(payload["claim"]),
                    stance=Stance(str(payload["stance"])),
                    material=str(payload["material"]),
                    property_name=str(payload["property_name"]),
                    conditions=payload["conditions"],
                    quote=str(payload["quote"]),
                    provenance=Provenance(
                        document_id=str(provenance_payload["document_id"]),
                        locator=str(provenance_payload["locator"]),
                        source=str(provenance_payload["source"]),
                        doi=provenance_payload.get("doi"),
                        content_hash=provenance_payload.get("content_hash"),
                        access_policy=AccessPolicy(
                            str(provenance_payload.get("access_policy", AccessPolicy.AUTHORIZED.value))
                        ),
                    ),
                    review_status=ReviewStatus(
                        str(payload.get("review_status", ReviewStatus.UNREVIEWED.value))
                    ),
                    extractor_confidence=payload.get("extractor_confidence"),
                    evidence_id=str(payload["evidence_id"]),
                    created_at=str(payload.get("created_at", utc_now())),
                )
            )
        except (KeyError, TypeError, ValueError) as error:
            raise UiExportError("evidence_cards.json contains an invalid evidence artifact") from error
    return tuple(cards)


def _verification_decisions_from_payloads(
    payloads: list[dict[str, Any]],
) -> tuple[VerificationDecision, ...]:
    decisions: list[VerificationDecision] = []
    for payload in payloads:
        try:
            missing_conditions = payload.get("missing_conditions", [])
            if not isinstance(missing_conditions, list):
                raise TypeError("missing_conditions must be a list")
            decisions.append(
                VerificationDecision(
                    mission_id=str(payload["mission_id"]),
                    evidence_id=str(payload["evidence_id"]),
                    status=ReviewStatus(str(payload["status"])),
                    reason=str(payload["reason"]),
                    missing_conditions=tuple(str(item) for item in missing_conditions),
                    decision_id=str(payload.get("decision_id", "verification_export")),
                    created_at=str(payload.get("created_at", utc_now())),
                )
            )
        except (KeyError, TypeError, ValueError) as error:
            raise UiExportError("verification_decisions.json contains an invalid decision artifact") from error
    return tuple(decisions)

def _condition_matrix_if_present(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise UiExportError("condition_matrix.json is invalid JSON") from error
    if not isinstance(payload, list):
        raise UiExportError("condition_matrix.json must be an array")
    required = {"condition_cluster", "supporting_evidence_ids", "contradicting_evidence_ids", "differing_fields", "unknowns"}
    safe_rows: list[dict[str, Any]] = []
    for row in payload:
        if not isinstance(row, dict) or set(row) != required or not isinstance(row["condition_cluster"], str):
            raise UiExportError("condition_matrix.json contains an invalid row")
        if not all(isinstance(row[key], list) and all(isinstance(item, str) for item in row[key]) for key in required - {"condition_cluster"}):
            raise UiExportError("condition_matrix.json contains invalid row lists")
        safe_rows.append(row)
    return safe_rows

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


def _mission_report_from_payload(payload: dict[str, Any]) -> MissionReport:
    try:
        evidence_ids = payload["evidence_ids"]
        limitations = payload["limitations"]
        next_steps = payload["next_steps"]
        if not all(isinstance(item, list) for item in (evidence_ids, limitations, next_steps)):
            raise TypeError("report arrays are required")
        return MissionReport(
            mission_id=str(payload["mission_id"]),
            summary=str(payload["summary"]),
            evidence_ids=tuple(str(item) for item in evidence_ids),
            limitations=tuple(str(item) for item in limitations),
            next_steps=tuple(str(item) for item in next_steps),
            report_id=str(payload.get("report_id", "report_export")),
            created_at=str(payload.get("created_at", utc_now())),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise UiExportError("mission_report.json does not satisfy MissionReport") from error

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


def _timeline_projection(path: Path) -> list[dict[str, str]]:
    """Project a small, allowlisted timeline without exposing audit records."""
    if not path.exists():
        return []
    projected: list[dict[str, str]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        event_type = event.get("event_type")
        created_at = event.get("created_at")
        state = event.get("state")
        if not isinstance(event_type, str) or not isinstance(created_at, str) or not isinstance(state, str):
            continue
        action: tuple[str, str] | None = _TIMELINE_ACTIONS.get(event_type)
        if event_type == "approved_plan_query_executed":
            payload = event.get("payload")
            query_kind = payload.get("query_kind") if isinstance(payload, dict) else None
            action = (
                "search_selection",
                "反例检索已完成" if query_kind == "counter" else "主检索已完成",
            )
        if action is None:
            continue
        try:
            state_label = MissionState(state).value
        except ValueError:
            continue
        station, label = action
        projected.append(
            {
                "station_type": station,
                "action": label,
                "state": state_label,
                "occurred_at": created_at,
            }
        )
    return projected[-_MAX_TIMELINE_ENTRIES:]


def _relation_expansion_projection(path: Path, mission_id: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise UiExportError("relation_expansion.json is invalid JSON") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != "1.0" or payload.get("mission_id") != mission_id:
        raise UiExportError("relation expansion identity is invalid")
    if payload.get("trust_status") != "public_relation_metadata_not_scientific_evidence" or not isinstance(payload.get("source"), dict) or not isinstance(payload.get("edges"), list):
        raise UiExportError("relation expansion trust status or structure is invalid")
    source = payload["source"]
    if set(source) != {"evidence_id", "document_id", "openalex_work_id"} or not all(isinstance(value, str) and value for value in source.values()):
        raise UiExportError("relation expansion source is invalid")
    edges: list[dict[str, str]] = []
    for edge in payload["edges"]:
        if not isinstance(edge, dict) or set(edge) != {"edge_type", "target_openalex_id"} or edge.get("edge_type") not in {"citation_reference", "algorithmic_related"}:
            raise UiExportError("relation expansion edge is invalid")
        target = edge.get("target_openalex_id")
        if not isinstance(target, str) or not target.startswith("https://openalex.org/W"):
            raise UiExportError("relation expansion target is invalid")
        edges.append({"edge_type": edge["edge_type"], "target_openalex_id": target})
    return {"trust_status": payload["trust_status"], "source": source, "edges": edges}

def _paper_source_map_projection(source_map: dict[str, Any] | None) -> dict[str, Any] | None:
    """Expose a few human-reviewed snippets, never raw parser output."""
    if source_map is None:
        return None
    projected: list[dict[str, str]] = []
    remaining = _MAX_PAPER_SOURCE_CHARS
    for segment in source_map["segments"]:
        if len(projected) == _MAX_PAPER_SOURCE_SEGMENTS or len(segment["quote"]) > remaining:
            break
        projected.append({key: segment[key] for key in ("segment_id", "locator", "kind", "quote")})
        remaining -= len(segment["quote"])
    return {"document_id": source_map["document_id"], "trust_status": "human_reviewed_parser_selection", "segments": projected}

def build_ui_bundle(
    mission: MissionBrief,
    assignment: FleetAssignment,
    state: MissionState = MissionState.INTAKE,
    evidence_cards: tuple[EvidenceCard, ...] = (),
    verification_decisions: tuple[VerificationDecision, ...] = (),
    mission_report: MissionReport | None = None,
    condition_matrix: list[dict[str, Any]] | None = None,
    timeline: list[dict[str, str]] | None = None,
    research_guide: dict[str, Any] | None = None,
    paper_source_map: dict[str, Any] | None = None,
    literature_relations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce the minimal browser-safe projection of a mission assignment."""
    if mission.mission_id != assignment.mission_id:
        raise UiExportError("mission and fleet assignment identifiers do not match")
    if mission_report is not None and mission_report.mission_id != mission.mission_id:
        raise UiExportError("mission report and mission identifiers do not match")
    spec = MissionDispatcher.from_project().specs.get(assignment.fleet_type)
    if spec is None:
        raise UiExportError(f"missing configured fleet: {assignment.fleet_type.value}")
    projected_evidence, verification_summary = approved_evidence_projection(
        mission.mission_id, evidence_cards, verification_decisions
    )
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
            "verification_summary": verification_summary,
        },
        "stations": stations,
        "facilities": facilities,
        "evidence_cards": projected_evidence,
        "verification_decisions": [],
        "condition_matrix": condition_matrix or [],
        "timeline": timeline or [],
        "research_guide": research_guide,
        "paper_source_map": _paper_source_map_projection(paper_source_map),
        "literature_relations": literature_relations,
        "mission_report": mission_report.to_dict() if mission_report is not None else None,
    }


def export_run_to_ui(runs_dir: Path, run_id: str, output_path: Path | None = None) -> Path:
    """Export one local run as a browser-safe JSON file and record only a summary."""
    safe_run_id = _safe_run_id(run_id)
    run_dir = runs_dir / safe_run_id
    mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
    assignment = _assignment_from_payload(_load_object(run_dir / "fleet_assignment.json", "fleet assignment artifact"))
    state = _last_recorded_state(run_dir / "events.jsonl")
    evidence_cards = _evidence_cards_from_payloads(
        _load_array_if_present(run_dir / "evidence_cards.json", "evidence artifacts")
    )
    verification_decisions = _verification_decisions_from_payloads(
        _load_array_if_present(run_dir / "verification_decisions.json", "verification decision artifacts")
    )
    report_path = run_dir / "mission_report.json"
    mission_report = _mission_report_from_payload(_load_object(report_path, "mission report artifact")) if report_path.exists() else None
    condition_matrix = _condition_matrix_if_present(run_dir / "condition_matrix.json")
    timeline = _timeline_projection(run_dir / "events.jsonl")
    literature_relations = _relation_expansion_projection(run_dir / "relation_expansion.json", mission.mission_id)
    try:
        research_guide = load_reading_guide(run_dir / "reading_guide.json", mission.mission_id)
        paper_source_map = load_source_map(run_dir / "source_map.json", mission.mission_id)
    except (ReadingGuideError, SourceMapError) as error:
        raise UiExportError(str(error)) from error
    bundle = build_ui_bundle(
        mission,
        assignment,
        state,
        evidence_cards=evidence_cards,
        verification_decisions=verification_decisions,
        mission_report=mission_report,
        condition_matrix=condition_matrix,
        timeline=timeline,
        research_guide=research_guide,
        paper_source_map=paper_source_map,
        literature_relations=literature_relations,
    )
    destination = output_path or run_dir / "ui.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    FlightRecorder(runs_dir, safe_run_id).record(
        event_type="ui_bundle_exported",
        actor="ui_export",
        state=state,
        payload={"schema_version": UI_SCHEMA_VERSION, "evidence_card_count": len(bundle["evidence_cards"])},
    )
    return destination
