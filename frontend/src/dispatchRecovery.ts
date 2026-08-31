import type { DispatchOperationTelemetry, OperationalTelemetry } from "./localApi";

export interface DispatchRecoveryItem {
  operation: DispatchOperationTelemetry["operation"];
  incompleteCount: number;
  unknownOutcomeCount: number;
}

/**
 * Derive read-only recovery guidance from aggregate telemetry.  It deliberately
 * exposes no automatic-retry action.  A ``dispatched`` entry is written before
 * provider I/O, so an incomplete entry can also represent an interrupted call
 * after the provider boundary.  Every non-terminal dispatch must therefore be
 * checked before any new explicitly authorised call is created.
 */
export function dispatchRecoveryItems(telemetry: OperationalTelemetry | null): DispatchRecoveryItem[] {
  if (!telemetry) return [];
  return telemetry.dispatch_operations.flatMap((operation) => {
    if (!operation.incomplete_count && !operation.unknown_outcome_count) return [];
    return [{
      operation: operation.operation,
      incompleteCount: operation.incomplete_count,
      unknownOutcomeCount: operation.unknown_outcome_count,
    }];
  });
}
