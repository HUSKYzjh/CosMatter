"""Artifact-level integrity audit for a review-gated research report.

The audit deliberately verifies identifiers and gate state, not scientific
truth or free-form prose.  It is therefore safe to use as an operational
check before a human reviews the cited locations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .gap_analysis import ResearchGapCandidate
from .models import EvidenceCard, MissionBrief, ReviewStatus
from .verification import VerificationDecision


REPORT_AUDIT_SCHEMA_VERSION = "1.3"
_REPORT_FIELDS = {
    "mission_id", "summary", "evidence_ids", "limitations", "next_steps",
    "research_gap_candidate_ids", "report_id", "created_at",
}


class ReportAuditError(ValueError):
    """Raised when a persisted report cannot prove its review-gated boundary."""


def audit_report_evidence(
    *,
    mission: MissionBrief,
    cards: tuple[EvidenceCard, ...],
    decisions: tuple[VerificationDecision, ...],
    research_gap_candidates: tuple[ResearchGapCandidate, ...],
    report_payload: dict[str, Any],
    structured_report: str,
    material_fact_artifacts: tuple[dict[str, Any], ...] = (),
    material_fact_fusion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify report identifiers against accepted evidence and available Gap cards.

    This does not assess whether a natural-language claim is scientifically
    correct.  Its coverage values concern only machine-readable report IDs and
    the rendered local report's required identifier presence.
    """
    _validate_report_payload(report_payload, mission.mission_id)
    if not isinstance(structured_report, str) or not structured_report.strip():
        raise ReportAuditError("structured report is missing or empty")

    card_ids = {card.evidence_id for card in cards}
    if len(card_ids) != len(cards):
        raise ReportAuditError("evidence cards have duplicate identifiers")
    accepted_ids = {
        decision.evidence_id
        for decision in decisions
        if decision.mission_id == mission.mission_id
        and decision.status is ReviewStatus.ACCEPTED
        and decision.evidence_id in card_ids
    }
    report_evidence_ids = tuple(report_payload["evidence_ids"])
    if not set(report_evidence_ids).issubset(accepted_ids):
        raise ReportAuditError("report contains an evidence ID without an accepted decision")
    if set(report_evidence_ids) != accepted_ids:
        raise ReportAuditError("report does not cover the complete accepted evidence set")

    candidates_by_id = {candidate.gap_id: candidate for candidate in research_gap_candidates}
    if len(candidates_by_id) != len(research_gap_candidates):
        raise ReportAuditError("Research Gap candidates have duplicate identifiers")
    report_gap_ids = tuple(report_payload["research_gap_candidate_ids"])
    if set(report_gap_ids) != set(candidates_by_id):
        raise ReportAuditError("report does not cover the current Research Gap candidate set")
    if any(
        candidate.review_status != "candidate_requires_human_review"
        or not set(candidate.evidence_ids).issubset(accepted_ids)
        for candidate in research_gap_candidates
    ):
        raise ReportAuditError("Research Gap candidates are outside the accepted-evidence review boundary")

    missing_report_evidence = tuple(item for item in report_evidence_ids if item not in structured_report)
    missing_report_gaps = tuple(item for item in report_gap_ids if item not in structured_report)
    if missing_report_evidence or missing_report_gaps:
        raise ReportAuditError("structured report is missing identifiers declared by its manifest")
    accepted_cards_by_id = {card.evidence_id: card for card in cards if card.evidence_id in accepted_ids}
    missing_evidence_locations = tuple(
        evidence_id
        for evidence_id, card in accepted_cards_by_id.items()
        if card.provenance.document_id not in structured_report or card.provenance.locator not in structured_report
    )
    if missing_evidence_locations:
        raise ReportAuditError("structured report is missing accepted evidence document IDs or locators")
    required_sections = (
        "## Evidence register", "## Reviewed structured material facts",
        "## Cross-document comparisons", "## Research Gap candidates", "## Review boundary",
    )
    if any(section not in structured_report for section in required_sections):
        raise ReportAuditError("structured report lacks required evidence or review sections")

    fact_references = _reviewed_fact_references(material_fact_artifacts)
    missing_facts = tuple(
        f"{document_id}/{fact_id}" for document_id, fact_id, locator in fact_references
        if fact_id not in structured_report or locator not in structured_report
    )
    if missing_facts:
        raise ReportAuditError("structured report is missing reviewed material-fact identifiers or locators")
    comparison_references = _comparison_observation_references(material_fact_fusion)
    missing_comparisons = tuple(
        comparison_id for comparison_id, _, _, _ in comparison_references
        if comparison_id not in structured_report
    )
    missing_observations = tuple(
        f"{document_id}/{fact_id}" for _, document_id, fact_id, locator in comparison_references
        if fact_id not in structured_report or locator not in structured_report
    )
    if missing_comparisons or missing_observations:
        raise ReportAuditError("structured report is missing comparison identifiers or observation references")

    counterevidence_boundaries = _executed_gap_counterevidence_boundaries(research_gap_candidates)
    missing_counterevidence_boundaries = tuple(
        gap_id for gap_id, status, history in counterevidence_boundaries
        if status not in structured_report or history not in structured_report
    )
    if missing_counterevidence_boundaries:
        raise ReportAuditError("structured report is missing executed Research Gap counterevidence boundaries")

    total_gap_evidence = sum(len(candidate.evidence_ids) for candidate in research_gap_candidates)
    return {
        "schema_version": REPORT_AUDIT_SCHEMA_VERSION,
        "mission_id": mission.mission_id,
        "report_id": report_payload["report_id"],
        "trust_status": "artifact_level_identifier_audit_not_scientific_validity_assessment",
        "accepted_evidence_count": len(accepted_ids),
        "manifest_evidence_count": len(report_evidence_ids),
        "accepted_evidence_manifest_coverage": 1.0,
        "research_gap_candidate_count": len(report_gap_ids),
        "gap_evidence_reference_count": total_gap_evidence,
        "gap_evidence_accepted_coverage": 1.0,
        "structured_report_identifier_coverage": 1.0,
        "accepted_evidence_locator_rendered_coverage": 1.0,
        "reviewed_material_fact_count": len(fact_references),
        "reviewed_material_fact_rendered_coverage": 1.0,
        "cross_document_comparison_count": len({item[0] for item in comparison_references}),
        "comparison_observation_reference_count": len(comparison_references),
        "comparison_observation_rendered_coverage": 1.0,
        "executed_gap_counterevidence_boundary_count": len(counterevidence_boundaries),
        "gap_counterevidence_boundary_rendered_coverage": 1.0,
        "human_source_locator_review_required": True,
    }


