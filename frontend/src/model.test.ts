import { describe, expect, it } from "vitest";

import { demoBundle, readBundle } from "./model";

describe("readBundle", () => {
  it("reads the complete safe UI projection", () => {
    const bundle = readBundle({ schema_version: "1.0", mission: { mission_id: "mission_1", question: "question", material: "BiFeO3", property_name: "phase", scope: "films" }, fleet_assignment: { display_name_en: "Route Diagnostics Fleet", mission_type: "literature_discrepancy", release_gate: "review" }, status: { mission_state: "REVIEW", retry_count: 1, retry_budget: 2, return_reason: null }, stations: [{ station_type: "question_intake", status: "done" }], facilities: [{ facility_type: "condition_differential", status: "queued" }], evidence_cards: [{ evidence_id: "evidence_1", claim: "A bounded claim", stance: "support", conditions: { strain: 1 }, quote: "Short quote", review_status: "accepted", provenance: { document_id: "doc_1", locator: "p.1", source: "fixture", access_policy: "authorized" } }, { evidence_id: "rejected", claim: "Hidden", quote: "Hidden", review_status: "rejected", provenance: {} }], condition_matrix: [{ condition_cluster: "film", supporting_evidence_ids: ["evidence_1"], contradicting_evidence_ids: [], differing_fields: ["strain"], unknowns: ["thickness"] }], timeline: [{ station_type: "review", action: "Reviewed", state: "REVIEW", occurred_at: "2026-01-01" }], reviewed_source_map_summary: { document_count: 2, segment_count: 5, document_ids: ["doc_1", "doc_2"] }, reviewed_material_fact_summary: { document_count: 2, fact_count: 7 }, audit_summary: { report_evidence: { accepted_evidence_count: 1, manifest_coverage: 1, gap_evidence_coverage: 1, structured_report_identifier_coverage: 1, accepted_evidence_locator_rendered_coverage: 1, executed_gap_counterevidence_boundary_count: 2, gap_counterevidence_boundary_rendered_coverage: 1 }, evidence_provenance: { accepted_evidence_count: 1, exact_source_map_match_count: 1, manual_locator_only_count: 0, exact_source_map_match_rate: 1 }, external_retrieval: { sciverse_agentic_search_count: 2 } }, literature_relations: { trust_status: "metadata", edges: [{ target: "work" }] }, mission_report: { summary: "Approved", limitations: ["limited"], next_steps: ["extend"] } });
    expect(bundle.evidenceCards).toHaveLength(1);
    expect(bundle.evidenceCards[0].evidenceId).toBe("evidence_1");
    expect(bundle.conditionMatrix[0].unknowns).toEqual(["thickness"]);
    expect(bundle.literatureRelations?.edgeCount).toBe(1);
    expect(bundle.sourceMapSummary).toEqual({ documentCount: 2, segmentCount: 5, documentIds: ["doc_1", "doc_2"] });
    expect(bundle.materialFactSummary).toEqual({ documentCount: 2, factCount: 7 });
    expect(bundle.auditSummary.evidenceProvenance?.exactSourceMapMatchCount).toBe(1);
    expect(bundle.auditSummary.reportEvidence).toMatchObject({
      executedGapCounterevidenceBoundaryCount: 2,
      gapCounterevidenceBoundaryRenderedCoverage: 1,
    });
    expect(bundle.auditSummary.sciverseAgenticSearchCount).toBe(2);
    expect(bundle.auditSummary.evaluation.retrieval).toBeNull();
    expect(bundle.report?.summary).toBe("Approved");
  });

  it("projects only aggregate human-reviewed evaluation metrics", () => {
    const bundle = readBundle({
      mission: { mission_id: "m", question: "q", material: "BiFeO3", property_name: "phase", scope: "films" },
      audit_summary: {
        evaluation: {
          evidence_quality: { evidence_count: 8, predicted_contradiction_count: 3, citation_precision: 0.875, condition_completeness: 0.75, contradiction_precision: 0.666667 },
          retrieval: { corpus_id: "private-corpus", k: 10, retrieved_count: 10, gold_relevant_count: 3, precision_at_k: 0.3, recall_at_k: 1, ndcg_at_k: 0.8 },
          material_facts: { corpus_id: "private-corpus", gold_fact_count: 20, reviewed_fact_count: 18, precision: 0.8, recall: 0.72, f1: 0.758, unit_match_accuracy: 0.9 },
          research_gaps: { candidate_count: 4, expert_approval_rate: 0.75, mean_novelty_rating: 4.2, mean_actionability_rating: 4, evidence_completeness_rate: 1 },
        },
      },
    });
    expect(bundle.auditSummary.evaluation.evidenceQuality).toMatchObject({ evidenceCount: 8, citationPrecision: 0.875 });
    expect(bundle.auditSummary.evaluation.retrieval).toMatchObject({ k: 10, ndcgAtK: 0.8 });
    expect(bundle.auditSummary.evaluation.materialFacts).toMatchObject({ f1: 0.758, unitMatchAccuracy: 0.9 });
    expect(bundle.auditSummary.evaluation.researchGaps).toMatchObject({ meanNoveltyRating: 4.2, candidateCount: 4 });
    expect(JSON.stringify(bundle.auditSummary.evaluation)).not.toContain("private-corpus");
  });

  it("projects only aggregate corpus, annotation, and bibliography readiness", () => {
    const bundle = readBundle({
      mission: { mission_id: "m", question: "q", material: "BiFeO3", property_name: "phase", scope: "films" },
      audit_summary: {
        submission_readiness: {
          frozen_corpus: { corpus_id: "private-corpus", expected_document_count: 90, frozen_document_count: 90, expected_count_matched: true, document_id_uniqueness_valid: true, doi_present_count: 88, doi_missing_count: 2, authorized_access_boundary_valid: true, evaluation_gate: "ready_for_private_human_annotation" },
          human_annotation: { corpus_id: "private-corpus", frozen_document_count: 90, annotation_file_status: "human_reviewed_gold_standard_for_evaluation", relevance_counts: { unreviewed: 0, relevant: 50, partially_relevant: 20, not_relevant: 20 }, documents_with_evidence_annotations: 30, documents_with_material_fact_annotations: 25, documents_with_comparison_annotations: 18, documents_with_gap_annotations: 5, relevance_evaluation_gate: "ready_for_human_retrieval_evaluation" },
          bibliographic_source: { corpus_id: "private-corpus", frozen_document_count: 90, documents_with_reviewed_bibliographic_source: 90, distinct_bibliographic_source_count: 3, bibliographic_source_coverage_gate: "ready_for_source_traceable_evaluation" },
        },
      },
    });
    expect(bundle.auditSummary.submissionReadiness.frozenCorpus).toMatchObject({ frozenDocumentCount: 90, doiMissingCount: 2 });
    expect(bundle.auditSummary.submissionReadiness.humanAnnotation?.relevanceCounts.unreviewed).toBe(0);
    expect(bundle.auditSummary.submissionReadiness.bibliographicSource?.documentsWithReviewedBibliographicSource).toBe(90);
    expect(JSON.stringify(bundle.auditSummary.submissionReadiness)).not.toContain("private-corpus");
  });

  it("reads only complete human-review-required Research Gap candidates", () => {
    const bundle = readBundle({
      mission: { mission_id: "m", question: "q", material: "BiFeO3", property_name: "phase", scope: "films" },
      research_gap_candidates: [
        { schema_version: "1.0", gap_id: "gap_001", material: "BiFeO3", property_name: "phase", problem_description: "Condition discrepancy", evidence_ids: ["e1", "e2"], conflict_or_missing_evidence: ["conflicting_condition:strain"], novelty_status: "unverified_requires_bounded_literature_review", actionability: "compare strain", falsifiable_hypothesis: "strain explains it", suggested_validation: ["retrieve counterevidence"], evidence_completeness: 1, review_status: "candidate_requires_human_review" },
        { gap_id: "invalid", problem_description: "missing evidence", review_status: "accepted" },
      ],
    });
    expect(bundle.researchGapCandidates).toHaveLength(1);
    expect(bundle.researchGapCandidates[0].evidenceIds).toEqual(["e1", "e2"]);
    expect(bundle.researchGapCandidates[0].reviewStatus).toBe("candidate_requires_human_review");
  });

  it("keeps only connected bounded literature graph records", () => {
    const bundle = readBundle({
      schema_version: "1.0",
      mission: { mission_id: "m", question: "q", material: "BiFeO3", property_name: "phase", scope: "films" },
      literature_graph: {
        trust_status: "navigation_only",
        nodes: [{ node_id: "paper:1", kind: "candidate_paper", label: "Paper", trust_status: "metadata", source: "Sciverse", score: 0.99 }],
        edges: [{ source_id: "paper:1", target_id: "missing", edge_type: "bad", relation_source: "fixture", trust_status: "metadata" }],
      },
    });
    expect(bundle.literatureGraph.nodes).toHaveLength(1);
    expect(bundle.literatureGraph.edges).toHaveLength(0);
    expect(JSON.stringify(bundle.literatureGraph)).not.toContain("score");
  });

  it("ships a dense but explicitly synthetic graph fixture for canvas verification", () => {
    expect(demoBundle.literatureGraph.trustStatus).toContain("synthetic_demo");
    expect(demoBundle.literatureGraph.nodes.length).toBeGreaterThanOrEqual(30);
    expect(demoBundle.literatureGraph.edges.length).toBeGreaterThanOrEqual(40);
    expect(demoBundle.literatureGraph.nodes.filter((node) => node.kind === "candidate_paper")).toHaveLength(20);
  });
  it("requires a complete mission boundary", () => {
    expect(() => readBundle({ mission: { mission_id: "m", question: "q" } })).toThrow("mission.material");
  });
});


