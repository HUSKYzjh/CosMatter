"""Prepare quote-free human freeze templates from a reviewed-source registry."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .potential_scope_intake import system_spec_template
from .potential_scope_review_registry import PotentialScopeReviewRegistryError, build_reviewed_source_registry


FREEZE_TEMPLATE_PACK_SCHEMA_VERSION = "1.0"


class PotentialScopeFreezeTemplateError(ValueError):
    """Raised when a safe, human-completed freeze template cannot be prepared."""


def build_freeze_template_pack(*, reviewed_source_registry: object) -> dict[str, Any]:
    """Seed a deliberately incomplete SystemSpec template with trusted source IDs.

    No material, condition, potential, numerical bound, model version, or
    scientific conclusion is inferred. The output is invalid as a frozen
    SystemSpec until a researcher supplies and approves the missing fields.
    """
    if not isinstance(reviewed_source_registry, dict) or reviewed_source_registry.get("trust_status") != "human_reviewed_private_source_registry_not_evidence":
        raise PotentialScopeFreezeTemplateError("a human-reviewed quote-free source registry is required")
    try:
        registry = build_reviewed_source_registry(
            mission_id=reviewed_source_registry.get("mission_id"), entries=reviewed_source_registry.get("sources")
        )
    except PotentialScopeReviewRegistryError as error:
        raise PotentialScopeFreezeTemplateError("reviewed source registry is invalid") from error
    spec = system_spec_template()
    spec["literature_source_ids"] = [item["source_id"] for item in registry["sources"]]
    spec["condition_axes"] = [
        {
            "axis_id": "【填写经审核文献支持的条件轴，例如 strain_percent】",
            "unit": "【填写单位】",
            "lower_bound": "【填写经过来源定位核对的下界】",
            "upper_bound": "【填写经过来源定位核对的上界】",
            "source_ids": list(spec["literature_source_ids"]),
        }
    ]
    return {
        "schema_version": FREEZE_TEMPLATE_PACK_SCHEMA_VERSION,
        "trust_status": "template_requires_human_literature_model_review_not_frozen",
        "mission_id": registry["mission_id"],
        "source_registry_sha256": _sha(registry),
        "reviewed_source_count": len(registry["sources"]),
        "system_spec_template": spec,
        "next_human_decisions": [
            "确认材料体系、比较对象、性质与可比边界。",
            "仅填写具有来源定位支持的条件轴及数值范围。",
            "登记至少两个真实可获得势函数的身份、版本、许可证和已知限制。",
            "在模型护照和条件矩阵完成后，冻结 SystemSpec 并运行 campaign 预检。",
        ],
        "execution_boundary": "This template pack is not a frozen SystemSpec, PotentialPassport, condition matrix, EvidenceCard, calculation input, or execution authorization.",
    }


def write_freeze_template_pack(path: Path, pack: object) -> Path:
    _validate_pack(pack)
    if path.suffix.casefold() != ".json" or "runs" in {part.casefold() for part in path.parts}:
        raise PotentialScopeFreezeTemplateError("freeze template pack must be a JSON file outside CosMatter/runs")
    if path.exists():
        raise PotentialScopeFreezeTemplateError("freeze template pack already exists and will not be overwritten")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(pack, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as error:
        raise PotentialScopeFreezeTemplateError("freeze template pack cannot be written") from error
    return path


def _validate_pack(payload: object) -> None:
    expected = {"schema_version", "trust_status", "mission_id", "source_registry_sha256", "reviewed_source_count", "system_spec_template", "next_human_decisions", "execution_boundary"}
    if not isinstance(payload, dict) or set(payload) != expected or payload.get("schema_version") != FREEZE_TEMPLATE_PACK_SCHEMA_VERSION or payload.get("trust_status") != "template_requires_human_literature_model_review_not_frozen":
        raise PotentialScopeFreezeTemplateError("freeze template pack schema is invalid")
    if not isinstance(payload.get("mission_id"), str) or not payload["mission_id"] or not isinstance(payload.get("source_registry_sha256"), str) or len(payload["source_registry_sha256"]) != 64:
        raise PotentialScopeFreezeTemplateError("freeze template pack identity is invalid")
    if not isinstance(payload.get("reviewed_source_count"), int) or payload["reviewed_source_count"] < 1:
        raise PotentialScopeFreezeTemplateError("freeze template pack source count is invalid")
    if not isinstance(payload.get("system_spec_template"), dict) or payload["system_spec_template"].get("trust_status") != "template_requires_human_literature_review":
        raise PotentialScopeFreezeTemplateError("freeze template SystemSpec state is invalid")
    if not isinstance(payload.get("next_human_decisions"), list) or not payload["next_human_decisions"] or not isinstance(payload.get("execution_boundary"), str) or not payload["execution_boundary"].strip():
        raise PotentialScopeFreezeTemplateError("freeze template pack boundary is invalid")


def _sha(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
