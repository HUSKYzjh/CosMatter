export type ReaderSourceAction =
  | "review_imported_evidence"
  | "record_source_locations"
  | "await_private_parsing"
  | "retry_authorized_pdf"
  | "align_selected_paper"
  | "choose_authorized_pdf"
  | "complete_screening";

/**
 * The reader never infers permission from metadata. This display-only
 * classifier names one next researcher action for the selected paper.
 */
export function readerSourceAction(input: {
  hasLinkedEvidence: boolean;
  hasMatchingPrivatePdf: boolean;
  privatePdfParsing: boolean;
  privatePdfFailed: boolean;
  hasOtherPaperPdf: boolean;
  screeningAllowsSourceReview: boolean;
}): ReaderSourceAction {
  if (input.hasLinkedEvidence) return "review_imported_evidence";
  if (input.privatePdfFailed) return "retry_authorized_pdf";
  if (input.privatePdfParsing) return "await_private_parsing";
  if (input.hasMatchingPrivatePdf) return "record_source_locations";
  if (input.hasOtherPaperPdf) return "align_selected_paper";
  if (input.screeningAllowsSourceReview) return "choose_authorized_pdf";
  return "complete_screening";
}
