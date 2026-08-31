import { expect, it } from "vitest";
import { currentStage, runtimeProjectionAttention, runtimeProjectionReadable } from "./runtimeProjection";
import type { OperationalTelemetry, StageContract } from "./localApi";

const contract = (): StageContract => ({
  schema_version: "cosmatter.stage-contract/v1", run_id: "run_1", mission_id: "mission_1", trust_status: "loopback", next_stage: "screening", runtime_safety: "attention_required",
  stages: ["intake", "plan", "retrieval", "screening", "parse", "extraction", "gap", "report", "evaluation"].map((stage, index) => ({ stage: stage as StageContract["stages"][number]["stage"], status: index < 3 ? "completed" : index === 3 ? "waiting_human_review" : "blocked", completion_requirements: ["fixed"], human_gate: "human", expected_outputs: ["fixed"], recovery_route: "review", metrics: { item_count: index } })),
});

it("selects the fixed next stage and reports only aggregate operational attention", () => {
  const telemetry: OperationalTelemetry = {
    schema_version: "cosmatter.operational-telemetry/v1", run_id: "run_1", mission_id: "mission_1", trust_status: "loopback", provider_operations: [],
    dispatch_operations: [{ operation: "metadata_query", dispatch_count: 2, completed_count: 1, incomplete_count: 0, unknown_outcome_count: 1 }], cost_latency_status: "invalid", cost_latency: [],
  };
  expect(currentStage(contract())?.stage).toBe("screening");
  expect(runtimeProjectionAttention(contract(), telemetry)).toEqual(["runtime_safety_attention", "human_review_required", "external_dispatch_unknown", "cost_latency_disclosure_invalid"]);
});

it("does not mistake an unavailable runtime projection for a readable one", () => {
  expect(runtimeProjectionReadable("ready")).toBe(true);
  expect(runtimeProjectionReadable("disabled")).toBe(false);
  expect(runtimeProjectionReadable("loading")).toBe(false);
  expect(runtimeProjectionReadable("unavailable")).toBe(false);
});
