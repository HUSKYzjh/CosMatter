"""Review-gated, evidence-manifest reporting work products."""

from __future__ import annotations

import json
from pathlib import Path

from .gap_analysis import ResearchGapCandidate
from .models import EvidenceCard, MissionBrief, MissionReport, ReviewStatus
from .verification import VerificationDecision


class ReportGateError(ValueError):
    """Raised when a report would contain unreviewed or rejected evidence."""


def build_evidence_manifest(
    mission: MissionBrief,
    cards: tuple[EvidenceCard, ...],
    decisions: tuple[VerificationDecision, ...],
    research_gap_candidates: tuple[ResearchGapCandidate, ...] = (),
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
    accepted_id_set = set(accepted_ids)
    if any(
        candidate.review_status != "candidate_requires_human_review"
        or candidate.material != mission.material
        or candidate.property_name != mission.property_name
        or not set(candidate.evidence_ids).issubset(accepted_id_set)
        for candidate in research_gap_candidates
    ):
        raise ReportGateError("report gap candidates must match this mission, require human review, and cite accepted evidence")
    gap_ids = tuple(candidate.gap_id for candidate in research_gap_candidates)
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
            "Research Gap candidates are proposals for human review, not validated findings.",
        ),
        next_steps=(
            "Inspect each evidence card together with its source locator and conditions.",
            "Use the route-diagnostics facilities before making a cross-condition conclusion.",
            "Review each Research Gap candidate against a bounded counterevidence search before approving a follow-up mission.",
        ),
        research_gap_candidate_ids=gap_ids,
    )


