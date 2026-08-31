"""Deterministic, fixture-backed evaluation for evidence-route diagnostics."""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .facilities import condition_differential, record_conditions, verification_decision
from .models import AccessPolicy, EvidenceCard, Provenance, ReviewStatus, Stance


class EvaluationError(ValueError):
    """Raised when a frozen evaluation fixture is incomplete or inconsistent."""


@dataclass(frozen=True)
class EvaluationReport:
    fixture_id: str
    fixture_sha256: str | None
    citation_precision: float
    condition_completeness: float
    contradiction_precision: float
    reproducibility_consistency: float
    expected_evidence_status: dict[str, str]
    observed_evidence_status: dict[str, str]
    expected_differing_fields: tuple[str, ...]
    observed_differing_fields: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "fixture_id": self.fixture_id,
            "citation_precision": self.citation_precision,
            "condition_completeness": self.condition_completeness,
            "contradiction_precision": self.contradiction_precision,
            "reproducibility_consistency": self.reproducibility_consistency,
            "expected_evidence_status": self.expected_evidence_status,
            "observed_evidence_status": self.observed_evidence_status,
            "expected_differing_fields": list(self.expected_differing_fields),
            "observed_differing_fields": list(self.observed_differing_fields),
        }
        if self.fixture_sha256 is not None:
            payload["fixture_sha256"] = self.fixture_sha256
        return payload


def _precision(predicted: set[str], expected: set[str]) -> float:
    return len(predicted & expected) / len(predicted) if predicted else 0.0


def evaluate_route_diagnostics(
    *,
    fixture_id: str,
    mission_id: str,
    cards: tuple[EvidenceCard, ...],
    counterevidence_queries: tuple[str, ...],
    expected_evidence_status: Mapping[str, str],
    expected_stances: Mapping[str, str],
    expected_differing_fields: tuple[str, ...],
    fixture_sha256: str | None = None,
) -> EvaluationReport:
    """Evaluate deterministic gates against independently frozen expected labels.

    ``citation_precision`` means precision of predicted accepted cards relative
    to fixture labels for citation-ready evidence; it is not a claim of
    scientific truth.  The frozen labels are deliberately distinct from the
    cards being evaluated.
    """
    if not fixture_id.strip() or not mission_id.strip() or not cards:
        raise EvaluationError("fixture_id, mission_id, and cards are required")
    if fixture_sha256 is not None and (len(fixture_sha256) != 64 or any(char not in "0123456789abcdef" for char in fixture_sha256)):
        raise EvaluationError("fixture_sha256 must be a lowercase SHA-256 digest when supplied")
    card_ids = {card.evidence_id for card in cards}
    if len(card_ids) != len(cards):
        raise EvaluationError("evaluation cards must have unique evidence identifiers")
    if set(expected_evidence_status) != card_ids or set(expected_stances) != card_ids:
        raise EvaluationError("frozen labels must cover exactly the evaluation cards")
    try:
        expected_status = {key: ReviewStatus(value) for key, value in expected_evidence_status.items()}
        expected_stance = {key: Stance(value) for key, value in expected_stances.items()}
    except ValueError as error:
        raise EvaluationError("frozen labels contain an unknown status or stance") from error

    decisions = tuple(verification_decision(mission_id, card) for card in cards)
    observed_status = {decision.evidence_id: decision.status for decision in decisions}
    matrix = condition_differential(cards, counterevidence_queries)
    observed_differing = tuple(matrix.rows[0].differing_fields)
    expected_accepted = {key for key, value in expected_status.items() if value is ReviewStatus.ACCEPTED}
    observed_accepted = {key for key, value in observed_status.items() if value is ReviewStatus.ACCEPTED}
    expected_contradictions = {key for key, value in expected_stance.items() if value is Stance.CONTRADICT}
    observed_contradictions = {card.evidence_id for card in cards if card.stance is Stance.CONTRADICT}
    profiles = [record_conditions(card) for card in cards]
    explicit_conditions = sum(value not in (None, "", "unknown") for profile in profiles for value in profile.values())
    condition_total = sum(len(profile) for profile in profiles)
    status_matches = observed_status == expected_status
    stance_matches = {card.evidence_id: card.stance for card in cards} == expected_stance
    differing_matches = set(observed_differing) == set(expected_differing_fields)
    return EvaluationReport(
        fixture_id=fixture_id,
        fixture_sha256=fixture_sha256,
        citation_precision=_precision(observed_accepted, expected_accepted),
        condition_completeness=explicit_conditions / condition_total if condition_total else 0.0,
        contradiction_precision=_precision(observed_contradictions, expected_contradictions),
        reproducibility_consistency=1.0 if status_matches and stance_matches and differing_matches else 0.0,
        expected_evidence_status={key: value.value for key, value in expected_status.items()},
        observed_evidence_status={key: value.value for key, value in observed_status.items()},
        expected_differing_fields=expected_differing_fields,
        observed_differing_fields=observed_differing,
    )


def evaluate_frozen_route_fixture(path: Path, mission_id: str) -> EvaluationReport:
    """Load a synthetic route-diagnostics fixture without touching local papers."""
    try:
        fixture_bytes = path.read_bytes()
        fixture = json.loads(fixture_bytes.decode("utf-8"))
    except FileNotFoundError as error:
        raise EvaluationError(f"missing frozen fixture: {path}") from error
    except json.JSONDecodeError as error:
        raise EvaluationError(f"invalid frozen fixture: {path.name}") from error
    if not isinstance(fixture, dict) or fixture.get("synthetic") is not True:
        raise EvaluationError("only explicitly synthetic frozen fixtures can be evaluated")
    try:
        entries = fixture["evidence_cards"]
        if not isinstance(entries, list):
            raise TypeError("evidence_cards must be an array")
        cards = tuple(
            EvidenceCard(
                claim="Synthetic regression record; not a scientific claim.",
                stance=Stance(str(entry["stance"])),
                material=str(fixture["material"]),
                property_name=str(fixture["property_name"]),
                conditions=entry["conditions"],
                quote="Synthetic fixture only; no paper text is included.",
                provenance=Provenance(
                    str(entry["evidence_id"]),
                    "fixture",
                    "CosMatter frozen test",
                    access_policy=AccessPolicy.LOCAL_ONLY,
                ),
                evidence_id=str(entry["evidence_id"]),
            )
            for entry in entries
        )
        return evaluate_route_diagnostics(
            fixture_id=f"{path.stem}_v{fixture['fixture_version']}",
            mission_id=mission_id,
            cards=cards,
            counterevidence_queries=tuple(str(item) for item in fixture["counterevidence_queries"]),
            expected_evidence_status=fixture["expected_evidence_status"],
            expected_stances=fixture["expected_stances"],
            expected_differing_fields=tuple(str(item) for item in fixture["expected_differing_fields"]),
            fixture_sha256=hashlib.sha256(fixture_bytes).hexdigest(),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise EvaluationError("frozen fixture has an invalid route-diagnostics shape") from error

def write_evaluation_record(run_dir: Path, report: EvaluationReport) -> Path:
    """Write one redacted metric record that can be compared across reruns."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "evaluation.json"
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
