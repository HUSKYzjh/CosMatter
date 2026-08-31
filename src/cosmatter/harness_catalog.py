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


CATALOGUE_API_VERSION = "2.0"


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
    input_schema: str = "cosmatter.plugin-input/v1"
    output_schema: str = "cosmatter.plugin-output/v1"
    execution_mode: str = "local_derivation"

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
            "contract": {
                "input_schema": self.input_schema,
                "output_schema": self.output_schema,
                "execution_mode": self.execution_mode,
                "lifecycle": "authorize -> dispatch -> execution_receipt -> human_review_when_required",
            },
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
            "workflow.status", "工作流状态只读投影", "workflow", "cosmatter.workflow_readiness:workflow_readiness",
            ("workflow_readiness_derive", "count_only_status_projection"), "run_summary", "local_safe",
            input_schema="cosmatter.workflow-status-input/v1",
            output_schema="cosmatter.workflow-status/v1",
            execution_mode="read_only_projection",
        ),
        CosMatterPluginDescriptor(
            "workflow.stage_contract", "阶段契约只读投影", "workflow", "cosmatter.stage_contract:stage_contract",
            ("stage_completion_contract_derive", "human_gate_projection", "nonexecuting_recovery_route_projection"), "run_summary", "local_safe",
            input_schema="cosmatter.stage-contract-input/v1",
            output_schema="cosmatter.stage-contract/v1",
            execution_mode="read_only_projection",
        ),
        CosMatterPluginDescriptor(
            "workflow.operational_telemetry", "运行级聚合遥测", "workflow", "cosmatter.operational_telemetry:operational_telemetry",
            ("receipt_count_derive", "dispatch_state_count_derive", "human_reviewed_cost_latency_projection"), "run_summary", "local_safe",
            input_schema="cosmatter.operational-telemetry-input/v1",
            output_schema="cosmatter.operational-telemetry/v1",
            execution_mode="read_only_projection",
        ),
        CosMatterPluginDescriptor(
            "workflow.dag", "固定阶段 DAG 就绪投影", "workflow", "cosmatter.workflow_dag:workflow_dag_projection",
            ("fixed_dag_validate", "single_stage_readiness_project", "nonexecuting_scheduler_boundary"), "run_summary", "local_safe",
            input_schema="cosmatter.workflow-dag-input/v1",
            output_schema="cosmatter.workflow-dag/v1",
            execution_mode="read_only_projection",
        ),
        CosMatterPluginDescriptor(
            "literature.question_candidates", "研究问题候选", "retrieval", "cosmatter.deepseek:DeepSeekClient",
            ("question_reframe", "llm_request"), "mission", "external_authorized",
            ("mission_scoped_egress_consent", "deepseek_request_consent"),
        ),
        CosMatterPluginDescriptor(
            "literature.plan_draft", "受限检索计划草案", "planning", "cosmatter.planning:research_planning_prompts",
            ("llm_request", "untrusted_plan_draft_write"), "mission", "external_authorized",
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
            "graph.project_accepted_evidence", "已接受证据图投影", "graph", "cosmatter.graph_builder:build_accepted_evidence_graph",
            ("accepted_evidence_graph_derive", "provenance_digest", "mission_scoped_entity_projection"),
            "accepted_evidence", "local_safe",
            input_schema="cosmatter.graph-build-input/v1",
            output_schema="cosmatter.graph-snapshot/v1",
            execution_mode="local_derivation",
        ),
        CosMatterPluginDescriptor(
            "graph.export_projection", "图插件只读投影", "graph", "cosmatter.graph_projection:external_graph_projection",
            ("graph_contract_validate", "read_only_graph_export"), "accepted_evidence", "local_safe",
            input_schema="cosmatter.graph-snapshot/v1",
            output_schema="cosmatter.graph-snapshot/v1",
            execution_mode="read_only_projection",
        ),
        CosMatterPluginDescriptor(
            "graph.plan", "图查询计划", "graph", "cosmatter.graph_plan:GraphPlanDraft",
            ("graph_query_plan_derive", "graph_budget_declare"), "accepted_evidence", "local_safe",
            requires_human_review=True,
            input_schema="cosmatter.graph-plan-input/v1",
            output_schema="cosmatter.graph-plan/v1",
            execution_mode="plan_only",
        ),
        CosMatterPluginDescriptor(
            "graph.plan_assist", "图模型计划草案", "graph", "cosmatter.graph_model_plan:normalized_graph_model_plan_draft",
            ("graph_minimal_context_prompt", "deepseek_request", "untrusted_graph_plan_draft"), "accepted_evidence", "external_authorized",
            ("mission_scoped_egress_consent", "deepseek_request_consent"),
            requires_human_review=True,
            input_schema="cosmatter.graph-model-plan-input/v1",
            output_schema="cosmatter.graph-model-plan-draft/v1",
            execution_mode="untrusted_model_draft_only",
        ),
        CosMatterPluginDescriptor(
            "graph.review_release", "图发布审核", "graph", "cosmatter.graph_validation:validate_graph_snapshot",
            ("graph_release_review",), "accepted_evidence", "human_gate",
            requires_human_review=True,
            input_schema="cosmatter.graph-snapshot/v1",
            output_schema="cosmatter.graph-release-decision/v1",
            execution_mode="human_review",
        ),
        CosMatterPluginDescriptor(
            "graph.review_request", "图人工审核请求", "graph", "cosmatter.graph_review:GraphReviewRequest",
            ("graph_review_request_write",), "accepted_evidence", "local_safe",
            requires_human_review=True,
            input_schema="cosmatter.graph-review-request/v1",
            output_schema="cosmatter.graph-review-request/v1",
            execution_mode="pending_human_review_only",
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
