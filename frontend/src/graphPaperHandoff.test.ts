import { describe, expect, it } from "vitest";

import { graphPaperHandoff } from "./graphPaperHandoff";
import { demoBundle, type EvidenceCard, type LiteratureGraphNode } from "./model";

const paper: LiteratureGraphNode = {
  nodeId: "paper:doc-1", kind: "candidate_paper", label: "Candidate", trustStatus: "candidate",
};
const evidence: EvidenceCard = {
  evidenceId: "ev-1", claim: "Reviewed claim", stance: "support", conditions: {}, quote: "Excerpt", reviewStatus: "accepted",
  provenance: { documentId: "doc-1", locator: "markdown_line:1-1", source: "reviewed", accessPolicy: "authorised" }, isSynthetic: false,
};

describe("graph paper handoff", () => {
  it("keeps source registration available when a selected paper has no accepted EvidenceCard", () => {
    expect(graphPaperHandoff({ ...demoBundle, literatureGraph: { ...demoBundle.literatureGraph, nodes: [paper], edges: [] }, evidenceCards: [] }, paper))
      .toEqual({ mode: "register-source", linkedEvidenceCount: 0 });
  });

  it("switches the reader action to evidence verification only for a reviewed provenance link", () => {
    const bundle = {
      ...demoBundle,
      evidenceCards: [evidence],
      literatureGraph: {
        ...demoBundle.literatureGraph,
        nodes: [paper],
        edges: [{ sourceId: "paper:doc-1", targetId: "evidence:ev-1", edgeType: "source_provenance", relationSource: "reviewed source map", trustStatus: "accepted" }],
      },
    };
    expect(graphPaperHandoff(bundle, paper)).toEqual({ mode: "verify-evidence", linkedEvidenceCount: 1 });
  });
});