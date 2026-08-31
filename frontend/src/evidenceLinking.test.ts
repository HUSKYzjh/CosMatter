import { describe, expect, it } from "vitest";

import { auditableAcceptedEvidence, evidenceForPaper, evidenceMatchesPaper, reviewablePaperCount } from "./evidenceLinking";
import { demoBundle, type EvidenceCard, type LiteratureGraphNode } from "./model";

const paper: LiteratureGraphNode = { nodeId: "paper:doc-1", kind: "evidence_paper", label: "Reviewed paper", trustStatus: "reviewed" };
const evidence: EvidenceCard = {
  evidenceId: "ev-1", claim: "A reviewed claim", stance: "supports", conditions: {}, quote: "Short excerpt.", reviewStatus: "accepted",
  provenance: { documentId: "doc-1", locator: "p. 3", source: "local", accessPolicy: "authorized" }, isSynthetic: false,
};

describe("evidenceForPaper", () => {
  it("requires the explicit projected source-provenance edge", () => {
    const withoutEdge = { ...demoBundle, evidenceCards: [evidence], literatureGraph: { ...demoBundle.literatureGraph, nodes: [paper], edges: [] } };
    expect(evidenceForPaper(withoutEdge, paper)).toEqual([]);
    const withEdge = { ...withoutEdge, literatureGraph: { ...withoutEdge.literatureGraph, edges: [{ sourceId: "paper:doc-1", targetId: "evidence:ev-1", edgeType: "source_provenance", relationSource: "reviewed source map", trustStatus: "accepted" }] } };
    expect(evidenceForPaper(withEdge, paper)).toEqual([evidence]);
    expect(evidenceMatchesPaper(withEdge, paper, evidence)).toBe(true);
  });

  it("rejects a provenance-shaped edge until its trust status is accepted", () => {
    const bundle = { ...demoBundle, evidenceCards: [evidence], literatureGraph: { ...demoBundle.literatureGraph, nodes: [paper], edges: [{ sourceId: "paper:doc-1", targetId: "evidence:ev-1", edgeType: "source_provenance", relationSource: "parser", trustStatus: "parser_output_not_evidence" }] } };
    expect(evidenceForPaper(bundle, paper)).toEqual([]);
    expect(auditableAcceptedEvidence(bundle)).toEqual([]);
  });
  it("does not treat a metadata-paper selection as linked evidence", () => {
    const other: LiteratureGraphNode = { ...paper, nodeId: "paper:other" };
    const bundle = { ...demoBundle, literatureGraph: { ...demoBundle.literatureGraph, nodes: [paper, other] } };
    expect(reviewablePaperCount(bundle)).toBe(2);
    expect(evidenceMatchesPaper(bundle, other, evidence)).toBe(false);
  });
  it("does not count imported cards without a reviewed paper-to-evidence projection", () => {
    const withoutEdge = { ...demoBundle, evidenceCards: [evidence], literatureGraph: { ...demoBundle.literatureGraph, nodes: [paper], edges: [] } };
    expect(auditableAcceptedEvidence(withoutEdge)).toEqual([]);
    const withEdge = { ...withoutEdge, sourceMapSummary: { documentCount: 1, segmentCount: 1, documentIds: ["doc-1"] }, literatureGraph: { ...withoutEdge.literatureGraph, edges: [{ sourceId: "paper:doc-1", targetId: "evidence:ev-1", edgeType: "source_provenance", relationSource: "reviewed source map", trustStatus: "accepted" }] } };
    expect(auditableAcceptedEvidence(withEdge)).toEqual([evidence]);
  });

  it("does not treat a graph edge as auditable without a matching reviewed Source Map document", () => {
    const bundle = {
      ...demoBundle,
      evidenceCards: [evidence],
      sourceMapSummary: { documentCount: 1, segmentCount: 2, documentIds: ["other-document"] },
      literatureGraph: { ...demoBundle.literatureGraph, nodes: [paper], edges: [{ sourceId: "paper:doc-1", targetId: "evidence:ev-1", edgeType: "source_provenance", relationSource: "reviewed source map", trustStatus: "accepted" }] },
    };
    expect(auditableAcceptedEvidence(bundle)).toEqual([]);
  });
});
