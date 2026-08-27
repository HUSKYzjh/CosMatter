import type { EvidenceCard, ResearchGapCandidate } from "./model";

/**
 * A Gap candidate is reviewable in the current session only when its recorded
 * evidence list explicitly contains the selected, provenance-linked card.
 * This prevents a global list of candidates from being presented as a
 * conclusion about whichever paper the researcher is currently reading.
 */
export function gapCandidatesForEvidence(candidates: ResearchGapCandidate[], evidence: EvidenceCard | null): ResearchGapCandidate[] {
  if (!evidence) return [];
  return candidates.filter((candidate) => candidate.evidenceIds.includes(evidence.evidenceId));
}
