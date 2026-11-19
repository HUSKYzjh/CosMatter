import { afterEach, describe, expect, it, vi } from "vitest";

import { getDshProfileStatus, isDshProfileStatus, LOCAL_API_READ_TIMEOUT_MS } from "./localApi";

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

describe("DSH profile receipt compatibility", () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

  const mockProfile = (response: Response) => {
    vi.stubGlobal("window", globalThis);
    const fetch = vi.fn().mockResolvedValueOnce(response);
    vi.stubGlobal("fetch", fetch);
    return fetch;
  };

  it("accepts an advertised receipt mode without the compatibility probe", async () => {
    for (const mode of ["per-port-v1", "future-version"]) {
      const fetch = mockProfile(Response.json(snapshot(), { headers: { "X-CosMatter-DSH-Receipts": mode } }));
      await expect(getDshProfileStatus()).resolves.toEqual({ profile: snapshot(), health: "ready" });
      expect(fetch).toHaveBeenCalledTimes(1);
    }
  });

  it("rejects a malformed profile before probing for an older workbench", async () => {
    const fetch = mockProfile(Response.json({ schema_version: "cosmatter.dsh-profile-status/v2" }));
    await expect(getDshProfileStatus()).rejects.toMatchObject({ failure: "transport" });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("identifies the specific unknown-route 404 with or without the original HTTP reason phrase", async () => {
    const html = "<p>Error code: 404</p><p>Message: Unknown local API route.</p>";
    for (const probe of [
      new Response(null, { status: 404, statusText: "Unknown local API route" }),
      new Response(html, { status: 404, headers: { "Content-Type": "text/html;charset=utf-8", "Content-Length": String(html.length) } }),
    ]) {
      const fetch = mockProfile(Response.json(snapshot())).mockResolvedValueOnce(probe);
      await expect(getDshProfileStatus()).resolves.toEqual({ profile: snapshot(), health: "legacy" });
      expect(fetch).toHaveBeenNthCalledWith(2, "./api/recent-run-links?probe=1", expect.objectContaining({ credentials: "omit", redirect: "error" }));
    }
  });

  it("keeps the validated profile after ambiguous responses, without reading a run index", async () => {
    for (const probe of [Response.json({ runs: [] }), new Response(null, { status: 400 }), new Response(null, { status: 404 }), new Response(null, { status: 503 })]) {
      const json = vi.spyOn(probe, "json");
      const text = vi.spyOn(probe, "text");
      mockProfile(Response.json(snapshot())).mockResolvedValueOnce(probe);
      await expect(getDshProfileStatus()).resolves.toEqual({ profile: snapshot(), health: "ready" });
      expect(json).not.toHaveBeenCalled();
      expect(text).not.toHaveBeenCalled();
    }
  });

  it("keeps a profile ready after an inconclusive probe timeout", async () => {
    vi.useFakeTimers();
    mockProfile(Response.json(snapshot())).mockImplementationOnce((_path, { signal }: RequestInit) =>
      new Promise((_resolve, reject) => signal?.addEventListener("abort", () => reject(signal.reason), { once: true })));
    const result = getDshProfileStatus();
    await vi.advanceTimersByTimeAsync(LOCAL_API_READ_TIMEOUT_MS + 1);
    await expect(result).resolves.toEqual({ profile: snapshot(), health: "ready" });
  });
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

it("validates a redacted historical composition check independently of install state", () => {
  const composition_check = {
    schema_version: "cosmatter.dsh-composition-check/v1",
    checked_at: "2026-11-18T03:00:00Z",
    dsh_version: "0.2.2-rc.3",
    bundles: [packages[0].package],
    matches_local_files: false,
  };
  expect(isDshProfileStatus({ ...snapshot(), composition_check })).toBe(true);
  expect(isDshProfileStatus({ ...snapshot(), composition_check: { ...composition_check, bundles: [packages[0].package, packages[0].package] } })).toBe(false);
  expect(isDshProfileStatus({ ...snapshot(), composition_check: { ...composition_check, checked_at: "2026-11-31T03:00:00Z" } })).toBe(false);
  expect(isDshProfileStatus({ ...snapshot(), composition_check: { ...composition_check, configuration_stamp: "private" } })).toBe(false);
});

it("limits observed registry tools to the checked bundles and rejects internal fields", () => {
  const tool_registry_check = {
    schema_version: "cosmatter.dsh-tool-registry-check/v1",
    checked_at: "2026-11-18T03:00:00Z",
    dsh_version: "0.2.2-rc.3",
    bundles: [packages[0].package],
    matches_local_files: true,
    registered_tools: ["cosmatter_mission_create"],
  };
  expect(isDshProfileStatus({ ...snapshot(), tool_registry_check })).toBe(true);
  expect(isDshProfileStatus({ ...snapshot(), tool_registry_check: { ...tool_registry_check, registered_tools: [] } })).toBe(true);
  expect(isDshProfileStatus({ ...snapshot(), tool_registry_check: { ...tool_registry_check, registered_tools: ["cosmatter_workflow_status"] } })).toBe(false);
  expect(isDshProfileStatus({ ...snapshot(), tool_registry_check: { ...tool_registry_check, runtime_stamp: "private" } })).toBe(false);
  expect(isDshProfileStatus({ ...snapshot(), tool_registry_check: {
    ...tool_registry_check, loopback_check: { port: 8789, status: "verified" },
  } })).toBe(false);
  const catalogueCheck = {
    ...tool_registry_check, bundles: [packages[2].package], registered_tools: ["cosmatter_plugin_catalogue"],
    loopback_check: { port: 8789, status: "verified" },
  };
  expect(isDshProfileStatus({ ...snapshot(), tool_registry_check: catalogueCheck })).toBe(true);
  expect(isDshProfileStatus({ ...snapshot(), tool_registry_check: {
    ...catalogueCheck, loopback_check: { ...catalogueCheck.loopback_check, url: "http://127.0.0.1" },
  } })).toBe(false);
});
