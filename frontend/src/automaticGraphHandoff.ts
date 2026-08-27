import type { JourneyView } from "./missionJourney";

export type AutomaticHandoffState = "queued" | "running" | "succeeded" | "failed" | "cancelled";

/**
 * Keep the question-mode handoff deterministic across the launch transition.
 * An automatic retrieval may finish before the launch animation has reached
 * the bridge; in that case the pending handoff waits for the bridge instead
 * of silently leaving a ready literature graph behind it.  It never moves a
 * researcher away from another page.
 */
export function automaticGraphHandoffTarget(
  pending: boolean,
  automaticState: AutomaticHandoffState | null | undefined,
  currentView: JourneyView,
  hasNavigableGraph: boolean,
): "graph" | null {
  return pending && automaticState === "succeeded" && currentView === "workflow" && hasNavigableGraph
    ? "graph"
    : null;
}