import { describe, expect, it } from "vitest";

import { demoBundle, type EvidenceCard, type LiteratureGraphNode } from "./model";
import { emptyResearchSession, evidenceGate, reconcileResearchSession, selectEvidence, selectPaper } from "./researchSession";

const paper: LiteratureGraphNode = { nodeId: "paper:doc-1", kind: "candidate_paper", label: "Candidate paper", trustStatus: "candidate" };
const evidence: EvidenceCard = {
  evidenceId: "ev-1",
  claim: "A reviewed claim",
  stance: "supports",
  conditions: { thickness_nm: 20 },
  quote: "Short reviewed excerpt.",
  reviewStatus: "accepted",
  provenance: { documentId: "doc-1", locator: "p. 3, Fig. 2", source: "local", accessPolicy: "authorised" },
  isSynthetic: false,
};

function reviewedBundle() {
  return { ...demoBundle, evidenceCards: [evidence], sourceMapSummary: { documentCount: 1, segmentCount: 3, documentIds: ["doc-1"] }, auditSummary: { ...demoBundle.auditSummary, evidenceProvenance: { acceptedEvidenceCount: 1, exactSourceMapMatchCount: 1, manualLocatorOnlyCount: 0, exactSourceMapMatchRate: 1 } }, literatureGraph: { ...demoBundle.literatureGraph, nodes: [paper], edges: [{ sourceId: "paper:doc-1", targetId: "evidence:ev-1", edgeType: "source_provenance", relationSource: "reviewed source map", trustStatus: "accepted" }] } };
}

describe("ResearchSession evidence gate", () => {
  it("does not treat a graph node ID as a source document ID", () => {
    const session = selectPaper(emptyResearchSession(), paper);
    expect(session.selectedNode?.nodeId).toBe("paper:doc-1");
    expect(session.documentId).toBeNull();
    expect(session.evidenceId).toBeNull();
  });

  it("does not open an evidence-verification session from a bibliography-only node", () => {
    const citation: LiteratureGraphNode = { ...paper, nodeId: "citation:doc-1", kind: "citation_work" };
    expect(selectPaper(emptyResearchSession(), citation)).toEqual(emptyResearchSession());
  });
  it("only obtains a document ID by selecting an imported accepted EvidenceCard", () => {
    const withPaper = selectPaper(emptyResearchSession(), paper);
    const session = selectEvidence(withPaper, evidence);
    expect(session.evidenceId).toBe("ev-1");
    expect(session.documentId).toBe("doc-1");
    expect(evidenceGate(reviewedBundle(), session)).toEqual({ ready: true, reason: null });
  });

  it("keeps research extension blocked for every missing audit artifact", () => {
    expect(evidenceGate(reviewedBundle(), emptyResearchSession()).reason).toBe("paper");
    const withPaper = selectPaper(emptyResearchSession(), paper);
    expect(evidenceGate(reviewedBundle(), withPaper).reason).toBe("evidence");
    const unrelatedPaper = { ...paper, nodeId: "paper:other" };
    expect(evidenceGate(reviewedBundle(), selectEvidence(selectPaper(emptyResearchSession(), unrelatedPaper), evidence)).reason).toBe("source-link");
    const noLocatorEvidence = { ...evidence, provenance: { ...evidence.provenance, locator: "" } };
    const noLocator = selectEvidence(withPaper, noLocatorEvidence);
    expect(evidenceGate({ ...reviewedBundle(), evidenceCards: [noLocatorEvidence] }, noLocator).reason).toBe("locator");
    expect(evidenceGate({ ...reviewedBundle(), sourceMapSummary: { documentCount: 0, segmentCount: 0, documentIds: [] } }, selectEvidence(withPaper, evidence)).reason).toBe("source-map");
  });
  it("does not accept a globally counted source map from another document", () => {
    const withPaper = selectPaper(emptyResearchSession(), paper);
    const session = selectEvidence(withPaper, evidence);
    const bundle = { ...reviewedBundle(), sourceMapSummary: { documentCount: 1, segmentCount: 3, documentIds: ["another-document"] } };
    expect(evidenceGate(bundle, session)).toEqual({ ready: false, reason: "source-map" });
  });

  it("reconciles only still-linked paper and EvidenceCard selections after a UI refresh", () => {
    const bundle = reviewedBundle();
    const session = selectEvidence(selectPaper(emptyResearchSession(), paper), evidence);
    const reconciled = reconcileResearchSession(bundle, session);
    expect(reconciled.selectedNode?.nodeId).toBe(paper.nodeId);
    expect(reconciled.evidenceId).toBe(evidence.evidenceId);
    const withoutEdge = { ...bundle, literatureGraph: { ...bundle.literatureGraph, edges: bundle.literatureGraph.edges.filter((edge) => edge.edgeType !== "source_provenance") } };
    expect(reconcileResearchSession(withoutEdge, session)).toMatchObject({ selectedNode: { nodeId: paper.nodeId }, evidenceId: null, documentId: null });
    const withoutPaper = { ...bundle, literatureGraph: { ...bundle.literatureGraph, nodes: bundle.literatureGraph.nodes.filter((node) => node.nodeId !== paper.nodeId) } };
    expect(reconcileResearchSession(withoutPaper, session)).toEqual(emptyResearchSession());
  });

  it("requires the quote-free exact provenance audit in addition to a document-level Source Map summary", () => {
    const session = selectEvidence(selectPaper(emptyResearchSession(), paper), evidence);
    expect(evidenceGate({ ...reviewedBundle(), auditSummary: { ...reviewedBundle().auditSummary, evidenceProvenance: null } }, session)).toEqual({ ready: false, reason: "provenance-audit" });
    expect(evidenceGate({ ...reviewedBundle(), auditSummary: { ...reviewedBundle().auditSummary, evidenceProvenance: { acceptedEvidenceCount: 1, exactSourceMapMatchCount: 0, manualLocatorOnlyCount: 1, exactSourceMapMatchRate: 0 } } }, session)).toEqual({ ready: false, reason: "provenance-audit" });
  });

});