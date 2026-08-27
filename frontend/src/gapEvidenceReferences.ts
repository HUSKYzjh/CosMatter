import type { EvidenceCard, ResearchGapCandidate } from "./model";

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