def write_report_evidence_audit(run_dir: Path, result: dict[str, Any]) -> Path:
    required = {
        "schema_version", "mission_id", "report_id", "trust_status",
        "accepted_evidence_count", "manifest_evidence_count",
        "accepted_evidence_manifest_coverage", "research_gap_candidate_count",
        "gap_evidence_reference_count", "gap_evidence_accepted_coverage",
        "structured_report_identifier_coverage", "accepted_evidence_locator_rendered_coverage", "reviewed_material_fact_count",
        "reviewed_material_fact_rendered_coverage", "cross_document_comparison_count",
        "comparison_observation_reference_count", "comparison_observation_rendered_coverage",
        "executed_gap_counterevidence_boundary_count", "gap_counterevidence_boundary_rendered_coverage",
        "human_source_locator_review_required",
    }
    if not isinstance(result, dict) or set(result) != required:
        raise ReportAuditError("report evidence audit result has an invalid schema")
    path = run_dir / "report_evidence_audit.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _validate_report_payload(payload: object, mission_id: str) -> None:
    if not isinstance(payload, dict) or set(payload) != _REPORT_FIELDS:
        raise ReportAuditError("mission report artifact has an invalid schema")
    if payload.get("mission_id") != mission_id:
        raise ReportAuditError("mission report belongs to a different mission")
    for field in ("report_id", "summary", "created_at"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise ReportAuditError("mission report has invalid identity fields")
    for field in ("evidence_ids", "research_gap_candidate_ids"):
        value = payload.get(field)
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value) or len(value) != len(set(value)):
            raise ReportAuditError(f"mission report has invalid {field}")
    for field in ("limitations", "next_steps"):
        value = payload.get(field)
        if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item.strip() for item in value):
            raise ReportAuditError(f"mission report has invalid {field}")


