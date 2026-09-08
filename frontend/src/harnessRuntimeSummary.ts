import type { OperationalTelemetry } from "./localApi";

export interface HarnessRuntimeSummary {
  state: "none" | "completed" | "incomplete" | "unknown";
  dispatchCount: number;
  completedCount: number;
  incompleteCount: number;
  unknownCount: number;
}

export function harnessRuntimeSummary(telemetry: OperationalTelemetry | null): HarnessRuntimeSummary {
  const summary = (telemetry?.dispatch_operations ?? []).reduce((current, operation) => ({
    dispatchCount: current.dispatchCount + operation.dispatch_count,
    completedCount: current.completedCount + operation.completed_count,
    incompleteCount: current.incompleteCount + operation.incomplete_count,
    unknownCount: current.unknownCount + operation.unknown_outcome_count,
  }), { dispatchCount: 0, completedCount: 0, incompleteCount: 0, unknownCount: 0 });
  const state = summary.unknownCount > 0 ? "unknown" : summary.incompleteCount > 0 ? "incomplete" : summary.dispatchCount > 0 && summary.completedCount === summary.dispatchCount ? "completed" : "none";
  return { state, ...summary };
}
