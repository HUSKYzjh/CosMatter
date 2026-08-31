import { describe, expect, it } from "vitest";

import type { PdfTaskStatus } from "./localApi";
import { pdfTaskForSession } from "./sessionPdfSelection";

const task = (documentId: string | null): PdfTaskStatus => ({
  document_id: `pdf-${documentId ?? "standalone"}`, candidate_document_id: documentId, audit_document_id: documentId ?? "standalone", audit_state: "done",
  file_name: "paper.pdf", state: "done", doi: null, doi_status: "resolved", markdown_ready: true,
  source_map_review_status: "recorded", source_map_segment_count: 1, trust_status: "private_markdown_outside_run_not_scientific_evidence",
});

describe("session PDF selection", () => {
  it("selects only a PDF attached to the newly selected screened candidate", () => {
    const paperA = task("paper-a");
    const paperB = task("paper-b");
    expect(pdfTaskForSession([paperA, paperB], "paper-b")).toBe(paperB);
  });

  it("clears a different-paper or standalone PDF from the active evidence session", () => {
    expect(pdfTaskForSession([task("paper-a"), task(null)], "paper-b")).toBeNull();
    expect(pdfTaskForSession([task("paper-a")], null)).toBeNull();
  });
});
