"""Two-stage human-completion templates for a real PotentialScope campaign.

The first stage consumes only a quote-free reviewed registry.  The second
stage consumes a human-frozen SystemSpec.  Neither stage guesses a material,
model, condition value, license, budget, source locator, or scientific fact.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .potential_scope_freeze_templates import build_freeze_template_pack
from .potential_scope_intake import (
    AUTONOMY_POLICY_SCHEMA_VERSION,
    CONDITION_MATRIX_SCHEMA_VERSION,
    PotentialScopeIntakeError,
    autonomy_policy_template,
    build_system_spec,
    potential_passport_template,
    system_spec_sha256,
)


CAMPAIGN_TEMPLATE_PACK_SCHEMA_VERSION = "1.0"


class PotentialScopeCampaignTemplateError(ValueError):
    """Raised when a template pack could be mistaken for a frozen artifact."""


def build_registry_completion_pack(*, reviewed_source_registry: object) -> dict[str, Any]:
    """Create the first human-fillable step from a reviewed source registry."""
    freeze_pack = build_freeze_template_pack(reviewed_source_registry=reviewed_source_registry)
    return {
        "schema_version": CAMPAIGN_TEMPLATE_PACK_SCHEMA_VERSION,
        "trust_status": "potential_scope_campaign_stage_one_templates_not_frozen",
        "mission_id": freeze_pack["mission_id"],
        "reviewed_source_count": freeze_pack["reviewed_source_count"],
        "source_registry_sha256": freeze_pack["source_registry_sha256"],
        "system_spec_template": freeze_pack["system_spec_template"],
        "next_human_actions": [
            "填写并人工冻结 SystemSpec；不可从模板占位符推断材料、条件或模型。",
            "冻结后使用第二阶段模板包登记每个可运行模型、条件单元与零预算自治策略。",
            "只有全部工件经校验后，才可运行 plan-only campaign。",
        ],
        "execution_boundary": "Stage-one output is a template only. It cannot create a campaign, authorize external activity, or serve as source evidence.",
    }


def build_post_system_spec_completion_pack(*, system_spec: object) -> dict[str, Any]:
    """Create empty model/matrix/policy templates bound to one frozen SystemSpec."""
    try:
        spec = build_system_spec(system_spec)
    except PotentialScopeIntakeError as error:
        raise PotentialScopeCampaignTemplateError("a human-frozen SystemSpec is required") from error
    spec_sha = system_spec_sha256(spec)
    matrix_template = {
        "schema_version": CONDITION_MATRIX_SCHEMA_VERSION,
        "trust_status": "template_requires_human_literature_condition_review",
        "system_spec_sha256": spec_sha,
        "cells": [{
            "cell_id": "【ASCII 单元 ID，例如 cell_strain_01】",
            "condition_values": {axis["axis_id"]: "【填写落在冻结上下界内的数值】" for axis in spec["condition_axes"]},
            "coverage_role": "【reported / conflict_candidate / coverage_gap】",
            "literature_source_ids": list(spec["literature_source_ids"]),
        }],
        "review": {"status": "pending_human_review", "reviewer": "【填写】", "reviewed_on": ""},
    }
    policy = autonomy_policy_template(spec)
    policy["approval"] = {"status": "pending_human_freeze", "reviewer": "【填写】", "frozen_on": ""}
    return {
        "schema_version": CAMPAIGN_TEMPLATE_PACK_SCHEMA_VERSION,
        "trust_status": "potential_scope_campaign_stage_two_templates_not_frozen",
        "system_spec_sha256": spec_sha,
        "potential_passport_templates": [potential_passport_template(spec) for _ in spec["potential_model_ids"]],
        "potential_model_ids_in_required_order": list(spec["potential_model_ids"]),
        "condition_matrix_template": matrix_template,
        "autonomy_policy_template": policy,
        "next_human_actions": [
            "为每个 SystemSpec 模型 ID 填写一个真实可获得模型的护照；不得写入权重路径或凭据。",
            "仅用已审核来源填写条件单元和 coverage_role；未知字段保留未知，不猜测。",
            "确认政策预算全部为零且禁止动作完整，然后由人冻结。",
            "通过 preflight 后才运行自动 plan-only campaign。",
        ],
        "execution_boundary": "Stage-two output is incomplete by design. No model is loaded, no condition is assumed, no TestCard is proposed, and no calculation is authorized.",
    }


def write_campaign_template_pack(path: Path, pack: object) -> Path:
    """Persist a template only once and never below private/run locations."""
    if not isinstance(pack, dict) or pack.get("schema_version") != CAMPAIGN_TEMPLATE_PACK_SCHEMA_VERSION or "template" not in str(pack.get("trust_status", "")):
        raise PotentialScopeCampaignTemplateError("campaign template pack is invalid")
    if path.suffix.casefold() != ".json" or path.exists() or any(part.casefold() in {"runs", "private", "03_paper"} for part in path.parts):
        raise PotentialScopeCampaignTemplateError("template output must be a new JSON file outside private and run directories")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(pack, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as error:
        raise PotentialScopeCampaignTemplateError("campaign template pack cannot be written") from error
    return path


def campaign_template_sha256(pack: object) -> str:
    if not isinstance(pack, dict):
        raise PotentialScopeCampaignTemplateError("campaign template pack is invalid")
    return hashlib.sha256(json.dumps(pack, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
