"""Evidence-bound Research Gap candidates, never free-form scientific claims."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .counterevidence import CounterevidenceExecution
from .facilities import DiscrepancyMatrix
from .models import EvidenceCard, ReviewStatus
from .verification import VerificationDecision


class GapAnalysisError(ValueError):
    pass


@dataclass(frozen=True)
class CounterevidenceBoundary:
    status: str
    approved_query_count: int
    executed_query_count: int
    query_sha256: tuple[str, ...]
    candidate_history_sha256: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "approved_query_count": self.approved_query_count,
            "executed_query_count": self.executed_query_count,
            "query_sha256": list(self.query_sha256),
            "candidate_history_sha256": self.candidate_history_sha256,
        }


@dataclass(frozen=True)
class ResearchGapCandidate:
    gap_id: str
    material: str
    property_name: str
    problem_description: str
    evidence_ids: tuple[str, ...]
    conflict_or_missing_evidence: tuple[str, ...]
    novelty_status: str
    actionability: str
    falsifiable_hypothesis: str
    suggested_validation: tuple[str, ...]
    evidence_completeness: float
    review_status: str = "candidate_requires_human_review"
    counterevidence_boundary: CounterevidenceBoundary | None = None

    def to_dict(self) -> dict[str, object]:
        boundary = self.counterevidence_boundary or CounterevidenceBoundary(
            "not_attested", 0, 0, (), None
        )
        return {
            "schema_version": "1.1",
            "gap_id": self.gap_id,
            "material": self.material,
            "property_name": self.property_name,
            "problem_description": self.problem_description,
            "evidence_ids": list(self.evidence_ids),
            "conflict_or_missing_evidence": list(self.conflict_or_missing_evidence),
            "novelty_status": self.novelty_status,
            "actionability": self.actionability,
            "falsifiable_hypothesis": self.falsifiable_hypothesis,
            "suggested_validation": list(self.suggested_validation),
            "evidence_completeness": self.evidence_completeness,
            "review_status": self.review_status,
            "counterevidence_boundary": boundary.to_dict(),
        }


_REQUIRED_GAP_FIELDS_V10 = {
    "schema_version", "gap_id", "material", "property_name", "problem_description",
    "evidence_ids", "conflict_or_missing_evidence", "novelty_status", "actionability",
    "falsifiable_hypothesis", "suggested_validation", "evidence_completeness", "review_status",
}
_REQUIRED_GAP_FIELDS_V11 = _REQUIRED_GAP_FIELDS_V10 | {"counterevidence_boundary"}
_BOUNDARY_FIELDS = {
    "status", "approved_query_count", "executed_query_count", "query_sha256", "candidate_history_sha256",
}
_EXECUTED_BOUNDARY_STATUS = "all_approved_counterevidence_queries_recorded"


def load_gap_candidates(path: Path) -> tuple[ResearchGapCandidate, ...]:
    """Load only bounded, evidence-linked candidates from an on-disk artifact."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GapAnalysisError("research gap candidate artifact is unreadable") from error
    if not isinstance(payload, list):
        raise GapAnalysisError("research gap candidate artifact must be an array")
    candidates: list[ResearchGapCandidate] = []
    for item in payload:
        if not isinstance(item, dict):
            raise GapAnalysisError("research gap candidate has an invalid schema")
        version = item.get("schema_version")
        expected = _REQUIRED_GAP_FIELDS_V10 if version == "1.0" else _REQUIRED_GAP_FIELDS_V11
        if set(item) != expected or version not in {"1.0", "1.1"} or item.get("review_status") != "candidate_requires_human_review":
            raise GapAnalysisError("research gap candidate has an invalid review boundary")
        text_fields = ("gap_id", "material", "property_name", "problem_description", "novelty_status", "actionability", "falsifiable_hypothesis")
        if not all(isinstance(item.get(field), str) and item[field].strip() for field in text_fields):
            raise GapAnalysisError("research gap candidate has invalid text fields")
        list_fields = ("evidence_ids", "conflict_or_missing_evidence", "suggested_validation")
        if not all(isinstance(item.get(field), list) and all(isinstance(value, str) and value.strip() for value in item[field]) for field in list_fields):
            raise GapAnalysisError("research gap candidate has invalid evidence lists")
        if len(item["evidence_ids"]) < 2 or len(set(item["evidence_ids"])) != len(item["evidence_ids"]) or not item["conflict_or_missing_evidence"] or not item["suggested_validation"]:
            raise GapAnalysisError("research gap candidate lacks a complete evidence, conflict, or validation boundary")
        completeness = item.get("evidence_completeness")
        if not isinstance(completeness, (int, float)) or isinstance(completeness, bool) or not 0 <= completeness <= 1:
            raise GapAnalysisError("research gap candidate has invalid completeness")
        boundary = _load_boundary(item.get("counterevidence_boundary"), legacy=version == "1.0")
        candidates.append(ResearchGapCandidate(
            gap_id=item["gap_id"], material=item["material"], property_name=item["property_name"],
            problem_description=item["problem_description"], evidence_ids=tuple(item["evidence_ids"]),
            conflict_or_missing_evidence=tuple(item["conflict_or_missing_evidence"]),
            novelty_status=item["novelty_status"], actionability=item["actionability"],
            falsifiable_hypothesis=item["falsifiable_hypothesis"], suggested_validation=tuple(item["suggested_validation"]),
            evidence_completeness=float(completeness), review_status=item["review_status"],
            counterevidence_boundary=boundary,
        ))
    if len({candidate.gap_id for candidate in candidates}) != len(candidates):
        raise GapAnalysisError("research gap candidate identifiers must be unique")
    return tuple(candidates)


