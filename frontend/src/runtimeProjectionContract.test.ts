import { describe, expect, it } from "vitest";

import type { OperationalTelemetry, StageContract, WorkflowDag } from "./localApi";
import { trustedRuntimeProjections } from "./runtimeProjectionContract";

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
const dagRows = [
  [[], ["mission.define"], "mission", "local_review_gated"], [["intake"], ["planning.orchestrate"], "mission", "local_review_gated"], [["plan"], ["literature.metadata_retrieval", "literature.deduplicate_and_rank"], "public_metadata", "explicit_consent_required"], [["retrieval"], [], "public_metadata", "human_review_required"], [["screening"], ["document.mineru_private_parse"], "private_fulltext", "explicit_consent_required"], [["parse"], ["evidence.material_extract", "evidence.source_map", "evidence.verify"], "reviewable_excerpt", "human_review_required"], [["extraction"], ["research.gap_candidates"], "accepted_evidence", "human_review_required"], [["gap"], ["report.generate"], "accepted_evidence", "local_review_gated"], [["report"], [], "run_summary", "human_review_required"],
] as const;
const names = ["intake", "plan", "retrieval", "screening", "parse", "extraction", "gap", "report", "evaluation"] as const;

function contract(): StageContract {
  return { schema_version: "cosmatter.stage-contract/v1", run_id: "run_1", mission_id: "mission_1", trust_status: "loopback_stage_contract_not_scientific_evidence_or_execution_authorization", next_stage: "retrieval", runtime_safety: "verified", stages: stageRows.map(([stage, completion_requirements, human_gate, expected_outputs, recovery_route], index) => ({ stage: stage as StageContract["stages"][number]["stage"], status: index < 2 ? "completed" : index === 2 ? "ready" : "blocked", completion_requirements: [...completion_requirements], human_gate, expected_outputs: [...expected_outputs], recovery_route, metrics: { reviewed: 0 } })) };
}
function dag(): WorkflowDag {
  return { schema_version: "cosmatter.workflow-dag/v1", run_id: "run_1", mission_id: "mission_1", trust_status: "loopback_declared_dag_readiness_projection_not_execution_authorization", dag_id: "cosmatter_review_gated_linear_workflow", max_concurrency: 1, scheduler_status: "declarative_only_no_execution_authorization", runtime_safety: "verified", eligible_stages: ["retrieval"], blocked_stage_count: 6, human_review_required: false, stages: dagRows.map(([depends_on, allowed_descriptors, data_classification, execution_class], index) => ({ stage: names[index], depends_on: [...depends_on] as WorkflowDag["stages"][number]["depends_on"], status: index < 2 ? "completed" : index === 2 ? "ready" : "blocked", allowed_descriptors: [...allowed_descriptors], data_classification, execution_class })) as WorkflowDag["stages"] };
}
function telemetry(): OperationalTelemetry {
  return { schema_version: "cosmatter.operational-telemetry/v1", run_id: "run_1", mission_id: "mission_1", trust_status: "loopback_aggregate_operational_telemetry_not_billing_or_scientific_evidence", provider_operations: [{ provider: "sciverse", operation: "search", request_count: 2, successful_response_count: 1, client_error_count: 1, server_error_count: 0, other_status_count: 0 }], dispatch_operations: [{ operation: "metadata_query", dispatch_count: 1, completed_count: 1, incomplete_count: 0, unknown_outcome_count: 0 }], cost_latency_status: "not_recorded", cost_latency: [] };
}

describe("trusted runtime projections", () => {
  it("accepts one complete, run-bound fixed projection triple", () => {
    expect(trustedRuntimeProjections("run_1", contract(), dag(), telemetry())).toBe(true);
  });

  it("fails closed for a malformed contract, DAG, or telemetry projection", () => {
    const badContract = contract(); badContract.stages[2].metrics = {};
    expect(trustedRuntimeProjections("run_1", badContract, dag(), telemetry())).toBe(false);
    const badDag = dag(); badDag.stages[2].allowed_descriptors = null as unknown as string[];
    expect(trustedRuntimeProjections("run_1", contract(), badDag, telemetry())).toBe(false);
    const badTelemetry = telemetry(); badTelemetry.provider_operations[0].request_count = 1;
    expect(trustedRuntimeProjections("run_1", contract(), dag(), badTelemetry)).toBe(false);
  });

  it("fails closed when individually valid projections disagree about runtime state", () => {
    const mismatchedStatus = dag();
    mismatchedStatus.stages[2].status = "waiting_human_review";
    mismatchedStatus.eligible_stages = [];
    mismatchedStatus.human_review_required = true;
    expect(trustedRuntimeProjections("run_1", contract(), mismatchedStatus, telemetry())).toBe(false);

    const mismatchedSafety = dag();
    mismatchedSafety.runtime_safety = "attention_required";
    mismatchedSafety.eligible_stages = [];
    expect(trustedRuntimeProjections("run_1", contract(), mismatchedSafety, telemetry())).toBe(false);
  });

  it("accepts every ledger-backed dispatch operation", () => {
    const snapshot = telemetry();
    snapshot.dispatch_operations = [
      "deepseek_plan_draft", "deepseek_graph_plan_draft", "metadata_query", "citation_expansion", "mineru_submit", "mineru_poll",
    ].map((operation) => ({ operation, dispatch_count: 1, completed_count: 1, incomplete_count: 0, unknown_outcome_count: 0 })) as OperationalTelemetry["dispatch_operations"];
    expect(trustedRuntimeProjections("run_1", contract(), dag(), snapshot)).toBe(true);
  });
});
