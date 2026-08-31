import { expect, it } from "vitest";

import { dispatchRecoveryItems } from "./dispatchRecovery";
import type { OperationalTelemetry } from "./localApi";

const telemetry = (dispatch_operations: OperationalTelemetry["dispatch_operations"]): OperationalTelemetry => ({
  schema_version: "cosmatter.operational-telemetry/v1", run_id: "run_1", mission_id: "mission_1", trust_status: "loopback",
  provider_operations: [], dispatch_operations, cost_latency_status: "not_recorded", cost_latency: [],
});

it("requires controlled status checks for every non-terminal external dispatch", () => {
  expect(dispatchRecoveryItems(telemetry([
    { operation: "metadata_query", dispatch_count: 3, completed_count: 1, incomplete_count: 2, unknown_outcome_count: 1 },
    { operation: "mineru_poll", dispatch_count: 1, completed_count: 1, incomplete_count: 0, unknown_outcome_count: 0 },
  ]))).toEqual([{ operation: "metadata_query", incompleteCount: 2, unknownOutcomeCount: 1 }]);
});

it("treats an incomplete entry as potentially provider-bound", () => {
  expect(dispatchRecoveryItems(telemetry([
    { operation: "deepseek_graph_plan_draft", dispatch_count: 1, completed_count: 0, incomplete_count: 1, unknown_outcome_count: 0 },
  ]))).toEqual([{ operation: "deepseek_graph_plan_draft", incompleteCount: 1, unknownOutcomeCount: 0 }]);
});

it("returns no recovery work when telemetry is absent or terminal", () => {
  expect(dispatchRecoveryItems(null)).toEqual([]);
  expect(dispatchRecoveryItems(telemetry([{ operation: "citation_expansion", dispatch_count: 1, completed_count: 1, incomplete_count: 0, unknown_outcome_count: 0 }]))).toEqual([]);
});
