"""Project-wide static plugin catalogue for CosMatter.

This is a stable CosMatter contract inspired by the composition model of
DeepSeek Harness.  It deliberately does *not* claim compatibility with an
upstream developer-preview ABI.  Existing domain modules remain their own
well-tested implementations; the catalogue only makes their capability,
privacy, human-gate and execution boundaries explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CATALOGUE_API_VERSION = "1.0"


class HarnessCatalogueError(ValueError):
    """Raised when a static catalogue request is malformed."""


@dataclass(frozen=True)
class CosMatterPluginDescriptor:
    """A static description of one application capability, never executable code."""

    plugin_id: str
    title: str
    domain: str
    entrypoint: str
    capabilities: tuple[str, ...]
    data_classification: str
    automation_class: str
    required_authorizations: tuple[str, ...] = ()
    requires_human_review: bool = False

    def manifest(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "title": self.title,
            "domain": self.domain,
            "entrypoint": self.entrypoint,
            "api_version": CATALOGUE_API_VERSION,
            "capabilities": list(self.capabilities),
            "data_classification": self.data_classification,
            "automation_class": self.automation_class,
            "required_authorizations": list(self.required_authorizations),
            "requires_human_review": self.requires_human_review,
            "execution_boundary": (
                "Descriptor only: no dynamic loading, shell execution, scheduler submission, "
                "calculator launch, model training or inference is granted by this catalogue."
            ),
        }


def default_cosmatter_plugin_catalogue() -> tuple[CosMatterPluginDescriptor, ...]:
    """Return the complete, reviewable plugin surface for the current project.

    ``automation_class`` is intentionally conservative: ``local_safe`` means
    deterministic local derivation only; ``external_authorized`` needs a
    mission-scoped grant; ``human_gate`` cannot be automatically accepted.
    """
    return (
        CosMatterPluginDescriptor(
            "mission.define", "任务边界定义", "mission", "cosmatter.models:MissionBrief",
            ("mission_boundary_write", "task_fingerprint_derive"), "mission", "local_safe",
        ),
        CosMatterPluginDescriptor(
            "planning.orchestrate", "受控工作流编排", "planning", "cosmatter.planning:build_plan",
            ("retrieval_plan_derive", "fleet_assignment_derive", "audit_plan_write"), "mission", "local_safe",
        ),
        CosMatterPluginDescriptor(
            "literature.question_candidates", "研究问题候选", "retrieval", "cosmatter.deepseek:DeepSeekClient",
            ("question_reframe", "llm_request"), "mission", "external_authorized",
            ("mission_scoped_egress_consent", "deepseek_request_consent"),
        ),
        CosMatterPluginDescriptor(
            "literature.metadata_retrieval", "书目元数据检索", "retrieval", "cosmatter.metadata_search:MetadataSearch",
            ("metadata_search", "provider_request", "deduplication_input"), "public_metadata", "external_authorized",
            ("mission_scoped_egress_consent", "metadata_provider_consent"),
        ),
        CosMatterPluginDescriptor(
            "literature.deduplicate_and_rank", "去重与排序", "retrieval", "cosmatter.retrieval:rank_candidates",
            ("metadata_deduplicate", "ranking_derive"), "public_metadata", "local_safe",
        ),
        CosMatterPluginDescriptor(
            "document.mineru_private_parse", "私有 PDF 解析", "document", "cosmatter.mineru:MinerUAdapter",
            ("private_pdf_upload", "mineru_request", "private_markdown_store"), "private_fulltext", "external_authorized",
            ("mission_scoped_egress_consent", "mineru_file_consent", "private_content_to_mineru"),
        ),
        CosMatterPluginDescriptor(
            "bibliography.two_hop_expand", "双向两层引文扩展", "bibliography", "cosmatter.citation_expansion:build_citation_expansion",
            ("citation_relation_fetch", "bibliographic_graph_derive"), "public_metadata", "external_authorized",
            ("mission_scoped_egress_consent", "metadata_provider_consent"),
        ),
        CosMatterPluginDescriptor(
            "evidence.material_extract", "材料事实抽取", "evidence", "cosmatter.material_extraction:extract",
            ("structured_fact_candidate_derive", "unit_normalization"), "reviewable_excerpt", "local_safe",
            requires_human_review=True,
        ),
        CosMatterPluginDescriptor(
            "evidence.source_map", "来源定位映射", "evidence", "cosmatter.source_map:record_source_map",
            ("locator_bind", "provenance_audit"), "private_fulltext", "human_gate",
            requires_human_review=True,
        ),
        CosMatterPluginDescriptor(
            "evidence.verify", "证据核验", "evidence", "cosmatter.verification:verify_evidence",
            ("evidence_acceptance", "conflict_check"), "reviewable_excerpt", "human_gate",
            requires_human_review=True,
        ),
        CosMatterPluginDescriptor(
            "knowledge.fuse", "跨文献知识融合", "knowledge", "cosmatter.knowledge_fusion:fuse",
            ("condition_cluster", "conflict_detection", "knowledge_graph_derive"), "accepted_evidence", "local_safe",
        ),
        CosMatterPluginDescriptor(
            "research.gap_candidates", "研究缺口候选", "research", "cosmatter.gap_drafting:draft_gaps",
            ("gap_candidate_derive", "hypothesis_template_derive"), "accepted_evidence", "local_safe",
            requires_human_review=True,
        ),
        CosMatterPluginDescriptor(
            "report.generate", "结构化调研报告", "reporting", "cosmatter.reporting:build_report",
            ("report_derive", "citation_check"), "accepted_evidence", "local_safe",
        ),
        CosMatterPluginDescriptor(
            "run_package.continue", "可执行运行包续航", "continuation", "cosmatter.run_package:restore_run_package",
            ("package_validate", "run_restore", "audit_event_write"), "run_summary", "local_safe",
        ),
        CosMatterPluginDescriptor(
            "potential_scope.plan_only", "势函数适用域计划层", "potential_scope", "cosmatter.potential_scope_harness_plugins:PotentialScopeHarness",
            ("frozen_artifact_validate", "plan_only_testcard_derive", "priority_derive"), "reviewed_registry", "local_safe",
        ),
        CosMatterPluginDescriptor(
            "potential_scope.private_triage", "势函数私有文献分诊", "potential_scope", "cosmatter.potential_scope_harness_plugins:PotentialScopeHarness",
            ("private_candidate_pool_read", "deepseek_prompt_prepare"), "private_fulltext", "external_authorized",
            ("mission_scoped_egress_consent", "private_content_to_deepseek"),
        ),
    )


class CosMatterHarnessCatalogue:
    """Static lookup only; it cannot import a plugin or call a provider."""

    def __init__(self, plugins: tuple[CosMatterPluginDescriptor, ...] | None = None) -> None:
        registered = plugins or default_cosmatter_plugin_catalogue()
        identifiers = [plugin.plugin_id for plugin in registered]
        if len(set(identifiers)) != len(identifiers):
            raise HarnessCatalogueError("plugin identifiers must be unique")
        self._plugins = {plugin.plugin_id: plugin for plugin in registered}

    def manifests(self) -> list[dict[str, Any]]:
        return [self._plugins[plugin_id].manifest() for plugin_id in sorted(self._plugins)]

    def describe(self, plugin_id: str) -> dict[str, Any]:
        if not isinstance(plugin_id, str) or plugin_id not in self._plugins:
            raise HarnessCatalogueError("unknown CosMatter plugin")
        return self._plugins[plugin_id].manifest()
