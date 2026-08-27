import type { PdfTaskStatus } from "./localApi";
import { documentIdForReviewablePaper } from "./evidenceLinking";
import type { LiteratureGraphNode } from "./model";

export type PaperPdfIntakeState = "none" | "parsing" | "failed" | "source-map" | "evidence-review";

export interface PaperPdfIntake {
  state: PaperPdfIntakeState;
  documentId: string | null;
}
/** Find only the task explicitly attached to this reviewable candidate. */
export function pdfTaskForPaper(tasks: readonly PdfTaskStatus[] | null | undefined, node: LiteratureGraphNode | null): PdfTaskStatus | null {
  const documentId = documentIdForReviewablePaper(node);
  if (!documentId) return null;
  return tasks?.find((task) => task.candidate_document_id?.trim() === documentId) ?? null;
}

/**
 * Projects one private PDF task onto the currently selected paper.  A task for
 * another candidate is deliberately invisible to this paper's evidence route.
 */
export function paperPdfIntake(pdfTask: PdfTaskStatus | null | undefined, node: LiteratureGraphNode | null): PaperPdfIntake {
  const documentId = documentIdForReviewablePaper(node);
  if (!documentId || pdfTask?.candidate_document_id?.trim() !== documentId) return { state: "none", documentId };
  if (pdfTask.state === "failed") return { state: "failed", documentId };
  const parsed = Boolean(pdfTask.markdown_ready && pdfTask.audit_state === "done");
  if (!parsed) return { state: "parsing", documentId };
  if (pdfTask.source_map_review_status === "recorded" && pdfTask.source_map_segment_count > 0) return { state: "evidence-review", documentId };
  return { state: "source-map", documentId };
}