def write_mission_report(run_dir: Path, report: MissionReport) -> Path:
    """Write a small, browser-safe report artifact without quotes or full text."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "mission_report.json"
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_structured_research_report(
    mission: MissionBrief,
    cards: tuple[EvidenceCard, ...],
    decisions: tuple[VerificationDecision, ...],
    research_gap_candidates: tuple[ResearchGapCandidate, ...] = (),
    material_fact_artifacts: tuple[dict[str, object], ...] = (),
    material_fact_fusion: dict[str, object] | None = None,
) -> str:
    """Render a local, review-gated report with evidence identifiers and locators.

    The renderer deliberately reports bounded observations and review status; it
    does not compose a free-form material-science conclusion.
    """
    manifest = build_evidence_manifest(mission, cards, decisions, research_gap_candidates)
    accepted = {item.evidence_id for item in cards if item.evidence_id in set(manifest.evidence_ids)}
    fact_references = _material_fact_reference_index(material_fact_artifacts)
    lines = [
        f"# CosMatter evidence-backed research report: {mission.material}", "",
        "## Mission boundary", "",
        f"- Research question: {mission.question}",
        f"- Property and scope: {mission.property_name} / {mission.scope}",
        f"- Accepted evidence cards: {len(manifest.evidence_ids)}",
        f"- Research Gap candidates requiring human review: {len(research_gap_candidates)}", "",
        "## Evidence register (reviewed literature facts)", "",
        "Only these accepted EvidenceCards are literature-fact records in this report. They are not merged into a scientific conclusion.", "",
        "| Evidence ID | Document ID | Locator | Stance | Claim | Recorded conditions |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for card in cards:
        if card.evidence_id not in accepted:
            continue
        conditions = "; ".join(f"{key}={value}" for key, value in sorted(card.conditions.items())) or "not recorded"
        lines.append(f"| {card.evidence_id} | {card.provenance.document_id} | {card.provenance.locator} | {card.stance.value} | {_cell(card.claim)} | {_cell(conditions)} |")
    lines += ["", "## Reviewed structured material facts (source-map observations)", ""]
    if not material_fact_artifacts:
        lines.append("No reviewed material-fact artifact is available for this run.")
    else:
        lines += ["| Document ID | Fact ID | Source segment | Category | Field | Reported value | Normalized value | Locator |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for artifact in material_fact_artifacts:
            document_id = str(artifact.get("document_id", "unknown"))
            for fact in artifact.get("facts", []):
                if not isinstance(fact, dict):
                    continue
                reported = _value_unit(fact.get("value"), fact.get("unit"))
                normalized = _value_unit(fact.get("normalized_value"), fact.get("normalized_unit"))
                lines.append(f"| {document_id} | {fact.get('fact_id', '')} | {fact.get('segment_id', '')} | {fact.get('category', '')} | {_cell(str(fact.get('name', '')))} | {_cell(reported)} | {_cell(normalized)} | {fact.get('locator', '')} |")
    lines += ["", "## Cross-document comparisons (not scientific conclusions)", ""]
    comparisons = material_fact_fusion.get("comparisons", []) if isinstance(material_fact_fusion, dict) else []
    if not comparisons:
        lines.append("No cross-document material-fact comparison is available.")
    else:
        comparison_ids: set[str] = set()
        for item in comparisons:
            if not isinstance(item, dict):
                raise ReportGateError("material-fact comparison must be an object")
            comparison_id = item.get("comparison_id")
            if not isinstance(comparison_id, str) or not comparison_id or comparison_id in comparison_ids:
                raise ReportGateError("material-fact comparison identifiers must be unique nonempty strings")
            comparison_ids.add(comparison_id)
            differing = item.get("differing_qualifier_fields", [])
            observations = item.get("observations", [])
            if not isinstance(differing, list) or not all(isinstance(value, str) for value in differing) or not isinstance(observations, list) or not observations:
                raise ReportGateError("material-fact comparison is missing a bounded observation set")
            lines += [
                f"### {comparison_id}", "",
                f"- Field: {item.get('category', '')} / {_cell(str(item.get('name', '')))} / {item.get('normalized_unit') or 'not specified'}",
                f"- Comparison status: {item.get('comparison_status', '')}",
                f"- Differing recorded qualifier fields: {', '.join(differing) or 'none recorded'}",
                "- Source-map fact references:",
            ]
            for observation in observations:
                lines.append(f"  - {_comparison_observation_reference(observation, fact_references)}")
            lines += ["- Interpretation boundary: this is a condition-aware grouping of reviewed facts; a human must review the listed locations before treating it as an explanation.", ""]
    lines += ["", "## Research Gap candidates (not findings)", ""]
    if not research_gap_candidates:
        lines.append("No evidence-bound Research Gap candidate has been generated.")
    else:
        for candidate in research_gap_candidates:
            lines += [
                f"### {candidate.gap_id}", "",
                f"- Status: {candidate.review_status}",
                f"- Evidence cards: {', '.join(candidate.evidence_ids)}",
                f"- Problem: {candidate.problem_description}",
                f"- Conflict or missing evidence: {', '.join(candidate.conflict_or_missing_evidence)}",
                f"- Novelty boundary: {candidate.novelty_status}",
                f"- Counterevidence boundary: {_counterevidence_boundary_text(candidate)}",
                f"- Actionability: {candidate.actionability}",
                f"- Falsifiable hypothesis: {candidate.falsifiable_hypothesis}",
                f"- Suggested validation: {'; '.join(candidate.suggested_validation)}",
                f"- Evidence completeness: {candidate.evidence_completeness:.2f}", "",
            ]
    lines += ["## Review boundary", "", "This report is a traceable work product, not an autonomous scientific conclusion. Claims, structured facts, comparisons, and Research Gap candidates must be checked against their listed locators, conditions, and review status before use.", ""]
    return "\n".join(lines)


def _counterevidence_boundary_text(candidate: ResearchGapCandidate) -> str:
    boundary = candidate.counterevidence_boundary
    if boundary is None:
        return "not recorded"
    history = boundary.candidate_history_sha256 or "not recorded"
    return (
        f"{boundary.status}; approved/executed queries "
        f"{boundary.approved_query_count}/{boundary.executed_query_count}; "
        f"history sha256={history}"
    )


def write_structured_research_report(run_dir: Path, content: str) -> Path:
    if not isinstance(content, str) or not content.strip():
        raise ReportGateError("structured research report content is required")
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "research_report.md"
    path.write_text(content, encoding="utf-8")
    return path


def _value_unit(value: object, unit: object) -> str:
    return f"{value if value is not None else 'not reported'}{f' {unit}' if isinstance(unit, str) else ''}"


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def _material_fact_reference_index(
    artifacts: tuple[dict[str, object], ...],
) -> dict[tuple[str, str], dict[str, object]]:
    """Index reviewed fact IDs so comparisons cannot lose their source locators."""
    result: dict[tuple[str, str], dict[str, object]] = {}
    for artifact in artifacts:
        document_id = artifact.get("document_id")
        facts = artifact.get("facts")
        if not isinstance(document_id, str) or not document_id or not isinstance(facts, list):
            raise ReportGateError("material-fact report artifact is invalid")
        for fact in facts:
            if not isinstance(fact, dict):
                raise ReportGateError("material-fact report entry is invalid")
            fact_id = fact.get("fact_id")
            locator = fact.get("locator")
            if not isinstance(fact_id, str) or not fact_id or not isinstance(locator, str) or not locator:
                raise ReportGateError("material-fact report entry lacks an identifier or locator")
            key = (document_id, fact_id)
            if key in result:
                raise ReportGateError("material-fact report identifiers must be unique per document")
            result[key] = fact
    return result


def _comparison_observation_reference(
    observation: object,
    fact_references: dict[tuple[str, str], dict[str, object]],
) -> str:
    if not isinstance(observation, dict):
        raise ReportGateError("material-fact comparison observation must be an object")
    document_id, fact_id, locator = observation.get("document_id"), observation.get("fact_id"), observation.get("locator")
    if not isinstance(document_id, str) or not isinstance(fact_id, str) or not isinstance(locator, str):
        raise ReportGateError("material-fact comparison observation lacks a document, fact, or locator")
    fact = fact_references.get((document_id, fact_id))
    if fact is None or fact.get("locator") != locator:
        raise ReportGateError("material-fact comparison observation is not linked to a reviewed source-map fact")
    reported = _value_unit(observation.get("value"), fact.get("normalized_unit") or fact.get("unit"))
    qualifiers = observation.get("qualifiers")
    if not isinstance(qualifiers, dict):
        raise ReportGateError("material-fact comparison observation qualifiers are invalid")
    condition_text = "; ".join(f"{key}={value}" for key, value in sorted(qualifiers.items())) or "no qualifier recorded"
    return f"{document_id} / {fact_id} / {locator}: {_cell(reported)}; conditions: {_cell(condition_text)}"
