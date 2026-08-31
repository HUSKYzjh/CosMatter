import { DISPATCH_OPERATIONS, type OperationalTelemetry, type StageContract, type WorkflowDag } from "./localApi";
import { workflowDagRail } from "./workflowDagProjection";

const STAGES = ["intake", "plan", "retrieval", "screening", "parse", "extraction", "gap", "report", "evaluation"] as const;
const STAGE_CONTRACT_TRUST = "loopback_stage_contract_not_scientific_evidence_or_execution_authorization";
const TELEMETRY_TRUST = "loopback_aggregate_operational_telemetry_not_billing_or_scientific_evidence";
const STAGE_SPECS = [
  [["mission_boundary_recorded"], "mission_definition", ["mission_brief"], "mission_boundary_review"],
  [["approved_flight_plan"], "plan_approval", ["approved_flight_plan"], "plan_review"],
  [["approved_queries_executed", "provider_receipt_links_valid"], "mission_scoped_egress_consent", ["retrieval_candidate_history", "provider_receipt_links"], "authorized_retrieval_review"],
  [["candidate_fingerprint_current", "human_candidate_screening_complete"], "candidate_screening", ["candidate_screening_decision"], "candidate_screening_review"],
  [["fulltext_access_confirmed", "mineru_task_receipts_linked"], "content_access_and_parse_consent", ["source_parse_task_ledger"], "content_access_review"],
  [["human_source_map_recorded", "human_evidence_decision_recorded"], "source_map_and_evidence_review", ["source_map", "material_fact", "verification_decision"], "source_map_review"],
  [["accepted_evidence_conditions_compared", "counterevidence_boundary_executed"], "gap_candidate_review", ["research_gap_candidate"], "counterevidence_review"],
  [["review_gated_inputs_available", "report_audit_valid"], "report_review", ["review_gated_report"], "report_audit_review"],
  [["required_human_metric_families_complete"], "evaluation_review", ["human_evaluation_summary"], "evaluation_review"],
] as const;
const STATUSES = new Set(["completed", "ready", "waiting_human_review", "blocked"]);
const dispatchOperationSet = new Set<string>(DISPATCH_OPERATIONS);
const exactKeys = (value: unknown, keys: readonly string[]) => Boolean(value && typeof value === "object" && !Array.isArray(value) && (() => { const actual = Object.keys(value as Record<string, unknown>); return actual.length === keys.length && actual.every((key) => keys.includes(key)); })());
const sameStrings = (actual: unknown, expected: readonly string[]) => Array.isArray(actual) && actual.length === expected.length && actual.every((value, index) => typeof value === "string" && value === expected[index]);
const boundedInteger = (value: unknown, maximum = 1_000_000) => typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= maximum;

function trustedStageContract(runId: string, contract: StageContract): boolean {
  if (!exactKeys(contract, ["schema_version", "run_id", "mission_id", "trust_status", "next_stage", "runtime_safety", "stages"])
    || contract.schema_version !== "cosmatter.stage-contract/v1" || contract.run_id !== runId || !contract.mission_id || contract.trust_status !== STAGE_CONTRACT_TRUST
    || !["verified", "attention_required"].includes(contract.runtime_safety) || !Array.isArray(contract.stages) || contract.stages.length !== STAGES.length) return false;
  if (contract.stages.some((raw, index) => {
    if (!exactKeys(raw, ["stage", "status", "completion_requirements", "human_gate", "expected_outputs", "recovery_route", "metrics"])) return true;
    const stage = raw as unknown as Record<string, unknown>;
    const [requirements, gate, outputs, recovery] = STAGE_SPECS[index];
    const metrics = stage.metrics;
    return stage.stage !== STAGES[index] || typeof stage.status !== "string" || !STATUSES.has(stage.status)
      || !sameStrings(stage.completion_requirements, requirements) || stage.human_gate !== gate || !sameStrings(stage.expected_outputs, outputs) || stage.recovery_route !== recovery
      || !metrics || typeof metrics !== "object" || Array.isArray(metrics) || Object.keys(metrics as Record<string, unknown>).length === 0 || Object.values(metrics as Record<string, unknown>).some((value) => !boundedInteger(value));
  })) return false;
  const expectedNext = contract.stages.find((stage) => stage.status !== "completed")?.stage ?? null;
  return contract.next_stage === expectedNext;
}

