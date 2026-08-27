import { describe, expect, it } from "vitest";

import { focusEvidenceSession } from "./evidenceSessionFocus";
import { demoBundle, type EvidenceCard } from "./model";

const evidence: EvidenceCard = { evidenceId: "ev-1", claim: "reviewed", stance: "support", conditions: {}, quote: "excerpt", reviewStatus: "accepted", provenance: { documentId: "paper-1", locator: "p. 2", source: "fixture", accessPolicy: "authorised" }, isSynthetic: false };
const bundle = { ...demoBundle, evidenceCards: [evidence], sourceMapSummary: { documentCount: 1, segmentCount: 1, documentIds: ["paper-1"] }, literatureGraph: { trustStatus: "fixture", nodes: [{ nodeId: "paper:paper-1", kind: "evidence_paper", label: "Paper 1", trustStatus: "accepted" }], edges: [{ sourceId: "paper:paper-1", targetId: "evidence:ev-1", edgeType: "source_provenance", relationSource: "reviewed source map", trustStatus: "accepted" }] } };
describe("focusEvidenceSession", () => {
  it("synchronizes an evidence choice to its explicitly linked paper", () => {
    expect(focusEvidenceSession(bundle, evidence)).toMatchObject({ selectedNode: { nodeId: "paper:paper-1" }, evidenceId: "ev-1", documentId: "paper-1" });
  });
  it("does not infer a paper context from a matching string without a reviewed graph edge", () => {
    expect(focusEvidenceSession({ ...bundle, literatureGraph: { ...bundle.literatureGraph, edges: [] } }, evidence)).toBeNull();
  });
});
