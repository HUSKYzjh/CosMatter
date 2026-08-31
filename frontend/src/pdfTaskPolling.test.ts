import { describe, expect, it } from "vitest";

import { shouldPollPdfTask } from "./pdfTaskPolling";
import type { PdfTaskState, PdfTaskStatus } from "./localApi";

const task = (state: PdfTaskState): PdfTaskStatus => ({
  document_id: "pdf-1", candidate_document_id: "doc-1", audit_document_id: "doc-1", audit_state: "pending",
  file_name: "paper.pdf", state, doi: null, doi_status: "pending", markdown_ready: false,
  source_map_review_status: "absent", source_map_segment_count: 0, trust_status: "private_markdown_outside_run_not_scientific_evidence",
});

describe("private PDF polling", () => {
  it("polls only a local run with an in-progress task", () => {
    expect(shouldPollPdfTask("run-1", task("pending"))).toBe(true);
    expect(shouldPollPdfTask(null, task("pending"))).toBe(false);
    expect(shouldPollPdfTask("run-1", null)).toBe(false);
  });

  it.each(["done", "failed"] as const)("stops polling terminal state %s", (state) => {
    expect(shouldPollPdfTask("run-1", task(state))).toBe(false);
  });
});
