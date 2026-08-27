import type { EvidenceCard } from "./model";

export interface ConditionEvidenceLink {
  evidenceId: string;
  evidence: EvidenceCard | null;
}

/** Preserve matrix order and make absent IDs explicit rather than inferred. */
export function conditionEvidenceLinks(
  evidenceIds: readonly string[],
  evidenceCards: readonly EvidenceCard[],
): ConditionEvidenceLink[] {
  const evidenceById = new Map(evidenceCards.map((card) => [card.evidenceId, card]));
  return evidenceIds.map((evidenceId) => ({ evidenceId, evidence: evidenceById.get(evidenceId) ?? null }));
}
