import type { ConditionMatrixRow } from "./model";

/** Prefer the comparison cluster that explicitly contains the current EvidenceCard. */
export function preferredConditionCluster(rows: readonly ConditionMatrixRow[], evidenceId: string): string {
  return rows.find((row) => row.supportingEvidenceIds.includes(evidenceId) || row.contradictingEvidenceIds.includes(evidenceId))?.conditionCluster
    ?? rows[0]?.conditionCluster
    ?? "";
}