def _executed_gap_counterevidence_boundaries(
    candidates: tuple[ResearchGapCandidate, ...],
) -> tuple[tuple[str, str, str], ...]:
    """Return report-safe proof references for each persisted Gap candidate.

    A report audit must not bless a Gap whose approved counterevidence searches
    were merely planned. The history digest contains query/document-id structure
    only, never prompts, snippets, or private source text.
    """
    expected_status = "all_approved_counterevidence_queries_recorded"
    references: list[tuple[str, str, str]] = []
    for candidate in candidates:
        boundary = candidate.counterevidence_boundary
        if (
            boundary is None
            or boundary.status != expected_status
            or boundary.approved_query_count < 1
            or boundary.executed_query_count != boundary.approved_query_count
            or not boundary.candidate_history_sha256
        ):
            raise ReportAuditError("Research Gap candidate lacks an executed counterevidence boundary")
        references.append((candidate.gap_id, boundary.status, boundary.candidate_history_sha256))
    return tuple(references)


def _reviewed_fact_references(
    artifacts: tuple[dict[str, Any], ...],
) -> tuple[tuple[str, str, str], ...]:
    references: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for artifact in artifacts:
        document_id, facts = artifact.get("document_id"), artifact.get("facts")
        if not isinstance(document_id, str) or not isinstance(facts, list):
            raise ReportAuditError("reviewed material-fact artifact is invalid")
        for fact in facts:
            if not isinstance(fact, dict):
                raise ReportAuditError("reviewed material fact is invalid")
            fact_id, locator = fact.get("fact_id"), fact.get("locator")
            if not isinstance(fact_id, str) or not isinstance(locator, str) or not fact_id or not locator:
                raise ReportAuditError("reviewed material fact lacks an identifier or locator")
            key = (document_id, fact_id)
            if key in seen:
                raise ReportAuditError("reviewed material facts contain duplicate document/fact identifiers")
            seen.add(key)
            references.append((document_id, fact_id, locator))
    return tuple(references)


def _comparison_observation_references(
    fusion: dict[str, Any] | None,
) -> tuple[tuple[str, str, str, str], ...]:
    if fusion is None:
        return ()
    comparisons = fusion.get("comparisons") if isinstance(fusion, dict) else None
    if not isinstance(comparisons, list):
        raise ReportAuditError("material-fact fusion artifact is invalid")
    references: list[tuple[str, str, str, str]] = []
    comparison_ids: set[str] = set()
    for comparison in comparisons:
        if not isinstance(comparison, dict):
            raise ReportAuditError("material-fact comparison is invalid")
        comparison_id, observations = comparison.get("comparison_id"), comparison.get("observations")
        if not isinstance(comparison_id, str) or not comparison_id or comparison_id in comparison_ids or not isinstance(observations, list):
            raise ReportAuditError("material-fact comparison identity or observations are invalid")
        comparison_ids.add(comparison_id)
        for observation in observations:
            if not isinstance(observation, dict):
                raise ReportAuditError("material-fact comparison observation is invalid")
            document_id, fact_id, locator = observation.get("document_id"), observation.get("fact_id"), observation.get("locator")
            if not all(isinstance(item, str) and item for item in (document_id, fact_id, locator)):
                raise ReportAuditError("material-fact comparison observation lacks a reference")
            references.append((comparison_id, document_id, fact_id, locator))
    return tuple(references)
