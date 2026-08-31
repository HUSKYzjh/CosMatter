import type { EvidenceCard, ImportedBundle, ResearchGapCandidate } from "./model";
import { auditableAcceptedEvidence } from "./evidenceLinking";

export interface GapEvidenceReferences {
  linked: EvidenceCard[];
  missingIds: string[];
}

/** Resolve a candidate's recorded evidence IDs without inventing a source link. */
export function gapEvidenceReferences(candidate: ResearchGapCandidate, evidenceCards: readonly EvidenceCard[]): GapEvidenceReferences {
  const byId = new Map(evidenceCards.map((card) => [card.evidenceId, card]));
  const linked: EvidenceCard[] = [];
  const missingIds: string[] = [];
  candidate.evidenceIds.forEach((id) => {
    const card = byId.get(id);
    if (card) linked.push(card);
    else missingIds.push(id);
  });
  return { linked, missingIds };
}

/**
 * A Gap candidate remains displayable when its old references no longer
 * resolve, but it cannot advance the research route until every basis card is
 * unique, current, non-synthetic, provenance-linked evidence.
 */
export function hasAuditableGapEvidenceBasis(candidate: ResearchGapCandidate, bundle: ImportedBundle): boolean {
  const evidenceIds = candidate.evidenceIds;
  if (evidenceIds.length < 2 || new Set(evidenceIds).size !== evidenceIds.length) return false;
  const auditableIds = new Set(auditableAcceptedEvidence(bundle).map((card) => card.evidenceId));
  return evidenceIds.every((evidenceId) => auditableIds.has(evidenceId));
}
