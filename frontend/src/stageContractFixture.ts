import type { StageContract } from "./localApi";

const stageRows = [
  ["intake", ["mission_boundary_recorded"], "mission_definition", ["mission_brief"], "mission_boundary_review"],
  ["plan", ["approved_flight_plan"], "plan_approval", ["approved_flight_plan"], "plan_review"],
  ["retrieval", ["approved_queries_executed", "provider_receipt_links_valid"], "mission_scoped_egress_consent", ["retrieval_candidate_history", "provider_receipt_links"], "authorized_retrieval_review"],
  ["screening", ["candidate_fingerprint_current", "human_candidate_screening_complete"], "candidate_screening", ["candidate_screening_decision"], "candidate_screening_review"],
  ["parse", ["fulltext_access_confirmed", "mineru_task_receipts_linked"], "content_access_and_parse_consent", ["source_parse_task_ledger"], "content_access_review"],
  ["extraction", ["human_source_map_recorded", "human_evidence_decision_recorded"], "source_map_and_evidence_review", ["source_map", "material_fact", "verification_decision"], "source_map_review"],
  ["gap", ["accepted_evidence_conditions_compared", "counterevidence_boundary_executed"], "gap_candidate_review", ["research_gap_candidate"], "counterevidence_review"],
  ["report", ["review_gated_inputs_available", "report_audit_valid"], "report_review", ["review_gated_report"], "report_audit_review"],
  ["evaluation", ["required_human_metric_families_complete"], "evaluation_review", ["human_evaluation_summary"], "evaluation_review"],
] as const;

export function stageContractFixture(runId: string, missionId: string, nextStage: StageContract["next_stage"]): StageContract {
  const nextIndex = stageRows.findIndex(([stage]) => stage === nextStage);
  return {
    schema_version: "cosmatter.stage-contract/v1",
    trust_status: "loopback_stage_contract_not_scientific_evidence_or_execution_authorization",
    run_id: runId,
    mission_id: missionId,
    next_stage: nextStage,
    runtime_safety: "verified",
    stages: stageRows.map(([stage, requirements, humanGate, outputs, recovery], index) => ({
      stage,
      status: nextIndex < 0 || index < nextIndex ? "completed" : index > nextIndex ? "blocked" : nextStage === "retrieval" ? "ready" : "waiting_human_review",
      completion_requirements: [...requirements],
      human_gate: humanGate,
      expected_outputs: [...outputs],
      recovery_route: recovery,
      metrics: { reviewed: 0 },
    })),
  };
}