def candidates_from_discrepancies(
    mission_id: str,
    material: str,
    property_name: str,
    cards: tuple[EvidenceCard, ...],
    decisions: tuple[VerificationDecision, ...],
    matrix: DiscrepancyMatrix,
    counterevidence_execution: CounterevidenceExecution | None = None,
) -> tuple[ResearchGapCandidate, ...]:
    """Turn only current-mission accepted conflicts into review-required candidates."""
    if not isinstance(mission_id, str) or not mission_id.strip():
        raise GapAnalysisError("Research Gap generation requires a mission identifier")
    boundary = _boundary_from_matrix(matrix, counterevidence_execution)
    accepted = {
        decision.evidence_id
        for decision in decisions
        if decision.mission_id == mission_id and decision.status is ReviewStatus.ACCEPTED
    }
    by_id = {card.evidence_id: card for card in cards}
    result: list[ResearchGapCandidate] = []
    for index, row in enumerate(matrix.rows, 1):
        ids = tuple(dict.fromkeys((*row.supporting_evidence_ids, *row.contradicting_evidence_ids)))
        if len(ids) < 2 or not row.differing_fields:
            continue
        row_cards = tuple(by_id.get(evidence_id) for evidence_id in ids)
        if any(card is None or card.evidence_id not in accepted for card in row_cards):
            continue
        if any(card.material != material or card.property_name != property_name for card in row_cards if card is not None):
            continue
        fields = ", ".join(dict.fromkeys(row.differing_fields))
        conflict_fields = tuple(dict.fromkeys(f"conflicting_condition:{field}" for field in row.differing_fields))
        result.append(ResearchGapCandidate(
            gap_id=f"gap_{index:03d}", material=material, property_name=property_name,
            problem_description=f"Under comparable recorded scope, opposing {property_name} evidence differs across {fields}.",
            evidence_ids=ids, conflict_or_missing_evidence=conflict_fields,
            novelty_status="unverified_requires_bounded_literature_review",
            actionability="compare the differing variables while holding the recorded shared conditions fixed",
            falsifiable_hypothesis=f"Changing one or more of {fields} accounts for the observed disagreement in {property_name}.",
            suggested_validation=(
                f"retrieve counterevidence for each of: {fields}",
                f"design a controlled experiment or simulation varying {fields}",
                "reject this candidate if matched-condition evidence removes the disagreement",
            ),
            evidence_completeness=1.0,
            review_status="candidate_requires_human_review",
            counterevidence_boundary=boundary,
        ))
    if not result:
        raise GapAnalysisError("no current-mission accepted conflict with explicit differing conditions is available")
    return tuple(result)


def _boundary_from_matrix(
    matrix: DiscrepancyMatrix, execution: CounterevidenceExecution | None,
) -> CounterevidenceBoundary:
    queries = tuple(matrix.counterevidence_queries)
    if not queries or any(not isinstance(query, str) or not query.strip() for query in queries):
        raise GapAnalysisError("Research Gap candidate requires approved counterevidence queries")
    hashes = tuple(hashlib.sha256(query.strip().encode("utf-8")).hexdigest() for query in queries)
    if execution is None:
        return CounterevidenceBoundary("not_attested", len(queries), 0, hashes, None)
    if execution.planned_query_count != len(queries) or execution.executed_query_count != len(queries):
        raise GapAnalysisError("counterevidence execution does not cover the approved query boundary")
    return _validate_executed_boundary(CounterevidenceBoundary(
        _EXECUTED_BOUNDARY_STATUS,
        execution.planned_query_count,
        execution.executed_query_count,
        hashes,
        execution.candidate_history_sha256,
    ))


def _validate_executed_boundary(boundary: CounterevidenceBoundary) -> CounterevidenceBoundary:
    """Validate an in-memory boundary with the same rules as a persisted artifact."""
    return _load_boundary(boundary.to_dict(), legacy=False)


def _load_boundary(value: object, *, legacy: bool) -> CounterevidenceBoundary:
    if legacy:
        return CounterevidenceBoundary("legacy_not_attested", 0, 0, (), None)
    if not isinstance(value, dict) or set(value) != _BOUNDARY_FIELDS:
        raise GapAnalysisError("research gap candidate counterevidence boundary is invalid")
    status = value.get("status")
    planned, executed = value.get("approved_query_count"), value.get("executed_query_count")
    hashes, history = value.get("query_sha256"), value.get("candidate_history_sha256")
    if status != _EXECUTED_BOUNDARY_STATUS or not isinstance(planned, int) or not isinstance(executed, int) or planned < 1 or executed != planned:
        raise GapAnalysisError("research gap candidate counterevidence execution is incomplete")
    if not isinstance(hashes, list) or len(hashes) != planned or len(set(hashes)) != len(hashes) or any(not isinstance(item, str) or len(item) != 64 or any(char not in "0123456789abcdef" for char in item) for item in hashes):
        raise GapAnalysisError("research gap candidate counterevidence query fingerprints are invalid")
    if not isinstance(history, str) or len(history) != 64 or any(char not in "0123456789abcdef" for char in history):
        raise GapAnalysisError("research gap candidate retrieval-history fingerprint is invalid")
    return CounterevidenceBoundary(status, planned, executed, tuple(hashes), history)


def write_gap_candidates(run_dir: Path, candidates: tuple[ResearchGapCandidate, ...]) -> Path:
    if not candidates:
        raise GapAnalysisError("at least one gap candidate is required")
    for candidate in candidates:
        boundary = candidate.counterevidence_boundary
        if boundary is None:
            raise GapAnalysisError("persisted Research Gap candidates require an executed counterevidence boundary")
        _validate_executed_boundary(boundary)
    path = run_dir / "research_gap_candidates.json"
    path.write_text(json.dumps([candidate.to_dict() for candidate in candidates], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
