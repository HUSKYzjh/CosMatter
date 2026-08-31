import type { OperationalTelemetry, StageContract, StageContractStage } from "./localApi";

export type RuntimeProjectionAttention = "runtime_safety_attention" | "human_review_required" | "stage_blocked" | "external_dispatch_incomplete" | "external_dispatch_unknown" | "cost_latency_disclosure_invalid";
export type RuntimeProjectionHealth = "disabled" | "loading" | "ready" | "unavailable";

/** Do not render a missing runtime projection as a perpetual loading state. */
export function runtimeProjectionReadable(health: RuntimeProjectionHealth): boolean {
  return health === "ready";
}

export function currentStage(contract: StageContract | null): StageContractStage | null {
  if (!contract?.next_stage) return null;
  return contract.stages.find((stage) => stage.stage === contract.next_stage) ?? null;
}

export function runtimeProjectionAttention(contract: StageContract | null, telemetry: OperationalTelemetry | null): RuntimeProjectionAttention[] {
  const result: RuntimeProjectionAttention[] = [];
  const stage = currentStage(contract);
  if (contract?.runtime_safety === "attention_required") result.push("runtime_safety_attention");
  if (stage?.status === "waiting_human_review") result.push("human_review_required");
  if (stage?.status === "blocked") result.push("stage_blocked");
  if (telemetry?.dispatch_operations.some((operation) => operation.incomplete_count > 0)) result.push("external_dispatch_incomplete");
  if (telemetry?.dispatch_operations.some((operation) => operation.unknown_outcome_count > 0)) result.push("external_dispatch_unknown");
  if (telemetry?.cost_latency_status === "invalid") result.push("cost_latency_disclosure_invalid");
  return result;
}
