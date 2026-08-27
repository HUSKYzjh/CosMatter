import type { PdfTaskStatus } from "./localApi";

export type WorkflowNextState = "align-pdf-context" | "select-attached-paper" | "source-map" | "evidence-review" | "citation-map" | "standalone-markdown" | "literature-map" | "pdf-parsing" | "pdf-failed" | "waiting";

/** Decide the single next action shown on the orchestration page. */
export function workflowNextState(paperCount: number, pdfTask: PdfTaskStatus | null, selectedDocumentId: string | null = null): WorkflowNextState {
  const linkedCandidateId = pdfTask?.candidate_document_id?.trim() || null;
  const linkedCandidate = Boolean(linkedCandidateId);
  const selectedAttachedPaper = Boolean(linkedCandidateId && selectedDocumentId === linkedCandidateId);
  // The task selector is independent from the current paper session.  When
  // they name different candidates, surface that mismatch before any parsing
  // or failure state so one paper can never inherit another paper's route.
  if (linkedCandidate && selectedDocumentId && !selectedAttachedPaper) return "align-pdf-context";
  if (pdfTask?.state === "failed") return "pdf-failed";
  const parsed = Boolean(pdfTask?.markdown_ready && pdfTask.audit_state === "done");
  if (parsed && linkedCandidate && selectedAttachedPaper) return pdfTask?.source_map_review_status === "recorded" && (pdfTask.source_map_segment_count ?? 0) > 0 ? "evidence-review" : "source-map";
  if (parsed && linkedCandidate) return "select-attached-paper";
  if (parsed && ["resolved", "human_confirmed"].includes(pdfTask?.doi_status ?? "")) return "citation-map";
  if (parsed) return "standalone-markdown";
  if (paperCount > 0) return "literature-map";
  if (pdfTask) return "pdf-parsing";
  return "waiting";
}