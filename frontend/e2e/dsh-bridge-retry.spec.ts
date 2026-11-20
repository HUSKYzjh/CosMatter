import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import group from "../../plugins/dsh-plugin-group.json" with { type: "json" };

const catalogue = {
  catalogue_api_version: "2.0", trust_status: "static_catalogue_not_plugin_execution_or_evidence_acceptance",
  plugins: [{
    plugin_id: "literature.metadata_retrieval", title: "Metadata retrieval", domain: "retrieval",
    entrypoint: "cosmatter.metadata_search:MetadataSearch", api_version: "2.0", capabilities: ["metadata_search"],
    data_classification: "public_metadata", automation_class: "external_authorized", requires_human_review: false,
    required_authorizations: ["mission_scoped_egress_consent", "metadata_provider_consent"],
    contract: { input_schema: "cosmatter.plugin-input/v1", output_schema: "cosmatter.plugin-output/v1",
      execution_mode: "provider_request", lifecycle: "authorize -> dispatch -> receipt" },
    execution_boundary: "Descriptor only; catalogue discovery grants no execution authority.",
  }],
};

function profile(graphInstalled: boolean, port: number) {
  const bundles = group.packages.map(bundle => bundle.package);
  const checked = { checked_at: "2026-11-18T03:00:00Z", dsh_version: "0.2.2-rc.3", matches_local_files: true, bundles };
  return {
    schema_version: "cosmatter.dsh-profile-status/v2", profile_name: "tui",
    composition_status: "not_checked_by_http_api", trust_status: "local_installation_snapshot_not_profile_boot_or_plugin_execution",
    expected_bundle_count: bundles.length, declared_bundle_count: bundles.length,
    installed_bundle_count: graphInstalled ? bundles.length : bundles.length - 1,
    installation_state: graphInstalled ? "installed" : "partial",
    packages: bundles.map(name => ({ package: name, dependency_kind: "local_link",
      install_status: !graphInstalled && name === "@cosmatter/dsh-graph-plugin" ? "missing_bundle" : "verified" })),
    ...(graphInstalled && {
      composition_check: { ...checked, schema_version: "cosmatter.dsh-composition-check/v1" },
      tool_registry_check: { ...checked, schema_version: "cosmatter.dsh-tool-registry-check/v1",
        registered_tools: group.packages.flatMap(bundle => bundle.tools).sort(), loopback_check: { status: "verified", port } },
    }),
  };
}

for (const initiallyInstalled of [true, false]) {
  test(`bridge catalogue retry waits for a fresh profile when a bundle was ${initiallyInstalled ? "removed" : "repaired"}`, async ({ page }) => {
    const run = "run_retry_bridge";
    const bundle = JSON.parse(await readFile(resolve("..", "examples/ui-demo/route_diagnostics.json"), "utf8"));
    let retrying = false;
    let profileReads = 0;
    let releaseProfile!: () => void;
    const pending = new Promise<void>(resolve => { releaseProfile = resolve; });
    await page.route("**/api/**", async route => {
      const { pathname, port } = new URL(route.request().url());
      if (pathname === `/api/runs/${run}/status`) return route.fulfill({ json: { run_id: run, mission_id: bundle.mission.mission_id, state: "INTAKE" } });
      if (pathname === `/api/runs/${run}/ui`) return route.fulfill({ json: bundle });
      if (pathname === "/api/plugins" && retrying) return route.fulfill({ json: catalogue });
      if (pathname === "/api/dsh-profile") {
        profileReads++;
        const installed = retrying ? !initiallyInstalled : initiallyInstalled;
        if (retrying) await pending;
        return route.fulfill({ json: profile(installed, Number(port)), headers: { "X-CosMatter-DSH-Receipts": "per-port-v1" } });
      }
      return route.fulfill({ status: 503, json: {} });
    });
    await page.goto(`/?api=local#run=${run}`);
    const bridge = page.getByRole("region", { name: "DSH 插件桥状态" });
    const verdict = bridge.getByRole("region", { name: "DSH 启用结论" });
    const launch = verdict.getByRole("button", { name: "复制 DSH 启动命令" });
    await expect(verdict).toContainText(initiallyInstalled ? "工作台未能读取插件目录" : "插件安装未齐", { timeout: 20_000 });
    const readsBeforeRetry = profileReads;
    retrying = true;
    try {
      await bridge.getByRole("button", { name: "重试目录连接" }).press("Enter");
      await expect(bridge).toHaveClass(/state-ready/);
      await expect(verdict).toContainText("正在核验 DSH 启用条件");
      await expect(launch).toHaveCount(0);
      await expect(verdict.locator("strong")).toBeFocused();
      await expect.poll(() => profileReads).toBe(readsBeforeRetry + 1);
    } finally {
      releaseProfile();
    }
    if (initiallyInstalled) {
      await expect(verdict).toContainText("插件安装未齐");
      await expect(launch).toHaveCount(0);
    } else {
      await expect(verdict).toContainText("插件注册与本机连通已核验");
      await expect(launch).toBeVisible();
      await expect(verdict.locator("code").filter({ hasText: "open-dsh-workbench" })).toContainText(`--run-id ${run}`);
    }
  });
}
