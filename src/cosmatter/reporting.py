"""Review-gated, evidence-manifest reporting work products."""

from __future__ import annotations

import json
from pathlib import Path

from .models import EvidenceCard, MissionBrief, MissionReport, ReviewStatus
from .verification import VerificationDecision


class ReportGateError(ValueError):
    """Raised when a report would contain unreviewed or rejected evidence."""


def build_evidence_manifest(
    mission: MissionBrief,
    cards: tuple[EvidenceCard, ...],
    decisions: tuple[VerificationDecision, ...],
) -> MissionReport:
    """Create a scoped manifest from accepted cards without inferring science."""
    decisions_by_evidence: dict[str, VerificationDecision] = {}
    for decision in decisions:
        if decision.mission_id != mission.mission_id:
            continue
        if decision.evidence_id in decisions_by_evidence:
            raise ReportGateError("multiple verification decisions for one evidence card")
        decisions_by_evidence[decision.evidence_id] = decision
    accepted_ids = tuple(
        card.evidence_id
        for card in cards
        if decisions_by_evidence.get(card.evidence_id, None) is not None
        and decisions_by_evidence[card.evidence_id].status is ReviewStatus.ACCEPTED
    )
    if not accepted_ids:
        raise ReportGateError("report delivery requires at least one accepted evidence card")
    return MissionReport(
        mission_id=mission.mission_id,
        summary=(
            f"Evidence manifest for {mission.material} / {mission.property_name}: "
            f"{len(accepted_ids)} reviewed evidence card(s) are available. "
            "This manifest does not by itself establish a scientific conclusion."
        ),
        evidence_ids=accepted_ids,
        limitations=(
            "Only evidence cards with accepted verification decisions are included.",
            "Condition differences and unresolved alternatives require separate review.",
        ),
        next_steps=(
            "Inspect each evidence card together with its source locator and conditions.",
            "Use the route-diagnostics facilities before making a cross-condition conclusion.",
        ),
    )


def write_mission_report(run_dir: Path, report: MissionReport) -> Path:
    """Write a small, browser-safe report artifact without quotes or full text."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "mission_report.json"
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