function trustedTelemetry(runId: string, telemetry: OperationalTelemetry): boolean {
  if (!exactKeys(telemetry, ["schema_version", "run_id", "mission_id", "trust_status", "provider_operations", "dispatch_operations", "cost_latency_status", "cost_latency"])
    || telemetry.schema_version !== "cosmatter.operational-telemetry/v1" || telemetry.run_id !== runId || !telemetry.mission_id || telemetry.trust_status !== TELEMETRY_TRUST
    || !Array.isArray(telemetry.provider_operations) || telemetry.provider_operations.length > 20 || !Array.isArray(telemetry.dispatch_operations) || telemetry.dispatch_operations.length > DISPATCH_OPERATIONS.length
    || !["not_recorded", "recorded", "invalid"].includes(telemetry.cost_latency_status) || !Array.isArray(telemetry.cost_latency) || telemetry.cost_latency_status !== "recorded" && telemetry.cost_latency.length > 0) return false;
  const providers = new Set<string>();
  if (telemetry.provider_operations.some((raw) => {
    if (!exactKeys(raw, ["provider", "operation", "request_count", "successful_response_count", "client_error_count", "server_error_count", "other_status_count"])) return true;
    const item = raw as unknown as Record<string, unknown>; const key = `${item.provider}:${item.operation}`;
    if (providers.has(key) || !["sciverse", "mineru"].includes(item.provider as string) || typeof item.operation !== "string" || !item.operation) return true;
    providers.add(key); const counts = [item.request_count, item.successful_response_count, item.client_error_count, item.server_error_count, item.other_status_count];
    return counts.some((value) => !boundedInteger(value, 10_000_000)) || counts[0] !== counts.slice(1).reduce<number>((total, value) => total + (value as number), 0);
  })) return false;
  const dispatches = new Set<string>();
  if (telemetry.dispatch_operations.some((raw) => {
    if (!exactKeys(raw, ["operation", "dispatch_count", "completed_count", "incomplete_count", "unknown_outcome_count"])) return true;
    const item = raw as unknown as Record<string, unknown>; const operation = item.operation;
    if (typeof operation !== "string" || !dispatchOperationSet.has(operation) || dispatches.has(operation)) return true;
    dispatches.add(operation); const counts = [item.dispatch_count, item.completed_count, item.incomplete_count, item.unknown_outcome_count];
    return counts.some((value) => !boundedInteger(value, 10_000_000)) || counts[0] !== counts.slice(1).reduce<number>((total, value) => total + (value as number), 0);
  })) return false;
  const costProviders = new Set<string>();
  return !telemetry.cost_latency.some((raw) => {
    if (!exactKeys(raw, ["provider_id", "request_count", "successful_request_count", "failed_request_count", "currency", "total_cost", "median_latency_seconds", "p95_latency_seconds"])) return true;
    const item = raw as unknown as Record<string, unknown>; const provider = item.provider_id;
    if (typeof provider !== "string" || !provider || costProviders.has(provider) || !["CNY", "USD", "EUR", "not_applicable"].includes(item.currency as string)) return true;
    costProviders.add(provider); const counts = [item.request_count, item.successful_request_count, item.failed_request_count]; const values = [item.total_cost, item.median_latency_seconds, item.p95_latency_seconds];
    return counts.some((value) => !boundedInteger(value, Number.MAX_SAFE_INTEGER)) || counts[0] !== (counts[1] as number) + (counts[2] as number) || values.some((value) => typeof value !== "number" || !Number.isFinite(value) || value < 0) || (item.p95_latency_seconds as number) < (item.median_latency_seconds as number);
  });
}

/** A runtime snapshot is usable only when all three local projections are valid and bound together. */
export function trustedRuntimeProjections(runId: string, contract: StageContract, dag: WorkflowDag, telemetry: OperationalTelemetry): boolean {
  if (!trustedStageContract(runId, contract)
    || workflowDagRail(dag).state !== "declared"
    || dag.run_id !== runId
    || !trustedTelemetry(runId, telemetry)
    || contract.mission_id !== dag.mission_id
    || contract.mission_id !== telemetry.mission_id
    || contract.runtime_safety !== dag.runtime_safety) return false;
  return contract.stages.every((stage, index) => stage.stage === dag.stages[index]?.stage && stage.status === dag.stages[index]?.status);
}
