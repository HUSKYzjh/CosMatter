import type { WorkflowStageName } from "./localApi";

/** Catalogue filters for the run's stage. Membership conveys relevance only. */
export const DSH_STAGE_TOOLS: Record<WorkflowStageName, readonly string[]> = {
  intake: ["cosmatter_mission_create", "cosmatter_recent_runs", "cosmatter_workflow_status"],
  plan: ["cosmatter_stage_contract", "cosmatter_research_plan_draft", "cosmatter_research_plan_approve"],
  retrieval: ["cosmatter_stage_contract", "cosmatter_plugin_authorization_plan", "cosmatter_research_query_execute", "cosmatter_operational_telemetry"],
  screening: ["cosmatter_stage_contract", "cosmatter_candidate_screening_template", "cosmatter_candidate_screening_record"],
  parse: ["cosmatter_stage_contract", "cosmatter_mineru_source_submit", "cosmatter_mineru_task_poll", "cosmatter_operational_telemetry"],
  extraction: ["cosmatter_stage_contract", "cosmatter_accepted_evidence_search"],
  gap: ["cosmatter_stage_contract", "cosmatter_graph_query", "cosmatter_accepted_evidence_search", "cosmatter_graph_plan", "cosmatter_graph_review_request"],
  report: ["cosmatter_stage_contract", "cosmatter_artifact_manifest"],
  evaluation: ["cosmatter_stage_contract", "cosmatter_artifact_manifest", "cosmatter_operational_telemetry"],
};

export const DSH_STAGE_NOTES: Partial<Record<WorkflowStageName, readonly [string, string]>> = {
  extraction: ["在工作台登记来源定位并审核证据卡。DSH 可检索已接受的证据卡。", "Record source locations and review evidence cards in the workbench. DSH can search accepted cards."],
  gap: ["在工作台复核反例和比较条件。DSH 提供已接受证据查询与图谱复核入口。", "Review counterevidence and comparison conditions in the workbench. DSH provides accepted-evidence queries and graph review requests."],
  report: ["在工作台审核报告。DSH 可查看已生成的获准工件目录。", "Review the report in the workbench. DSH can list the approved artifacts that have been generated."],
  evaluation: ["在工作台登记人工评测。DSH 可读取阶段门禁、获准工件目录和聚合回执。", "Record the human evaluation in the workbench. DSH can read stage requirements, approved artifacts, and aggregate receipts."],
};
