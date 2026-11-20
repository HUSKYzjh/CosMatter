import { packages } from "../../plugins/dsh-plugin-group.json";
import { canRepairBundleRegistration, registryMatchesComposition } from "./dshReadProfile";
import type { DshProfileHealth, DshProfileStatus, HarnessCatalogueHealth } from "./localApi";

export const DSH_TOOL_COUNT = packages.reduce((total, bundle) => total + bundle.tools.length, 0);

/** Only a bundle included in the current registry probe can have confirmed missing tools. */
export function missingRegisteredTools(profile: DshProfileStatus | null) {
  const receipt = profile?.tool_registry_check;
  if (!receipt) return [];
  return packages.filter(bundle => canRepairBundleRegistration(profile, bundle.package)).flatMap(bundle =>
    bundle.tools.filter(name => !receipt.registered_tools.includes(name)).map(name => ({ name, bundle: bundle.package })),
  );
}

export type DshSessionReadiness =
  | "checking" | "disconnected" | "workbench-update" | "repair-files" | "profile-unavailable" | "catalogue-unavailable"
  | "composition-unchecked" | "repair-composition" | "composition-check" | "registry-check" | "loopback-check" | "ready";

export function dshSessionReadiness(
  profile: DshProfileStatus | null, profileHealth: DshProfileHealth, catalogueHealth: HarnessCatalogueHealth, port: number | null,
): DshSessionReadiness {
  if (profileHealth === "loading" || catalogueHealth === "loading") return "checking";
  if (port && profileHealth === "legacy" && profile) return "workbench-update";
  const snapshot = profileHealth === "ready" || profileHealth === "legacy" ? profile : null;
  if (snapshot && snapshot.installation_state !== "unavailable" && snapshot.installed_bundle_count < snapshot.expected_bundle_count) {
    return "repair-files";
  }
  if (profileHealth === "unavailable" || snapshot?.installation_state === "unavailable") return "profile-unavailable";
  if (catalogueHealth === "unavailable") return "catalogue-unavailable";
  if (!snapshot || catalogueHealth !== "ready") return "disconnected";

  const composition = snapshot.composition_check;
  if (!composition) return "composition-unchecked";
  if (!composition.matches_local_files) return "composition-check";
  if (composition.bundles.length !== snapshot.expected_bundle_count) return port ? "repair-composition" : "composition-check";

  const registry = snapshot.tool_registry_check;
  if (!registry || !registryMatchesComposition(snapshot) || registry.bundles.length !== snapshot.expected_bundle_count
    || registry.registered_tools.length !== DSH_TOOL_COUNT) return "registry-check";
  const loopback = registry.loopback_check;
  if (port && (loopback?.port !== port || loopback.status !== "verified")) return "loopback-check";
  return "ready";
}
