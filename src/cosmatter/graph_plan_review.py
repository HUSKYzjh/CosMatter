"""Human acknowledgement records for graph-plan drafts; never execution grants."""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import new_id, utc_now


@dataclass(frozen=True)
class GraphPlanApproval:
    mission_id: str
    graph_id: str
    plan_id: str
    reviewer: str
    rationale: str
    approval_id: str = field(default_factory=lambda: new_id("graph_plan_approval"))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.mission_id.strip() or not self.graph_id.startswith("graph:"):
            raise ValueError("graph plan approval identifiers are invalid")
        if not self.plan_id.startswith(("graph_plan_", "graph_model_plan_")):
            raise ValueError("graph plan approval plan identifier is invalid")
        if not self.reviewer.strip() or len(self.reviewer.strip()) > 200:
            raise ValueError("graph plan approval reviewer is invalid")
        if not self.rationale.strip() or len(self.rationale.strip()) > 1_000:
            raise ValueError("graph plan approval rationale is invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "approval_id": self.approval_id,
            "mission_id": self.mission_id,
            "graph_id": self.graph_id,
            "plan_id": self.plan_id,
            "reviewer": self.reviewer.strip(),
            "rationale": self.rationale.strip(),
            "status": "human_approved_graph_plan_follow_up_not_execution_or_evidence_acceptance",
            "created_at": self.created_at,
        }
