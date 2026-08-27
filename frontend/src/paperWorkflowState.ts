import { documentIdForReviewablePaper } from "./evidenceLinking";
import { paperPdfIntake, pdfTaskForPaper, type PaperPdfIntakeState } from "./paperPdfIntake";
import type { CandidateScreeningDecision, PdfTaskStatus } from "./localApi";
import type { LiteratureGraphNode } from "./model";

export type PaperWorkflowState = "untracked" | "screening" | "included" | "parsing" | "source_map" | "evidence_review" | "accepted_evidence" | "failed" | "excluded";

/**
 * A display-only projection of one candidate's audited workflow position.
 * It never turns metadata, parsing state, or bibliography relations into facts.
 */
export function paperWorkflowState(
  node: LiteratureGraphNode,
  tasks: readonly PdfTaskStatus[] | null | undefined,
  decision: CandidateScreeningDecision["decision"] | "unreviewed" | null | undefined,
  acceptedEvidenceCount: number,
): PaperWorkflowState | null {
  if (!documentIdForReviewablePaper(node)) return null;
  if (acceptedEvidenceCount > 0) return "accepted_evidence";
  const intake: PaperPdfIntakeState = paperPdfIntake(pdfTaskForPaper(tasks, node), node).state;
  if (intake === "failed") return "failed";
  if (intake === "parsing") return "parsing";
  if (intake === "source-map") return "source_map";
  if (intake === "evidence-review") return "evidence_review";
  if (decision === "exclude") return "excluded";
  if (decision === "include_for_fulltext") return "included";
  if (decision === "needs_metadata_review" || decision === "unreviewed") return "screening";
  return "untracked";
}