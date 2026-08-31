import type { FlightRecordEntry } from "./missionFlightRecorder";

export type FlightRecordView = "discover" | "graph" | "reader" | "horizon";
export interface FlightNavigationContext {
  paperCount: number;
  hasReviewContext: boolean;
  hasEvidence: boolean;
  hasGapCandidate: boolean;
}

/**
 * Navigation is deliberately narrower than the visible flight record.  A
 * station is clickable only when a local workbench has enough registered
 * context to show it without inventing a task or an evidence relation.
 */
export function flightRecordDestination(id: FlightRecordEntry["id"], context: FlightNavigationContext): FlightRecordView | null {
  if (id === "brief") return "discover";
  if (id === "candidates") return context.paperCount > 0 ? "graph" : null;
  if (["fulltext", "source-map", "facts", "evidence"].includes(id)) return context.hasReviewContext ? "reader" : null;
  if (id === "horizon") return context.hasEvidence || context.hasGapCandidate ? "horizon" : null;
  return null;
}
