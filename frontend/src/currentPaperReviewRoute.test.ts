import { describe, expect, it } from "vitest";

import type { CandidateScreening, PdfTaskStatus } from "./localApi";
import { completedPrivateSourceMapMatchesPaper, screeningAllowsSourceReview } from "./currentPaperReviewRoute";

const screening: CandidateScreening = {
  run_id: "run-1",
  trust_status: "human_reviewed_candidate_screening_not_scientific_evidence",
  candidate_count: 2,
  candidates: [
    { document_id: "paper-a", title: "A", source: "Crossref", publication_year: 2024 },
    { document_id: "paper-b", title: "B", source: "Crossref", publication_year: 2023 },
  ],
  decisions: [
    { document_id: "paper-a", decision: "include_for_fulltext", reason_codes: ["relevant"] },
    { document_id: "paper-b", decision: "exclude", reason_codes: ["out_of_scope"] },
  ],
};

function pdfTask(candidateDocumentId: string): PdfTaskStatus {
  return {
    document_id: "pdf-1", candidate_document_id: candidateDocumentId, audit_document_id: "audit-1",
    audit_state: "done", file_name: "paper.pdf", state: "done", doi: null, doi_status: "needs_human_doi",
    markdown_ready: true, source_map_review_status: "absent", source_map_segment_count: 0,
    trust_status: "private_pdf_not_scientific_evidence",
  };
}

describe("currentPaperReviewRoute", () => {
  it("requires a persisted include_for_fulltext decision for the current candidate", () => {
    expect(screeningAllowsSourceReview(screening, "run-1", "paper-a")).toBe(true);
    expect(screeningAllowsSourceReview(screening, "run-1", "paper-b")).toBe(false);
    expect(screeningAllowsSourceReview(screening, "run-1", "paper-missing")).toBe(false);
  });

  it("does not treat an incomplete or untrusted screening record as an authorization", () => {
    expect(screeningAllowsSourceReview({ ...screening, decisions: [] }, "run-1", "paper-a")).toBe(false);
    expect(screeningAllowsSourceReview({ ...screening, trust_status: "candidate_metadata_not_scientific_evidence" }, "run-1", "paper-a")).toBe(false);
  });

  it("does not project another run's screening decision into the active reader", () => {
    expect(screeningAllowsSourceReview(screening, "run-2", "paper-a")).toBe(false);
  });

  it("requires the completed private source map to belong to the selected paper", () => {
    expect(completedPrivateSourceMapMatchesPaper(pdfTask("paper-a"), "paper-a")).toBe(true);
    expect(completedPrivateSourceMapMatchesPaper(pdfTask("paper-a"), "paper-b")).toBe(false);
  });
});
