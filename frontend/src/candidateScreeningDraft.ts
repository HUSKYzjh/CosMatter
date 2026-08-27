import type { CandidateScreening, CandidateScreeningCandidate, CandidateScreeningDecision } from "./localApi";

export type ScreeningDraft = Record<string, CandidateScreeningDecision>;

export function screeningDraftForCandidates(screening: CandidateScreening): ScreeningDraft {
  const recorded = new Map(screening.decisions.map((item) => [item.document_id, item]));
  return Object.fromEntries(screening.candidates.map((candidate) => [candidate.document_id, recorded.get(candidate.document_id) ?? {
    document_id: candidate.document_id,
    decision: "unreviewed",
    reason_codes: [],
  }]));
}

export function isScreeningComplete(candidates: CandidateScreeningCandidate[], draft: ScreeningDraft): boolean {
  return candidates.length > 0 && candidates.every((candidate) => {
    const decision = draft[candidate.document_id];
    return Boolean(decision && decision.decision !== "unreviewed" && decision.reason_codes.length > 0);
  });
}

/** Serialize exactly the candidates visible in this task, never stale decisions. */
export function screeningSubmission(candidates: CandidateScreeningCandidate[], draft: ScreeningDraft): CandidateScreeningDecision[] {
  return candidates.map((candidate) => draft[candidate.document_id] ?? {
    document_id: candidate.document_id,
    decision: "unreviewed",
    reason_codes: [],
  });
}
/**
 * Full-text processing may use only an already persisted human decision.
 * Browser edits are intentionally excluded until the complete checklist has
 * been submitted and reloaded from the local audit artifact.
 */
export function recordedIncludedCandidates(screening: CandidateScreening | null): CandidateScreeningCandidate[] {
  if (!screening || screening.trust_status !== "human_reviewed_candidate_screening_not_scientific_evidence") return [];
  const included = new Set(screening.decisions.filter((decision) => decision.decision === "include_for_fulltext").map((decision) => decision.document_id));
  return screening.candidates.filter((candidate) => included.has(candidate.document_id));
}
