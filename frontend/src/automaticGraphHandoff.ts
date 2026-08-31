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

/**
 * A researcher may open the graph manually while the automatic completion
 * response is in flight.  That already satisfies the one-time handoff; leave
 * no pending marker that could later pull them away from the bridge again.
 */
export function automaticGraphHandoffAlreadySettled(
  pending: boolean,
  automaticState: AutomaticHandoffState | null | undefined,
  currentView: JourneyView,
  hasNavigableGraph: boolean,
): boolean {
  return pending && automaticState === "succeeded" && currentView === "graph" && hasNavigableGraph;
}
