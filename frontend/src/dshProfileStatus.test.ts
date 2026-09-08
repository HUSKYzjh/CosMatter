import { expect, it } from "vitest";

import { isDshProfileStatus } from "./localApi";

const packages = ["mission", "observability", "policy", "research", "review", "document", "graph"].map((name) => ({
  package: `@cosmatter/dsh-${name}-plugin`, installed: true, dependency_kind: "local_link" as const,
}));
const snapshot = () => ({
  schema_version: "cosmatter.dsh-profile-status/v1" as const,
  profile_name: "tui" as const,
  installation_state: "installed" as const,
  expected_bundle_count: 7 as const,
  installed_bundle_count: 7,
  packages,
  composition_status: "not_checked_by_http_api" as const,
  trust_status: "local_dependency_snapshot_not_profile_boot_or_plugin_execution" as const,
});

it("accepts a complete redacted TUI dependency snapshot", () => {
  expect(isDshProfileStatus(snapshot())).toBe(true);
});

it("rejects inconsistent counts, package order, and leaked dependency values", () => {
  expect(isDshProfileStatus({ ...snapshot(), installed_bundle_count: 6 })).toBe(false);
  expect(isDshProfileStatus({ ...snapshot(), packages: [...packages].reverse() })).toBe(false);
  expect(isDshProfileStatus({ ...snapshot(), packages: packages.map((item, index) => index ? item : { ...item, reference: "D:/private" }) })).toBe(false);
});
