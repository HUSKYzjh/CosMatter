import type { CandidateScreening } from "./localApi";

export type CandidateScreeningProgressState = "not_loaded" | "unavailable" | "in_progress" | "completed";

export interface CandidateScreeningProgress {
  state: CandidateScreeningProgressState;
  candidateCount: number;
  reviewedCount: number;
  pendingCount: number;
  includedCount: number;
}

/**
 * A display-only summary of the human screening gate.  Candidate metadata is
 * deliberately kept separate from accepted evidence: a completed checklist
 * permits controlled full-text intake, but still establishes no material fact.
 */
export function candidateScreeningProgress(
  screening: CandidateScreening | null,
  fallbackCandidateCount: number,
  screeningAvailable: boolean,
): CandidateScreeningProgress {
  if (!screening) {
    return {
      state: screeningAvailable ? "not_loaded" : "unavailable",
      candidateCount: fallbackCandidateCount,
      reviewedCount: 0,
      pendingCount: fallbackCandidateCount,
      includedCount: 0,
    };
  }
  const candidates = screening.candidates;
  const decisions = new Map(screening.decisions.map((decision) => [decision.document_id, decision]));
  const reviewed = candidates.filter((candidate) => (decisions.get(candidate.document_id)?.decision ?? "unreviewed") !== "unreviewed");
  const complete = candidates.length > 0
    && reviewed.length === candidates.length
    && screening.trust_status === "human_reviewed_candidate_screening_not_scientific_evidence";
  return {
    state: complete ? "completed" : "in_progress",
    candidateCount: candidates.length,
    reviewedCount: reviewed.length,
    pendingCount: Math.max(0, candidates.length - reviewed.length),
    includedCount: complete
      ? reviewed.filter((candidate) => decisions.get(candidate.document_id)?.decision === "include_for_fulltext").length
      : 0,
  };
}