import type { OperationalTelemetry, RunStatus, StageContract, WorkflowDag } from "./localApi";
import type { ImportedBundle } from "./model";

export function isLocalRunId(value: string): boolean {
  return /^[A-Za-z0-9][A-Za-z0-9_-]{0,254}$/.test(value);
}

export function localRunLinkId(hash: string): string | null {
  const runId = hash.startsWith("#run=") ? hash.slice(5) : "";
  return isLocalRunId(runId) ? runId : null;
}

export function localRunLink(origin: string, runId: string): string {
  const url = new URL("/?api=local", origin);
  url.hash = `run=${runId}`;
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
