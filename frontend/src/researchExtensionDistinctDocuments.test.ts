import { describe, expect, it } from "vitest";

import { demoBundle, type EvidenceCard } from "./model";
import { researchExtensionReadiness } from "./researchExtensionReadiness";

const card = (id: string, stance: string, documentId: string): EvidenceCard => ({
  evidenceId: id, claim: "Reviewed claim", stance, conditions: {}, quote: "Reviewed excerpt.", reviewStatus: "accepted",
  provenance: { documentId, locator: "p. 1", source: "local", accessPolicy: "authorized" }, isSynthetic: false,
});

describe("researchExtensionReadiness distinct document boundary", () => {
  it("keeps two opposed cards from one paper out of the cross-paper comparison gate", () => {
    const bundle = {
      ...demoBundle,
      evidenceCards: [card("ev-1", "support", "doc-1"), card("ev-2", "contradict", "doc-1")],
      conditionMatrix: [{ conditionCluster: "cluster", supportingEvidenceIds: ["ev-1"], contradictingEvidenceIds: ["ev-2"], differingFields: ["substrate"], unknowns: [] }],
      auditSummary: { ...demoBundle.auditSummary, evidenceProvenance: { acceptedEvidenceCount: 2, exactSourceMapMatchCount: 2, manualLocatorOnlyCount: 0, exactSourceMapMatchRate: 1 } },
      literatureGraph: { ...demoBundle.literatureGraph, nodes: [{ nodeId: "paper:doc-1", kind: "evidence_paper", label: "doc-1", trustStatus: "reviewed" }], edges: [
        { sourceId: "paper:doc-1", targetId: "evidence:ev-1", edgeType: "source_provenance", relationSource: "reviewed source map", trustStatus: "accepted" },
        { sourceId: "paper:doc-1", targetId: "evidence:ev-2", edgeType: "source_provenance", relationSource: "reviewed source map", trustStatus: "accepted" },
      ] },
    };
    expect(researchExtensionReadiness(bundle)).toMatchObject({ ready: false, reason: "documents", distinctDocumentCount: 1 });
  });
});
