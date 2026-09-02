"""Read-only P1 import and review for externally executed simulation summaries.

This is intentionally an artifact validator, not an execution adapter.  It
does not submit, poll, cancel, retry, download, or otherwise contact an
external calculation system.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .simulation_campaign import SimulationCampaignError, migrate_simulation_campaign, simulation_campaign_ui_projection
from .simulation_contracts import SimulationContractError, canonical_sha256, validate_external_run_receipt, validate_reviewed_simulation_evidence


class SimulationResultImportError(ValueError):
    """Raised when a result does not remain within the read-only P1 boundary."""


def import_external_run_receipt(*, campaign: object, mission_id: str, payload: object) -> dict[str, Any]:
    """Validate an external aggregate result against an approved campaign."""
    _require_campaign(campaign, mission_id)
    normalized = migrate_simulation_campaign(campaign)
    try:
        receipt = validate_external_run_receipt(
            payload, campaign_id=normalized["campaign_id"],
            input_manifest_sha256=normalized["contract_hashes"]["input_manifest_sha256"],
        )
    except SimulationContractError as error:
        raise SimulationResultImportError(str(error)) from error
    if receipt.get("schema_version") != "1.1":
        raise SimulationResultImportError("P1 import requires external run receipt schema 1.1")
    if receipt.get("protocol_sha256") != normalized["contract_hashes"]["protocol_sha256"]:
        raise SimulationResultImportError("external run receipt protocol hash does not match the approved campaign")
    return dict(receipt)


def review_external_run_receipt(*, campaign: object, mission_id: str, receipt: object, payload: object) -> dict[str, Any]:
    """Record a human review, still outside the EvidenceCard acceptance gate."""
    accepted = import_external_run_receipt(campaign=campaign, mission_id=mission_id, payload=receipt)
    try:
        reviewed = validate_reviewed_simulation_evidence(
            payload, campaign_id=accepted["campaign_id"], receipt_sha256=canonical_sha256(accepted)
        )
    except SimulationContractError as error:
        raise SimulationResultImportError(str(error)) from error
    if reviewed.get("schema_version") != "1.1":
        raise SimulationResultImportError("P1 review requires reviewed simulation evidence schema 1.1")
    return dict(reviewed)


def simulation_evidence_ui_projection(*, campaign: object, mission_id: str, receipt: object, review: object) -> dict[str, Any]:
    """Return a browser-safe outcome: no IDs, hashes, raw values, or run details."""
    accepted = import_external_run_receipt(campaign=campaign, mission_id=mission_id, payload=receipt)
    reviewed = review_external_run_receipt(campaign=campaign, mission_id=mission_id, receipt=accepted, payload=review)
    return {
        "delivery_status": "human_reviewed_pending_evidencecard_gate",
        "result_kind": accepted["result_kind"],
        "convergence_status": accepted["convergence_status"],
        "relation_to_hypothesis": reviewed["relation_to_hypothesis"],
        "applicability_boundary": reviewed["applicability_boundary"],
        "uncertainty": reviewed["uncertainty"],
        "result_interpretation_boundary": "Imported external aggregate only; it is not an EvidenceCard or a general scientific conclusion.",
    }


def write_external_run_receipt(run_dir: Path, payload: dict[str, Any]) -> Path:
    return _write_once(run_dir / "simulation_external_run_receipt.json", payload, "external simulation run receipt")


def write_reviewed_simulation_evidence(run_dir: Path, payload: dict[str, Any]) -> Path:
    return _write_once(run_dir / "reviewed_simulation_evidence.json", payload, "reviewed simulation evidence")


def _require_campaign(campaign: object, mission_id: str) -> None:
    try:
        simulation_campaign_ui_projection(campaign, mission_id)
    except SimulationCampaignError as error:
        raise SimulationResultImportError(f"approved plan-only campaign is required: {error}") from error


def _write_once(path: Path, payload: dict[str, Any], label: str) -> Path:
    if path.exists():
        raise SimulationResultImportError(f"{label} already exists; create a new run for another import")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
