import { describe, expect, it } from "vitest";

import { graphFootnote } from "./graphFootnote";

describe("graphFootnote", () => {
  const base = { locale: "zh" as const, hasCitationMap: false, bibliographyCount: 0, paperLikeNodeCount: 0, reviewablePaperCount: 0, visibleEdgeCount: 0 };

  it("labels synthetic or navigation-only paper-like nodes as non-reviewable", () => {
    expect(graphFootnote({ ...base, paperLikeNodeCount: 20, visibleEdgeCount: 42 })).toContain("不能用于人工筛选、全文处理或 EvidenceCard");
  });

  it("distinguishes mixed maps from a fully reviewable paper map", () => {
    expect(graphFootnote({ ...base, paperLikeNodeCount: 4, reviewablePaperCount: 2, visibleEdgeCount: 3 })).toContain("其中 2 篇可审查");
    expect(graphFootnote({ ...base, paperLikeNodeCount: 2, reviewablePaperCount: 2, visibleEdgeCount: 3 })).toContain("2 篇可审查论文");
  });

  it("keeps DOI citation maps labelled as bibliography", () => {
    expect(graphFootnote({ ...base, hasCitationMap: true, bibliographyCount: 8, visibleEdgeCount: 12 })).toContain("8 个书目条目");
  });
});
