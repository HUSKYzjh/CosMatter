"""Immutable verification decisions used by release gates and UI projections."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import ReviewStatus, new_id, utc_now


@dataclass(frozen=True)
class VerificationDecision:
    mission_id: str
    evidence_id: str
    status: ReviewStatus
    reason: str
    missing_conditions: tuple[str, ...] = ()
    decision_id: str = field(default_factory=lambda: new_id("verification"))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.mission_id.strip() or not self.evidence_id.strip() or not self.reason.strip():
            raise ValueError("VerificationDecision requires mission_id, evidence_id, and reason")
        if self.status is ReviewStatus.ACCEPTED and self.missing_conditions:
            raise ValueError("accepted verification cannot retain missing conditions")

    def to_dict(self) -> dict[str, object]:
        return {"decision_id": self.decision_id, "mission_id": self.mission_id, "evidence_id": self.evidence_id, "status": self.status.value, "reason": self.reason, "missing_conditions": list(self.missing_conditions), "created_at": self.created_at}
