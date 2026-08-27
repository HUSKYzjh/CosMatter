"""Safe external-result admission and conditional applicability analysis.

This module does not execute science.  It accepts only a complete, aggregate
numeric matrix that an external, human-approved runner has already produced.
It cannot see structures, trajectories, input files, model weights, commands
or provider responses.  Every map and boundary statement is explicitly a
human-review-required, condition-limited interpretation aid.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from .potential_scope_campaign_runner import campaign_sha256, validate_plan_only_campaign


RESULT_IMPORT_SCHEMA_VERSION = "1.0"
APPLICABILITY_POLICY_SCHEMA_VERSION = "1.0"


class PotentialScopeResultAnalysisError(ValueError):
    """Raised when an execution receipt, aggregate row, or review boundary is unsafe."""


def build_external_result_import_receipt(*, campaign: object, payload: object) -> dict[str, Any]:
    """Validate a human approval for importing summaries from an external runner.

    Approval authorizes importing rows only. It is neither a scheduler permit
    nor proof that a calculation was executed correctly.
    """
    cards, model_ids = _campaign_cards(campaign)
    expected = {"schema_version", "trust_status", "campaign_sha256", "approved_test_ids", "potential_model_ids", "approval", "result_boundary"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise PotentialScopeResultAnalysisError("external result-import receipt has unsupported or missing fields")
    if payload.get("schema_version") != RESULT_IMPORT_SCHEMA_VERSION or payload.get("trust_status") != "human_approved_external_result_import_receipt_not_execution_record":
        raise PotentialScopeResultAnalysisError("external result-import receipt identity is invalid")
    if payload.get("campaign_sha256") != campaign_sha256(campaign):
        raise PotentialScopeResultAnalysisError("external result-import receipt belongs to another campaign")
    test_ids = _id_list(payload.get("approved_test_ids"), "approved test IDs")
    if not set(test_ids).issubset(set(cards)):
        raise PotentialScopeResultAnalysisError("receipt approves a TestCard not present in the campaign")
    received_models = _id_list(payload.get("potential_model_ids"), "potential model IDs")
    if set(received_models) != set(model_ids):
        raise PotentialScopeResultAnalysisError("receipt must cover every frozen potential model exactly once")
    _human_approval(payload.get("approval"), status="approved_for_external_result_import")
    _safe_text(payload.get("result_boundary"), "result boundary")
    return {**payload, "approved_test_ids": sorted(test_ids), "potential_model_ids": sorted(received_models)}


def import_aggregate_result_rows(*, campaign: object, receipt: object, rows: object) -> dict[str, Any]:
    """Validate a complete selected TestCard×model numeric matrix and derive errors."""
    cards, model_ids = _campaign_cards(campaign)
    reviewed = build_external_result_import_receipt(campaign=campaign, payload=receipt)
    if not isinstance(rows, list):
        raise PotentialScopeResultAnalysisError("external result rows must be an array")
    expected_pairs = {(test_id, model_id) for test_id in reviewed["approved_test_ids"] for model_id in model_ids}
    observed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        normalized = _result_row(row, allowed_tests=set(reviewed["approved_test_ids"]), allowed_models=set(model_ids))
        key = (normalized["test_id"], normalized["model_id"])
        if key in observed:
            raise PotentialScopeResultAnalysisError("external result rows contain a duplicate TestCard/model pair")
        observed[key] = normalized
    if set(observed) != expected_pairs:
        raise PotentialScopeResultAnalysisError("external result rows must cover every approved TestCard/model pair exactly once")
    diagnostics: list[dict[str, Any]] = []
    for test_id in reviewed["approved_test_ids"]:
        pair_rows = [observed[(test_id, model_id)] for model_id in model_ids]
        ref = pair_rows[0]["reference_energy_ev"]
        atoms = pair_rows[0]["atom_count"]
        if any(row["reference_energy_ev"] != ref or row["atom_count"] != atoms for row in pair_rows[1:]):
            raise PotentialScopeResultAnalysisError("all models for one TestCard must report the same reference energy and atom count")
        for row in pair_rows:
            energy_error = abs(row["predicted_energy_ev"] - row["reference_energy_ev"])
            diagnostics.append({
                "test_id": test_id,
                "model_id": row["model_id"],
                "atom_count": atoms,
                "absolute_energy_error_ev": energy_error,
                "absolute_energy_error_ev_per_atom": energy_error / atoms,
                "force_rmse_ev_per_a": row["force_rmse_ev_per_a"],
                "wall_time_seconds": row["wall_time_seconds"],
            })
    return {
        "schema_version": RESULT_IMPORT_SCHEMA_VERSION,
        "trust_status": "imported_aggregate_external_results_require_human_scientific_review",
        "campaign_sha256": campaign_sha256(campaign),
        "receipt_sha256": _sha(reviewed),
        "approved_test_ids": list(reviewed["approved_test_ids"]),
        "potential_model_ids": list(model_ids),
        "diagnostics": diagnostics,
        "execution_boundary": "Rows are aggregate numeric imports only. They are not raw execution logs, proof of transferability, a model ranking, or an accepted BoundaryClaim.",
    }


def build_applicability_policy(*, imported_results: object, payload: object) -> dict[str, Any]:
    """Validate a human-frozen tolerance policy before conditionally labelling rows."""
    imported = _imported_results(imported_results)
    expected = {"schema_version", "trust_status", "imported_results_sha256", "max_energy_error_ev_per_atom", "max_force_rmse_ev_per_a", "failure_multiplier", "approval"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise PotentialScopeResultAnalysisError("applicability policy has unsupported or missing fields")
    if payload.get("schema_version") != APPLICABILITY_POLICY_SCHEMA_VERSION or payload.get("trust_status") != "human_frozen_condition_limited_applicability_policy":
        raise PotentialScopeResultAnalysisError("applicability policy identity is invalid")
    if payload.get("imported_results_sha256") != _sha(imported):
        raise PotentialScopeResultAnalysisError("applicability policy belongs to different imported results")
    for field in ("max_energy_error_ev_per_atom", "max_force_rmse_ev_per_a", "failure_multiplier"):
        value = payload.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) or float(value) <= 0:
            raise PotentialScopeResultAnalysisError("applicability policy thresholds must be finite positive numbers")
    if float(payload["failure_multiplier"]) <= 1:
        raise PotentialScopeResultAnalysisError("failure multiplier must be greater than one")
    _human_approval(payload.get("approval"), status="human_frozen")
    return payload


def build_applicability_map(*, campaign: object, imported_results: object, applicability_policy: object) -> dict[str, Any]:
    """Label observed rows using pre-registered tolerances, never a global ranking."""
    cards, _models = _campaign_cards(campaign)
    imported = _imported_results(imported_results)
    if imported["campaign_sha256"] != campaign_sha256(campaign):
        raise PotentialScopeResultAnalysisError("imported results belong to a different campaign")
    policy = build_applicability_policy(imported_results=imported, payload=applicability_policy)
    rows: list[dict[str, Any]] = []
    for diagnostic in imported["diagnostics"]:
        energy = diagnostic["absolute_energy_error_ev_per_atom"]
        force = diagnostic["force_rmse_ev_per_a"]
        if energy <= policy["max_energy_error_ev_per_atom"] and force <= policy["max_force_rmse_ev_per_a"]:
            state = "observed_within_tolerance"
        elif energy >= policy["max_energy_error_ev_per_atom"] * policy["failure_multiplier"] or force >= policy["max_force_rmse_ev_per_a"] * policy["failure_multiplier"]:
            state = "observed_failure"
        else:
            state = "boundary_signal"
        card = cards[diagnostic["test_id"]]
        rows.append({
            "test_id": diagnostic["test_id"],
            "model_id": diagnostic["model_id"],
            "observable": card["plugin_id"],
            "condition_axes": card["condition_axes"],
            "state": state,
            "result_diagnostic": dict(diagnostic),
            "literature_source_ids": list(card["literature_source_ids"]),
        })
    return {
        "schema_version": APPLICABILITY_POLICY_SCHEMA_VERSION,
        "trust_status": "condition_limited_applicability_map_requires_human_scientific_review",
        "campaign_sha256": campaign_sha256(campaign),
        "imported_results_sha256": _sha(imported),
        "applicability_policy_sha256": _sha(policy),
        "cells": rows,
        "execution_boundary": "Map states apply only to the imported TestCard coordinates and pre-registered tolerances. They do not prove a global model ranking or transferability beyond the frozen scope.",
    }


def draft_boundary_claim_candidates(*, applicability_map: object) -> dict[str, Any]:
    """Derive auditable, non-accepted candidates from observed signals/failures."""
    if not isinstance(applicability_map, dict) or applicability_map.get("trust_status") != "condition_limited_applicability_map_requires_human_scientific_review":
        raise PotentialScopeResultAnalysisError("a condition-limited applicability map is required")
    cells = applicability_map.get("cells")
    if not isinstance(cells, list):
        raise PotentialScopeResultAnalysisError("applicability map cells are invalid")
    candidates = []
    for cell in cells:
        if not isinstance(cell, dict) or cell.get("state") not in {"boundary_signal", "observed_failure"}:
            continue
        candidates.append({
            "candidate_id": "boundary_" + _sha({"test_id": cell["test_id"], "model_id": cell["model_id"]})[:16],
            "model_id": cell["model_id"],
            "test_id": cell["test_id"],
            "condition_axes": cell["condition_axes"],
            "observed_state": cell["state"],
            "supporting_literature_source_ids": cell["literature_source_ids"],
            "falsifier": "A human-approved independent reference comparison at the same or adjacent frozen condition coordinates that resolves the signal below the pre-registered tolerance.",
            "human_review": "required",
        })
    return {
        "schema_version": APPLICABILITY_POLICY_SCHEMA_VERSION,
        "trust_status": "boundary_claim_candidates_require_human_scientific_review",
        "applicability_map_sha256": _sha(applicability_map),
        "candidates": candidates,
        "execution_boundary": "Candidates are not accepted BoundaryClaims or scientific conclusions. Human review must assess numerical setup, source context, comparability, limitations and falsifiers.",
    }


def _campaign_cards(campaign: object) -> tuple[dict[str, dict[str, Any]], list[str]]:
    reviewed = validate_plan_only_campaign(campaign)
    if reviewed["campaign_state"] != "planned" or not isinstance(reviewed.get("frozen_plan"), dict):
        raise PotentialScopeResultAnalysisError("a planned plan-only campaign is required")
    proposal = reviewed["frozen_plan"].get("proposal")
    cards = proposal.get("proposed_test_cards") if isinstance(proposal, dict) else None
    if not isinstance(cards, list) or not cards:
        raise PotentialScopeResultAnalysisError("campaign has no proposed TestCards")
    indexed: dict[str, dict[str, Any]] = {}
    model_ids: set[str] = set()
    for card in cards:
        if not isinstance(card, dict) or not isinstance(card.get("test_id"), str) or not isinstance(card.get("potential_model_ids"), list) or not card.get("potential_model_ids"):
            raise PotentialScopeResultAnalysisError("campaign TestCard fields are invalid")
        indexed[card["test_id"]] = card
        model_ids.update(card["potential_model_ids"])
    if len(indexed) != len(cards) or len(model_ids) < 2:
        raise PotentialScopeResultAnalysisError("campaign TestCards do not form a valid model comparison")
    return indexed, sorted(model_ids)


def _result_row(row: object, *, allowed_tests: set[str], allowed_models: set[str]) -> dict[str, Any]:
    expected = {"test_id", "model_id", "atom_count", "reference_energy_ev", "predicted_energy_ev", "force_rmse_ev_per_a", "wall_time_seconds"}
    if not isinstance(row, dict) or set(row) != expected or row.get("test_id") not in allowed_tests or row.get("model_id") not in allowed_models:
        raise PotentialScopeResultAnalysisError("aggregate result row fields are invalid")
    atoms = row.get("atom_count")
    if not isinstance(atoms, int) or isinstance(atoms, bool) or atoms < 1:
        raise PotentialScopeResultAnalysisError("aggregate result row atom count is invalid")
    values: dict[str, float] = {}
    for field in ("reference_energy_ev", "predicted_energy_ev", "force_rmse_ev_per_a", "wall_time_seconds"):
        value = row.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
            raise PotentialScopeResultAnalysisError("aggregate result row has a non-finite numeric value")
        values[field] = float(value)
    if values["force_rmse_ev_per_a"] < 0 or values["wall_time_seconds"] <= 0:
        raise PotentialScopeResultAnalysisError("aggregate result row force/time values are invalid")
    return {"test_id": row["test_id"], "model_id": row["model_id"], "atom_count": atoms, **values}


def _imported_results(payload: object) -> dict[str, Any]:
    expected = {"schema_version", "trust_status", "campaign_sha256", "receipt_sha256", "approved_test_ids", "potential_model_ids", "diagnostics", "execution_boundary"}
    if not isinstance(payload, dict) or set(payload) != expected or payload.get("schema_version") != RESULT_IMPORT_SCHEMA_VERSION or payload.get("trust_status") != "imported_aggregate_external_results_require_human_scientific_review":
        raise PotentialScopeResultAnalysisError("imported result package is invalid")
    if not isinstance(payload.get("diagnostics"), list) or not payload["diagnostics"]:
        raise PotentialScopeResultAnalysisError("imported result diagnostics are invalid")
    return payload


def _human_approval(value: object, *, status: str) -> None:
    if not isinstance(value, dict) or set(value) != {"status", "reviewer", "approved_on", "external_runner"} or value.get("status") != status:
        raise PotentialScopeResultAnalysisError("human approval record is invalid")
    for field in ("reviewer", "approved_on", "external_runner"):
        _safe_text(value.get(field), "human approval record")


def _id_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value or len(value) != len(set(value)):
        raise PotentialScopeResultAnalysisError(f"{label} are invalid")
    for item in value:
        if not isinstance(item, str) or not item or len(item) > 128 or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in item):
            raise PotentialScopeResultAnalysisError(f"{label} contain an invalid identifier")
    return sorted(value)


def _safe_text(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise PotentialScopeResultAnalysisError(f"{label} is invalid")
    if any(token in value.casefold() for token in ("api_key", "authorization", "bearer ", "c:\\users\\", "/home/", "ssh://")):
        raise PotentialScopeResultAnalysisError(f"{label} must not contain credentials or private paths")


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
