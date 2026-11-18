import { expect, it } from "vitest";

import { isDshProfileStatus } from "./localApi";

const packages = ["mission", "observability", "policy", "research", "review", "document", "graph"].map((name) => ({
  package: `@cosmatter/dsh-${name}-plugin`, install_status: "verified" as const, dependency_kind: "local_link" as const,
}));
const snapshot = () => ({
  schema_version: "cosmatter.dsh-profile-status/v2" as const,
  profile_name: "tui" as const,
  installation_state: "installed" as const,
  expected_bundle_count: 7 as const,
  declared_bundle_count: 7,
  installed_bundle_count: 7,
  packages,
  composition_status: "not_checked_by_http_api" as const,
  trust_status: "local_installation_snapshot_not_profile_boot_or_plugin_execution" as const,
});

it("accepts a complete redacted TUI dependency snapshot", () => {
  expect(isDshProfileStatus(snapshot())).toBe(true);
});

it("rejects inconsistent counts, package order, and leaked dependency values", () => {
  expect(isDshProfileStatus({ ...snapshot(), installed_bundle_count: 6 })).toBe(false);
  expect(isDshProfileStatus({ ...snapshot(), packages: [...packages].reverse() })).toBe(false);
  expect(isDshProfileStatus({ ...snapshot(), packages: packages.map((item, index) => index ? item : { ...item, reference: "D:/private" }) })).toBe(false);
});

it("keeps all declared dependencies distinct from physically verified bundles", () => {
  const partial = {
    ...snapshot(),
    installed_bundle_count: 6,
    installation_state: "partial",
    packages: [{ ...packages[0], install_status: "missing_bundle" }, ...packages.slice(1)],
  };
  expect(isDshProfileStatus(partial)).toBe(true);
  expect(isDshProfileStatus({ ...partial, installation_state: "installed" })).toBe(false);
  expect(isDshProfileStatus({ ...partial, declared_bundle_count: 6 })).toBe(false);
});
