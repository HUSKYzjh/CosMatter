import type { ResearchGapCandidate } from "./model";

export const EXECUTED_GAP_COUNTEREVIDENCE_BOUNDARY = "all_approved_counterevidence_queries_recorded";

export interface CounterevidenceBoundaryExpectation {
  ready: boolean;
  plannedQueryCount: number;
  executedQueryCount: number;
}

/** A pending Gap candidate is displayable only; this gate identifies an audited execution boundary. */
export function hasExecutedGapCounterevidenceBoundary(
  candidate: ResearchGapCandidate,
  expected?: CounterevidenceBoundaryExpectation,
): boolean {
  const boundary = candidate.counterevidenceBoundary;
  const boundaryComplete = Boolean(
    boundary
    && boundary.status === EXECUTED_GAP_COUNTEREVIDENCE_BOUNDARY
    && Number.isInteger(boundary.approvedQueryCount)
    && boundary.approvedQueryCount > 0
    && boundary.executedQueryCount === boundary.approvedQueryCount,
  );
  if (!boundaryComplete) return false;
  if (!expected) return true;
  // A persisted candidate may be restored beside a newer run-level audit. It
  // remains displayable, but cannot be labelled as verified until its bounded
  // execution record agrees with the current task summary.
  return expected.ready
    && expected.plannedQueryCount === boundary!.approvedQueryCount
    && expected.executedQueryCount === boundary!.executedQueryCount;
}
