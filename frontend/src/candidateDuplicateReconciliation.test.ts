import { describe, expect, it } from "vitest";

import { readBundle } from "./model";

const mission = { mission_id: "mission-1", question: "q", material: "BiFeO3", property_name: "phase", scope: "films" };
const summary = { conflicting_doi_review_required_count: 0, partial_doi_review_required_count: 0, same_doi_merge_allowed_count: 0, title_only_review_required_count: 1 };
const titleOnlyQueue = {
  trust_status: "derived_exact_title_duplicate_queue_not_scientific_evidence",
  group_count: 1,
  groups: [{ group_id: "candidate_duplicate_aaaaaaaaaaaaaaaaaaaaaaaa", document_ids: ["doc-a", "doc-b"], doi_state: "title_only_review_required", canonical_document_id: null, alias_document_ids: [] }],
  summary,
};

describe("candidate duplicate reconciliation projection", () => {
  it("keeps title-only candidates unresolved without inventing an alias", () => {
    const bundle = readBundle({ mission, candidate_duplicate_queue: titleOnlyQueue, literature_graph: { nodes: [{ node_id: "paper:doc-a", kind: "candidate_paper", label: "Same title", trust_status: "metadata" }], edges: [] } });
    expect(bundle.candidateDuplicateQueue?.groups[0]).toMatchObject({ doiState: "title_only_review_required", canonicalDocumentId: null, aliasDocumentIds: [] });
    expect(bundle.candidateDuplicateReconciliation).toBeNull();
  });

  it("accepts only a reconciliation bound to the current queue", () => {
    const queue = {
      ...titleOnlyQueue,
      groups: [{ ...titleOnlyQueue.groups[0], doi_state: "same_doi_merge_allowed", canonical_document_id: "doc-a", alias_document_ids: ["doc-b"] }],
      summary: { ...summary, same_doi_merge_allowed_count: 1, title_only_review_required_count: 0 },
    };
    const counts = { same_work_count: 1, distinct_works_count: 0, unresolved_count: 0, automatic_doi_count: 1, human_decision_count: 0 };
    const reconciliation = {
      trust_status: "candidate_identity_alias_layer_not_scientific_evidence",
      resolutions: [{ group_id: queue.groups[0].group_id, resolution: "same_work", basis: "exact_normalized_doi", canonical_document_id: "doc-a", alias_document_ids: ["doc-b"] }],
      summary: counts,
      revision_history: [{ revision: 1, recorded_at: "2026-09-08T10:00:00+00:00", resolution_counts: counts }],
    };
    const parsed = readBundle({ mission, candidate_duplicate_queue: queue, candidate_duplicate_reconciliation: reconciliation });
    expect(parsed.candidateDuplicateReconciliation?.resolutions[0]).toMatchObject({ resolution: "same_work", basis: "exact_normalized_doi", canonicalDocumentId: "doc-a" });
  });

  it("rejects an automatic DOI alias attached to a title-only group", () => {
    const counts = { same_work_count: 1, distinct_works_count: 0, unresolved_count: 0, automatic_doi_count: 1, human_decision_count: 0 };
    const malformed = {
      trust_status: "candidate_identity_alias_layer_not_scientific_evidence",
      resolutions: [{ group_id: titleOnlyQueue.groups[0].group_id, resolution: "same_work", basis: "exact_normalized_doi", canonical_document_id: "doc-a", alias_document_ids: ["doc-b"] }],
      summary: counts,
      revision_history: [{ revision: 1, recorded_at: "2026-09-08T10:00:00Z", resolution_counts: counts }],
    };
    expect(readBundle({ mission, candidate_duplicate_queue: titleOnlyQueue, candidate_duplicate_reconciliation: malformed }).candidateDuplicateReconciliation).toBeNull();
  });

  it("withholds human-looking duplicate decisions from delegated technical trials", () => {
    const counts = { same_work_count: 0, distinct_works_count: 1, unresolved_count: 0, automatic_doi_count: 0, human_decision_count: 1 };
    const reconciliation = {
      trust_status: "candidate_identity_alias_layer_not_scientific_evidence",
      resolutions: [{ group_id: titleOnlyQueue.groups[0].group_id, resolution: "distinct_works", basis: "distinct_study_same_title", canonical_document_id: null, alias_document_ids: [] }],
      summary: counts,
      revision_history: [{ revision: 1, recorded_at: "2026-09-08T10:00:00Z", resolution_counts: counts }],
    };
    const parsed = readBundle({ mission, delegated_test_boundary: true, candidate_duplicate_queue: titleOnlyQueue, candidate_duplicate_reconciliation: reconciliation });
    expect(parsed.candidateDuplicateQueue).not.toBeNull();
    expect(parsed.candidateDuplicateReconciliation).toBeNull();
  });
});
