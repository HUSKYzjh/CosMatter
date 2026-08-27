import { describe, expect, it } from "vitest";

import { literatureGraphMode } from "./literatureGraphMode";

describe("literatureGraphMode", () => {
  it("keeps a DOI-only citation expansion visible as bibliography rather than treating it as an empty graph", () => {
    expect(literatureGraphMode(
      [{ nodeId: "doi:10.1/root", kind: "citation_work", label: "10.1/root", trustStatus: "bibliography" }, { nodeId: "doi:10.1/ref", kind: "citation_work", label: "10.1/ref", trustStatus: "bibliography" }],
      [{ sourceId: "doi:10.1/root", targetId: "doi:10.1/ref", edgeType: "citation_reference", relationSource: "Crossref", trustStatus: "bibliography" }],
    )).toBe("bibliography");
  });

  it("keeps paper-like bibliography roots out of the evidence-map mode without a reviewable document ID", () => {
    expect(literatureGraphMode(
      [{ nodeId: "relation-root:doi:10.1/root", kind: "relation_root_paper", label: "Root metadata", trustStatus: "bibliography" }],
      [],
    )).toBe("empty");
  });
  it("prioritizes a reviewable paper map and does not call a mission marker a graph", () => {
    expect(literatureGraphMode([{ nodeId: "mission:1", kind: "mission", label: "Task", trustStatus: "mission" }], [])).toBe("empty");
    expect(literatureGraphMode([{ nodeId: "paper:1", kind: "candidate_paper", label: "Candidate", trustStatus: "metadata" }], [])).toBe("evidence");
  });
});
