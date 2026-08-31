"""Human-review requests for graph artifacts; never an evidence decision API."""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import new_id, utc_now


@dataclass(frozen=True)
class GraphReviewRequest:
    mission_id: str
    graph_id: str
    node_ids: tuple[str, ...]
    rationale: str
    request_id: str = field(default_factory=lambda: new_id("graph_review"))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.mission_id.strip() or not self.graph_id.startswith("graph:"):
            raise ValueError("graph review request identifiers are invalid")
        if not self.node_ids or len(set(self.node_ids)) != len(self.node_ids) or any(not item.strip() for item in self.node_ids):
            raise ValueError("graph review request requires unique node identifiers")
        if not self.rationale.strip() or len(self.rationale) > 1000:
            raise ValueError("graph review rationale is invalid")

    def to_dict(self) -> dict[str, object]:
        return {"request_id": self.request_id, "mission_id": self.mission_id, "graph_id": self.graph_id, "node_ids": list(self.node_ids), "rationale": self.rationale, "status": "pending_human_review_not_evidence_acceptance", "created_at": self.created_at}
