"""Mission routing for the interstellar-fleet runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .config import AGENT_ROOT
from .fleet_config import load_fleet_specs
from .models import FleetAssignment, FleetHandoff, FleetSpec, FleetType, MissionBrief, ReviewStatus


class DispatchError(ValueError):
    """Raised when no safe fleet assignment or handoff can be created."""


_MISSION_SIGNALS: Mapping[str, tuple[str, ...]] = {
    "literature_discrepancy": ("矛盾", "分歧", "不同结论", "conflict", "discrepancy", "contradict"),
    "conditional_comparison": ("条件差异", "条件比较", "为什么不同", "condition comparison"),
    "claim_verification": ("哪篇", "原文", "支持这个说法", "evidence", "verify", "support this claim"),
    "literature_mapping": ("综述", "研究到哪里", "研究现状", "landscape", "overview", "map the literature"),
    "research_gap": ("空白", "缺口", "下一步", "gap", "unexplored", "research direction"),
    "validation_design": ("如何验证", "实验设计", "计算设计", "validation", "experimental design", "verify this hypothesis"),
}


@dataclass(frozen=True)
class MissionDispatcher:
    """Select one configured primary fleet and enforce handoff gates."""

    specs: Mapping[FleetType, FleetSpec]

    @classmethod
    def from_project(cls, config_dir: Path | None = None) -> "MissionDispatcher":
        return cls(load_fleet_specs(config_dir or AGENT_ROOT / "configs" / "fleets"))

    def assign(self, brief: MissionBrief, mission_type: str | None = None) -> FleetAssignment:
        selected_type, reason = self._select_mission_type(brief, mission_type)
        matches = [spec for spec in self.specs.values() if selected_type in spec.mission_types]
        if len(matches) != 1:
            raise DispatchError(f"mission type {selected_type!r} must map to exactly one fleet; found {len(matches)}")
        spec = matches[0]
        return FleetAssignment(
            mission_id=brief.mission_id,
            fleet_type=spec.fleet_type,
            mission_type=selected_type,
            reason=reason,
            required_stations=spec.required_stations,
            required_facilities=spec.required_facilities,
            release_gate=spec.release_gate,
        )

    def handoff(
        self,
        assignment: FleetAssignment,
        target: FleetType,
        artifact_ids: tuple[str, ...],
        verification_status: ReviewStatus,
        reason: str,
    ) -> FleetHandoff:
        source = self.specs[assignment.fleet_type]
        if target not in source.handoff_allowed_to:
            raise DispatchError(f"{source.fleet_type.value} is not allowed to hand off to {target.value}")
        if verification_status is not ReviewStatus.ACCEPTED:
            raise DispatchError("cross-fleet handoff requires accepted verification")
        return FleetHandoff(
            mission_id=assignment.mission_id,
            from_fleet=assignment.fleet_type,
            to_fleet=target,
            artifact_ids=artifact_ids,
            verification_status=verification_status,
            reason=reason,
        )

    def _select_mission_type(self, brief: MissionBrief, explicit: str | None) -> tuple[str, str]:
        available = {mission_type for spec in self.specs.values() for mission_type in spec.mission_types}
        if explicit is not None:
            if explicit not in available:
                raise DispatchError(f"unsupported mission type {explicit!r}")
            return explicit, "explicit mission type requested by user"
        text_parts = [brief.question]
        if brief.output_request != "evidence-backed research report":
            text_parts.append(brief.output_request)
        text = " ".join(text_parts).lower()
        candidates: list[tuple[int, str, tuple[str, ...]]] = []
        for mission_type, signals in _MISSION_SIGNALS.items():
            matched = tuple(signal for signal in signals if signal.lower() in text)
            if matched and mission_type in available:
                candidates.append((len(matched), mission_type, matched))
        if candidates:
            _, mission_type, matched = max(candidates, key=lambda item: (item[0], item[1]))
            return mission_type, f"matched task signals: {', '.join(matched)}"
        if "literature_mapping" not in available:
            raise DispatchError("no default literature_mapping fleet is configured")
        return "literature_mapping", "no specialised task signal found; default to literature mapping"
