"""Local, typed persistence for evidence and verification work products."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .facilities import verification_decision
from .models import EvidenceCard
from .verification import VerificationDecision


class ArtifactWriteError(ValueError):
    """Raised when an evidence artifact cannot be safely appended."""


def _read_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ArtifactWriteError(f"invalid JSON artifact: {path.name}") from error
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ArtifactWriteError(f"artifact must be an array of objects: {path.name}")
    return payload


def _write_array(path: Path, payload: list[dict[str, Any]]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def persist_evidence_review(
    run_dir: Path,
    mission_id: str,
    card: EvidenceCard,
) -> VerificationDecision:
    """Append a card and its deterministic verification outcome as paired artifacts.

    The pair is append-only at the logical level: duplicate evidence identifiers
    are rejected, rather than silently replacing a previous decision.
    """
    if not mission_id.strip():
        raise ArtifactWriteError("mission_id must not be empty")
    run_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = run_dir / "evidence_cards.json"
    decisions_path = run_dir / "verification_decisions.json"
    evidence_payload = _read_array(evidence_path)
    decision_payload = _read_array(decisions_path)
    if any(item.get("evidence_id") == card.evidence_id for item in evidence_payload):
        raise ArtifactWriteError("evidence identifier already exists in this run")
    if any(item.get("evidence_id") == card.evidence_id for item in decision_payload):
        raise ArtifactWriteError("verification decision already exists for this evidence")
    decision = verification_decision(mission_id, card)
    evidence_payload.append(card.to_dict())
    decision_payload.append(decision.to_dict())
    _write_array(evidence_path, evidence_payload)
    _write_array(decisions_path, decision_payload)
    return decision
