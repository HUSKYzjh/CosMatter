import { evidenceForPaper } from "./evidenceLinking";
import type { ImportedBundle, LiteratureGraphNode } from "./model";

export type GraphPaperHandoffMode = "register-source" | "verify-evidence";

/**
 * The map must always provide a path into the reader after a paper is selected.
 * An absent EvidenceCard is not an absent next step: it means source registration
 * is still required. This helper deliberately relies only on reviewed graph links.
 */
export function graphPaperHandoff(bundle: ImportedBundle, paper: LiteratureGraphNode | null): {
  mode: GraphPaperHandoffMode;
  linkedEvidenceCount: number;
} {
  const linkedEvidenceCount = evidenceForPaper(bundle, paper).length;
  return {
    mode: linkedEvidenceCount ? "verify-evidence" : "register-source",
    linkedEvidenceCount,
  };
}