import { createContext, type Accessor } from "solid-js";
import { packages } from "../../plugins/dsh-plugin-group.json";
import type { DshProfileHealth, DshProfileStatus } from "./localApi";

export const DshReadProfile = createContext<{
  profile: Accessor<DshProfileStatus | null>;
  health: Accessor<DshProfileHealth>;
  refresh: () => void;
}>();

const requiredTools = {
  status: ["cosmatter_workflow_status", "cosmatter_stage_contract"],
  recent: ["cosmatter_recent_runs"],
  artifacts: ["cosmatter_artifact_manifest"],
  evidence: ["cosmatter_accepted_evidence_search"],
  screening: ["cosmatter_candidate_screening_template"],
};
export type DshReadCommand = keyof typeof requiredTools;
export type DshReadIssue = { kind: "repair"; bundle: string } | { kind: "verify"; missingTools: string[] };

export function dshReadIssue(command: DshReadCommand, profile: DshProfileStatus | null, health: DshProfileHealth): DshReadIssue | null {
  if (!profile || health === "disabled" || health === "unavailable" || profile.installation_state === "unavailable") return null;
  const tools = requiredTools[command];
  const bundle = packages.find(entry => entry.tools.includes(tools[0]))?.package;
  if (!bundle) return null;
  const installed = profile.packages.find(entry => entry.package === bundle)?.install_status;
  if (installed === "missing_bundle" || installed === "invalid_bundle") return { kind: "repair", bundle };
  const registry = profile.tool_registry_check;
  if (!registry?.matches_local_files || !registry.bundles.includes(bundle)) return null;
  const missingTools = tools.filter(tool => !registry.registered_tools.includes(tool));
  return missingTools.length ? { kind: "verify", missingTools } : null;
}
