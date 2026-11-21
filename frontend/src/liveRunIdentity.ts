import type { OperationalTelemetry, RunStatus, StageContract, WorkflowDag } from "./localApi";
import type { ImportedBundle } from "./model";

export function isLocalRunId(value: string): boolean {
  return /^[A-Za-z0-9][A-Za-z0-9_-]{0,254}$/.test(value);
}

export function isLoopbackWorkbenchLocation(location: Pick<URL, "protocol" | "hostname">): boolean {
  return location.protocol === "http:" && ["127.0.0.1", "localhost"].includes(location.hostname);
}

export interface LocalRunLinkTarget { runId: string; documentId: string | null; evidenceId: string | null; screeningRevision?: string; artifactList?: true; }

function validLinkIdentifier(value: string, maxLength: number): boolean {
  return value.length > 0 && value.length <= maxLength && value.trim() === value && !/[\u0000-\u001f\u007f]/.test(value);
}

export function parseLocalRunLink(hash: string): LocalRunLinkTarget | null {
  if (!hash.startsWith("#") || hash.length > 4_608) return null;
  const params = new URLSearchParams(hash.slice(1));
  const keys = [...params.keys()];
  const runId = params.get("run") ?? "";
  const documentId = params.get("document");
  const evidenceId = params.get("evidence");
  const screeningRevision = params.get("screening");
  const artifacts = params.get("artifacts");
  if (!isLocalRunId(runId) || new Set(keys).size !== keys.length || keys.some((key) => !["run", "document", "evidence", "screening", "artifacts"].includes(key))) return null;
  if (documentId !== null && !validLinkIdentifier(documentId, 255)) return null;
  if (evidenceId !== null && (!documentId || !validLinkIdentifier(evidenceId, 200))) return null;
  if (screeningRevision !== null && (documentId !== null || evidenceId !== null || !/^[a-f0-9]{64}$/.test(screeningRevision))) return null;
  if (artifacts !== null && (artifacts !== "1" || documentId !== null || evidenceId !== null || screeningRevision !== null)) return null;
  return { runId, documentId, evidenceId, ...(screeningRevision === null ? {} : { screeningRevision }), ...(artifacts === "1" ? { artifactList: true } : {}) };
}

export function localRunLink(origin: string, runId: string, documentId: string | null = null, evidenceId: string | null = null): string {
  const url = new URL("/?api=local", origin);
  const params = new URLSearchParams({ run: runId });
  if (documentId) {
    params.set("document", documentId);
    if (evidenceId) params.set("evidence", evidenceId);
  }
  url.hash = params.toString();
  return url.href;
}

export function localRunScreeningLink(origin: string, runId: string, screeningRevision: string): string {
  const url = new URL("/?api=local", origin);
  url.hash = new URLSearchParams({ run: runId, screening: screeningRevision }).toString();
  return url.href;
}

export function localRunArtifactsLink(origin: string, runId: string): string {
  const url = new URL("/?api=local", origin);
  url.hash = new URLSearchParams({ run: runId, artifacts: "1" }).toString();
  return url.href;
}

/** Keep every loopback projection bound to the run and mission that produced it. */
export function liveBundleMatchesRun(runId: string, status: RunStatus, bundle: ImportedBundle): boolean {
  return status.run_id === runId && status.mission_id === bundle.mission.missionId;
}

export function runtimeProjectionsMatchRun(runId: string, contract: StageContract, dag: WorkflowDag, telemetry: OperationalTelemetry): boolean {
  return contract.run_id === runId
    && dag.run_id === runId
    && telemetry.run_id === runId
    && contract.mission_id === dag.mission_id
    && contract.mission_id === telemetry.mission_id;
}
