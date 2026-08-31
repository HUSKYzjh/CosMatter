import { describe, expect, it } from "vitest";

import { isPdfTaskRegistry, isPdfTaskStatus } from "./localApi";

const task = () => ({
  document_id: "pdf-1", candidate_document_id: "paper-1", audit_document_id: "paper-1",
  audit_state: "done", file_name: "paper.pdf", state: "done", doi: null,
  doi_status: "needs_human_doi", markdown_ready: true,
  source_map_review_status: "absent", source_map_segment_count: 0, error: null,
  trust_status: "private_markdown_outside_run_not_scientific_evidence",
});

describe("private PDF task status", () => {
  it("accepts only the bounded metadata projection for a completed private parse", () => {
    expect(isPdfTaskStatus(task())).toBe(true);
    expect(isPdfTaskRegistry({ run_id: "run-1", tasks: [task()], trust_status: "private_pdf_task_registry_metadata_only" }, "run-1")).toBe(true);
  });

  it("fails closed for unknown states or impossible parse and review combinations", () => {
    expect(isPdfTaskStatus({ ...task(), state: "still_processing" })).toBe(false);
    expect(isPdfTaskStatus({ ...task(), markdown_ready: false })).toBe(false);
    expect(isPdfTaskStatus({ ...task(), source_map_review_status: "recorded", source_map_segment_count: 0 })).toBe(false);
    expect(isPdfTaskStatus({ ...task(), provider_command: "untrusted" })).toBe(false);
  });

  it("rejects a registry with duplicate document identities or a mismatched run", () => {
    const duplicate = { run_id: "run-1", tasks: [task(), task()], trust_status: "private_pdf_task_registry_metadata_only" };
    expect(isPdfTaskRegistry(duplicate, "run-1")).toBe(false);
    expect(isPdfTaskRegistry({ run_id: "run-2", tasks: [task()], trust_status: "private_pdf_task_registry_metadata_only" }, "run-1")).toBe(false);
  });
});
