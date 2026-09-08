import { expect, it } from "vitest";

import { harnessRuntimeSummary } from "./harnessRuntimeSummary";
import type { OperationalTelemetry } from "./localApi";

const telemetry = (dispatchOperations: OperationalTelemetry["dispatch_operations"]): OperationalTelemetry => ({
  schema_version: "cosmatter.operational-telemetry/v2",
  run_id: "run",
  mission_id: "mission",
  trust_status: "local aggregate",
  provider_operations: [],
  dispatch_operations: dispatchOperations,
  validation_rejections: [],
  cost_latency_status: "not_recorded",
  cost_latency: [],
});

it("keeps an empty runtime distinct from a completed dispatch", () => {
  expect(harnessRuntimeSummary(null)).toEqual({ state: "none", dispatchCount: 0, completedCount: 0, incompleteCount: 0, unknownCount: 0 });
  expect(harnessRuntimeSummary(telemetry([{ operation: "metadata_query", dispatch_count: 2, completed_count: 2, incomplete_count: 0, unknown_outcome_count: 0 }])).state).toBe("completed");
});

it("gives unknown outcomes precedence over incomplete dispatches", () => {
  expect(harnessRuntimeSummary(telemetry([
    { operation: "deepseek_plan_draft", dispatch_count: 1, completed_count: 0, incomplete_count: 1, unknown_outcome_count: 0 },
    { operation: "metadata_query", dispatch_count: 1, completed_count: 0, incomplete_count: 0, unknown_outcome_count: 1 },
  ]))).toEqual({ state: "unknown", dispatchCount: 2, completedCount: 0, incompleteCount: 1, unknownCount: 1 });
});
