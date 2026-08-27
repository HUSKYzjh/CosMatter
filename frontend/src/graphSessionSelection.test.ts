import { describe, expect, it } from "vitest";
import { graphNodeForSessionDocument } from "./graphSessionSelection";
import type { LiteratureGraphNode } from "./model";

const papers: LiteratureGraphNode[] = [
  { nodeId: "paper:doc-1", kind: "candidate_paper", label: "First", trustStatus: "candidate" },
  { nodeId: "paper:doc-2", kind: "candidate_paper", label: "Second", trustStatus: "candidate" },
  { nodeId: "citation:10.1/example", kind: "citation_work", label: "Reference", trustStatus: "bibliographic" },
];

describe("graphNodeForSessionDocument", () => {
  it("restores only a reviewable paper matching the session document ID", () => {
    expect(graphNodeForSessionDocument(papers, "doc-2")?.nodeId).toBe("paper:doc-2");
    expect(graphNodeForSessionDocument(papers, "10.1/example")).toBeNull();
  });

  it("does not infer a selected paper from an empty or missing document ID", () => {
    expect(graphNodeForSessionDocument(papers, "")).toBeNull();
    expect(graphNodeForSessionDocument(papers, null)).toBeNull();
  });
});
