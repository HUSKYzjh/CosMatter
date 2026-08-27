import type { ImportedBundle, Mission } from "./model";

/**
 * Creates the browser-side shell for a freshly confirmed task.  It contains a
 * mission marker only—not an inherited demo graph, evidence card, condition
 * matrix, report, or Gap candidate.  A real UI bundle may later replace this
 * shell after an explicit local retrieval/import operation.
 */
export function emptyBundleForMission(mission: Mission): ImportedBundle {
  return {
    schemaVersion: "1.0",
    mission,
    source: "local-file",
    fleet: null,
    status: { missionState: "INTAKE", retryCount: 0, retryBudget: 0, returnReason: null },
    stations: [{ stationType: "question_intake", status: "active" }],
    facilities: [],
    evidenceCards: [],
    conditionMatrix: [],
    researchGapCandidates: [],
    materialFacts: null,
    sourceMapSummary: { documentCount: 0, segmentCount: 0, documentIds: [] },
    materialFactSummary: { documentCount: 0, factCount: 0 },
    auditSummary: {
      counterevidence: { state: "plan_not_approved", plannedQueryCount: 0, executedQueryCount: 0 },
      reportEvidence: null,
      evidenceProvenance: null,
      sciverseAgenticSearchCount: 0,
      submissionReadiness: { frozenCorpus: null, humanAnnotation: null, bibliographicSource: null },
      evaluation: { evidenceQuality: null, retrieval: null, materialFacts: null, researchGaps: null },
    },
    timeline: [],
    literatureRelations: null,
    crossrefRelations: null,
    literatureGraph: {
      trustStatus: "mission_marker_only_no_literature_has_been_imported",
      nodes: [{ nodeId: `mission:${mission.missionId}`, kind: "mission", label: `${mission.material} / ${mission.property}`, trustStatus: "mission_navigation" }],
      edges: [],
    },
    report: null,
  };
}

export function newLocalMissionId(): string {
  const random = globalThis.crypto?.randomUUID?.().replaceAll("-", "").slice(0, 16);
  return `local_${random ?? `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`}`;
}
