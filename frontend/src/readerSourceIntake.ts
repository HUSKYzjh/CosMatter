import { documentIdForReviewablePaper, evidenceForPaper } from "./evidenceLinking";
import type { PdfTaskStatus } from "./localApi";
import type { ImportedBundle } from "./model";
import type { ResearchSession } from "./researchSession";

/**
 * A private PDF can contribute to the evidence route only when it was attached
 * to the same human-screened candidate that is selected in the literature map.
 * Standalone PDF parsing remains useful for local Markdown and bibliography
 * navigation, but it must not be presented as a source for an EvidenceCard.
 */
export interface ReaderSourceIntake {
  selectedDocumentId: string | null;
  attachedDocumentId: string | null;
  matchingPrivatePdf: boolean;
  /** A reviewed Source Map exists; material facts and EvidenceCard may still be pending. */
  sourceMapRecorded: boolean;
  hasLinkedEvidence: boolean;
}

export function readerSourceIntake(bundle: ImportedBundle, session: ResearchSession, pdfTask: PdfTaskStatus | null): ReaderSourceIntake {
  const selectedDocumentId = documentIdForReviewablePaper(session.selectedNode);
  const attachedDocumentId = pdfTask?.candidate_document_id?.trim() || null;
  const matchingPrivatePdf = Boolean(selectedDocumentId && attachedDocumentId === selectedDocumentId);
  return {
    selectedDocumentId,
    attachedDocumentId,
    matchingPrivatePdf,
    sourceMapRecorded: Boolean(matchingPrivatePdf && pdfTask?.source_map_review_status === "recorded" && pdfTask.source_map_segment_count > 0),
    hasLinkedEvidence: evidenceForPaper(bundle, session.selectedNode).length > 0,
  };
}
/** Stable local identity for browser-only Source Map drafts. */
export function sourceMapTaskKey(pdfTask: PdfTaskStatus | null): string | null {
  if (!pdfTask) return null;
  return [pdfTask.document_id, pdfTask.audit_document_id, pdfTask.candidate_document_id ?? ""].join("\u241f");
}