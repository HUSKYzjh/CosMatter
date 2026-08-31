import { describe, expect, it } from "vitest";

import { readingRoute } from "./readingRoute";
import type { LiteratureGraphNode } from "./model";

const node = (id: string, title: string, trustStatus = "candidate_metadata_not_scientific_evidence"): LiteratureGraphNode => ({ nodeId: `paper:${id}`, kind: "candidate_paper", label: title, trustStatus });

describe("readingRoute", () => {
  it("orders recorded recovery and evidence work before screening, with stable local reasons", () => {
    const route = readingRoute([node("screen", "Screen"), node("source", "Source"), node("failed", "Failed")], {
      "paper:screen": "screening", "paper:source": "source_map", "paper:failed": "failed",
    });
    expect(route.map((entry) => [entry.documentId, entry.action, entry.ordinal])).toEqual([
      ["failed", "recover-pdf", 1], ["source", "register-source-map", 2], ["screen", "screen-paper", 3],
    ]);
  });

  it("excludes synthetic, metadata-only, and human-excluded records from the route", () => {
    const route = readingRoute([
      node("reviewable", "Reviewable"),
      node("synthetic", "Synthetic", "synthetic_demo_candidate_not_scientific_evidence"),
      { nodeId: "doi:10.1/example", kind: "citation_work", label: "DOI", trustStatus: "bibliography" },
      node("excluded", "Excluded"),
    ], { "paper:excluded": "excluded" });
    expect(route).toHaveLength(1);
    expect(route[0]).toMatchObject({ documentId: "reviewable", action: "load-screening" });
  });
});
