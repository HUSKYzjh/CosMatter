"""Static, DeepSeek-Harness-inspired plugin host for PotentialScope.

The official DeepSeek Harness is a rapidly changing developer preview.  This
module adopts its "everything is a plugin" composition style without claiming
an unstable third-party ABI: scientific logic stays in CosMatter, while a
small, static registry exposes capability-labelled plugin boundaries.  Dynamic
plugin loading, shell execution and calculator access are intentionally absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .potential_scope_auto_triage import potential_scope_triage_prompts
from .potential_scope_campaign_preflight import inspect_campaign
from .potential_scope_freeze_templates import build_freeze_template_pack
from .potential_scope_frozen_plan import build_frozen_plugin_plan
from .potential_scope_task_priority import prioritize_proposed_test_cards


HARNESS_PLUGIN_API_VERSION = "1.0"


class PotentialScopeHarnessPluginError(ValueError):
    """Raised for unknown, unauthorized or malformed plugin invocations."""


@dataclass(frozen=True)
class PotentialScopeHarnessPlugin:
    plugin_id: str
    title: str
    capabilities: tuple[str, ...]
    required_authorizations: tuple[str, ...]
    output_sensitivity: str
    handler: Callable[[dict[str, Any]], dict[str, Any]]

    def manifest(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "title": self.title,
            "api_version": HARNESS_PLUGIN_API_VERSION,
            "capabilities": list(self.capabilities),
            "required_authorizations": list(self.required_authorizations),
            "output_sensitivity": self.output_sensitivity,
            "execution_boundary": "Static plugin only: no dynamic module load, shell command, scheduler, calculator, training or inference access.",
        }


class PotentialScopeHarness:
    """A tiny explicit plugin host with deny-by-default capability gates."""

    def __init__(self, plugins: tuple[PotentialScopeHarnessPlugin, ...] | None = None) -> None:
        registered = plugins or default_harness_plugins()
        if len({plugin.plugin_id for plugin in registered}) != len(registered):
            raise PotentialScopeHarnessPluginError("harness plugin identifiers must be unique")
        self._plugins = {plugin.plugin_id: plugin for plugin in registered}

    def manifests(self) -> list[dict[str, Any]]:
        return [self._plugins[key].manifest() for key in sorted(self._plugins)]

    def invoke(self, *, plugin_id: str, payload: object, authorizations: object = ()) -> dict[str, Any]:
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            raise PotentialScopeHarnessPluginError("unknown PotentialScope harness plugin")
        if not isinstance(payload, dict):
            raise PotentialScopeHarnessPluginError("plugin payload must be a JSON object")
        if not isinstance(authorizations, (list, tuple, set, frozenset)) or not all(isinstance(item, str) for item in authorizations):
            raise PotentialScopeHarnessPluginError("plugin authorizations are invalid")
        missing = set(plugin.required_authorizations) - set(authorizations)
        if missing:
            raise PotentialScopeHarnessPluginError("plugin is blocked pending explicit authorization: " + ", ".join(sorted(missing)))
        try:
            result = plugin.handler(payload)
        except (TypeError, ValueError, KeyError) as error:
            raise PotentialScopeHarnessPluginError("plugin rejected its input safely") from error
        if not isinstance(result, dict):
            raise PotentialScopeHarnessPluginError("plugin returned an invalid result")
        return {
            "plugin": plugin.manifest(),
            "result": result,
            "invocation_boundary": "The host returns plugin output only. It does not persist output, call a provider, or grant follow-up privileges.",
        }


def default_harness_plugins() -> tuple[PotentialScopeHarnessPlugin, ...]:
    """Return the complete current PotentialScope plugin surface.

    The external-LLM entry returns a bounded prompt only.  A separate adapter
    may send it to DeepSeek after the caller records the two consent tokens.
    """
    return (
        PotentialScopeHarnessPlugin(
            "potential_scope.private_triage_prompt",
            "私有文献自动分诊提示",
            ("private_candidate_pool_read", "deepseek_prompt_prepare"),
            ("private_content_to_deepseek", "mission_scoped_egress_consent"),
            "private",
            _triage_prompt,
        ),
        PotentialScopeHarnessPlugin(
            "potential_scope.freeze_template",
            "来源注册表到冻结模板",
            ("reviewed_registry_read", "template_derive"),
            (),
            "safe",
            _freeze_template,
        ),
        PotentialScopeHarnessPlugin(
            "potential_scope.campaign_preflight",
            "冻结工件预检",
            ("frozen_artifact_validate",),
            (),
            "safe",
            _campaign_preflight,
        ),
        PotentialScopeHarnessPlugin(
            "potential_scope.plan_only_test_cards",
            "文献绑定 TestCard 提案",
            ("frozen_artifact_validate", "plan_only_task_derive"),
            (),
            "safe",
            _frozen_plan,
        ),
        PotentialScopeHarnessPlugin(
            "potential_scope.prioritize_test_cards",
            "文献驱动测试优先级",
            ("frozen_artifact_validate", "plan_only_priority_derive"),
            (),
            "safe",
            _priority_queue,
        ),
    )


def _triage_prompt(payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"pool"}:
        raise ValueError("triage prompt accepts only a private candidate pool")
    system_prompt, user_prompt = potential_scope_triage_prompts(payload["pool"])
    return {
        "trust_status": "private_untrusted_deepseek_prompt_not_evidence_not_sent",
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "next_boundary": "Prompt preparation is not transmission. A provider adapter must record consent and keep raw responses private.",
    }


def _freeze_template(payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"reviewed_source_registry"}:
        raise ValueError("freeze template accepts only a reviewed source registry")
    return build_freeze_template_pack(reviewed_source_registry=payload["reviewed_source_registry"])


def _campaign_preflight(payload: dict[str, Any]) -> dict[str, Any]:
    expected = {"machine", "reviewed_source_registry", "system_spec", "passports", "condition_matrix"}
    if set(payload) != expected:
        raise ValueError("preflight requires the complete frozen artifact set")
    return inspect_campaign(**payload)


def _frozen_plan(payload: dict[str, Any]) -> dict[str, Any]:
    expected = {"machine", "reviewed_source_registry", "system_spec", "passports", "condition_matrix"}
    if set(payload) != expected:
        raise ValueError("plan-only TestCards require the complete frozen artifact set")
    return build_frozen_plugin_plan(
        machine=payload["machine"],
        reviewed_source_registry=payload["reviewed_source_registry"],
        system_spec=payload["system_spec"],
        passports=payload["passports"],
        condition_matrix=payload["condition_matrix"],
    )


def _priority_queue(payload: dict[str, Any]) -> dict[str, Any]:
    expected = {"frozen_plan", "system_spec", "passports", "condition_matrix"}
    if set(payload) != expected:
        raise ValueError("priority queue requires a frozen non-executing plan and frozen artifacts")
    return prioritize_proposed_test_cards(
        frozen_plan=payload["frozen_plan"],
        system_spec=payload["system_spec"],
        passports=payload["passports"],
        condition_matrix=payload["condition_matrix"],
    )
