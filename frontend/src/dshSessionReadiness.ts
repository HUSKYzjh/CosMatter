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

/** Compact verdict for the homepage entry. The session panel offers the matching action. */
export function dshEntryStatus(profile: DshProfileStatus | null, profileHealth: DshProfileHealth,
  catalogueHealth: HarnessCatalogueHealth, port: number, locale: "zh" | "en") {
  const state = dshSessionReadiness(profile, profileHealth, catalogueHealth, port);
  const label = (zh: string, en: string) => locale === "zh" ? zh : en;
  switch (state) {
    case "ready": return { tone: "ready", text: label("此端口已核验", "Port verified") };
    case "checking": return { tone: "neutral", text: label("读取中", "Checking") };
    case "repair-files": return { tone: "attention", text: profile?.installed_bundle_count
      ? label("待补齐", "Repair needed") : label("待安装", "Install needed") };
    case "repair-composition": return { tone: "attention", text: label("待启用", "Enable bundles") };
    case "workbench-update": return { tone: "attention", text: label("需更新", "Update needed") };
    case "profile-unavailable":
    case "catalogue-unavailable":
    case "disconnected": return { tone: "attention", text: label("连接待检查", "Check connection") };
    case "registry-check":
      if (missingRegisteredTools(profile).length) return { tone: "attention", text: label("工具缺项", "Tools missing") };
      break;
  }
  return { tone: "attention", text: label("待核验", "Check needed") };
}
