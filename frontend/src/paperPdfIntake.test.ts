import { describe, expect, it } from "vitest";

import { paperPdfIntake, pdfTaskForPaper } from "./paperPdfIntake";
import type { PdfTaskStatus } from "./localApi";
import type { LiteratureGraphNode } from "./model";

const paper: LiteratureGraphNode = { nodeId: "paper:doc-1", kind: "candidate_paper", label: "Candidate", trustStatus: "candidate" };
const task = (overrides: Partial<PdfTaskStatus> = {}): PdfTaskStatus => ({
  document_id: "private-1", candidate_document_id: "doc-1", audit_document_id: "doc-1", audit_state: "pending",
  file_name: "paper.pdf", state: "pending", doi: null, doi_status: "pending", markdown_ready: false,
  source_map_review_status: "absent", source_map_segment_count: 0, trust_status: "private_markdown_outside_run_not_scientific_evidence", ...overrides,
});

describe("paperPdfIntake", () => {
  it("does not expose another candidate's private PDF to the selected paper", () => {
    expect(paperPdfIntake(task({ candidate_document_id: "doc-2" }), paper).state).toBe("none");
  });

  it("finds the matching PDF from a registry without exposing another paper task", () => {
    const matching = task({ document_id: "private-2", candidate_document_id: "doc-1", state: "done", markdown_ready: true, audit_state: "done" });
    const other = task({ document_id: "private-3", candidate_document_id: "doc-2", state: "failed" });
    expect(pdfTaskForPaper([other, matching], paper)?.document_id).toBe("private-2");
    expect(paperPdfIntake(pdfTaskForPaper([other, matching], paper), paper).state).toBe("source-map");
  });
  it("does not project a private PDF onto a paper-like bibliography root", () => {
    const bibliographyRoot: LiteratureGraphNode = { ...paper, nodeId: "paper:doc-1", kind: "relation_root_paper" };
    expect(paperPdfIntake(task(), bibliographyRoot)).toEqual({ state: "none", documentId: null });
  });
  it("keeps a matching PDF in parsing until the private parse ledger is complete", () => {
    expect(paperPdfIntake(task(), paper).state).toBe("parsing");
  });

  it("surfaces a matching failed PDF as retryable rather than parsing", () => {
    expect(paperPdfIntake(task({ state: "failed" }), paper).state).toBe("failed");
  });
  it("routes a parsed matching PDF to Source Map registration before evidence review", () => {
    expect(paperPdfIntake(task({ state: "done", markdown_ready: true, audit_state: "done" }), paper).state).toBe("source-map");
  });

  it("routes a recorded Source Map to material-fact and EvidenceCard review", () => {
    expect(paperPdfIntake(task({ state: "done", markdown_ready: true, audit_state: "done", source_map_review_status: "recorded", source_map_segment_count: 2 }), paper).state).toBe("evidence-review");
  });
});
