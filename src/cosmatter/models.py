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
