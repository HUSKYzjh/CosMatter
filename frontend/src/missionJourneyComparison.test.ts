import { describe, expect, it } from "vitest";

import { demoBundle, type EvidenceCard, type ResearchGapCandidate } from "./model";
import { missionJourney } from "./missionJourney";

const card = (id: string, stance: string): EvidenceCard => ({
  evidenceId: id, claim: "Reviewed claim", stance, conditions: {}, quote: "Reviewed excerpt.", reviewStatus: "accepted",
  provenance: { documentId: `doc-${id}`, locator: "p. 1", source: "local", accessPolicy: "authorized" }, isSynthetic: false,
});
const graphFor = (cards: EvidenceCard[]) => ({ ...demoBundle.literatureGraph, nodes: cards.map((item) => ({ nodeId: `paper:${item.provenance.documentId}`, kind: "evidence_paper", label: item.provenance.documentId, trustStatus: "reviewed" })), edges: cards.map((item) => ({ sourceId: `paper:${item.provenance.documentId}`, targetId: `evidence:${item.evidenceId}`, edgeType: "source_provenance", relationSource: "reviewed source map", trustStatus: "accepted" })) });
const candidate: ResearchGapCandidate = {
  gapId: "gap-1", problemDescription: "Candidate", evidenceIds: ["ev-1"], conflictOrMissingEvidence: [], noveltyStatus: "unverified", actionability: "review", falsifiableHypothesis: "test", suggestedValidation: [], evidenceCompleteness: .5,
  reviewStatus: "candidate_requires_human_review",
  counterevidenceBoundary: { status: "all_approved_counterevidence_queries_recorded", approvedQueryCount: 1, executedQueryCount: 1 },
};

describe("missionJourney research-extension completion", () => {
  it("does not complete extension from a candidate when cross-paper comparison artifacts are absent", () => {
    const evidence = [card("ev-1", "support")];
    const bundle = { ...demoBundle, evidenceCards: evidence, literatureGraph: graphFor(evidence), sourceMapSummary: { documentCount: 1, segmentCount: 1, documentIds: [] }, conditionMatrix: [], researchGapCandidates: [candidate] };
    expect(missionJourney(bundle, bundle.mission.question, "graph", false, false, { paperSelected: true, evidenceReady: true }).find((stage) => stage.id === "extend")?.state).toBe("ready");
  });

  it("keeps extension ready when comparison exists but the counterevidence boundary is not recorded", () => {
    const evidence = [card("ev-1", "support"), card("ev-2", "contradict")];
    const bundle = {
      ...demoBundle, evidenceCards: evidence, literatureGraph: graphFor(evidence), sourceMapSummary: { documentCount: 2, segmentCount: 2, documentIds: [] },
      auditSummary: { ...demoBundle.auditSummary, evidenceProvenance: { acceptedEvidenceCount: 2, exactSourceMapMatchCount: 2, manualLocatorOnlyCount: 0, exactSourceMapMatchRate: 1 } },
      conditionMatrix: [{ conditionCluster: "cluster", supportingEvidenceIds: ["ev-1"], contradictingEvidenceIds: ["ev-2"], differingFields: ["substrate"], unknowns: [] }], researchGapCandidates: [candidate],
    };
    expect(missionJourney(bundle, bundle.mission.question, "graph", false, false, { paperSelected: true, evidenceReady: true }).find((stage) => stage.id === "extend")?.state).toBe("ready");
  });
});


describe("missionJourney counterevidence completion", () => {
  it("completes extension only after comparison, the recorded counterevidence boundary, and a candidate coexist", () => {
    const evidence = [card("ev-1", "support"), card("ev-2", "contradict")];
    const bundle = {
      ...demoBundle,
      evidenceCards: evidence,
      literatureGraph: graphFor(evidence),
      sourceMapSummary: { documentCount: 2, segmentCount: 2, documentIds: [] },
      conditionMatrix: [{ conditionCluster: "cluster", supportingEvidenceIds: ["ev-1"], contradictingEvidenceIds: ["ev-2"], differingFields: ["substrate"], unknowns: [] }],
      researchGapCandidates: [candidate],
      auditSummary: { ...demoBundle.auditSummary, evidenceProvenance: { acceptedEvidenceCount: 2, exactSourceMapMatchCount: 2, manualLocatorOnlyCount: 0, exactSourceMapMatchRate: 1 }, counterevidence: { state: "ready" as const, plannedQueryCount: 1, executedQueryCount: 1 } },
    };
    expect(missionJourney(bundle, bundle.mission.question, "graph", false, false, { paperSelected: true, evidenceReady: true }).find((stage) => stage.id === "extend")?.state).toBe("complete");
  });

  it("does not complete extension from a candidate whose boundary belongs to a different counterevidence summary", () => {
    const evidence = [card("ev-1", "support"), card("ev-2", "contradict")];
    const bundle = {
      ...demoBundle,
      evidenceCards: evidence,
      literatureGraph: graphFor(evidence),
      sourceMapSummary: { documentCount: 2, segmentCount: 2, documentIds: [] },
      conditionMatrix: [{ conditionCluster: "cluster", supportingEvidenceIds: ["ev-1"], contradictingEvidenceIds: ["ev-2"], differingFields: ["substrate"], unknowns: [] }],
      researchGapCandidates: [candidate],
      auditSummary: { ...demoBundle.auditSummary, evidenceProvenance: { acceptedEvidenceCount: 2, exactSourceMapMatchCount: 2, manualLocatorOnlyCount: 0, exactSourceMapMatchRate: 1 }, counterevidence: { state: "ready" as const, plannedQueryCount: 2, executedQueryCount: 2 } },
    };
    expect(missionJourney(bundle, bundle.mission.question, "graph", false, false, { paperSelected: true, evidenceReady: true }).find((stage) => stage.id === "extend")?.state).toBe("ready");
  });
});
