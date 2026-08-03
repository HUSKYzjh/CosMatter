"""Explicit mission-state transitions for the navigation workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .models import MissionState


ALLOWED_TRANSITIONS: Final[dict[MissionState, frozenset[MissionState]]] = {
    MissionState.INTAKE: frozenset({MissionState.NEED_SCOPE, MissionState.PLAN, MissionState.FAILED}),
    MissionState.NEED_SCOPE: frozenset({MissionState.INTAKE, MissionState.FAILED}),
    MissionState.PLAN: frozenset({MissionState.RETRIEVE, MissionState.FAILED}),
    MissionState.RETRIEVE: frozenset({MissionState.SELECT, MissionState.FAILED}),
    MissionState.SELECT: frozenset({MissionState.EXTRACT, MissionState.PLAN, MissionState.FAILED}),
    MissionState.EXTRACT: frozenset({MissionState.MAP, MissionState.FAILED}),
    MissionState.MAP: frozenset({MissionState.HAZARD_SCAN, MissionState.FAILED}),
    MissionState.HAZARD_SCAN: frozenset({MissionState.VERIFY, MissionState.FAILED}),
    MissionState.VERIFY: frozenset({MissionState.PLAN, MissionState.HUMAN_REVIEW, MissionState.REPORT, MissionState.FAILED}),
    MissionState.HUMAN_REVIEW: frozenset({MissionState.PLAN, MissionState.REPORT, MissionState.FAILED}),
    MissionState.REPORT: frozenset({MissionState.COMPLETE, MissionState.FAILED}),
    MissionState.COMPLETE: frozenset(),
    MissionState.FAILED: frozenset(),
}


class InvalidTransitionError(ValueError):
    """Raised when an actor attempts to bypass the research workflow."""


@dataclass
class MissionMachine:
    state: MissionState = MissionState.INTAKE
    round_count: int = 0
    max_rounds: int = 3

    def transition(self, target: MissionState) -> MissionState:
        if target not in ALLOWED_TRANSITIONS[self.state]:
            raise InvalidTransitionError(f"cannot transition from {self.state.value} to {target.value}")
        if target is MissionState.PLAN and self.state in {MissionState.SELECT, MissionState.VERIFY, MissionState.HUMAN_REVIEW}:
            self.round_count += 1
            if self.round_count > self.max_rounds:
                raise InvalidTransitionError("maximum planning rounds exceeded; require human review or stop")
        self.state = target
        return self.state
