import { documentIdForReviewablePaper } from "./evidenceLinking";
import { candidatePdfAction, paperPdfIntake, pdfTaskForPaper } from "./paperPdfIntake";
import type { CandidateScreeningDecision, PdfTaskStatus, SavedSourceParseTask } from "./localApi";
import type { LiteratureGraphNode } from "./model";

export type PaperWorkflowState = "untracked" | "screening" | "included" | "parsing" | "source_recorded" | "source_map" | "evidence_review" | "provenance_audit" | "accepted_evidence" | "failed" | "excluded";

/**
 * A display-only projection of one candidate's audited workflow position.
 * It never turns metadata, parsing state, or bibliography relations into facts.
 */
export function paperWorkflowState(
  node: LiteratureGraphNode,
  tasks: readonly PdfTaskStatus[] | null | undefined,
  decision: CandidateScreeningDecision["decision"] | "unreviewed" | null | undefined,
  acceptedEvidenceCount: number,
  acceptedEvidenceProvenanceAudited = true,
  recordedTask?: SavedSourceParseTask,
): PaperWorkflowState | null {
  const documentId = documentIdForReviewablePaper(node);
  if (!documentId) return null;
  if (acceptedEvidenceCount > 0) return acceptedEvidenceProvenanceAudited ? "accepted_evidence" : "provenance_audit";
  const local = pdfTaskForPaper(tasks, node);
  const action = candidatePdfAction(local, recordedTask?.document_id === documentId ? recordedTask : null);
  if (action === "recorded_done") return "source_recorded";
  if (action === "recorded_reader") return recordedTask?.source_map_segment_count ? "evidence_review" : "source_map";
  if (action === "recorded_active" || action === "open_bridge") return "parsing";
  if (action === "retry_pdf") return "failed";
  const intake = paperPdfIntake(local, node).state;
  if (intake === "source-map") return "source_map";
  if (intake === "evidence-review") return "evidence_review";
  if (decision === "exclude") return "excluded";
  if (decision === "include_for_fulltext") return "included";
  if (decision === "needs_metadata_review" || decision === "unreviewed") return "screening";
  return "untracked";
}
