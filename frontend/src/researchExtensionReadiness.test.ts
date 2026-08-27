import { describe, expect, it } from "vitest";

import { demoBundle, type EvidenceCard } from "./model";
import { isAuditableConditionContrast, researchExtensionReadiness } from "./researchExtensionReadiness";

const evidence = (id: string, stance: string): EvidenceCard => ({
  evidenceId: id, claim: "Reviewed claim", stance, conditions: {}, quote: "Reviewed excerpt.", reviewStatus: "accepted",
  provenance: { documentId: `doc-${id}`, locator: "p. 1", source: "local", accessPolicy: "authorized" }, isSynthetic: false,
});

function bundleFor(cards: EvidenceCard[], conditionMatrix: typeof demoBundle.conditionMatrix = []) {
  return {
    ...demoBundle,
    evidenceCards: cards,
    conditionMatrix,
    auditSummary: {
      ...demoBundle.auditSummary,
      evidenceProvenance: { acceptedEvidenceCount: cards.length, exactSourceMapMatchCount: cards.length, manualLocatorOnlyCount: 0, exactSourceMapMatchRate: 1 },
    },
    literatureGraph: {
      ...demoBundle.literatureGraph,
      nodes: cards.map((card) => ({ nodeId: `paper:${card.provenance.documentId}`, kind: "evidence_paper", label: card.provenance.documentId, trustStatus: "reviewed" })),
      edges: cards.map((card) => ({ sourceId: `paper:${card.provenance.documentId}`, targetId: `evidence:${card.evidenceId}`, edgeType: "source_provenance", relationSource: "reviewed source map", trustStatus: "accepted" })),
    },
  };
}

describe("researchExtensionReadiness", () => {
  it("does not treat one accepted observation as a cross-paper comparison", () => {
    expect(researchExtensionReadiness(bundleFor([evidence("1", "support")]))).toMatchObject({ ready: false, reason: "evidence", acceptedEvidenceCount: 1 });
  });

  it("requires both recorded positions before describing a contradiction", () => {
    expect(researchExtensionReadiness(bundleFor([evidence("1", "support"), evidence("2", "context")]))).toMatchObject({ ready: false, reason: "comparison" });
  });

  it("requires an exact reviewed Source Map audit before exposing a cross-paper comparison", () => {
    const observations = [evidence("1", "support"), evidence("2", "contradict")];
    const bundle = bundleFor(observations, [{ conditionCluster: "thin films", supportingEvidenceIds: ["1"], contradictingEvidenceIds: ["2"], differingFields: ["substrate"], unknowns: [] }]);
    expect(researchExtensionReadiness({ ...bundle, auditSummary: { ...bundle.auditSummary, evidenceProvenance: null } })).toMatchObject({ ready: false, reason: "provenance-audit", linkedConditionClusterCount: 0 });
    expect(isAuditableConditionContrast(bundle.conditionMatrix[0], { ...bundle, auditSummary: { ...bundle.auditSummary, evidenceProvenance: null } })).toBe(false);
  });

  it("requires an imported condition matrix before a comparison is ready for interpretation", () => {
    const observations = [evidence("1", "supports"), evidence("2", "contradicts")];
    expect(researchExtensionReadiness(bundleFor(observations))).toMatchObject({ ready: false, reason: "conditions" });
    expect(researchExtensionReadiness(bundleFor(observations, [{ conditionCluster: "thin films", supportingEvidenceIds: ["1"], contradictingEvidenceIds: ["2"], differingFields: ["substrate"], unknowns: [] }]))).toMatchObject({ ready: true, reason: null });
  });
});


describe("condition-matrix evidence linkage", () => {
  it("does not treat an unrelated or same-sided matrix row as a cross-paper contrast", () => {
    const observations = [evidence("1", "support"), evidence("2", "contradict")];
    const unrelated = [{ conditionCluster: "unlinked", supportingEvidenceIds: ["unknown"], contradictingEvidenceIds: ["2"], differingFields: ["substrate"], unknowns: [] }];
    expect(researchExtensionReadiness(bundleFor(observations, unrelated))).toMatchObject({ ready: false, reason: "conditions", conditionClusterCount: 1, linkedConditionClusterCount: 0 });
  });

  it("counts only rows that explicitly connect accepted opposing evidence from distinct papers", () => {
    const observations = [evidence("1", "support"), evidence("2", "contradict")];
    const rows = [
      { conditionCluster: "unlinked", supportingEvidenceIds: ["missing"], contradictingEvidenceIds: ["2"], differingFields: [], unknowns: [] },
      { conditionCluster: "linked", supportingEvidenceIds: ["1"], contradictingEvidenceIds: ["2"], differingFields: ["substrate"], unknowns: [] },
    ];
    expect(researchExtensionReadiness(bundleFor(observations, rows))).toMatchObject({ ready: true, linkedConditionClusterCount: 1 });
  });
});


describe("condition-matrix explanatory boundary", () => {
  it("does not unlock comparison when opposing linked cards have no recorded differing field", () => {
    const observations = [evidence("1", "support"), evidence("2", "contradict")];
    const row = [{ conditionCluster: "empty-difference", supportingEvidenceIds: ["1"], contradictingEvidenceIds: ["2"], differingFields: [], unknowns: ["thickness_nm"] }];
    expect(researchExtensionReadiness(bundleFor(observations, row))).toMatchObject({ ready: false, reason: "conditions", linkedConditionClusterCount: 0 });
  });
});


describe("single condition-matrix row status", () => {
  it("uses the same auditable contrast rule as the aggregate gate", () => {
    const observations = [evidence("1", "support"), evidence("2", "contradict")];
    const valid = { conditionCluster: "linked", supportingEvidenceIds: ["1"], contradictingEvidenceIds: ["2"], differingFields: ["substrate"], unknowns: [] };
    const invalid = { ...valid, differingFields: [] };
    const bundle = bundleFor(observations, [valid]);
    expect(isAuditableConditionContrast(valid, bundle)).toBe(true);
    expect(isAuditableConditionContrast(invalid, bundle)).toBe(false);
  });
});
