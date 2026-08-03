"""Deterministic execution gates for the shared fleet-station sequence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .dispatch import MissionDispatcher
from .models import FleetAssignment, ReviewStatus, StationType


class StationRunStatus(str, Enum):
    WAITING = "waiting"
    ACTIVE = "active"
    COMPLETE = "complete"
    RETURNED = "returned"


class StationGateError(ValueError):
    """Raised when a station attempts to skip sequence or release gates."""


@dataclass
class StationRun:
    """One auditable traversal of an assignment's configured station sequence."""

    assignment: FleetAssignment
    statuses: dict[StationType, StationRunStatus] = field(init=False)
    artifact_ids: dict[StationType, tuple[str, ...]] = field(default_factory=dict)
    planning_loops: int = 0
    max_planning_loops: int = field(init=False)
    return_reason: str | None = None

    def __post_init__(self) -> None:
        self.statuses = {station: StationRunStatus.WAITING for station in self.assignment.required_stations}
        self.statuses[self.assignment.required_stations[0]] = StationRunStatus.ACTIVE
        self.max_planning_loops = MissionDispatcher.from_project().specs[self.assignment.fleet_type].max_planning_loops

    @property
    def active_station(self) -> StationType:
        active = [station for station, status in self.statuses.items() if status is StationRunStatus.ACTIVE]
        if len(active) != 1:
            raise StationGateError("exactly one station must be active")
        return active[0]

    def complete(
        self,
        station: StationType,
        artifact_ids: tuple[str, ...],
        verification_status: ReviewStatus | None = None,
    ) -> StationType | None:
        if station is not self.active_station:
            raise StationGateError(f"cannot complete {station.value}; {self.active_station.value} is active")
        if not artifact_ids or any(not artifact_id.strip() for artifact_id in artifact_ids):
            raise StationGateError("station completion requires nonempty artifact IDs")
        if station is self.assignment.release_gate and verification_status is not ReviewStatus.ACCEPTED:
            raise StationGateError("release gate requires accepted verification before report delivery")
        self.statuses[station] = StationRunStatus.COMPLETE
        self.artifact_ids[station] = artifact_ids
        index = self.assignment.required_stations.index(station)
        if index + 1 == len(self.assignment.required_stations):
            return None
        next_station = self.assignment.required_stations[index + 1]
        self.statuses[next_station] = StationRunStatus.ACTIVE
        return next_station

    def return_to_planning(self, reason: str) -> StationType:
        if self.active_station is not self.assignment.release_gate:
            raise StationGateError("only the release gate may return a mission to planning")
        if not reason.strip():
            raise StationGateError("return-to-planning requires a reason")
        self.planning_loops += 1
        if self.planning_loops > self.max_planning_loops:
            raise StationGateError("planning-loop limit exceeded; require human review")
        planning = StationType.RESEARCH_PLANNING
        if planning not in self.statuses:
            raise StationGateError("configured fleet has no research planning station")
        self.statuses[self.active_station] = StationRunStatus.RETURNED
        for station in self.assignment.required_stations[self.assignment.required_stations.index(planning) :]:
            self.statuses[station] = StationRunStatus.WAITING
            self.artifact_ids.pop(station, None)
        self.statuses[planning] = StationRunStatus.ACTIVE
        self.return_reason = reason.strip()
        return planning
