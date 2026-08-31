"""Human-reviewed condition naming and unit declarations without conversion."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .models import EvidenceCard, MissionBrief, ReviewStatus
from .verification import VerificationDecision


_CANONICAL = {"thickness", "temperature", "strain", "pressure", "composition", "field", "energy_cutoff", "kpoint_density"}
SCHEMA_VERSION = "1.0"


class ConditionNormalizationError(ValueError):
    pass


def _is_reviewable_raw_condition(value: Any) -> bool:
    """Keep a naming ledger from legitimising missing or non-finite values."""
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().casefold() != "unknown"
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    return False


def condition_normalization_from_review(mission: MissionBrief, cards: tuple[EvidenceCard, ...], decisions: tuple[VerificationDecision, ...], selection: object) -> dict[str, Any]:
    """Preserve raw values while recording reviewer-approved canonical names/units."""
    accepted = {decision.evidence_id for decision in decisions if decision.mission_id == mission.mission_id and decision.status is ReviewStatus.ACCEPTED}
    by_id = {card.evidence_id: card for card in cards if card.evidence_id in accepted}
    if not isinstance(selection, dict) or set(selection) != {"mappings"} or not isinstance(selection["mappings"], list) or len(selection["mappings"]) > 36:
        raise ConditionNormalizationError("normalization selection is invalid")
    mappings: list[dict[str, str]] = []; seen: set[tuple[str, str]] = set()
    for item in selection["mappings"]:
        if not isinstance(item, dict) or set(item) != {"evidence_id", "raw_field", "canonical_field", "unit"}: raise ConditionNormalizationError("normalization mapping fields are invalid")
        evidence_id, raw_field, canonical, unit = (item[key] for key in ("evidence_id", "raw_field", "canonical_field", "unit"))
        card = by_id.get(evidence_id)
        if not all(isinstance(value, str) and value.strip() for value in (evidence_id, raw_field, canonical, unit)) or card is None or canonical not in _CANONICAL or raw_field not in card.conditions or not _is_reviewable_raw_condition(card.conditions[raw_field]) or (evidence_id, raw_field) in seen or len(unit) > 40:
            raise ConditionNormalizationError("normalization mapping values are invalid")
        seen.add((evidence_id, raw_field)); mappings.append({"evidence_id": evidence_id, "raw_field": raw_field, "canonical_field": canonical, "unit": unit})
    return {"schema_version": SCHEMA_VERSION, "mission_id": mission.mission_id, "trust_status": "human_reviewed_condition_normalization_no_conversion", "mappings": mappings}


def write_condition_normalization(run_dir: Path, artifact: dict[str, Any]) -> Path:
    _validate_artifact(artifact)
    path = run_dir / "condition_normalization.json"; path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); return path


def load_condition_normalization(path: Path, mission_id: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ConditionNormalizationError("condition_normalization.json is invalid JSON") from error
    _validate_artifact(payload)
    if payload["mission_id"] != mission_id:
        raise ConditionNormalizationError("condition normalization does not belong to mission")
    return payload


def _validate_artifact(payload: Any) -> None:
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "mission_id", "trust_status", "mappings"} or payload.get("schema_version") != SCHEMA_VERSION or payload.get("trust_status") != "human_reviewed_condition_normalization_no_conversion" or not isinstance(payload.get("mission_id"), str) or not payload["mission_id"].strip() or not isinstance(payload.get("mappings"), list) or len(payload["mappings"]) > 36:
        raise ConditionNormalizationError("normalization artifact is invalid")
    seen: set[tuple[str, str]] = set()
    for item in payload["mappings"]:
        if not isinstance(item, dict) or set(item) != {"evidence_id", "raw_field", "canonical_field", "unit"}:
            raise ConditionNormalizationError("normalization mapping fields are invalid")
        evidence_id, raw_field, canonical, unit = (item[key] for key in ("evidence_id", "raw_field", "canonical_field", "unit"))
        if not all(isinstance(value, str) and value.strip() for value in (evidence_id, raw_field, canonical, unit)) or canonical not in _CANONICAL or len(evidence_id) > 200 or len(raw_field) > 120 or len(unit) > 40 or (evidence_id, raw_field) in seen:
            raise ConditionNormalizationError("normalization mapping values are invalid")
        seen.add((evidence_id, raw_field))
