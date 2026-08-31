import { describe, expect, it } from "vitest";

import { missionFlightRecorder } from "./missionFlightRecorder";
import { demoBundle, type ImportedBundle } from "./model";
import type { PdfTaskStatus } from "./localApi";

const task = (overrides: Partial<PdfTaskStatus> = {}): PdfTaskStatus => ({
  document_id: "pdf-1", candidate_document_id: "doc-1", audit_document_id: "doc-1", audit_state: "pending", file_name: "paper.pdf", state: "submitted", doi: null, doi_status: "pending", markdown_ready: false, source_map_review_status: "absent", source_map_segment_count: 0, trust_status: "private_markdown_outside_run_not_scientific_evidence", ...overrides,
});
const at = (missionState: string): ImportedBundle => ({ ...demoBundle, status: { missionState, retryCount: 0, retryBudget: 0, returnReason: null } });

describe("mission flight recorder", () => {
  it("does not mistake candidate metadata for source evidence", () => {
    const entries = missionFlightRecorder(at("RETRIEVE"), null);
    expect(entries.find((entry) => entry.id === "candidates")).toMatchObject({ state: "complete" });
    expect(entries.find((entry) => entry.id === "source-map")).toMatchObject({ state: "waiting" });
    expect(entries.find((entry) => entry.id === "evidence")).toMatchObject({ state: "waiting" });
  });

  it("unlocks source-map work only after a registered private parse and marks failed parsing as a block", () => {
    const parsed = missionFlightRecorder(at("EXTRACT"), task({ markdown_ready: true, audit_state: "done", state: "done" }));
    expect(parsed.find((entry) => entry.id === "fulltext")).toMatchObject({ state: "complete" });
    expect(parsed.find((entry) => entry.id === "source-map")).toMatchObject({ state: "active" });
    const failed = missionFlightRecorder(at("EXTRACT"), task({ state: "failed" }));
    expect(failed.find((entry) => entry.id === "fulltext")).toMatchObject({ state: "blocked" });
    expect(failed.find((entry) => entry.id === "source-map")).toMatchObject({ state: "blocked" });
  });

  it("keeps evidence and gaps waiting until their local artifacts exist", () => {
    const entries = missionFlightRecorder(at("VERIFY"), task({ markdown_ready: true, audit_state: "done", state: "done" }));
    expect(entries.find((entry) => entry.id === "facts")).toMatchObject({ state: "waiting" });
    expect(entries.find((entry) => entry.id === "evidence")).toMatchObject({ state: "waiting" });
    expect(entries.find((entry) => entry.id === "horizon")).toMatchObject({ state: "waiting" });
  });
});
