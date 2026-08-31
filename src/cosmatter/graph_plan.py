"""Bounded graph-plan drafts that cannot execute or accept evidence."""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import new_id, utc_now

@dataclass(frozen=True)
class GraphPlanDraft:
    """A local planning artifact, deliberately separate from graph mutation."""

    mission_id: str
    graph_id: str
    node_ids: tuple[str, ...]
    intent: str
    plan_id: str = field(default_factory=lambda: new_id("graph_plan"))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.mission_id.strip() or not self.graph_id.startswith("graph:"):
            raise ValueError("graph plan identifiers are invalid")
        if not self.node_ids or len(self.node_ids) > 25 or len(set(self.node_ids)) != len(self.node_ids):
            raise ValueError("graph plan requires 1 to 25 unique node identifiers")
        if any(not node_id.strip() for node_id in self.node_ids):
            raise ValueError("graph plan node identifiers are invalid")
        if not self.intent.strip() or len(self.intent.strip()) > 500:
            raise ValueError("graph plan intent is invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "mission_id": self.mission_id,
            "graph_id": self.graph_id,
            "node_ids": list(self.node_ids),
            "intent": self.intent.strip(),
            "proposed_action": "request_human_to_review_or_project_graph",
            "trust_status": "untrusted_graph_plan_draft_not_execution_or_evidence_acceptance",
            "created_at": self.created_at,
        }
