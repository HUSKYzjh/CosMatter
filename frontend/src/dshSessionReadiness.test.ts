import { expect, it } from "vitest";
import { packages } from "../../plugins/dsh-plugin-group.json";
import type { DshProfileStatus } from "./localApi";
import { dshSessionReadiness } from "./dshSessionReadiness";

const port = 8789;
const receipt = {
  checked_at: "2026-11-19T02:00:00Z", dsh_version: "0.2.2-rc.3",
  matches_local_files: true, bundles: packages.map(bundle => bundle.package),
};
const composition = { ...receipt, schema_version: "cosmatter.dsh-composition-check/v1" } as const;
const registry = {
  ...receipt, schema_version: "cosmatter.dsh-tool-registry-check/v1",
  registered_tools: packages.flatMap(bundle => bundle.tools).sort(), loopback_check: { port, status: "verified" },
} as const;
const profile: DshProfileStatus = {
  schema_version: "cosmatter.dsh-profile-status/v2", profile_name: "tui", installation_state: "installed",
  expected_bundle_count: 7, declared_bundle_count: 7, installed_bundle_count: 7,
  packages: packages.map(bundle => ({ package: bundle.package, dependency_kind: "local_link", install_status: "verified" })),
  composition_status: "not_checked_by_http_api", composition_check: composition, tool_registry_check: registry,
  trust_status: "local_installation_snapshot_not_profile_boot_or_plugin_execution",
};

it("prioritises loading and installation problems when the capability catalogue is also unavailable", () => {
  const partial: DshProfileStatus = { ...profile, installation_state: "partial", installed_bundle_count: 6 };
  expect(dshSessionReadiness(partial, "loading", "unavailable", port)).toBe("checking");
  expect(dshSessionReadiness(partial, "ready", "loading", port)).toBe("checking");
  expect(dshSessionReadiness(partial, "ready", "unavailable", port)).toBe("repair-files");
  expect(dshSessionReadiness(null, "unavailable", "unavailable", port)).toBe("profile-unavailable");
  expect(dshSessionReadiness(profile, "ready", "unavailable", port)).toBe("catalogue-unavailable");
  expect(dshSessionReadiness(profile, "disabled", "ready", port)).toBe("disconnected");
});

it("offers repair only for a current incomplete local composition", () => {
  const incomplete = { ...composition, bundles: composition.bundles.slice(1) };
  const snapshot = { ...profile, composition_check: incomplete };
  expect(dshSessionReadiness({ ...profile, composition_check: undefined }, "ready", "ready", port)).toBe("composition-unchecked");
  expect(dshSessionReadiness(snapshot, "ready", "ready", port)).toBe("repair-composition");
  expect(dshSessionReadiness(snapshot, "ready", "ready", null)).toBe("composition-check");
  const stale = { ...snapshot, composition_check: { ...incomplete, matches_local_files: false } };
  expect(dshSessionReadiness(stale, "ready", "ready", port)).toBe("composition-check");
});

it("requires current registration for all tools and a successful check of the workbench port", () => {
  for (const check of [undefined, { ...registry, matches_local_files: false }, { ...registry, registered_tools: registry.registered_tools.slice(1) }]) {
    expect(dshSessionReadiness({ ...profile, tool_registry_check: check }, "ready", "ready", port)).toBe("registry-check");
  }
  const failed = { ...profile, tool_registry_check: { ...registry, loopback_check: { port, status: "unavailable" as const } } };
  expect(dshSessionReadiness(failed, "ready", "ready", port)).toBe("loopback-check");
  expect(dshSessionReadiness(profile, "ready", "ready", port + 1)).toBe("loopback-check");
  expect(dshSessionReadiness(profile, "ready", "ready", port)).toBe("ready");
  expect(dshSessionReadiness(failed, "ready", "ready", null)).toBe("ready");
});
