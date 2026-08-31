import type { PdfTaskStatus } from "./localApi";

/**
 * Selecting a paper or EvidenceCard changes only the reader's active PDF.
 * Tasks for other screened candidates remain registered, but cannot bleed
 * into the newly selected evidence session.
 */
export function pdfTaskForSession(tasks: readonly PdfTaskStatus[], documentId: string | null): PdfTaskStatus | null {
  if (!documentId) return null;
  return tasks.find((task) => task.candidate_document_id === documentId) ?? null;
}