describe("Gap counterevidence boundary projection", () => {
  it("retains only the bounded summary, not query text or raw response data", () => {
    const hash = "a".repeat(64);
    const bundle = readBundle({
      mission: { mission_id: "m", question: "q", material: "BiFeO3", property_name: "phase", scope: "films" },
      research_gap_candidates: [{
        schema_version: "1.1", gap_id: "gap_001", material: "BiFeO3", property_name: "phase",
        problem_description: "Condition discrepancy", evidence_ids: ["e1", "e2"],
        conflict_or_missing_evidence: ["conflicting_condition:strain"], novelty_status: "unverified",
        actionability: "compare strain", falsifiable_hypothesis: "strain explains it",
        suggested_validation: ["retrieve counterevidence"], evidence_completeness: 1,
        review_status: "candidate_requires_human_review",
        counterevidence_boundary: {
          status: "all_approved_counterevidence_queries_recorded",
          approved_query_count: 2, executed_query_count: 2,
          query_sha256: [hash, "b".repeat(64)], candidate_history_sha256: hash,
        },
      }],
    });
    expect(bundle.researchGapCandidates[0].counterevidenceBoundary).toEqual({
      status: "all_approved_counterevidence_queries_recorded", approvedQueryCount: 2, executedQueryCount: 2,
    });
    expect(JSON.stringify(bundle.researchGapCandidates)).not.toContain("query_sha256");
  });

  it("does not treat a malformed v1.1 boundary as attested", () => {
    const bundle = readBundle({
      mission: { mission_id: "m", question: "q", material: "BiFeO3", property_name: "phase", scope: "films" },
      research_gap_candidates: [{
        schema_version: "1.1", gap_id: "gap_001", material: "BiFeO3", property_name: "phase",
        problem_description: "Condition discrepancy", evidence_ids: ["e1", "e2"],
        conflict_or_missing_evidence: ["conflicting_condition:strain"], novelty_status: "unverified",
        actionability: "compare strain", falsifiable_hypothesis: "strain explains it",
        suggested_validation: ["retrieve counterevidence"], evidence_completeness: 1,
        review_status: "candidate_requires_human_review",
        counterevidence_boundary: { status: "incomplete", approved_query_count: 2, executed_query_count: 1 },
      }],
    });
    expect(bundle.researchGapCandidates[0].counterevidenceBoundary).toBeNull();
  });
});
