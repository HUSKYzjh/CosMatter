import { describe, expect, it } from "vitest";

import type { PdfTaskStatus } from "./localApi";
import { PDF_TASK_STALE_AFTER_MS, pdfTaskSnapshotFreshness } from "./pdfTaskFreshness";

const task: PdfTaskStatus = {
  document_id: "pdf-1", candidate_document_id: "doc-1", audit_document_id: "doc-1", audit_state: "pending",
  file_name: "paper.pdf", state: "running", doi: null, doi_status: "pending", markdown_ready: false,
  source_map_review_status: "absent", source_map_segment_count: 0, trust_status: "private_markdown_outside_run_not_scientific_evidence",
};

describe("private PDF task freshness", () => {
  it("marks a locally confirmed task current, then aging after the polling window", () => {
    expect(pdfTaskSnapshotFreshness(task, "ready", 1_000, 1_000)).toMatchObject({ state: "current", observedAt: 1_000 });
    expect(pdfTaskSnapshotFreshness(task, "ready", 1_000, 1_001 + PDF_TASK_STALE_AFTER_MS)).toMatchObject({ state: "aging" });
  });

  it("retains a known task but never calls it current after a failed read", () => {
    expect(pdfTaskSnapshotFreshness(task, "unavailable", 1_000, 2_000)).toEqual({ state: "unavailable", observedAt: 1_000, ageMs: 1_000 });
    expect(pdfTaskSnapshotFreshness(null, "ready", 1_000, 2_000)).toEqual({ state: "absent", observedAt: null, ageMs: null });
  });
});
