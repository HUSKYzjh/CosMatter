import type { CandidateScreening, PdfTaskStatus } from "./localApi";

/**
 * Returns true only for a persisted human decision that explicitly includes
 * the currently selected graph paper for private full-text review. Candidate
 * metadata stays navigation-only until this decision exists.
 */
export function screeningAllowsSourceReview(
  screening: CandidateScreening | null,
  runId: string | null | undefined,
  documentId: string | null,
): boolean {
  if (!screening || !runId || screening.run_id !== runId || !documentId) return false;
  if (screening.trust_status !== "human_reviewed_candidate_screening_not_scientific_evidence") return false;
  const isCurrentCandidate = screening.candidates.some((candidate) => candidate.document_id === documentId);
  const decision = screening.decisions.find((item) => item.document_id === documentId);
  return isCurrentCandidate && decision?.decision === "include_for_fulltext";
}

/**
 * A private MinerU result is relevant to the reader rail only if the task was
 * created for the currently selected candidate. A completed PDF for another
 * paper cannot make this paper look source-ready.
 */
export function completedPrivateSourceMapMatchesPaper(
  task: PdfTaskStatus | null,
  documentId: string | null,
): boolean {
  return Boolean(
    task
    && documentId
    && task.candidate_document_id === documentId
    && task.markdown_ready
    && task.audit_state === "done",
  );
}
