import { expect, test } from "@playwright/test";
import group from "../../plugins/dsh-plugin-group.json" with { type: "json" };

const catalogue = {
  catalogue_api_version: "2.0", trust_status: "static_catalogue_not_plugin_execution_or_evidence_acceptance",
  plugins: [{
    plugin_id: "literature.metadata_retrieval", title: "Metadata retrieval", domain: "retrieval", api_version: "2.0",
    entrypoint: "cosmatter.metadata_search:MetadataSearch", capabilities: ["metadata_search"], data_classification: "public_metadata",
    automation_class: "external_authorized", required_authorizations: ["mission_scoped_egress_consent", "metadata_provider_consent"],
    requires_human_review: false, contract: { input_schema: "cosmatter.plugin-input/v1", output_schema: "cosmatter.plugin-output/v1",
      execution_mode: "provider_request", lifecycle: "authorize -> dispatch -> receipt" },
    execution_boundary: "Descriptor only; catalogue discovery grants no execution authority.",
  }],
};

type Phase = "missing-files" | "missing-composition" | "missing-tool" | "ready";
const bundles = group.packages.map(bundle => bundle.package);
const tools = group.packages.flatMap(bundle => bundle.tools).sort();
const missing = "cosmatter_candidate_screening_template";

function profile(phase: Phase, port: number) {
  const filesMissing = phase === "missing-files";
  const snapshot = {
    schema_version: "cosmatter.dsh-profile-status/v2", profile_name: "tui",
    composition_status: "not_checked_by_http_api", trust_status: "local_installation_snapshot_not_profile_boot_or_plugin_execution",
    expected_bundle_count: bundles.length, declared_bundle_count: bundles.length,
    installed_bundle_count: bundles.length - (filesMissing ? 1 : 0), installation_state: filesMissing ? "partial" : "installed",
    packages: bundles.map((name, index) => ({ package: name, dependency_kind: "local_link",
      install_status: filesMissing && index === 0 ? "missing_bundle" : "verified" })),
  };
  if (filesMissing) return snapshot;
  const checked = { checked_at: "2026-11-18T03:00:00Z", dsh_version: "0.2.2-rc.3", matches_local_files: true, bundles };
  const composition = { ...checked, schema_version: "cosmatter.dsh-composition-check/v1",
    bundles: phase === "missing-composition" ? bundles.slice(1) : bundles };
  if (phase === "missing-composition") return { ...snapshot, composition_check: composition };
  return { ...snapshot, composition_check: composition, tool_registry_check: {
    ...checked, schema_version: "cosmatter.dsh-tool-registry-check/v1",
    registered_tools: phase === "missing-tool" ? tools.filter(name => name !== missing) : tools,
    loopback_check: { status: "verified", port },
  } };
}

for (const width of [320, 1280]) {
  test("offers the port check in the same keyboard sequence as first-time repair at " + width + "px", async ({ page, baseURL }) => {
    await page.setViewportSize({ width, height: 580 });
    const port = Number(new URL(baseURL!).port);
    let phase: Phase = width === 320 ? "missing-files" : "missing-composition";
    const writes: string[] = [];
    await page.addInitScript(() => {
      Object.defineProperty(navigator, "clipboard", { configurable: true, value: {
        writeText: async (value: string) => { document.documentElement.dataset.copied = value; },
      } });
    });
    await page.route("**/api/**", route => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (request.method() !== "GET") writes.push(path);
      if (path === "/api/plugins") return route.fulfill({ json: catalogue });
      if (path === "/api/dsh-profile") return route.fulfill({ json: profile(phase, port), headers: { "X-CosMatter-DSH-Receipts": "per-port-v1" } });
      return route.fulfill({ status: 503, json: {} });
    });
    await page.goto("/?api=local", { waitUntil: "domcontentloaded" });
    const opener = page.locator(".launch-dsh-entry");
    await expect(opener).toHaveAccessibleDescription(phase === "missing-files" ? "待补齐" : "待启用");
    expect((await opener.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await opener.press("Enter");
    const dialog = page.getByRole("dialog", { name: "DSH 工具与会话" });
    const tab = dialog.getByRole("tab", { name: "DSH 会话" });
    await tab.press("Enter");
    const panel = dialog.getByRole("tabpanel", { name: "DSH 会话" });
    const repair = panel.getByRole("button", { name: "复制补齐命令" });
    const check = panel.getByRole("button", { name: "复制核验命令" });
    const refresh = panel.getByRole("button", { name: "刷新会话状态" });
    const launch = panel.getByRole("button", { name: "复制 DSH 启动命令" });
    await expect(panel).toContainText(phase === "missing-files" ? "本机插件安装未齐" : "本机 tui 配置缺少插件条目");
    await expect(launch).toHaveCount(0);
    await page.keyboard.press("Tab");
    await expect(panel).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(panel.getByRole("combobox", { name: "命令运行环境" })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(repair).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator("html")).toHaveAttribute("data-copied", "cosmatter repair-dsh-bundles");
    await page.keyboard.press("Tab");
    await expect(check).toBeFocused();
    await expect(check).toBeInViewport({ ratio: 1 });
    await page.keyboard.press("Enter");
    await expect(page.locator("html")).toHaveAttribute("data-copied", "cosmatter check-dsh-profile --verify-tools --loopback-port " + port);
    await page.keyboard.press("Tab");
    await expect(refresh).toBeFocused();
    phase = "missing-tool";
    await page.keyboard.press("Enter");
    await expect(panel).toContainText("已注册 19/20 个工具");
    await expect(panel.getByRole("button", { name: "在目录中查看 " + missing })).toBeVisible();
    await expect(repair).toHaveCount(1);
    await expect(check).toHaveCount(1);
    await expect(launch).toHaveCount(0);
    phase = "ready";
    await refresh.press("Enter");
    await expect(launch).toBeVisible();
    await expect(repair).toHaveCount(0);
    await expect(check).toHaveCount(0);
    await launch.press("Enter");
    await expect(page.locator("html")).toHaveAttribute("data-copied", "cosmatter open-dsh-workbench --port " + port);
    await page.keyboard.press("Escape");
    await expect(opener).toBeFocused();
    await expect(opener).toHaveAccessibleDescription("此端口已核验");
    expect(writes).toEqual([]);
  });
}
