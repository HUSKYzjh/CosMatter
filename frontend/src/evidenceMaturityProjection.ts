import type { EvidenceMaturityLevel, ImportedBundle } from "./model";

export const EVIDENCE_MATURITY_LEVELS: EvidenceMaturityLevel[] = ["literature_mentioned", "data_supported", "reproducibility_ready", "independently_reproduced"];

export function evidenceMaturityProjection(bundle: ImportedBundle) {
  const registry = bundle.evidenceMaturityRegistry;
  return {
    registry,
    counts: Object.fromEntries(EVIDENCE_MATURITY_LEVELS.map((level) => [level, registry?.claims.filter((claim) => claim.maturityLevel === level).length ?? 0])) as Record<EvidenceMaturityLevel, number>,
  };
}
