"""Human-reviewed condition naming and unit declarations without conversion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import EvidenceCard, MissionBrief, ReviewStatus
from .verification import VerificationDecision


_CANONICAL = {"thickness", "temperature", "strain", "pressure", "composition", "field", "energy_cutoff", "kpoint_density"}


class ConditionNormalizationError(ValueError):
    pass


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
        if not all(isinstance(value, str) and value.strip() for value in (evidence_id, raw_field, canonical, unit)) or card is None or canonical not in _CANONICAL or raw_field not in card.conditions or isinstance(card.conditions[raw_field], (dict, list)) or (evidence_id, raw_field) in seen or len(unit) > 40:
            raise ConditionNormalizationError("normalization mapping values are invalid")
        seen.add((evidence_id, raw_field)); mappings.append({"evidence_id": evidence_id, "raw_field": raw_field, "canonical_field": canonical, "unit": unit})
    return {"schema_version": "1.0", "mission_id": mission.mission_id, "trust_status": "human_reviewed_condition_normalization_no_conversion", "mappings": mappings}


def write_condition_normalization(run_dir: Path, artifact: dict[str, Any]) -> Path:
    if not isinstance(artifact, dict) or set(artifact) != {"schema_version", "mission_id", "trust_status", "mappings"} or artifact.get("schema_version") != "1.0" or artifact.get("trust_status") != "human_reviewed_condition_normalization_no_conversion": raise ConditionNormalizationError("normalization artifact is invalid")
    path = run_dir / "condition_normalization.json"; path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); return path
