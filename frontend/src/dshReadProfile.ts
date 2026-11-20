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
export type DshReadIssue = { kind: "repair"; bundle: string; missingTools?: string[] } | { kind: "verify"; missingTools?: string[] };

export function registryMatchesComposition(profile: DshProfileStatus | null): boolean {
  const composition = profile?.composition_check;
  const registry = profile?.tool_registry_check;
  return Boolean(composition?.matches_local_files && registry?.matches_local_files
    && composition.dsh_version === registry.dsh_version);
}

/** Registration repair relinks only packages covered by matching composition and registry checks. */
export function canRepairBundleRegistration(profile: DshProfileStatus | null, bundle: string): boolean {
  return registryMatchesComposition(profile) && Boolean(profile?.composition_check?.bundles.includes(bundle)
    && profile.tool_registry_check?.bundles.includes(bundle));
}

export function dshReadIssue(command: DshReadCommand, profile: DshProfileStatus | null, health: DshProfileHealth): DshReadIssue | null {
  if (!profile || health === "disabled" || health === "unavailable" || profile.installation_state === "unavailable") return null;
  const tools = requiredTools[command];
  const bundle = packages.find(entry => entry.tools.includes(tools[0]))?.package;
  if (!bundle) return null;
  const installed = profile.packages.find(entry => entry.package === bundle)?.install_status;
  if (installed === "missing_bundle" || installed === "invalid_bundle") return { kind: "repair", bundle };
  const registry = profile.tool_registry_check;
  if (!registry?.bundles.includes(bundle)) return null;
  const composition = profile.composition_check;
  if (!registry.matches_local_files || composition && (!composition.matches_local_files || composition.dsh_version !== registry.dsh_version)) {
    return { kind: "verify" };
  }
  const missingTools = tools.filter(tool => !registry.registered_tools.includes(tool));
  if (!missingTools.length) return null;
  return canRepairBundleRegistration(profile, bundle) ? { kind: "repair", bundle, missingTools } : { kind: "verify", missingTools };
}
