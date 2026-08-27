import { describe, expect, it } from "vitest";

import { graphEdgeStillExists, graphSelectionVisibility } from "./graphSelectionState";
import type { LiteratureGraphEdge, LiteratureGraphNode } from "./model";

const papers: LiteratureGraphNode[] = [
  { nodeId: "paper:a", kind: "candidate_paper", label: "A", trustStatus: "candidate" },
  { nodeId: "paper:b", kind: "candidate_paper", label: "B", trustStatus: "candidate" },
];
const edge: LiteratureGraphEdge = { sourceId: "paper:a", targetId: "paper:b", edgeType: "retrieval_candidate", relationSource: "test", trustStatus: "candidate" };

describe("graph selection state", () => {
  it("distinguishes a hidden current paper from a stale node", () => {
    expect(graphSelectionVisibility("paper:a", papers, [papers[1]])).toEqual({ exists: true, visible: false });
    expect(graphSelectionVisibility("paper:gone", papers, papers)).toEqual({ exists: false, visible: false });
  });

  it("recognizes whether an inspected edge survived a graph refresh", () => {
    expect(graphEdgeStillExists(edge, [edge])).toBe(true);
    expect(graphEdgeStillExists(edge, [])).toBe(false);
  });
});