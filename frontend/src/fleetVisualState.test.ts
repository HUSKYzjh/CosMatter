import { describe, expect, it } from "vitest";

import { fleetVisualState, fleetVisualStyle } from "./fleetVisualState";
import { demoBundle, type ImportedBundle } from "./model";

function emptyBundle(): ImportedBundle {
  return {
    ...demoBundle,
    status: null,
    stations: [],
    facilities: [],
    evidenceCards: [],
    conditionMatrix: [],
    researchGapCandidates: [],
    sourceMapSummary: { documentCount: 0, segmentCount: 0, documentIds: [] },
    materialFactSummary: { documentCount: 0, factCount: 0 },
    auditSummary: { ...demoBundle.auditSummary, reportEvidence: null, evidenceProvenance: null },
    timeline: [],
    literatureGraph: { trustStatus: "empty", nodes: [], edges: [] },
    report: null,
  };
}

describe("fleetVisualState", () => {
  it("keeps missing local artifacts in a static, low-signal state", () => {
    const bundle = emptyBundle();
    for (const kind of ["discover", "workflow", "graph", "reader", "horizon"] as const) {
      const state = fleetVisualState(bundle, kind);
      expect(state.mode).toBe("idle");
      expect(state.progress).toBe(0);
      expect(state.signal).toBe(0);
    }
  });

  it("derives discovery and workflow motion from actual active stations", () => {
    const discovery = fleetVisualState(demoBundle, "discover");
    const workflow = fleetVisualState(demoBundle, "workflow");
    expect(discovery.mode).toBe("active");
    expect(discovery.signal).toBeGreaterThan(0);
    expect(workflow.mode).toBe("active");
    expect(workflow.density).toBeGreaterThan(0);
  });

  it("does not mark a research horizon ready without a rendered counterevidence boundary", () => {
    const reviewBundle: ImportedBundle = {
      ...emptyBundle(),
      researchGapCandidates: [{ gapId: "gap_1", problemDescription: "condition boundary", evidenceIds: ["e_1"], conflictOrMissingEvidence: ["strain"], noveltyStatus: "bounded", actionability: "review", falsifiableHypothesis: "test", suggestedValidation: ["measure"], evidenceCompleteness: 1, reviewStatus: "candidate_requires_human_review" }],
      auditSummary: { ...demoBundle.auditSummary, reportEvidence: { acceptedEvidenceCount: 1, manifestCoverage: 1, gapEvidenceCoverage: 1, structuredReportIdentifierCoverage: 1, acceptedEvidenceLocatorRenderedCoverage: 1, executedGapCounterevidenceBoundaryCount: 0, gapCounterevidenceBoundaryRenderedCoverage: 0 } },
    };
    expect(fleetVisualState(reviewBundle, "horizon").mode).toBe("review");

    const readyBundle: ImportedBundle = {
      ...reviewBundle,
      auditSummary: { ...reviewBundle.auditSummary, reportEvidence: { ...reviewBundle.auditSummary.reportEvidence!, executedGapCounterevidenceBoundaryCount: 1, gapCounterevidenceBoundaryRenderedCoverage: 1 } },
    };
    expect(fleetVisualState(readyBundle, "horizon").mode).toBe("ready");
  });

  it("writes only the visual CSS variables required by the decoration", () => {
    const style = fleetVisualStyle(fleetVisualState(demoBundle, "discover"));
    expect(style).toContain("--fleet-progress:");
    expect(style).toContain("--fleet-signal:");
    expect(style).toContain("--fleet-density:");
    expect(style).toContain("--fleet-mode:");
  });
});
