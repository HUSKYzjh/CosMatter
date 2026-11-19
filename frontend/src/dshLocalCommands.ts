import { isLocalRunId, localRunLink, parseLocalRunLink } from "./liveRunIdentity";
import { localApiEnabled } from "./localApi";

const runReadTools = new Set([
  "cosmatter_workflow_status",
  "cosmatter_stage_contract",
  "cosmatter_operational_telemetry",
  "cosmatter_workflow_dag",
  "cosmatter_candidate_screening_template",
]);

export interface DshEvidenceTarget { documentId: string; evidenceId: string; }

export const BUNDLE_REPAIR_COMMAND = "cosmatter repair-dsh-bundles";
export function updatedWorkbenchCommand(runId?: string | null): string {
  return "cosmatter preview-ui --solid --api --port 0" + (runId && isLocalRunId(runId) ? ` --open-run ${runId}` : "");
}

export function dshProfileCheckCommand(port: number | null) {
  return `cosmatter check-dsh-profile --verify-tools${port ? ` --loopback-port ${port}` : ""}`;
}

export function localWorkbenchLocation() {
  const location = window.location;
  return location.protocol === "http:" && ["127.0.0.1", "localhost"].includes(location.hostname) ? location : null;
}

export function localEvidenceLink(runId: string, evidence: DshEvidenceTarget): string | null {
  const location = localWorkbenchLocation();
  if (!location) return null;
  const url = localRunLink(location.origin, runId, evidence.documentId, evidence.evidenceId);
  const target = parseLocalRunLink(new URL(url).hash);
  return target?.evidenceId === evidence.evidenceId && target.documentId === evidence.documentId ? url : null;
}

export function dshCatalogueCommand(tool: string, runId?: string | null, evidence?: DshEvidenceTarget | null): string | null {
  const location = localWorkbenchLocation();
  if (!location || !localApiEnabled()) return null;
  const port = location.port || "80";
  if (tool === "cosmatter_plugin_catalogue") return `cosmatter dsh-catalogue --port ${port}`;
  if (tool === "cosmatter_recent_runs") return `cosmatter dsh-recent-runs --port ${port}`;
  if (!runId || !isLocalRunId(runId)) return null;
  if (tool === "cosmatter_artifact_manifest") return `cosmatter dsh-run-artifacts ${runId} --port ${port}`;
  if (tool === "cosmatter_accepted_evidence_search" && evidence) {
    const link = localEvidenceLink(runId, evidence);
    return link ? `cosmatter dsh-evidence '${link}'` : null;
  }
  return runReadTools.has(tool) ? `cosmatter dsh-read ${tool} --run-id ${runId} --port ${port}` : null;
}
