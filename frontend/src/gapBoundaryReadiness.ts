import type { ResearchGapCandidate } from "./model";

export const EXECUTED_GAP_COUNTEREVIDENCE_BOUNDARY = "all_approved_counterevidence_queries_recorded";

/** A pending Gap candidate is displayable only; this gate identifies an audited execution boundary. */
export function hasExecutedGapCounterevidenceBoundary(candidate: ResearchGapCandidate): boolean {
  const boundary = candidate.counterevidenceBoundary;
  return Boolean(
    boundary
    && boundary.status === EXECUTED_GAP_COUNTEREVIDENCE_BOUNDARY
    && Number.isInteger(boundary.approvedQueryCount)
    && boundary.approvedQueryCount > 0
    && boundary.executedQueryCount === boundary.approvedQueryCount,
  );
}
