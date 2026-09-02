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
    normalize_public_title,
    utc_now,
)

from .dispatch import MissionDispatcher
from .gap_analysis import GapAnalysisError, load_gap_candidates
from .provenance_audit import ProvenanceAuditError, audit_accepted_evidence_provenance
from .material_extraction import MaterialExtractionError, iter_material_facts, load_material_facts, validate_material_fact_source_links
from .reading_guide import ReadingGuideError, load_reading_guide
from .source_map import SourceMapError, iter_source_maps, load_source_map
from .paper_structure import PaperStructureError, iter_paper_structures, load_paper_structure
from .relation_reconciliation import RelationReconciliationError, load_relation_reconciliation
from .condition_normalization import ConditionNormalizationError, load_condition_normalization
from .evidence_maturity_registry import EvidenceMaturityRegistryError, audit_evidence_maturity_registry_against_runs, load_evidence_maturity_registry, validate_evidence_maturity_registry_audit
from .verification import VerificationDecision
from .citation_expansion import CitationExpansionError, validate_citation_expansion
from .counterevidence import CounterevidenceGateError, require_executed_counterevidence
from .planning import PlanApprovalError, load_approved_flight_plan
from .simulation_campaign import SimulationCampaignError, simulation_campaign_ui_projection


UI_SCHEMA_VERSION = "1.0"
_MAX_UI_QUOTE_CHARS = 500
_MAX_TIMELINE_ENTRIES = 40
_MAX_PAPER_SOURCE_SEGMENTS = 3
_MAX_PAPER_SOURCE_CHARS = 1_000
_MAX_LITERATURE_GRAPH_CANDIDATES = 48
_MAX_LITERATURE_GRAPH_NODES = 96
_MAX_LITERATURE_GRAPH_EDGES = 144

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
    "material_extraction_drafted": ("evidence_extraction", "材料事实草稿已生成，待人工审核"),
    "material_facts_reviewed": ("evidence_extraction", "结构化材料事实已人工复核"),
    "condition_normalization_reviewed": ("cross_check_review", "条件字段名称与单位已人工规范化（未换算）"),
    "public_relations_expanded": ("cross_check_review", "OpenAlex 关系元数据已扩展（非科学证据）"),
    "crossref_references_expanded": ("cross_check_review", "Crossref 参考元数据已扩展（非科学证据）"),
    "citation_graph_expanded": ("cross_check_review", "双向两层引文图谱已扩展（非科学证据）"),
    "evidence_ingested": ("evidence_extraction", "证据卡已进入审核流程"),
    "condition_diagnostics_completed": ("cross_check_review", "条件差分已完成"),
    "material_facts_fused": ("cross_check_review", "已审查材料事实完成跨文献对比"),
    "mission_report_built": ("report_delivery", "审核后报告已生成"),
    "simulation_campaign_approved_plan_only": ("research_planning", "计算活动计划已人工批准；执行仍被禁用"),
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



def _material_facts_projection(artifact: dict[str, Any] | None) -> dict[str, Any] | None:
    if artifact is None:
        return None
    facts = [{key: fact[key] for key in ("fact_id", "segment_id", "category", "name", "value", "unit", "normalized_value", "normalized_unit", "qualifiers", "locator")} for fact in artifact["facts"]]
    return {"document_id": artifact["document_id"], "trust_status": artifact["trust_status"], "facts": facts}

