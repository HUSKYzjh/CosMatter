import type { OperationalTelemetry, RunStatus, StageContract, WorkflowDag } from "./localApi";
import type { ImportedBundle } from "./model";

export function isLocalRunId(value: string): boolean {
  return /^[A-Za-z0-9][A-Za-z0-9_-]{0,254}$/.test(value);
}

export interface LocalRunLinkTarget { runId: string; documentId: string | null; }

export function parseLocalRunLink(hash: string): LocalRunLinkTarget | null {
  if (!hash.startsWith("#") || hash.length > 4_096) return null;
  const params = new URLSearchParams(hash.slice(1));
  const keys = [...params.keys()];
  const runId = params.get("run") ?? "";
  const documentId = params.get("document");
  if (!isLocalRunId(runId) || keys.length !== (documentId === null ? 1 : 2)
    || keys.some((key) => key !== "run" && key !== "document")) return null;
  if (documentId !== null && (!documentId || documentId.length > 255 || documentId.trim() !== documentId
    || /[\u0000-\u001f\u007f]/.test(documentId))) return null;
  return { runId, documentId };
}

export function localRunLink(origin: string, runId: string, documentId: string | null = null): string {
  const url = new URL("/?api=local", origin);
  const params = new URLSearchParams({ run: runId });
  if (documentId) params.set("document", documentId);
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
