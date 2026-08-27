import { documentIdForReviewablePaper } from "./evidenceLinking";
import type { ImportedBundle } from "./model";
import type { ResearchSession } from "./researchSession";

/**
 * Material facts are local, document-bound observations. They must never be
 * shown as if they belonged to a different paper selected in the reader.
 */
export function materialFactsForSelectedPaper(bundle: ImportedBundle, session: ResearchSession) {
  const selectedDocumentId = documentIdForReviewablePaper(session.selectedNode);
  const ledger = bundle.materialFacts;
  return selectedDocumentId && ledger?.documentId === selectedDocumentId ? ledger : null;
}