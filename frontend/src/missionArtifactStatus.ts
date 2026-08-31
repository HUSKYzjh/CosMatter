import type { ImportedBundle, Mission } from "./model";
import { auditableAcceptedEvidence } from "./evidenceLinking";
import { evidenceProvenanceAuditComplete } from "./evidenceProvenanceAudit";
import { hasAuditableGapEvidenceBasis } from "./gapEvidenceReferences";

export type ArtifactKey = "brief" | "conditions" | "evidence" | "counterevidence";
export type ArtifactState = "ready" | "pending" | "recheck";

export interface ArtifactMetric { key: string; value: string | number; }
export interface MissionArtifactStatus {
  key: ArtifactKey;
  state: ArtifactState;
  metrics: ArtifactMetric[];
  detail: string;
  next: "complete-brief" | "orchestrate" | "import-conditions" | "verify-source" | "review-counterevidence" | "reimport";
}

export function taskBoundaryFingerprint(mission: Mission): string {
  return [mission.question, mission.material, mission.property, mission.scope].map((value) => value.trim().replaceAll(/\s+/g, " ").toLocaleLowerCase()).join("\u241f");
}

export function deriveMissionArtifactStatus(bundle: ImportedBundle, locked: boolean): MissionArtifactStatus[] {
  const missionReady = Boolean(bundle.mission.question.trim() && bundle.mission.material.trim() && bundle.mission.property.trim() && bundle.mission.scope.trim());
  const conditionClusters = new Set(bundle.conditionMatrix.map((row) => row.conditionCluster)).size;
  const contradictionCount = bundle.conditionMatrix.reduce((sum, row) => sum + row.contradictingEvidenceIds.length, 0);
  const unknownCount = bundle.conditionMatrix.reduce((sum, row) => sum + row.unknowns.length, 0);
  const provenance = bundle.auditSummary.evidenceProvenance;
  const auditableEvidence = auditableAcceptedEvidence(bundle);
  const auditableGapCandidateCount = bundle.researchGapCandidates.filter((candidate) => hasAuditableGapEvidenceBasis(candidate, bundle)).length;
  const hasLocatorAudit = evidenceProvenanceAuditComplete(provenance, bundle.evidenceCards.length);
  const recheck = (state: ArtifactState): ArtifactState => locked ? "recheck" : state;
  const next = <T extends MissionArtifactStatus["next"]>(value: T): T => locked ? "reimport" as T : value;

  return [
    {
      key: "brief", state: recheck(missionReady ? "ready" : "pending"),
      metrics: [{ key: "material", value: bundle.mission.material }, { key: "property", value: bundle.mission.property }, { key: "scope", value: bundle.mission.scope }],
      detail: bundle.mission.question, next: next(missionReady ? "orchestrate" : "complete-brief"),
    },
    {
      key: "conditions", state: recheck(conditionClusters ? "ready" : "pending"),
      metrics: [{ key: "conditionClusters", value: conditionClusters }, { key: "contradictions", value: contradictionCount }, { key: "unknowns", value: unknownCount }],
      detail: conditionClusters ? `${conditionClusters} condition cluster(s) are available in the imported artifact.` : "No condition cluster has been imported for this task.", next: next("import-conditions"),
    },
    {
      key: "evidence", state: recheck(auditableEvidence.length && bundle.sourceMapSummary.segmentCount && hasLocatorAudit ? "ready" : "pending"),
      metrics: [{ key: "acceptedEvidence", value: auditableEvidence.length }, { key: "sourceDocuments", value: bundle.sourceMapSummary.documentCount }, { key: "sourceSegments", value: bundle.sourceMapSummary.segmentCount }],
      detail: hasLocatorAudit ? "Imported audit records include exact source-map matches." : "No verified source-map match is available for the current artifact.", next: next("verify-source"),
    },
    {
      key: "counterevidence", state: recheck(auditableGapCandidateCount || contradictionCount || unknownCount ? "ready" : "pending"),
      metrics: [{ key: "gapCandidates", value: auditableGapCandidateCount }, { key: "contradictions", value: contradictionCount }, { key: "unknowns", value: unknownCount }],
      detail: auditableGapCandidateCount || contradictionCount || unknownCount ? "Imported candidates and condition boundaries remain pending human review." : "No counterevidence boundary has been recorded for this task.", next: next("review-counterevidence"),
    },
  ];
}