def _reviewed_source_map_summary(source_maps: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    """Export reviewed document identifiers and counts; excerpts and paths stay local."""
    document_ids = sorted({item.get("document_id", "") for item in source_maps if isinstance(item.get("document_id"), str) and item["document_id"].strip()})
    return {
        "document_count": len(source_maps),
        "segment_count": sum(len(item.get("segments", [])) for item in source_maps),
        "document_ids": document_ids,
    }


def _reviewed_material_fact_summary(artifacts: tuple[dict[str, Any], ...]) -> dict[str, int]:
    """Export aggregate counts only; detailed facts use the bounded first-artifact projection."""
    return {
        "document_count": len(artifacts),
        "fact_count": sum(len(item.get("facts", [])) for item in artifacts),
    }


def _gap_candidates_if_present(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        return [candidate.to_dict() for candidate in load_gap_candidates(path)]
    except GapAnalysisError as error:
        raise UiExportError(str(error)) from error


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
        gap_ids = payload.get("research_gap_candidate_ids", [])
        if not all(isinstance(item, list) for item in (evidence_ids, limitations, next_steps, gap_ids)):
            raise TypeError("report arrays are required")
        return MissionReport(
            mission_id=str(payload["mission_id"]),
            summary=str(payload["summary"]),
            evidence_ids=tuple(str(item) for item in evidence_ids),
            limitations=tuple(str(item) for item in limitations),
            next_steps=tuple(str(item) for item in next_steps),
            research_gap_candidate_ids=tuple(str(item) for item in gap_ids),
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

def _crossref_relation_expansion_projection(path: Path, mission_id: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise UiExportError("crossref_relation_expansion.json is invalid JSON") from error
    trust_status = "public_bibliographic_reference_metadata_not_scientific_evidence"
    if not isinstance(payload, dict) or payload.get("schema_version") != "1.0" or payload.get("mission_id") != mission_id:
        raise UiExportError("Crossref relation expansion identity is invalid")
    if payload.get("trust_status") != trust_status or not isinstance(payload.get("source"), dict) or not isinstance(payload.get("reference_field_present"), bool) or not isinstance(payload.get("edges"), list):
        raise UiExportError("Crossref relation expansion structure is invalid")
    source = payload["source"]
    if set(source) != {"evidence_id", "document_id", "crossref_doi"} or not all(isinstance(value, str) and value for value in source.values()):
        raise UiExportError("Crossref relation expansion source is invalid")
    edges: list[dict[str, str]] = []
    for edge in payload["edges"]:
        if not isinstance(edge, dict) or set(edge) != {"edge_type", "target_doi"} or edge.get("edge_type") != "crossref_reference":
            raise UiExportError("Crossref relation expansion edge is invalid")
        target = edge.get("target_doi")
        if not isinstance(target, str) or not target.startswith("10.") or "/" not in target:
            raise UiExportError("Crossref relation expansion target is invalid")
        edges.append({"edge_type": "crossref_reference", "target_doi": target})
    return {"trust_status": trust_status, "source": {"evidence_id": source["evidence_id"], "document_id": source["document_id"]}, "reference_field_present": payload["reference_field_present"], "edges": edges}
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

def _relation_reconciliation_projection(reconciliation: dict[str, Any] | None) -> dict[str, Any] | None:
    if reconciliation is None: return None
    history = reconciliation.get("revision_history", [])
    return {"trust_status": reconciliation["trust_status"], "source": reconciliation["source"], "mappings": [{key: mapping[key] for key in ("openalex_work_id", "crossref_doi", "status", "basis")} for mapping in reconciliation["mappings"]], "revision_history": [{key: revision[key] for key in ("revision", "recorded_at", "mapping_count", "status_counts")} for revision in history]}


def _condition_normalization_projection(normalization: dict[str, Any] | None) -> dict[str, Any] | None:
    """Expose only reviewer-declared field names and units, never values or conversions."""
    if normalization is None:
        return None
    return {
        "trust_status": normalization["trust_status"],
        "mappings": [
            {key: mapping[key] for key in ("evidence_id", "raw_field", "canonical_field", "unit")}
            for mapping in normalization["mappings"]
        ],
    }
def _paper_structure_projection(structure: dict[str, Any] | None) -> dict[str, Any] | None:
    if structure is None:
        return None
    entities = [{key: entity[key] for key in ("entity_id", "label", "kind", "segment_id")} for entity in structure["entities"]]
    relations = [{key: relation[key] for key in ("source_entity_id", "target_entity_id", "relation_type", "segment_id")} for relation in structure["relations"]]
    return {"document_id": structure["document_id"], "trust_status": structure["trust_status"], "entities": entities, "relations": relations}
def _retrieval_candidate_projection(path: Path) -> list[dict[str, Any]]:
    """Release public-looking candidate metadata, never query text or scores."""
    if not path.exists():
        return []
    payload = _load_object(path, "retrieval candidate artifact")
    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list):
        raise UiExportError("retrieval candidate artifact has invalid candidates")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_candidates:
        if not isinstance(item, dict):
            raise UiExportError("retrieval candidate artifact contains an invalid candidate")
        document_id, title, source = item.get("document_id"), item.get("title"), item.get("source")
        if (
            not isinstance(document_id, str) or not document_id or len(document_id) > 255 or document_id in seen
            or not isinstance(title, str) or not title.strip() or len(title.strip()) > 500
            or not isinstance(source, str) or not source.strip() or len(source.strip()) > 120
        ):
            raise UiExportError("retrieval candidate artifact contains invalid public metadata")
        year = item.get("publication_year")
        if year is not None and (not isinstance(year, int) or not 1600 <= year <= 3000):
            raise UiExportError("retrieval candidate artifact contains an invalid publication year")
        try:
            safe_title = normalize_public_title(title)
        except ValueError as error:
            raise UiExportError("retrieval candidate title is not safe for UI export") from error
        result.append({
            "document_id": document_id,
            "title": safe_title,
            "source": source.strip(),
            "publication_year": year,
            "is_content_accessible": item.get("is_content_accessible") is True,
        })
        seen.add(document_id)
        if len(result) == _MAX_LITERATURE_GRAPH_CANDIDATES:
            break
    return result


def _citation_expansion_projection(path: Path, mission_id: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = _load_object(path, "citation expansion artifact")
    try:
        validate_citation_expansion(payload)
    except CitationExpansionError as error:
        raise UiExportError(str(error)) from error
    if payload.get("mission_id") != mission_id:
        raise UiExportError("citation expansion does not belong to this mission")
    return payload

def _literature_graph_projection(
    mission: MissionBrief,
    evidence_cards: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    literature_relations: dict[str, Any] | None,
    crossref_relations: dict[str, Any] | None,
    paper_structure: dict[str, Any] | None,
    research_gap_candidates: list[dict[str, Any]] | None = None,
    paper_structures: tuple[dict[str, Any], ...] = (),
    citation_expansion: dict[str, Any] | None = None,
    condition_matrix: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a bounded navigation graph with explicit non-evidence labels."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    node_ids: set[str] = set()
    edge_ids: set[tuple[str, str, str]] = set()

    def add_node(node_id: str, kind: str, label: str, trust_status: str, **extra: Any) -> None:
        if node_id in node_ids or len(nodes) == _MAX_LITERATURE_GRAPH_NODES:
            return
        node = {"node_id": node_id, "kind": kind, "label": label, "trust_status": trust_status}
        node.update(extra)
        nodes.append(node)
        node_ids.add(node_id)

    def add_edge(source_id: str, target_id: str, edge_type: str, relation_source: str, trust_status: str) -> None:
        key = (source_id, target_id, edge_type)
        if source_id not in node_ids or target_id not in node_ids or key in edge_ids or len(edges) == _MAX_LITERATURE_GRAPH_EDGES:
            return
        edges.append({"source_id": source_id, "target_id": target_id, "edge_type": edge_type, "relation_source": relation_source, "trust_status": trust_status})
        edge_ids.add(key)

    mission_node = f"mission:{mission.mission_id}"
    add_node(mission_node, "mission", f"{mission.material} / {mission.property_name}", "mission_navigation")
    for candidate in candidates:
        paper_id = f"paper:{candidate['document_id']}"
        add_node(paper_id, "candidate_paper", candidate["title"], "retrieval_candidate_not_scientific_evidence", source=candidate["source"], publication_year=candidate["publication_year"], is_content_accessible=candidate["is_content_accessible"])
        add_edge(mission_node, paper_id, "retrieval_candidate", candidate["source"], "retrieval_candidate_not_scientific_evidence")

    for card in evidence_cards:
        provenance = card["provenance"]
        paper_id = f"paper:{provenance['document_id']}"
        if paper_id not in node_ids:
            add_node(paper_id, "evidence_paper", provenance["document_id"], "accepted_evidence_source", source=provenance["source"], publication_year=None, is_content_accessible=provenance["access_policy"] != AccessPolicy.METADATA_ONLY.value)
        evidence_id = f"evidence:{card['evidence_id']}"
        add_node(evidence_id, "accepted_evidence", card["claim"], "accepted_evidence")
        add_edge(paper_id, evidence_id, "source_provenance", provenance["source"], "accepted_evidence")

    # The condition matrix is a comparison artifact, not a scientific conclusion.
    # Project it explicitly so researchers can see which accepted EvidenceCards
    # contribute to a comparable condition cluster and which stance each card has.
    for index, row in enumerate(condition_matrix or [], start=1):
        cluster = row.get("condition_cluster") if isinstance(row, dict) else None
        if not isinstance(cluster, str) or not cluster.strip():
            continue
        cluster_id = f"condition:{index}"
        trust_status = "derived_condition_comparison_not_scientific_conclusion"
        add_node(cluster_id, "condition_cluster", cluster.strip()[:320], trust_status)
        for evidence_id in row.get("supporting_evidence_ids", []):
            if isinstance(evidence_id, str) and evidence_id:
                add_edge(f"evidence:{evidence_id}", cluster_id, "condition_support", "condition matrix", trust_status)
        for evidence_id in row.get("contradicting_evidence_ids", []):
            if isinstance(evidence_id, str) and evidence_id:
                add_edge(f"evidence:{evidence_id}", cluster_id, "condition_contradiction", "condition matrix", trust_status)


    for candidate in research_gap_candidates or []:
        gap_id = f"gap:{candidate['gap_id']}"
        add_node(gap_id, "research_gap_candidate", candidate["problem_description"], "candidate_requires_human_review_not_a_scientific_finding")
        for evidence_id in candidate["evidence_ids"]:
            add_edge(f"evidence:{evidence_id}", gap_id, "gap_evidence_basis", "accepted EvidenceCard", "candidate_requires_human_review_not_a_scientific_finding")

    if literature_relations is not None:
        root_id = f"paper:{literature_relations['source']['document_id']}"
        if root_id not in node_ids:
            add_node(root_id, "relation_root_paper", literature_relations["source"]["document_id"], "public_relation_metadata_not_scientific_evidence")
        for relation in literature_relations["edges"]:
            target = relation["target_openalex_id"]
            target_id = f"openalex:{target.rsplit('/', maxsplit=1)[-1]}"
            add_node(target_id, "openalex_work", target.rsplit("/", maxsplit=1)[-1], "public_relation_metadata_not_scientific_evidence", source="OpenAlex")
            add_edge(root_id, target_id, relation["edge_type"], "OpenAlex", "public_relation_metadata_not_scientific_evidence")

    if crossref_relations is not None:
        root_id = f"paper:{crossref_relations['source']['document_id']}"
        if root_id not in node_ids:
            add_node(root_id, "relation_root_paper", crossref_relations["source"]["document_id"], "public_bibliographic_reference_metadata_not_scientific_evidence")
        for relation in crossref_relations["edges"]:
            target = relation["target_doi"]
            target_id = f"doi:{target}"
            add_node(target_id, "crossref_work", target, "public_bibliographic_reference_metadata_not_scientific_evidence", source="Crossref")
            add_edge(root_id, target_id, "crossref_reference", "Crossref", "public_bibliographic_reference_metadata_not_scientific_evidence")

    if citation_expansion is not None:
        trust_status = citation_expansion["trust_status"]
        for node in citation_expansion["nodes"]:
            doi = node["doi"]
            add_node(f"doi:{doi}", "citation_work", doi, trust_status, source="DOI citation expansion")
        for edge in citation_expansion["edges"]:
            add_edge(f"doi:{edge['source_doi']}", f"doi:{edge['target_doi']}", edge["edge_type"], "OpenAlex/Crossref DOI expansion", trust_status)

    structures_by_document: dict[str, dict[str, Any]] = {}
    for structure in ((paper_structure,) if paper_structure is not None else ()) + paper_structures:
        document_id = structure.get("document_id") if isinstance(structure, dict) else None
        if isinstance(document_id, str) and document_id:
            structures_by_document[document_id] = structure
    for document_id in sorted(structures_by_document):
        structure = structures_by_document[document_id]
        paper_id = f"paper:{document_id}"
        if paper_id not in node_ids:
            add_node(paper_id, "structured_paper", document_id, structure["trust_status"])
        for entity in structure["entities"]:
            entity_id = f"entity:{document_id}:{entity['entity_id']}"
            add_node(entity_id, "paper_entity", entity["label"], structure["trust_status"], entity_kind=entity["kind"])
            add_edge(paper_id, entity_id, "paper_contains", "reviewed_structure", structure["trust_status"])
        for relation in structure["relations"]:
            add_edge(
                f"entity:{document_id}:{relation['source_entity_id']}",
                f"entity:{document_id}:{relation['target_entity_id']}",
                relation["relation_type"],
                "reviewed_structure",
                structure["trust_status"],
            )
    return {"trust_status": "navigation_metadata_and_reviewed_artifacts_not_a_scientific_conclusion", "nodes": nodes, "edges": edges}

def _counterevidence_readiness_summary(run_dir: Path, mission_id: str) -> dict[str, Any]:
    """Project only counterevidence gate progress, never plan or query text.

    A condition matrix or Gap candidate may be built only after every approved
    counterevidence query has a local retrieval-history record.  This small UI
    projection keeps that operational boundary visible without exporting query
    strings, candidate metadata, receipt IDs, or audit-event payloads.
    """
    try:
        plan = load_approved_flight_plan(run_dir, mission_id)
    except PlanApprovalError:
        return {"state": "plan_not_approved", "planned_query_count": 0, "executed_query_count": 0}
    planned_query_count = len(plan.counter_queries)
    if not planned_query_count:
        return {"state": "plan_not_approved", "planned_query_count": 0, "executed_query_count": 0}
    try:
        history = _load_object(run_dir / "retrieval_candidates.json", "retrieval candidate history")
    except UiExportError:
        history = {}
    try:
        execution = require_executed_counterevidence(plan, history)
    except CounterevidenceGateError:
        searches = history.get("searches") if isinstance(history, dict) else None
        executed_queries = {
            entry.get("query").strip()
            for entry in searches
            if isinstance(entry, dict) and isinstance(entry.get("query"), str) and entry["query"].strip()
        } if isinstance(searches, list) else set()
        executed_query_count = sum(query in executed_queries for query in plan.counter_queries)
        return {
            "state": "awaiting_counterevidence_execution",
            "planned_query_count": planned_query_count,
            "executed_query_count": executed_query_count,
        }
    return {
        "state": "ready",
        "planned_query_count": execution.planned_query_count,
        "executed_query_count": execution.executed_query_count,
    }


def _audit_summary_from_run(run_dir: Path, mission_id: str) -> dict[str, Any]:
    return {
        "counterevidence": _counterevidence_readiness_summary(run_dir, mission_id),
        "report_evidence": _report_evidence_audit_summary(run_dir / "report_evidence_audit.json", mission_id),
        "evidence_provenance": _evidence_provenance_audit_summary(run_dir / "evidence_provenance_audit.json", mission_id),
        "external_retrieval": {"sciverse_agentic_search_count": _sciverse_receipt_count(run_dir / "provider_receipts.jsonl")},
        "submission_readiness": {
            "frozen_corpus": _frozen_corpus_readiness_summary(run_dir / "frozen_corpus_readiness.json", mission_id),
            "human_annotation": _human_annotation_coverage_summary(run_dir / "human_annotation_coverage.json", mission_id),
            "bibliographic_source": _bibliographic_source_coverage_summary(run_dir / "bibliographic_source_coverage.json", mission_id),
        },
        "evaluation": _evaluation_summary_from_run(run_dir, mission_id),
    }


def _evaluation_summary_from_run(run_dir: Path, mission_id: str) -> dict[str, Any]:
    return {
        "evidence_quality": _evidence_quality_evaluation_summary(run_dir / "human_evidence_quality_evaluation.json", mission_id),
        "retrieval": _retrieval_evaluation_summary(run_dir / "human_retrieval_evaluation.json", mission_id),
        "material_facts": _material_fact_evaluation_summary(run_dir / "human_material_fact_evaluation.json", mission_id),
        "research_gaps": _gap_evaluation_summary(run_dir / "human_gap_evaluation.json", mission_id),
    }


def _frozen_corpus_readiness_summary(path: Path, mission_id: str) -> dict[str, Any] | None:
    """Project only submission-safe corpus readiness counts and gate state."""
    if not path.exists():
        return None
    payload = _load_object(path, "frozen corpus readiness")
    expected = {
        "schema_version", "trust_status", "mission_id", "corpus_id", "expected_document_count",
        "frozen_document_count", "expected_count_matched", "unique_document_id_count",
        "document_id_uniqueness_valid", "doi_present_count", "doi_missing_count",
        "authorized_access_policy_count", "authorized_access_boundary_valid", "manifest_sha256",
        "evaluation_gate", "boundary",
    }
    if (
        set(payload) != expected
        or payload.get("schema_version") != "1.0"
        or payload.get("trust_status") != "aggregate_frozen_corpus_readiness_not_evaluation_result"
        or payload.get("mission_id") != mission_id
        or not isinstance(payload.get("corpus_id"), str)
        or not isinstance(payload.get("manifest_sha256"), str)
        or len(payload["manifest_sha256"]) != 64
        or not isinstance(payload.get("expected_count_matched"), bool)
        or not isinstance(payload.get("document_id_uniqueness_valid"), bool)
        or not isinstance(payload.get("authorized_access_boundary_valid"), bool)
        or not isinstance(payload.get("evaluation_gate"), str)
    ):
        raise UiExportError("frozen corpus readiness audit is invalid for this mission")
    return {
        "expected_document_count": _audit_nonnegative_int(payload, "expected_document_count"),
        "frozen_document_count": _audit_nonnegative_int(payload, "frozen_document_count"),
        "expected_count_matched": payload["expected_count_matched"],
        "document_id_uniqueness_valid": payload["document_id_uniqueness_valid"],
        "doi_present_count": _audit_nonnegative_int(payload, "doi_present_count"),
        "doi_missing_count": _audit_nonnegative_int(payload, "doi_missing_count"),
        "authorized_access_boundary_valid": payload["authorized_access_boundary_valid"],
        "evaluation_gate": payload["evaluation_gate"],
    }


def _human_annotation_coverage_summary(path: Path, mission_id: str) -> dict[str, Any] | None:
    """Project aggregate review coverage without document identities or labels."""
    if not path.exists():
        return None
    payload = _load_object(path, "human annotation coverage")
    expected = {
        "schema_version", "trust_status", "mission_id", "corpus_id", "frozen_document_count",
        "annotation_file_status", "relevance_counts", "documents_with_evidence_annotations",
        "documents_with_material_fact_annotations", "documents_with_comparison_annotations",
        "documents_with_gap_annotations", "relevance_evaluation_gate", "annotation_file_sha256", "boundary",
    }
    relevance_counts = payload.get("relevance_counts")
    expected_relevance = {"unreviewed", "relevant", "partially_relevant", "not_relevant"}
    if (
        set(payload) != expected
        or payload.get("schema_version") != "1.0"
        or payload.get("trust_status") != "aggregate_human_annotation_coverage_not_evaluation_result"
        or payload.get("mission_id") != mission_id
        or not isinstance(payload.get("corpus_id"), str)
        or not isinstance(payload.get("annotation_file_status"), str)
        or not isinstance(relevance_counts, dict)
        or set(relevance_counts) != expected_relevance
        or not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in relevance_counts.values())
        or not isinstance(payload.get("relevance_evaluation_gate"), str)
        or not isinstance(payload.get("annotation_file_sha256"), str)
        or len(payload["annotation_file_sha256"]) != 64
    ):
        raise UiExportError("human annotation coverage audit is invalid for this mission")
    return {
        "frozen_document_count": _audit_nonnegative_int(payload, "frozen_document_count"),
        "annotation_file_status": payload["annotation_file_status"],
        "relevance_counts": relevance_counts,
        "documents_with_evidence_annotations": _audit_nonnegative_int(payload, "documents_with_evidence_annotations"),
        "documents_with_material_fact_annotations": _audit_nonnegative_int(payload, "documents_with_material_fact_annotations"),
        "documents_with_comparison_annotations": _audit_nonnegative_int(payload, "documents_with_comparison_annotations"),
        "documents_with_gap_annotations": _audit_nonnegative_int(payload, "documents_with_gap_annotations"),
        "relevance_evaluation_gate": payload["relevance_evaluation_gate"],
    }


def _bibliographic_source_coverage_summary(path: Path, mission_id: str) -> dict[str, Any] | None:
    """Project source-traceability aggregate values, never source labels or IDs."""
    if not path.exists():
        return None
    payload = _load_object(path, "bibliographic source coverage")
    expected = {
        "schema_version", "trust_status", "mission_id", "corpus_id", "frozen_document_count",
        "documents_with_reviewed_bibliographic_source", "distinct_bibliographic_source_count",
        "bibliographic_source_coverage_gate", "registry_sha256", "boundary",
    }
    if (
        set(payload) != expected
        or payload.get("schema_version") != "1.0"
        or payload.get("trust_status") != "aggregate_bibliographic_source_coverage_not_evaluation_result"
        or payload.get("mission_id") != mission_id
        or not isinstance(payload.get("corpus_id"), str)
        or not isinstance(payload.get("bibliographic_source_coverage_gate"), str)
        or not isinstance(payload.get("registry_sha256"), str)
        or len(payload["registry_sha256"]) != 64
    ):
        raise UiExportError("bibliographic source coverage audit is invalid for this mission")
    return {
        "frozen_document_count": _audit_nonnegative_int(payload, "frozen_document_count"),
        "documents_with_reviewed_bibliographic_source": _audit_nonnegative_int(payload, "documents_with_reviewed_bibliographic_source"),
        "distinct_bibliographic_source_count": _audit_nonnegative_int(payload, "distinct_bibliographic_source_count"),
        "bibliographic_source_coverage_gate": payload["bibliographic_source_coverage_gate"],
    }


def _evidence_quality_evaluation_summary(path: Path, mission_id: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = _load_object(path, "human evidence-quality evaluation")
    expected = {
        "schema_version", "mission_id", "trust_status", "evidence_count", "predicted_contradiction_count",
        "citation_precision", "condition_completeness", "contradiction_precision",
    }
    if set(payload) != expected or payload.get("mission_id") != mission_id or payload.get("trust_status") != "metrics_from_human_reviewed_evidence_locator_condition_and_contradiction_audit":
        raise UiExportError("human evidence-quality evaluation is invalid for this mission")
    return {
        "trust_status": payload["trust_status"],
        "evidence_count": _audit_nonnegative_int(payload, "evidence_count"),
        "predicted_contradiction_count": _audit_nonnegative_int(payload, "predicted_contradiction_count"),
        "citation_precision": _audit_rate(payload, "citation_precision"),
        "condition_completeness": _audit_rate(payload, "condition_completeness"),
        "contradiction_precision": _audit_rate(payload, "contradiction_precision"),
    }


def _retrieval_evaluation_summary(path: Path, mission_id: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = _load_object(path, "human retrieval evaluation")
    legacy_fields = {
        "schema_version", "mission_id", "corpus_id", "trust_status", "search_index", "k",
        "retrieved_count", "gold_relevant_count", "gold_partially_relevant_count",
        "precision_at_k", "recall_at_k", "ndcg_at_k",
    }
    resolved_identity_fields = legacy_fields | {
        "identity_resolution_policy", "raw_retrieved_count",
        "doi_resolved_candidate_count", "duplicate_alias_count",
    }
    expected = legacy_fields if payload.get("schema_version") == "1.0" else resolved_identity_fields
    if (
        set(payload) != expected
        or payload.get("mission_id") != mission_id
        or payload.get("trust_status") != "metrics_from_human_reviewed_gold_standard"
        or (payload.get("schema_version") == "1.1" and payload.get("identity_resolution_policy") != "exact_document_id_or_normalized_doi_to_frozen_manifest")
    ):
        raise UiExportError("human retrieval evaluation is invalid for this mission")
    if payload.get("schema_version") == "1.1":
        _audit_nonnegative_int(payload, "raw_retrieved_count")
        _audit_nonnegative_int(payload, "doi_resolved_candidate_count")
        _audit_nonnegative_int(payload, "duplicate_alias_count")
    return {
        "trust_status": payload["trust_status"],
        "k": _audit_nonnegative_int(payload, "k"),
        "retrieved_count": _audit_nonnegative_int(payload, "retrieved_count"),
        "gold_relevant_count": _audit_nonnegative_int(payload, "gold_relevant_count"),
        "precision_at_k": _audit_rate(payload, "precision_at_k"),
        "recall_at_k": _audit_rate(payload, "recall_at_k"),
        "ndcg_at_k": _audit_rate(payload, "ndcg_at_k"),
    }


def _material_fact_evaluation_summary(path: Path, mission_id: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = _load_object(path, "human material fact evaluation")
    expected = {
        "schema_version", "mission_id", "corpus_id", "trust_status",
        "gold_fact_count", "reviewed_fact_count", "exact_match_count",
        "precision", "recall", "f1", "unit_match_denominator", "unit_match_accuracy",
    }
    if set(payload) != expected or payload.get("mission_id") != mission_id or payload.get("trust_status") != "metrics_for_review_gated_material_fact_pipeline_not_raw_llm_accuracy":
        raise UiExportError("human material fact evaluation is invalid for this mission")
    return {
        "trust_status": payload["trust_status"],
        "gold_fact_count": _audit_nonnegative_int(payload, "gold_fact_count"),
        "reviewed_fact_count": _audit_nonnegative_int(payload, "reviewed_fact_count"),
        "precision": _audit_rate(payload, "precision"),
        "recall": _audit_rate(payload, "recall"),
        "f1": _audit_rate(payload, "f1"),
        "unit_match_accuracy": _audit_rate(payload, "unit_match_accuracy"),
    }


def _gap_evaluation_summary(path: Path, mission_id: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = _load_object(path, "human Gap evaluation")
    expected = {
        "schema_version", "mission_id", "trust_status", "candidate_count",
        "expert_approval_rate", "mean_novelty_rating",
        "mean_actionability_rating", "evidence_completeness_rate",
        "counterevidence_review_rate", "bounded_no_direct_match_rate",
        "related_prior_work_found_rate", "inconclusive_novelty_search_rate",
    }
    if set(payload) != expected or payload.get("mission_id") != mission_id or payload.get("trust_status") != "metrics_from_human_expert_review_of_evidence_bound_gap_candidates":
        raise UiExportError("human Gap evaluation is invalid for this mission")
    for key in ("mean_novelty_rating", "mean_actionability_rating"):
        value = payload.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 1 <= float(value) <= 5:
            raise UiExportError(f"human Gap evaluation field {key} is invalid")
    return {
        "trust_status": payload["trust_status"],
        "candidate_count": _audit_nonnegative_int(payload, "candidate_count"),
        "expert_approval_rate": _audit_rate(payload, "expert_approval_rate"),
        "mean_novelty_rating": float(payload["mean_novelty_rating"]),
        "mean_actionability_rating": float(payload["mean_actionability_rating"]),
        "evidence_completeness_rate": _audit_rate(payload, "evidence_completeness_rate"),
        "counterevidence_review_rate": _audit_rate(payload, "counterevidence_review_rate"),
        "bounded_no_direct_match_rate": _audit_rate(payload, "bounded_no_direct_match_rate"),
        "related_prior_work_found_rate": _audit_rate(payload, "related_prior_work_found_rate"),
        "inconclusive_novelty_search_rate": _audit_rate(payload, "inconclusive_novelty_search_rate"),
    }


def _report_evidence_audit_summary(path: Path, mission_id: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = _load_object(path, "report evidence audit")
    expected = {
        "schema_version", "mission_id", "report_id", "trust_status", "accepted_evidence_count",
        "manifest_evidence_count", "accepted_evidence_manifest_coverage", "research_gap_candidate_count",
        "gap_evidence_reference_count", "gap_evidence_accepted_coverage",
        "structured_report_identifier_coverage", "accepted_evidence_locator_rendered_coverage",
        "reviewed_material_fact_count", "reviewed_material_fact_rendered_coverage",
        "cross_document_comparison_count", "comparison_observation_reference_count",
        "comparison_observation_rendered_coverage",
        "executed_gap_counterevidence_boundary_count", "gap_counterevidence_boundary_rendered_coverage",
        "human_source_locator_review_required",
    }
    if set(payload) != expected or payload.get("mission_id") != mission_id or payload.get("trust_status") != "artifact_level_identifier_audit_not_scientific_validity_assessment":
        raise UiExportError("report evidence audit is invalid for this mission")
    return {
        "accepted_evidence_count": _audit_nonnegative_int(payload, "accepted_evidence_count"),
        "manifest_coverage": _audit_rate(payload, "accepted_evidence_manifest_coverage"),
        "gap_evidence_coverage": _audit_rate(payload, "gap_evidence_accepted_coverage"),
        "structured_report_identifier_coverage": _audit_rate(payload, "structured_report_identifier_coverage"),
        "accepted_evidence_locator_rendered_coverage": _audit_rate(payload, "accepted_evidence_locator_rendered_coverage"),
        "executed_gap_counterevidence_boundary_count": _audit_nonnegative_int(payload, "executed_gap_counterevidence_boundary_count"),
        "gap_counterevidence_boundary_rendered_coverage": _audit_rate(payload, "gap_counterevidence_boundary_rendered_coverage"),
    }


def _evidence_provenance_audit_summary(path: Path, mission_id: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = _load_object(path, "evidence provenance audit")
    expected = {
        "schema_version", "mission_id", "trust_status", "accepted_evidence_count",
        "exact_reviewed_source_map_match_count", "manual_locator_only_count",
        "exact_source_map_match_rate", "items",
    }
    if set(payload) != expected or payload.get("mission_id") != mission_id or payload.get("trust_status") != "accepted_evidence_provenance_coverage_not_source_authenticity_assessment" or not isinstance(payload.get("items"), list):
        raise UiExportError("evidence provenance audit is invalid for this mission")
    return {
        "accepted_evidence_count": _audit_nonnegative_int(payload, "accepted_evidence_count"),
        "exact_source_map_match_count": _audit_nonnegative_int(payload, "exact_reviewed_source_map_match_count"),
        "manual_locator_only_count": _audit_nonnegative_int(payload, "manual_locator_only_count"),
        "exact_source_map_match_rate": _audit_rate(payload, "exact_source_map_match_rate"),
    }


def _sciverse_receipt_count(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise UiExportError("provider receipt log cannot be read") from error
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError as error:
            raise UiExportError("provider receipt log is invalid") from error
        if not isinstance(item, dict):
            raise UiExportError("provider receipt log contains an invalid entry")
        provider, operation = item.get("provider"), item.get("operation")
        if provider == "sciverse" and operation == "agentic_search":
            count += 1
        elif (provider == "sciverse" and operation == "content") or (
            provider == "mineru" and operation in {"source_parse_submit", "source_parse_poll"}
        ):
            continue
        else:
            raise UiExportError("provider receipt log contains an unsupported entry")
    return count


def _audit_nonnegative_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise UiExportError(f"audit field {key} is invalid")
    return value


def _audit_rate(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= float(value) <= 1:
        raise UiExportError(f"audit field {key} is invalid")
    return float(value)


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
    source_maps: tuple[dict[str, Any], ...] = (),
    paper_structure: dict[str, Any] | None = None,
    paper_structures: tuple[dict[str, Any], ...] = (),
    literature_relations: dict[str, Any] | None = None,
    crossref_relations: dict[str, Any] | None = None,
    citation_expansion: dict[str, Any] | None = None,

    relation_reconciliation: dict[str, Any] | None = None,
    condition_normalization: dict[str, Any] | None = None,
    retrieval_candidates: list[dict[str, Any]] | None = None,
    research_gap_candidates: list[dict[str, Any]] | None = None,
    material_facts: dict[str, Any] | None = None,
    material_fact_artifacts: tuple[dict[str, Any], ...] = (),
    audit_summary: dict[str, Any] | None = None,
    evidence_maturity_registry: dict[str, Any] | None = None,
    evidence_maturity_registry_delivery_status: str = "not_supplied",
    simulation_campaign: dict[str, Any] | None = None,
    simulation_campaign_delivery_status: str = "not_supplied",
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
    accepted_ids = {item["evidence_id"] for item in projected_evidence}
    candidate_ids: set[str] = set()
    for candidate in research_gap_candidates or []:
        if not isinstance(candidate, dict):
            raise UiExportError("research gap candidate must be an object")
        gap_id = candidate.get("gap_id")
        evidence_ids = candidate.get("evidence_ids")
        if not isinstance(gap_id, str) or not gap_id.strip() or gap_id in candidate_ids:
            raise UiExportError("research gap candidate identifiers must be unique non-empty strings")
        if candidate.get("review_status") != "candidate_requires_human_review":
            raise UiExportError("research gap candidate must remain pending human review")
        if candidate.get("material") != mission.material or candidate.get("property_name") != mission.property_name:
            raise UiExportError("research gap candidate does not match this mission material and property")
        if not isinstance(evidence_ids, list) or not evidence_ids or not all(isinstance(item, str) and item for item in evidence_ids):
            raise UiExportError("research gap candidate must contain evidence identifiers")
        if not set(evidence_ids).issubset(accepted_ids):
            raise UiExportError("research gap candidate references evidence not accepted in this mission")
        candidate_ids.add(gap_id)
    if mission_report is not None and not set(mission_report.research_gap_candidate_ids).issubset(candidate_ids):
        raise UiExportError("mission report references a research gap candidate missing from this export")
    if evidence_maturity_registry_delivery_status not in {"not_supplied", "accepted", "rejected"}:
        raise UiExportError("evidence maturity registry delivery status is invalid")
    if evidence_maturity_registry is not None and evidence_maturity_registry_delivery_status != "accepted":
        raise UiExportError("evidence maturity registry requires an accepted delivery status")
    if simulation_campaign_delivery_status not in {"not_supplied", "approved", "rejected"}:
        raise UiExportError("simulation campaign delivery status is invalid")
    if simulation_campaign is not None and simulation_campaign_delivery_status != "approved":
        raise UiExportError("simulation campaign requires an approved delivery status")
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
        "research_gap_candidates": research_gap_candidates or [],
        "timeline": timeline or [],
        "research_guide": research_guide,
        "paper_source_map": _paper_source_map_projection(paper_source_map),
        "reviewed_source_map_summary": _reviewed_source_map_summary(source_maps),
        "paper_structure": _paper_structure_projection(paper_structure),
        "material_facts": _material_facts_projection(material_facts),
        "reviewed_material_fact_summary": _reviewed_material_fact_summary(material_fact_artifacts),
        "evidence_maturity_registry": evidence_maturity_registry,
        "evidence_maturity_registry_delivery_status": evidence_maturity_registry_delivery_status,
        "simulation_campaign": simulation_campaign,
        "simulation_campaign_delivery_status": simulation_campaign_delivery_status,
        "literature_relations": literature_relations,
        "crossref_relations": crossref_relations,
        "relation_reconciliation": _relation_reconciliation_projection(relation_reconciliation),
        "condition_normalization": _condition_normalization_projection(condition_normalization),
        "literature_graph": _literature_graph_projection(
            mission,
            projected_evidence,
            retrieval_candidates or [],
            literature_relations,
            crossref_relations,
            paper_structure,
            research_gap_candidates or [],
            paper_structures,
            citation_expansion,
            condition_matrix,
        ),
        "mission_report": mission_report.to_dict() if mission_report is not None else None,
        "audit_summary": audit_summary or {
            "counterevidence": {"state": "plan_not_approved", "planned_query_count": 0, "executed_query_count": 0},
            "report_evidence": None,
            "evidence_provenance": None,
            "external_retrieval": {"sciverse_agentic_search_count": 0},
            "submission_readiness": {
                "frozen_corpus": None,
                "human_annotation": None,
                "bibliographic_source": None,
            },
            "evaluation": {"evidence_quality": None, "retrieval": None, "material_facts": None, "research_gaps": None},
        },
        "coverage": {"scope": "bounded local mission artifacts and configured providers", "empty_result_meaning": "No current result means no matching artifact or response in this bounded mission; it does not establish that the material-science literature or phenomenon is absent."},
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
    research_gap_candidates = _gap_candidates_if_present(run_dir / "research_gap_candidates.json")
    timeline = _timeline_projection(run_dir / "events.jsonl")
    literature_relations = _relation_expansion_projection(run_dir / "relation_expansion.json", mission.mission_id)
    crossref_relations = _crossref_relation_expansion_projection(run_dir / "crossref_relation_expansion.json", mission.mission_id)
    citation_expansion = _citation_expansion_projection(run_dir / "citation_expansion.json", mission.mission_id)
    retrieval_candidates = _retrieval_candidate_projection(run_dir / "retrieval_candidates.json")
    maturity_registry, maturity_delivery_status = _evidence_maturity_registry_projection(run_dir, runs_dir, mission.mission_id)
    simulation_campaign, simulation_campaign_delivery_status = _simulation_campaign_projection(run_dir, mission.mission_id)
    try:
        research_guide = load_reading_guide(run_dir / "reading_guide.json", mission.mission_id)
        source_maps = iter_source_maps(run_dir, mission.mission_id)
        if any(
            decision.mission_id == mission.mission_id and decision.status is ReviewStatus.ACCEPTED
            for decision in verification_decisions
        ):
            audit_accepted_evidence_provenance(
                mission=mission,
                cards=evidence_cards,
                decisions=verification_decisions,
                source_maps=source_maps,
            )
        paper_source_map = source_maps[0] if source_maps else None
        paper_structures = iter_paper_structures(run_dir, mission.mission_id)
        paper_structure = paper_structures[0] if paper_structures else None
        material_fact_artifacts = iter_material_facts(run_dir, mission.mission_id)
        validate_material_fact_source_links(
            mission_id=mission.mission_id,
            artifacts=material_fact_artifacts,
            source_maps=source_maps,
        )
        material_facts = material_fact_artifacts[0] if material_fact_artifacts else None
        relation_reconciliation = load_relation_reconciliation(run_dir / "relation_reconciliation.json", mission.mission_id)
        condition_normalization = load_condition_normalization(run_dir / "condition_normalization.json", mission.mission_id)
        audit_summary = _audit_summary_from_run(run_dir, mission.mission_id)
    except (ReadingGuideError, SourceMapError, PaperStructureError, MaterialExtractionError, ProvenanceAuditError, RelationReconciliationError, ConditionNormalizationError) as error:
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
        source_maps=source_maps,
        paper_structure=paper_structure,
        paper_structures=paper_structures,
        literature_relations=literature_relations,
        crossref_relations=crossref_relations,
        citation_expansion=citation_expansion,
        relation_reconciliation=relation_reconciliation,
        condition_normalization=condition_normalization,
        retrieval_candidates=retrieval_candidates,
        research_gap_candidates=research_gap_candidates,
        material_facts=material_facts,
        material_fact_artifacts=material_fact_artifacts,
        audit_summary=audit_summary,
        evidence_maturity_registry=maturity_registry,
        evidence_maturity_registry_delivery_status=maturity_delivery_status,
        simulation_campaign=simulation_campaign,
        simulation_campaign_delivery_status=simulation_campaign_delivery_status,
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


def _simulation_campaign_projection(run_dir: Path, mission_id: str) -> tuple[dict[str, Any] | None, str]:
    """Safely expose only an approved, non-executing campaign summary."""
    path = run_dir / "simulation_campaign.json"
    if not path.exists():
        return None, "not_supplied"
    try:
        return simulation_campaign_ui_projection(_load_object(path, "simulation campaign"), mission_id), "approved"
    except (SimulationCampaignError, UiExportError):
        return None, "rejected"


def _evidence_maturity_registry_projection(run_dir: Path, runs_dir: Path, mission_id: str) -> tuple[dict[str, Any] | None, str]:
    """Expose maturity only when the recorded count-only audit still matches."""
    registry_path = run_dir / "evidence_maturity_registry.json"
    audit_path = run_dir / "evidence_maturity_registry_audit.json"
    if not registry_path.exists() and not audit_path.exists():
        return None, "not_supplied"
    if not registry_path.exists() or not audit_path.exists():
        return None, "rejected"
    try:
        registry = load_evidence_maturity_registry(registry_path)
        audit = _load_object(audit_path, "evidence maturity registry audit")
        if registry.get("question_id") != mission_id:
            return None, "rejected"
        validate_evidence_maturity_registry_audit(audit, registry)
        if audit["passed"] is not True:
            return None, "rejected"
        if audit_evidence_maturity_registry_against_runs(registry, runs_dir) != audit:
            return None, "rejected"
    except (EvidenceMaturityRegistryError, UiExportError):
        return None, "rejected"
    return registry, "accepted"


