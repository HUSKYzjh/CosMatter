import { describe, expect, it } from "vitest";

import { paperWorkflowState } from "./paperWorkflowState";
import type { CandidateScreeningDecision, PdfTaskStatus } from "./localApi";
import type { LiteratureGraphNode } from "./model";

const paper: LiteratureGraphNode = { nodeId: "paper:doc-1", kind: "candidate_paper", label: "Candidate", trustStatus: "candidate" };
const task = (overrides: Partial<PdfTaskStatus> = {}): PdfTaskStatus => ({
  document_id: "pdf-1", candidate_document_id: "doc-1", audit_document_id: "doc-1", audit_state: "pending", file_name: "paper.pdf", state: "pending", doi: null, doi_status: "pending", markdown_ready: false, source_map_review_status: "absent", source_map_segment_count: 0, trust_status: "private", ...overrides,
});
const decision = (value: CandidateScreeningDecision["decision"]): CandidateScreeningDecision["decision"] => value;

describe("paperWorkflowState", () => {
  it("shows screening or inclusion only from an explicit human decision", () => {
    expect(paperWorkflowState(paper, [], "unreviewed", 0)).toBe("screening");
    expect(paperWorkflowState(paper, [], decision("include_for_fulltext"), 0)).toBe("included");
  });
  it("projects the matching document task but never another paper task", () => {
    expect(paperWorkflowState(paper, [task({ candidate_document_id: "doc-2", state: "failed" })], decision("include_for_fulltext"), 0)).toBe("included");
    expect(paperWorkflowState(paper, [task()], decision("include_for_fulltext"), 0)).toBe("parsing");
  });
  it("orders source and accepted evidence states above earlier workflow states", () => {
    expect(paperWorkflowState(paper, [task({ state: "done", markdown_ready: true, audit_state: "done" })], decision("include_for_fulltext"), 0)).toBe("source_map");
    expect(paperWorkflowState(paper, [task({ state: "done", markdown_ready: true, audit_state: "done", source_map_review_status: "recorded", source_map_segment_count: 1 })], decision("include_for_fulltext"), 0)).toBe("evidence_review");
    expect(paperWorkflowState(paper, [task({ state: "failed" })], decision("include_for_fulltext"), 0)).toBe("failed");
    expect(paperWorkflowState(paper, [task({ state: "failed" })], decision("include_for_fulltext"), 1)).toBe("accepted_evidence");
    expect(paperWorkflowState(paper, [task({ state: "failed" })], decision("include_for_fulltext"), 1, false)).toBe("provenance_audit");
  });
});
