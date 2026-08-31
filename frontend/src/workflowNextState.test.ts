import { describe, expect, it } from "vitest";

import { workflowNextState } from "./workflowNextState";
import type { PdfTaskStatus } from "./localApi";

const task = (overrides: Partial<PdfTaskStatus> = {}): PdfTaskStatus => ({
  document_id: "pdf-1", candidate_document_id: null, audit_document_id: "pdf-1", audit_state: "pending",
  file_name: "paper.pdf", state: "pending", doi: null, doi_status: "pending", markdown_ready: false, source_map_review_status: "absent", source_map_segment_count: 0,
  trust_status: "private_markdown_outside_run_not_scientific_evidence", ...overrides,
});

describe("workflow next action", () => {
  it("routes a screened, parsed PDF to selecting its attached paper first", () => {
    expect(workflowNextState(3, task({ candidate_document_id: "paper-1", state: "done", markdown_ready: true, audit_state: "done" }))).toBe("select-attached-paper");
  });

  it("continues directly to reader work only when the attached paper is already selected in this session", () => {
    const parsed = task({ candidate_document_id: "paper-1", state: "done", markdown_ready: true, audit_state: "done" });
    expect(workflowNextState(3, parsed, "paper-1")).toBe("source-map");
    expect(workflowNextState(3, { ...parsed, source_map_review_status: "recorded", source_map_segment_count: 2 }, "paper-1")).toBe("evidence-review");
  });
  it("keeps the attached-paper selection step even after source locations are recorded", () => {
    expect(workflowNextState(3, task({ candidate_document_id: "paper-1", state: "done", markdown_ready: true, audit_state: "done", source_map_review_status: "recorded", source_map_segment_count: 2 }))).toBe("select-attached-paper");
  });
  it("promotes citation expansion only for an unlinked PDF with a confirmed DOI", () => {
    expect(workflowNextState(0, task({ state: "done", markdown_ready: true, audit_state: "done", doi_status: "resolved", doi: "10.1000/example" }))).toBe("citation-map");
    expect(workflowNextState(3, task({ candidate_document_id: "paper-1", state: "done", markdown_ready: true, audit_state: "done", doi_status: "resolved", doi: "10.1000/example" }))).toBe("select-attached-paper");
  });

  it("keeps an unlinked parsed PDF on the private Markdown navigation branch until its DOI is confirmed", () => {
    expect(workflowNextState(0, task({ state: "done", markdown_ready: true, audit_state: "done" }))).toBe("standalone-markdown");
  });

  it("surfaces a failed PDF before any generic literature-map route", () => {
    expect(workflowNextState(3, task({ state: "failed" }))).toBe("pdf-failed");
  });
  it("does not hide a pending PDF task behind an empty literature-map message", () => {
    expect(workflowNextState(0, task())).toBe("pdf-parsing");
  });

  it("uses the literature map only when no parsed PDF branch takes precedence", () => {
    expect(workflowNextState(2, null)).toBe("literature-map");
  });
  it("never projects a private PDF task onto a different selected paper session", () => {
    expect(workflowNextState(3, task({ candidate_document_id: "paper-1", state: "failed" }), "paper-2")).toBe("align-pdf-context");
    expect(workflowNextState(3, task({ candidate_document_id: "paper-1", state: "done", markdown_ready: true, audit_state: "done" }), "paper-2")).toBe("align-pdf-context");
  });

});
