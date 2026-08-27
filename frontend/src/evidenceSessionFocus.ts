import type { EvidenceCard, ImportedBundle } from "./model";
import { evidenceMatchesPaper, reviewablePaperForDocumentId } from "./evidenceLinking";
import { emptyResearchSession, selectEvidence, selectPaper, type ResearchSession } from "./researchSession";

/** Resolve an accepted EvidenceCard through an explicit reviewed paper-to-evidence graph path. */
export function focusEvidenceSession(bundle: ImportedBundle, evidence: EvidenceCard): ResearchSession | null {
  const paper = reviewablePaperForDocumentId(bundle.literatureGraph.nodes, evidence.provenance.documentId);
  if (!paper || !evidenceMatchesPaper(bundle, paper, evidence)) return null;
  return selectEvidence(selectPaper(emptyResearchSession(), paper), evidence);
}
