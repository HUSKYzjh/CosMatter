import type { ImportedBundle } from "./model";
import { auditableAcceptedEvidence } from "./evidenceLinking";
import { evidenceProvenanceAuditComplete } from "./evidenceProvenanceAudit";

export type ComparisonReadinessReason = "evidence" | "provenance-audit" | "documents" | "comparison" | "conditions" | null;

export interface ResearchExtensionReadiness {
  acceptedEvidenceCount: number;
  distinctDocumentCount: number;
  supportingEvidenceCount: number;
  contradictingEvidenceCount: number;
  conditionClusterCount: number;
  linkedConditionClusterCount: number;
  ready: boolean;
  reason: ComparisonReadinessReason;
}

function isSupporting(stance: string): boolean {
  return ["support", "supports", "supporting"].includes(stance.trim().toLowerCase());
}

function isContradicting(stance: string): boolean {
  return ["contradict", "contradicts", "contradicting", "refute", "refutes"].includes(stance.trim().toLowerCase());
}

/** A cross-paper comparison may only use cards covered by the exact reviewed Source Map audit. */
export function hasExactEvidenceProvenanceAudit(bundle: ImportedBundle, acceptedEvidenceCount: number): boolean {
  return evidenceProvenanceAuditComplete(bundle.auditSummary.evidenceProvenance, acceptedEvidenceCount);
}

/** A comparison row must point at accepted evidence on both opposing sides. */
function hasAuditableContrast(
  row: ImportedBundle["conditionMatrix"][number],
  acceptedById: ReadonlyMap<string, ReturnType<typeof auditableAcceptedEvidence>[number]>,
): boolean {
  const supporting = row.supportingEvidenceIds
    .map((evidenceId) => acceptedById.get(evidenceId))
    .filter((card): card is ReturnType<typeof auditableAcceptedEvidence>[number] => Boolean(card && isSupporting(card.stance)));
  const contradicting = row.contradictingEvidenceIds
    .map((evidenceId) => acceptedById.get(evidenceId))
    .filter((card): card is ReturnType<typeof auditableAcceptedEvidence>[number] => Boolean(card && isContradicting(card.stance)));
  const documentIds = new Set([...supporting, ...contradicting].map((card) => card.provenance.documentId.trim()).filter(Boolean));
  return supporting.length > 0 && contradicting.length > 0 && documentIds.size >= 2 && row.differingFields.some((field) => field.trim().length > 0);
}

/** Exposes the same row-level gate used by the aggregate readiness summary. */
export function isAuditableConditionContrast(
  row: ImportedBundle["conditionMatrix"][number],
  bundle: ImportedBundle,
): boolean {
  const accepted = auditableAcceptedEvidence(bundle);
  return hasExactEvidenceProvenanceAudit(bundle, accepted.length)
    && hasAuditableContrast(row, new Map(accepted.map((card) => [card.evidenceId, card])));
}

/**
 * This is deliberately a readiness check, not a Gap generator. It keeps a
 * single reviewed observation or multiple cards from one document separate from an across-paper comparison.
 * A matrix row is usable only when it explicitly points to accepted opposing evidence from distinct papers.
 */
export function researchExtensionReadiness(bundle: ImportedBundle): ResearchExtensionReadiness {
  const accepted = auditableAcceptedEvidence(bundle);
  const acceptedById = new Map(accepted.map((card) => [card.evidenceId, card]));
  const distinctDocumentCount = new Set(accepted.map((card) => card.provenance.documentId.trim()).filter(Boolean)).size;
  const supportingEvidenceCount = accepted.filter((card) => isSupporting(card.stance)).length;
  const contradictingEvidenceCount = accepted.filter((card) => isContradicting(card.stance)).length;
  const conditionClusterCount = bundle.conditionMatrix.length;
  const exactProvenance = hasExactEvidenceProvenanceAudit(bundle, accepted.length);
  // Imported rows remain visible, but only become auditable after every accepted card has an exact reviewed map link.
  const linkedConditionClusterCount = exactProvenance
    ? bundle.conditionMatrix.filter((row) => hasAuditableContrast(row, acceptedById)).length
    : 0;
  const base = {
    acceptedEvidenceCount: accepted.length,
    distinctDocumentCount,
    supportingEvidenceCount,
    contradictingEvidenceCount,
    conditionClusterCount,
    linkedConditionClusterCount,
  };
  if (accepted.length < 2) return { ...base, ready: false, reason: "evidence" };
  if (!exactProvenance) return { ...base, ready: false, reason: "provenance-audit" };
  if (distinctDocumentCount < 2) return { ...base, ready: false, reason: "documents" };
  if (!supportingEvidenceCount || !contradictingEvidenceCount) return { ...base, ready: false, reason: "comparison" };
  if (!linkedConditionClusterCount) return { ...base, ready: false, reason: "conditions" };
  return { ...base, ready: true, reason: null };
}
