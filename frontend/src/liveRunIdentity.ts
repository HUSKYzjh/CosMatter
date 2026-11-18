import type { OperationalTelemetry, RunStatus, StageContract, WorkflowDag } from "./localApi";
import type { ImportedBundle } from "./model";

export function isLocalRunId(value: string): boolean {
  return /^[A-Za-z0-9][A-Za-z0-9_-]{0,254}$/.test(value);
}

export interface LocalRunLinkTarget { runId: string; documentId: string | null; evidenceId: string | null; }

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
  if (!isLocalRunId(runId) || new Set(keys).size !== keys.length || keys.some((key) => !["run", "document", "evidence"].includes(key))) return null;
  if (documentId !== null && !validLinkIdentifier(documentId, 255)) return null;
  if (evidenceId !== null && (!documentId || !validLinkIdentifier(evidenceId, 200))) return null;
  return { runId, documentId, evidenceId };
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
