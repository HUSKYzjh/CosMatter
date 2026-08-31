import { describe, expect, it } from "vitest";

import { readBundle } from "./model";

const base = { mission: { mission_id: "mission-1", question: "q", material: "BiFeO3", property_name: "phase", scope: "films" } };
const reconciliation = {
  trust_status: "human_reviewed_cross_source_identity_not_scientific_evidence",
  source: { evidence_id: "ev-1", document_id: "doc-1" },
  mappings: [
    { openalex_work_id: "W123", crossref_doi: "10.1000/example", status: "matched", basis: "Human DOI check" },
    { openalex_work_id: "W999", crossref_doi: "10.1000/conflict", status: "conflict", basis: "Year and author disagreement" },
  ],
};

describe("relation reconciliation UI projection", () => {
  it("keeps only explicit human-reviewed mappings and their conflict state", () => {
    const parsed = readBundle({ ...base, relation_reconciliation: { ...reconciliation, revision_history: [{ revision: 1, recorded_at: "2026-08-31T09:30:00Z", mapping_count: 2, status_counts: { matched: 1, conflict: 1, unresolved: 0 } }] } }).relationReconciliation;
    expect(parsed).toMatchObject({ sourceEvidenceId: "ev-1", sourceDocumentId: "doc-1" });
    expect(parsed?.mappings.map((item) => item.status)).toEqual(["matched", "conflict"]);
    expect(parsed?.revisionHistory[0]).toMatchObject({ revision: 1, mappingCount: 2, statusCounts: { conflict: 1 } });
  });

  it("rejects malformed or implicit cross-source mappings instead of guessing identity", () => {
    const parsed = readBundle({ ...base, relation_reconciliation: { ...reconciliation, mappings: [{ openalex_work_id: "W123", crossref_doi: "10.1000/example", status: "matched" }] } }).relationReconciliation;
    expect(parsed).toBeNull();
  });

  it("rejects revision summaries with extra fields or inconsistent counts", () => {
    const malformed = { ...reconciliation, revision_history: [{ revision: 1, recorded_at: "2026-08-31T09:30:00Z", mapping_count: 2, status_counts: { matched: 2, conflict: 1, unresolved: 0 }, reviewer: "must not project" }] };
    expect(readBundle({ ...base, relation_reconciliation: malformed }).relationReconciliation).toBeNull();
  });
});
