import type { AuditSummary } from "./model";

/**
 * True only when every accepted card has an exact reviewed Source Map match.
 *
 * Callers that know their current accepted-card count must pass it.  This
 * prevents a complete-looking audit for a stale subset from unlocking a
 * reader, graph, or comparison route after imported artifacts diverge.
 */
export function evidenceProvenanceAuditComplete(
  audit: AuditSummary["evidenceProvenance"],
  expectedAcceptedEvidenceCount?: number,
): boolean {
  return Boolean(
    audit
    && audit.acceptedEvidenceCount > 0
    && (expectedAcceptedEvidenceCount === undefined || audit.acceptedEvidenceCount === expectedAcceptedEvidenceCount)
    && audit.exactSourceMapMatchCount === audit.acceptedEvidenceCount
    && audit.manualLocatorOnlyCount === 0
    && audit.exactSourceMapMatchRate >= 1,
  );
}
