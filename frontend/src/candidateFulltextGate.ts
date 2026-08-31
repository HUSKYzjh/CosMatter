import { reviewablePaperForDocumentId } from "./evidenceLinking";
import type { CandidateScreening, CandidateScreeningCandidate } from "./localApi";
import type { LiteratureGraphNode } from "./model";

export type CandidateFulltextGateReason = "run" | "screening" | "candidate" | "decision" | "paper" | null;

export interface CandidateFulltextGate {
  ready: boolean;
  reason: CandidateFulltextGateReason;
}

/**
 * Recheck a PDF request at the page boundary. The server repeats this check,
 * but the UI must not transition into an apparently valid intake path for a
 * stale, unscreened, or graph-detached candidate.
 */
export function candidateFulltextGate(
  screening: CandidateScreening | null,
  runId: string | null | undefined,
  nodes: LiteratureGraphNode[],
  candidate: CandidateScreeningCandidate,
): CandidateFulltextGate {
  // A locally cached screening artifact must never authorize an intake after a
  // run switch, even if the two runs happen to reuse a candidate document ID.
  if (!runId || screening?.run_id !== runId) return { ready: false, reason: "run" };
  if (screening?.trust_status !== "human_reviewed_candidate_screening_not_scientific_evidence") return { ready: false, reason: "screening" };
  if (!screening.candidates.some((item) => item.document_id === candidate.document_id)) return { ready: false, reason: "candidate" };
  if (screening.decisions.find((item) => item.document_id === candidate.document_id)?.decision !== "include_for_fulltext") return { ready: false, reason: "decision" };
  if (!reviewablePaperForDocumentId(nodes, candidate.document_id)) return { ready: false, reason: "paper" };
  return { ready: true, reason: null };
}
