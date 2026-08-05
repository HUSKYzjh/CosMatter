import { describe, expect, it } from "vitest";

import { relatedLiteraturePairs, topicFor } from "./literatureTopology";
import type { LiteratureGraphNode } from "./model";

function paper(nodeId: string, label: string): LiteratureGraphNode {
  return { nodeId, label, kind: "candidate_paper", trustStatus: "local_filename_metadata_only", source: "local library" };
}

describe("literature topology", () => {
  it("assigns explainable title-only topic clusters", () => {
    expect(topicFor(paper("a", "Epitaxial thin film strain in BiFeO3"))).toBe("thin_film");
    expect(topicFor(paper("b", "Ferroelectric domain microstructure of a perovskite"))).toBe("domain_microstructure");
    expect(topicFor(paper("c", "Molecular dynamics potential for perovskites"))).toBe("simulation_method");
  });

  it("creates sparse navigation links only for shared title metadata", () => {
    const pairs = relatedLiteraturePairs([
      paper("a", "Ferroelectric domain evolution in BiFeO3"),
      paper("b", "Fractal ferroelectric domain patterns in films"),
      paper("c", "Molecular dynamics potential training"),
    ]);
    expect(pairs).toHaveLength(1);
    expect(pairs[0].sharedTerms).toEqual(["domain", "ferroelectric"]);
    expect(pairs[0].edge.edgeType).toBe("title_similarity_suggestion");
    expect(pairs[0].edge.trustStatus).toContain("navigation_only_not_evidence");
  });
});
