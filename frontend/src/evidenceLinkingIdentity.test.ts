import { describe, expect, it } from "vitest";

import { documentIdForReviewablePaper, reviewablePaperForDocumentId } from "./evidenceLinking";
import type { LiteratureGraphNode } from "./model";

const paper: LiteratureGraphNode = {
  nodeId: "paper:doc-42",
  kind: "candidate_paper",
  label: "Candidate paper",
  trustStatus: "metadata_only",
};

describe("reviewable paper identity", () => {
  it("accepts only an explicit paper projection with a reviewable-paper kind", () => {
    expect(documentIdForReviewablePaper(paper)).toBe("doc-42");
    expect(documentIdForReviewablePaper({ ...paper, nodeId: "citation:doc-42", kind: "citation_work" })).toBeNull();
    expect(documentIdForReviewablePaper({ ...paper, kind: "citation_work" })).toBeNull();
  });

  it("keeps a paper-kind navigation record out of the reviewable-paper contract without a paper document ID", () => {
    expect(documentIdForReviewablePaper({ ...paper, nodeId: "relation-root:doi:10.1/example", kind: "relation_root_paper" })).toBeNull();
  });
  it("does not use suffix matches to bind a citation record to a private document", () => {
    const citation: LiteratureGraphNode = { ...paper, nodeId: "citation:doc-42", kind: "citation_work" };
    expect(reviewablePaperForDocumentId([citation], "doc-42")).toBeNull();
    expect(reviewablePaperForDocumentId([citation, paper], "doc-42")).toBe(paper);
  });
});