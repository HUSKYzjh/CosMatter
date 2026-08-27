"""Human-frozen, literature-bound intake artifacts for PotentialScope.

The module turns reviewed literature identifiers into three small, safe
artifacts: a SystemSpec, PotentialPassports and a condition matrix.  It never
opens PDF/Markdown files, fetches a provider, loads a model, builds a
structure, or runs a calculation.  The output can be translated into a task
plugin request only after all three artifacts validate together.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SYSTEM_SPEC_SCHEMA_VERSION = "1.0"
POTENTIAL_PASSPORT_SCHEMA_VERSION = "1.0"
CONDITION_MATRIX_SCHEMA_VERSION = "1.0"
AUTONOMY_POLICY_SCHEMA_VERSION = "1.0"


class PotentialScopeIntakeError(ValueError):
    """Raised when an intake artifact is incomplete, unsafe or cross-bound."""


def system_spec_template() -> dict[str, Any]:
    """Return a non-executable review template; placeholders are not valid input."""
    return {
        "schema_version": SYSTEM_SPEC_SCHEMA_VERSION,
        "trust_status": "template_requires_human_literature_review",
        "system_spec_id": "【仅 ASCII ID，例如 bfo_scope_v1】",
        "material_systems": ["【从审核文献填写；可多材料】"],
        "scope_description": "【比较对象、性质和可比范围；不写未验证结论】",
        "target_observables": ["relative_phase_energy", "forces"],
        "condition_axes": [{
            "axis_id": "【如 strain_percent】",
            "unit": "【如 percent】",
            "lower_bound": "【文献审核值】",
            "upper_bound": "【文献审核值】",
            "source_ids": ["【审核 Source Map 或 EvidenceCard ID】"],
        }],
        "potential_model_ids": ["【模型 A ID】", "【模型 B ID】"],
        "reference_method": "【人工批准的参考方法名称】",
        "pre_registered_metrics": ["energy_mae_ev_per_atom", "force_rmse_ev_per_angstrom"],
        "literature_source_ids": ["【审核 Source Map 或 EvidenceCard ID】"],
        "approval": {
            "status": "pending_human_freeze",
            "reviewer": "【填写】",
            "frozen_on": "",
        },
        "execution_boundary": "Literature-bound planning only; no structure generation, model loading, calculation, scheduler submission or external API call is authorized.",
    }


def build_system_spec(payload: object) -> dict[str, Any]:
    """Validate an already human-frozen system specification."""
    expected = {
        "schema_version", "trust_status", "system_spec_id", "material_systems", "scope_description",
        "target_observables", "condition_axes", "potential_model_ids", "reference_method",
        "pre_registered_metrics", "literature_source_ids", "approval", "execution_boundary",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise PotentialScopeIntakeError("SystemSpec has unsupported or missing fields")
    if payload.get("schema_version") != SYSTEM_SPEC_SCHEMA_VERSION:
        raise PotentialScopeIntakeError("SystemSpec schema version is invalid")
    if payload.get("trust_status") != "human_frozen_literature_bound_system_spec":
        raise PotentialScopeIntakeError("SystemSpec must be explicitly human frozen")
    _identifier(payload.get("system_spec_id"), "system_spec_id")
    _string_list(payload.get("material_systems"), "material systems", minimum=1, maximum=8, identifiers=False)
    _safe_text(payload.get("scope_description"), "scope description")
    _string_list(payload.get("target_observables"), "target observables", minimum=1, maximum=12, identifiers=True)
    source_ids = _string_list(payload.get("literature_source_ids"), "literature source IDs", minimum=1, maximum=200, identifiers=True)
    axes = _validate_axes(payload.get("condition_axes"), allowed_source_ids=set(source_ids))
    model_ids = _string_list(payload.get("potential_model_ids"), "potential model IDs", minimum=2, maximum=16, identifiers=True)
    _safe_text(payload.get("reference_method"), "reference method")
    _string_list(payload.get("pre_registered_metrics"), "pre-registered metrics", minimum=1, maximum=12, identifiers=True)
    _validate_approval(payload.get("approval"))
    _safe_text(payload.get("execution_boundary"), "execution boundary")
    return {
        **payload,
        "material_systems": list(payload["material_systems"]),
        "target_observables": list(payload["target_observables"]),
        "condition_axes": axes,
        "potential_model_ids": list(model_ids),
        "literature_source_ids": list(source_ids),
        "pre_registered_metrics": list(payload["pre_registered_metrics"]),
    }


def system_spec_sha256(spec: object) -> str:
    return _canonical_sha256(build_system_spec(spec))


def potential_passport_template(system_spec: object) -> dict[str, Any]:
    spec = build_system_spec(system_spec)
    return {
        "schema_version": POTENTIAL_PASSPORT_SCHEMA_VERSION,
        "trust_status": "template_requires_human_model_and_literature_review",
        "system_spec_sha256": system_spec_sha256(spec),
        "model_id": "【必须为 SystemSpec 已登记模型 ID】",
        "implementation": "【人工填写：实现或推理接口名称】",
        "version_or_commit": "【人工填写】",
        "artifact_sha256": "【64 位模型工件哈希；不填本机路径】",
        "license_or_terms": "【人工核对】",
        "training_envelope_status": "training_envelope_unknown",
        "declared_training_axes": [],
        "supports_observables": ["【从模型卡/文献审核】"],
        "known_limitations": ["【从模型卡/文献审核；不能为空】"],
        "literature_source_ids": ["【审核 Source Map 或 EvidenceCard ID】"],
        "review": {"status": "pending_human_review", "reviewer": "【填写】", "reviewed_on": ""},
    }


def build_potential_passport(*, system_spec: object, payload: object) -> dict[str, Any]:
    spec = build_system_spec(system_spec)
    expected = {
        "schema_version", "trust_status", "system_spec_sha256", "model_id", "implementation", "version_or_commit",
        "artifact_sha256", "license_or_terms", "training_envelope_status", "declared_training_axes",
        "supports_observables", "known_limitations", "literature_source_ids", "review",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise PotentialScopeIntakeError("PotentialPassport has unsupported or missing fields")
    if payload.get("schema_version") != POTENTIAL_PASSPORT_SCHEMA_VERSION:
        raise PotentialScopeIntakeError("PotentialPassport schema version is invalid")
    if payload.get("trust_status") != "human_reviewed_literature_bound_potential_passport":
        raise PotentialScopeIntakeError("PotentialPassport must be explicitly human reviewed")
    if payload.get("system_spec_sha256") != system_spec_sha256(spec):
        raise PotentialScopeIntakeError("PotentialPassport does not bind to the supplied SystemSpec")
    if payload.get("model_id") not in spec["potential_model_ids"]:
        raise PotentialScopeIntakeError("PotentialPassport model ID is absent from SystemSpec")
    _safe_text(payload.get("implementation"), "potential implementation")
    _safe_text(payload.get("version_or_commit"), "potential version or commit")
    _sha256_text(payload.get("artifact_sha256"), "potential artifact hash")
    _safe_text(payload.get("license_or_terms"), "potential license or terms")
    status = payload.get("training_envelope_status")
    if status not in {"training_envelope_unknown", "declared_only", "partially_tested", "validated_for_declared_task", "boundary_observed"}:
        raise PotentialScopeIntakeError("PotentialPassport training-envelope status is invalid")
    declared_axes = _validate_declared_training_axes(payload.get("declared_training_axes"), allowed_source_ids=set(spec["literature_source_ids"]))
    if status == "training_envelope_unknown" and declared_axes:
        raise PotentialScopeIntakeError("unknown training envelope must not claim declared axes")
    if status != "training_envelope_unknown" and not declared_axes:
        raise PotentialScopeIntakeError("known training-envelope status requires reviewer-declared axes")
    _string_list(payload.get("supports_observables"), "supported observables", minimum=1, maximum=20, identifiers=True)
    _string_list(payload.get("known_limitations"), "known limitations", minimum=1, maximum=20, identifiers=False)
    source_ids = _string_list(payload.get("literature_source_ids"), "PotentialPassport literature source IDs", minimum=1, maximum=100, identifiers=True)
    if not set(source_ids).issubset(set(spec["literature_source_ids"])):
        raise PotentialScopeIntakeError("PotentialPassport source IDs must be frozen in SystemSpec")
    _validate_review(payload.get("review"))
    return {**payload, "declared_training_axes": declared_axes, "literature_source_ids": list(source_ids)}


def build_condition_matrix(*, system_spec: object, payload: object) -> dict[str, Any]:
    """Validate a condition matrix built from reviewer-mapped literature only."""
    spec = build_system_spec(system_spec)
    expected = {"schema_version", "trust_status", "system_spec_sha256", "cells", "review"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise PotentialScopeIntakeError("condition matrix has unsupported or missing fields")
    if payload.get("schema_version") != CONDITION_MATRIX_SCHEMA_VERSION:
        raise PotentialScopeIntakeError("condition matrix schema version is invalid")
    if payload.get("trust_status") != "human_reviewed_literature_condition_matrix":
        raise PotentialScopeIntakeError("condition matrix must be explicitly human reviewed")
    if payload.get("system_spec_sha256") != system_spec_sha256(spec):
        raise PotentialScopeIntakeError("condition matrix does not bind to the supplied SystemSpec")
    cells = payload.get("cells")
    if not isinstance(cells, list) or not (1 <= len(cells) <= 500):
        raise PotentialScopeIntakeError("condition matrix requires one through five hundred reviewed cells")
    expected_axis_ids = {axis["axis_id"] for axis in spec["condition_axes"]}
    source_ids = set(spec["literature_source_ids"])
    seen: set[str] = set()
    normalized_cells: list[dict[str, Any]] = []
    for cell in cells:
        expected_cell = {"cell_id", "condition_values", "coverage_role", "literature_source_ids"}
        if not isinstance(cell, dict) or set(cell) != expected_cell:
            raise PotentialScopeIntakeError("condition cell has unsupported or missing fields")
        _identifier(cell.get("cell_id"), "condition cell ID")
        if cell["cell_id"] in seen:
            raise PotentialScopeIntakeError("condition matrix cell IDs must be unique")
        seen.add(cell["cell_id"])
        values = cell.get("condition_values")
        if not isinstance(values, dict) or not values or not set(values).issubset(expected_axis_ids):
            raise PotentialScopeIntakeError("condition cell values must name SystemSpec condition axes")
        normalized_values: dict[str, float] = {}
        bounds_by_axis = {axis["axis_id"]: axis for axis in spec["condition_axes"]}
        for axis_id, value in values.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise PotentialScopeIntakeError("condition cell values must be numeric")
            numeric = float(value)
            bounds = bounds_by_axis[axis_id]
            if not bounds["lower_bound"] <= numeric <= bounds["upper_bound"]:
                raise PotentialScopeIntakeError("condition cell value lies outside its frozen literature range")
            normalized_values[axis_id] = numeric
        if cell.get("coverage_role") not in {"reported", "conflict_candidate", "coverage_gap"}:
            raise PotentialScopeIntakeError("condition cell coverage role is invalid")
        cell_source_ids = _string_list(cell.get("literature_source_ids"), "condition cell source IDs", minimum=1, maximum=100, identifiers=True)
        if not set(cell_source_ids).issubset(source_ids):
            raise PotentialScopeIntakeError("condition cell source IDs must be frozen in SystemSpec")
        normalized_cells.append({**cell, "condition_values": normalized_values, "literature_source_ids": list(cell_source_ids)})
    _validate_review(payload.get("review"))
    return {**payload, "cells": normalized_cells}


def build_plugin_request(*, system_spec: object, passports: object, condition_matrix: object) -> dict[str, Any]:
    """Build the exact request accepted by ``TaskPluginRegistry.plan``.

    Axis bounds are frozen by the SystemSpec.  Source IDs are the union of
    reviewed condition cells; no model creates or fills missing axes.
    """
    spec = build_system_spec(system_spec)
    if not isinstance(passports, list) or len(passports) != len(spec["potential_model_ids"]):
        raise PotentialScopeIntakeError("exactly one PotentialPassport per SystemSpec model is required")
    reviewed = [build_potential_passport(system_spec=spec, payload=item) for item in passports]
    if {item["model_id"] for item in reviewed} != set(spec["potential_model_ids"]):
        raise PotentialScopeIntakeError("PotentialPassports must cover every SystemSpec model exactly once")
    matrix = build_condition_matrix(system_spec=spec, payload=condition_matrix)
    cited_source_ids = sorted({source_id for cell in matrix["cells"] for source_id in cell["literature_source_ids"]})
    if not cited_source_ids:
        raise PotentialScopeIntakeError("condition matrix contains no reviewer-mapped literature sources")
    return {
        "system_spec_id": spec["system_spec_id"],
        "system_spec_sha256": system_spec_sha256(spec),
        "potential_model_ids": list(spec["potential_model_ids"]),
        "reference_method": spec["reference_method"],
        "condition_axes": {axis["axis_id"]: [axis["lower_bound"], axis["upper_bound"]] for axis in spec["condition_axes"]},
        "literature_source_ids": cited_source_ids,
    }


def autonomy_policy_template(system_spec: object) -> dict[str, Any]:
    spec = build_system_spec(system_spec)
    return {
        "schema_version": AUTONOMY_POLICY_SCHEMA_VERSION,
        "trust_status": "human_frozen_planning_only_autonomy_policy",
        "system_spec_sha256": system_spec_sha256(spec),
        "allowed_actions": ["validate_local_artifacts", "derive_plugin_task_proposals"],
        "forbidden_actions": ["external_api_call", "pdf_or_markdown_read", "structure_generation", "model_load", "potential_inference", "dft_submission", "md_submission", "mc_submission", "training", "scheduler_poll"],
        "budgets": {"dft_tasks": 0, "gpu_tasks": 0, "external_calls": 0},
        "approval": {"status": "human_frozen", "reviewer": "【填写】", "frozen_on": "【填写】"},
    }


def write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _validate_axes(value: object, *, allowed_source_ids: set[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not (1 <= len(value) <= 12):
        raise PotentialScopeIntakeError("SystemSpec requires one through twelve condition axes")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for axis in value:
        expected = {"axis_id", "unit", "lower_bound", "upper_bound", "source_ids"}
        if not isinstance(axis, dict) or set(axis) != expected:
            raise PotentialScopeIntakeError("condition axis has unsupported or missing fields")
        _identifier(axis.get("axis_id"), "condition axis ID")
        if axis["axis_id"] in seen:
            raise PotentialScopeIntakeError("condition axis IDs must be unique")
        seen.add(axis["axis_id"])
        _safe_text(axis.get("unit"), "condition axis unit")
        bounds = (axis.get("lower_bound"), axis.get("upper_bound"))
        if not all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in bounds):
            raise PotentialScopeIntakeError("condition-axis bounds must be numeric")
        lower, upper = float(bounds[0]), float(bounds[1])
        if not lower < upper:
            raise PotentialScopeIntakeError("condition-axis lower bound must be less than upper bound")
        source_ids = _string_list(axis.get("source_ids"), "condition axis source IDs", minimum=1, maximum=100, identifiers=True)
        if not set(source_ids).issubset(allowed_source_ids):
            raise PotentialScopeIntakeError("condition-axis sources must be frozen in SystemSpec")
        normalized.append({"axis_id": axis["axis_id"], "unit": axis["unit"].strip(), "lower_bound": lower, "upper_bound": upper, "source_ids": list(source_ids)})
    return normalized


def _validate_declared_training_axes(value: object, *, allowed_source_ids: set[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > 12:
        raise PotentialScopeIntakeError("declared training axes must be a list of at most twelve entries")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for axis in value:
        expected = {"axis_id", "description", "source_ids"}
        if not isinstance(axis, dict) or set(axis) != expected:
            raise PotentialScopeIntakeError("declared training axis has unsupported or missing fields")
        _identifier(axis.get("axis_id"), "declared training axis ID")
        if axis["axis_id"] in seen:
            raise PotentialScopeIntakeError("declared training axis IDs must be unique")
        seen.add(axis["axis_id"])
        _safe_text(axis.get("description"), "declared training axis description")
        source_ids = _string_list(axis.get("source_ids"), "declared training axis source IDs", minimum=1, maximum=100, identifiers=True)
        if not set(source_ids).issubset(allowed_source_ids):
            raise PotentialScopeIntakeError("declared training-axis source IDs must be frozen in SystemSpec")
        normalized.append({"axis_id": axis["axis_id"], "description": axis["description"].strip(), "source_ids": list(source_ids)})
    return normalized


def _validate_approval(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {"status", "reviewer", "frozen_on"} or value.get("status") != "human_frozen":
        raise PotentialScopeIntakeError("SystemSpec approval must record human_frozen status")
    _safe_text(value.get("reviewer"), "SystemSpec reviewer")
    _safe_text(value.get("frozen_on"), "SystemSpec freeze date")


def _validate_review(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {"status", "reviewer", "reviewed_on"} or value.get("status") != "human_reviewed":
        raise PotentialScopeIntakeError("review artifact must record human_reviewed status")
    _safe_text(value.get("reviewer"), "reviewer")
    _safe_text(value.get("reviewed_on"), "review date")


def _string_list(value: object, field: str, *, minimum: int, maximum: int, identifiers: bool) -> list[str]:
    if not isinstance(value, list) or not (minimum <= len(value) <= maximum) or len(set(value)) != len(value):
        raise PotentialScopeIntakeError(f"{field} must contain {minimum} through {maximum} unique values")
    for item in value:
        if identifiers:
            _identifier(item, field)
        else:
            _safe_text(item, field)
    return sorted(value)


def _identifier(value: object, field: str) -> None:
    if not isinstance(value, str) or not value or len(value) > 128 or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in value):
        raise PotentialScopeIntakeError(f"{field} must be an ASCII identifier without paths or spaces")


def _sha256_text(value: object, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value.casefold()):
        raise PotentialScopeIntakeError(f"{field} must be a SHA-256 hex digest")


def _safe_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 1000:
        raise PotentialScopeIntakeError(f"{field} must be non-empty text")
    lowered = value.casefold()
    if any(marker in lowered for marker in ("api_key", "authorization", "bearer ", "c:\\users\\", "/home/", "ssh://")):
        raise PotentialScopeIntakeError(f"{field} must not include credentials or private paths")


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
