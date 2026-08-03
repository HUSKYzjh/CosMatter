"""Versioned work products exchanged by CosMatter modules.

The system deliberately shares typed artifacts instead of a mutable group-chat
history.  Every scientific assertion is represented as an EvidenceCard and
must retain source provenance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class MissionState(str, Enum):
    INTAKE = "INTAKE"
    NEED_SCOPE = "NEED_SCOPE"
    PLAN = "PLAN"
    RETRIEVE = "RETRIEVE"
    SELECT = "SELECT"
    EXTRACT = "EXTRACT"
    MAP = "MAP"
    HAZARD_SCAN = "HAZARD_SCAN"
    VERIFY = "VERIFY"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    REPORT = "REPORT"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class Stance(str, Enum):
    SUPPORT = "support"
    CONTRADICT = "contradict"
    CONTEXT = "context"
    UNKNOWN = "unknown"


class ReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class AccessPolicy(str, Enum):
    OA = "oa"
    AUTHORIZED = "authorized"
    METADATA_ONLY = "metadata_only"
    LOCAL_ONLY = "local_only"


class FleetType(str, Enum):
    DEEP_SPACE_SURVEY = "deep_space_survey"
    EVIDENCE_PATROL = "evidence_patrol"
    ROUTE_DIAGNOSTICS = "route_diagnostics"
    UNCHARTED_SECTOR_EXPLORATION = "uncharted_sector_exploration"
    MISSION_VALIDATION = "mission_validation"


class StationType(str, Enum):
    QUESTION_INTAKE = "question_intake"
    RESEARCH_PLANNING = "research_planning"
    SEARCH_SELECTION = "search_selection"
    EVIDENCE_EXTRACTION = "evidence_extraction"
    CROSS_CHECK_REVIEW = "cross_check_review"
    REPORT_DELIVERY = "report_delivery"


class FacilityType(str, Enum):
    SECTOR_CARTOGRAPHY = "sector_cartography"
    TIMELINE_OBSERVATORY = "timeline_observatory"
    CITATION_ARRAY = "citation_array"
    SOURCE_LOCATOR = "source_locator"
    EVIDENCE_COMPARATOR = "evidence_comparator"
    CONDITION_RECORDER = "condition_recorder"
    TRAJECTORY_OVERLAY = "trajectory_overlay"
    CONDITION_DIFFERENTIAL = "condition_differential"
    COUNTEREVIDENCE_DETECTOR = "counterevidence_detector"
    BLIND_SPOT_SCAN = "blind_spot_scan"
    VARIABLE_COMBINATION_SCAN = "variable_combination_scan"
    HYPOTHESIS_TRIAGE = "hypothesis_triage"
    EXPERIMENT_MISSION_DESIGN = "experiment_mission_design"
    COMPUTATION_MISSION_DESIGN = "computation_mission_design"
    FALSIFICATION_MONITOR = "falsification_monitor"


@dataclass(frozen=True)
class FleetSpec:
    fleet_type: FleetType
    display_name_zh: str
    display_name_en: str
    mission_types: tuple[str, ...]
    required_stations: tuple[StationType, ...]
    required_facilities: tuple[FacilityType, ...]
    handoff_allowed_to: tuple[FleetType, ...]
    release_gate: StationType
    max_planning_loops: int
    max_facility_attempts: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "display_name_zh", _nonempty(self.display_name_zh, "display_name_zh"))
        object.__setattr__(self, "display_name_en", _nonempty(self.display_name_en, "display_name_en"))
        if not self.mission_types or not self.required_stations or not self.required_facilities:
            raise ValueError("FleetSpec requires mission types, stations, and facilities")
        if len(set(self.mission_types)) != len(self.mission_types):
            raise ValueError("FleetSpec mission_types must be unique")
        if len(set(self.required_stations)) != len(self.required_stations):
            raise ValueError("FleetSpec required_stations must be unique")
        if len(set(self.required_facilities)) != len(self.required_facilities):
            raise ValueError("FleetSpec required_facilities must be unique")
        if self.release_gate not in self.required_stations:
            raise ValueError("FleetSpec release_gate must be one of required_stations")
        if self.max_planning_loops < 1 or self.max_facility_attempts < 1:
            raise ValueError("FleetSpec limits must be positive")


@dataclass(frozen=True)
class FleetAssignment:
    mission_id: str
    fleet_type: FleetType
    mission_type: str
    reason: str
    required_stations: tuple[StationType, ...]
    required_facilities: tuple[FacilityType, ...]
    release_gate: StationType
    assignment_id: str = field(default_factory=lambda: new_id("assignment"))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "mission_id", _nonempty(self.mission_id, "mission_id"))
        object.__setattr__(self, "mission_type", _nonempty(self.mission_type, "mission_type"))
        object.__setattr__(self, "reason", _nonempty(self.reason, "reason"))
        if not self.required_stations or not self.required_facilities:
            raise ValueError("FleetAssignment requires stations and facilities")
        if self.release_gate not in self.required_stations:
            raise ValueError("FleetAssignment release_gate must be required")

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)


@dataclass(frozen=True)
class FleetHandoff:
    mission_id: str
    from_fleet: FleetType
    to_fleet: FleetType
    artifact_ids: tuple[str, ...]
    verification_status: ReviewStatus
    reason: str
    handoff_id: str = field(default_factory=lambda: new_id("handoff"))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "mission_id", _nonempty(self.mission_id, "mission_id"))
        object.__setattr__(self, "reason", _nonempty(self.reason, "reason"))
        if self.from_fleet is self.to_fleet:
            raise ValueError("FleetHandoff must target another fleet")
        if not self.artifact_ids or any(not artifact_id.strip() for artifact_id in self.artifact_ids):
            raise ValueError("FleetHandoff requires nonempty artifact_ids")
        if self.verification_status is not ReviewStatus.ACCEPTED:
            raise ValueError("FleetHandoff requires accepted verification")

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)

def _nonempty(value: str, field_name: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    return value


def to_primitive(value: Any) -> Any:
    """Convert dataclasses and enums to JSON-serialisable primitive values."""
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return to_primitive(asdict(value))
    if isinstance(value, dict):
        return {str(key): to_primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_primitive(item) for item in value]
    return value


@dataclass(frozen=True)
class MissionBrief:
    question: str
    material: str
    property_name: str
    scope: str
    source_policy: AccessPolicy = AccessPolicy.AUTHORIZED
    output_request: str = "evidence-backed research report"
    mission_id: str = field(default_factory=lambda: new_id("mission"))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "question", _nonempty(self.question, "question"))
        object.__setattr__(self, "material", _nonempty(self.material, "material"))
        object.__setattr__(self, "property_name", _nonempty(self.property_name, "property_name"))
        object.__setattr__(self, "scope", _nonempty(self.scope, "scope"))

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)


@dataclass(frozen=True)
class FlightPlan:
    mission_id: str
    subquestions: tuple[str, ...]
    queries: tuple[str, ...]
    counter_queries: tuple[str, ...]
    max_rounds: int = 3
    max_papers: int = 20
    artifact_id: str = field(default_factory=lambda: new_id("plan"))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.subquestions or not self.queries:
            raise ValueError("FlightPlan requires at least one subquestion and query")
        if self.max_rounds < 1 or self.max_papers < 1:
            raise ValueError("FlightPlan limits must be positive")

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)


@dataclass(frozen=True)
class Provenance:
    document_id: str
    locator: str
    source: str
    doi: str | None = None
    content_hash: str | None = None
    access_policy: AccessPolicy = AccessPolicy.AUTHORIZED

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", _nonempty(self.document_id, "document_id"))
        object.__setattr__(self, "locator", _nonempty(self.locator, "locator"))
        object.__setattr__(self, "source", _nonempty(self.source, "source"))


@dataclass(frozen=True)
class EvidenceCard:
    claim: str
    stance: Stance
    material: str
    property_name: str
    conditions: dict[str, Any]
    quote: str
    provenance: Provenance
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    extractor_confidence: float | None = None
    evidence_id: str = field(default_factory=lambda: new_id("evidence"))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim", _nonempty(self.claim, "claim"))
        object.__setattr__(self, "material", _nonempty(self.material, "material"))
        object.__setattr__(self, "property_name", _nonempty(self.property_name, "property_name"))
        object.__setattr__(self, "quote", _nonempty(self.quote, "quote"))
        if self.extractor_confidence is not None and not 0 <= self.extractor_confidence <= 1:
            raise ValueError("extractor_confidence must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)


@dataclass(frozen=True)
class PaperCandidate:
    """A retrieval candidate, explicitly not yet an evidence claim."""

    document_id: str
    title: str
    query: str
    source: str
    publication_year: int | None = None
    locator_hint: str | None = None
    score: float | None = None
    is_content_accessible: bool = False
    candidate_id: str = field(default_factory=lambda: new_id("candidate"))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", _nonempty(self.document_id, "document_id"))
        object.__setattr__(self, "title", _nonempty(self.title, "title"))
        object.__setattr__(self, "query", _nonempty(self.query, "query"))
        object.__setattr__(self, "source", _nonempty(self.source, "source"))
        if self.publication_year is not None and not 1000 <= self.publication_year <= 3000:
            raise ValueError("publication_year must be plausible")
        if self.score is not None and not isinstance(self.score, (int, float)):
            raise ValueError("score must be numeric when present")

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)

@dataclass(frozen=True)
class MissionReport:
    """A review-gated evidence manifest, never an unverified scientific claim."""

    mission_id: str
    summary: str
    evidence_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    next_steps: tuple[str, ...]
    report_id: str = field(default_factory=lambda: new_id("report"))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "mission_id", _nonempty(self.mission_id, "mission_id"))
        object.__setattr__(self, "summary", _nonempty(self.summary, "summary"))
        if not self.evidence_ids or len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("MissionReport requires unique evidence_ids")
        if not self.limitations or not self.next_steps:
            raise ValueError("MissionReport requires limitations and next_steps")

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)

@dataclass(frozen=True)
class AuditEvent:
    run_id: str
    event_type: str
    actor: str
    state: MissionState
    payload: dict[str, Any]
    event_id: str = field(default_factory=lambda: new_id("evt"))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _nonempty(self.run_id, "run_id"))
        object.__setattr__(self, "event_type", _nonempty(self.event_type, "event_type"))
        object.__setattr__(self, "actor", _nonempty(self.actor, "actor"))

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)
