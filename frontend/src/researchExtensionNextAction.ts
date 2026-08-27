import type { CounterevidenceReadiness } from "./counterevidenceReadiness";
import type { ResearchExtensionReadiness } from "./researchExtensionReadiness";

export type ResearchExtensionNextAction = "comparison-evidence" | "provenance-audit" | "counterevidence" | "condition-matrix" | "gap-candidates" | "review-candidates";

/**
 * Keeps the extension page to one action at a time. This is navigation state,
 * not a claim that the resulting scientific comparison is valid.
 */
export function researchExtensionNextAction(
  comparison: Pick<ResearchExtensionReadiness, "ready" | "reason">,
  counterevidence: Pick<CounterevidenceReadiness, "ready">,
  candidateCount: number,
): ResearchExtensionNextAction {
  if (!comparison.ready && comparison.reason === "provenance-audit") return "provenance-audit";
  if (!comparison.ready && comparison.reason !== "conditions") return "comparison-evidence";
  if (!counterevidence.ready) return "counterevidence";
  if (comparison.reason === "conditions") return "condition-matrix";
  if (!candidateCount) return "gap-candidates";
  return "review-candidates";
}