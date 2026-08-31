import { describe, expect, it } from "vitest";
import { EXECUTED_GAP_COUNTEREVIDENCE_BOUNDARY, hasExecutedGapCounterevidenceBoundary } from "./gapBoundaryReadiness";
import type { ResearchGapCandidate } from "./model";

const candidate = (counterevidenceBoundary?: ResearchGapCandidate["counterevidenceBoundary"]): ResearchGapCandidate => ({
  gapId: "gap-1", problemDescription: "Candidate", evidenceIds: ["ev-1", "ev-2"], conflictOrMissingEvidence: ["condition"], noveltyStatus: "unverified", actionability: "review", falsifiableHypothesis: "test", suggestedValidation: ["validate"], evidenceCompleteness: 1, reviewStatus: "candidate_requires_human_review", counterevidenceBoundary,
});

describe("hasExecutedGapCounterevidenceBoundary", () => {
  it("accepts only a recorded complete counterevidence boundary", () => {
    expect(hasExecutedGapCounterevidenceBoundary(candidate({ status: EXECUTED_GAP_COUNTEREVIDENCE_BOUNDARY, approvedQueryCount: 2, executedQueryCount: 2 }))).toBe(true);
    expect(hasExecutedGapCounterevidenceBoundary(candidate({ status: EXECUTED_GAP_COUNTEREVIDENCE_BOUNDARY, approvedQueryCount: 2, executedQueryCount: 1 }))).toBe(false);
  });

  it("keeps legacy or missing-boundary candidates out of completion state", () => {
    expect(hasExecutedGapCounterevidenceBoundary(candidate())).toBe(false);
  });

  it("requires a candidate boundary to match the current run-level counterevidence summary", () => {
    const bounded = candidate({ status: EXECUTED_GAP_COUNTEREVIDENCE_BOUNDARY, approvedQueryCount: 1, executedQueryCount: 1 });
    expect(hasExecutedGapCounterevidenceBoundary(bounded, { ready: true, plannedQueryCount: 1, executedQueryCount: 1 })).toBe(true);
    expect(hasExecutedGapCounterevidenceBoundary(bounded, { ready: true, plannedQueryCount: 2, executedQueryCount: 2 })).toBe(false);
  });
});
