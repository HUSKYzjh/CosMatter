import { describe, expect, it } from "vitest";

import { demoBundle, type EvidenceCard, type ImportedBundle } from "./model";
import { deriveMissionArtifactStatus, taskBoundaryFingerprint } from "./missionArtifactStatus";

function withSourceLinks(cards: EvidenceCard[]) {
  return { ...demoBundle.literatureGraph, nodes: cards.map((card) => ({ nodeId: `paper:${card.provenance.documentId}`, kind: "evidence_paper", label: card.provenance.documentId, trustStatus: "reviewed" })), edges: cards.map((card) => ({ sourceId: `paper:${card.provenance.documentId}`, targetId: `evidence:${card.evidenceId}`, edgeType: "source_provenance", relationSource: "reviewed source map", trustStatus: "accepted" })) };
}
function bundle(overrides: Partial<ImportedBundle> = {}): ImportedBundle {
  return { ...demoBundle, stations: [], timeline: [], evidenceCards: [], conditionMatrix: [], researchGapCandidates: [], sourceMapSummary: { documentCount: 0, segmentCount: 0, documentIds: [] }, auditSummary: { ...demoBundle.auditSummary, evidenceProvenance: null }, ...overrides };
}

describe("mission artifact status", () => {
  it("derives an empty task without inventing domain conditions", () => {
    const cards = deriveMissionArtifactStatus(bundle(), false);
    expect(cards.find((item) => item.key === "conditions")?.metrics).toEqual([{ key: "conditionClusters", value: 0 }, { key: "contradictions", value: 0 }, { key: "unknowns", value: 0 }]);
    expect(cards.find((item) => item.key === "conditions")?.state).toBe("pending");
  });

  it("marks an incomplete mission brief as pending instead of registered", () => {
    const cards = deriveMissionArtifactStatus(bundle({ mission: { ...demoBundle.mission, property: "" } }), false);
    const brief = cards.find((item) => item.key === "brief");
    expect(brief).toMatchObject({ state: "pending", next: "complete-brief" });
  });
  it("uses imported condition, evidence, and gap records only with reviewed source links", () => {
    const evidence: EvidenceCard = { evidenceId: "e1", claim: "claim", stance: "supports", conditions: {}, quote: "quote", reviewStatus: "accepted", provenance: { documentId: "doc", locator: "p1", source: "local", accessPolicy: "authorised" }, isSynthetic: false };
    const cards = deriveMissionArtifactStatus(bundle({
      conditionMatrix: [{ conditionCluster: "substrate=A", supportingEvidenceIds: ["e1"], contradictingEvidenceIds: ["e2"], differingFields: ["strain"], unknowns: ["thickness"] }],
      evidenceCards: [evidence], literatureGraph: withSourceLinks([evidence]),
      sourceMapSummary: { documentCount: 1, segmentCount: 2, documentIds: ["doc"] },
      researchGapCandidates: [{ gapId: "g1", problemDescription: "gap", evidenceIds: ["e1"], conflictOrMissingEvidence: ["e2"], noveltyStatus: "pending", actionability: "review", falsifiableHypothesis: "test", suggestedValidation: ["measure"], evidenceCompleteness: 1, reviewStatus: "candidate_requires_human_review" }],
      auditSummary: { ...demoBundle.auditSummary, evidenceProvenance: { acceptedEvidenceCount: 1, exactSourceMapMatchCount: 1, manualLocatorOnlyCount: 0, exactSourceMapMatchRate: 1 } },
    }), false);
    expect(cards.map((item) => item.state)).toEqual(["ready", "ready", "ready", "ready"]);
  });

  it("locks every card without erasing its derived counts", () => {
    const unlocked = deriveMissionArtifactStatus(bundle({ conditionMatrix: [{ conditionCluster: "A", supportingEvidenceIds: [], contradictingEvidenceIds: [], differingFields: [], unknowns: ["x"] }] }), false);
    const locked = deriveMissionArtifactStatus(bundle({ conditionMatrix: [{ conditionCluster: "A", supportingEvidenceIds: [], contradictingEvidenceIds: [], differingFields: [], unknowns: ["x"] }] }), true);
    expect(locked.every((item) => item.state === "recheck" && item.next === "reimport")).toBe(true);
    expect(locked[1].metrics).toEqual(unlocked[1].metrics);
  });

  it("normalises task-boundary fingerprints", () => {
    expect(taskBoundaryFingerprint({ ...demoBundle.mission, question: "  Why   now? " })).toBe(taskBoundaryFingerprint({ ...demoBundle.mission, question: "why now?" }));
  });
});
