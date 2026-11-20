import { expect, test, type Locator } from "@playwright/test";
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

function readyProfile(port: number) {
  const bundles = group.packages.map(item => item.package);
  const checked = { checked_at: "2026-11-18T03:00:00Z", dsh_version: "0.2.2-rc.3", matches_local_files: true, bundles };
  return {
    schema_version: "cosmatter.dsh-profile-status/v2", profile_name: "tui", installation_state: "installed",
    expected_bundle_count: bundles.length, declared_bundle_count: bundles.length, installed_bundle_count: bundles.length,
    packages: bundles.map(name => ({ package: name, dependency_kind: "local_link", install_status: "verified" })),
    composition_status: "not_checked_by_http_api", trust_status: "local_installation_snapshot_not_profile_boot_or_plugin_execution",
    composition_check: { ...checked, schema_version: "cosmatter.dsh-composition-check/v1" },
    tool_registry_check: { ...checked, schema_version: "cosmatter.dsh-tool-registry-check/v1",
      registered_tools: group.packages.flatMap(item => item.tools).sort(), loopback_check: { status: "verified", port } },
  };
}

async function verifyInPlaceCopy(button: Locator, status: Locator, preview: Locator) {
  await button.focus();
  await button.scrollIntoViewIfNeeded();
  const before = await button.boundingBox();
  const previewBefore = await preview.boundingBox();
  expect(before!.height).toBeGreaterThanOrEqual(44);
  await button.press("Enter");
  await expect(button).toBeFocused();
  await expect(status).toContainText("已复制");
  expect(await status.boundingBox()).toEqual(before);
  expect(await button.boundingBox()).toEqual(before);
  expect(await preview.boundingBox()).toEqual(previewBefore);
  return button.page().evaluate(() => navigator.clipboard.readText());
}

for (const viewport of [{ width: 320, height: 620 }, { width: 1360, height: 850 }]) {
  test(`returns from DSH to the chosen oversized brief field at ${viewport.width}px`, async ({ page, context, baseURL }) => {
    await page.setViewportSize(viewport);
    await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: new URL(baseURL!).origin });
    const writes: string[] = [];
    await page.route("**/api/**", route => {
      if (route.request().method() !== "GET") writes.push(route.request().method());
      return route.fulfill({ status: 503, json: {} });
    });
    await page.goto("/?api=local");
    const question = "BiFeO₃ 薄膜的温度和应变如何影响相稳定性？";
    await page.getByLabel("候选航向研究问题").fill(question);
    await page.getByRole("button", { name: "按原问题填写简报" }).press("Enter");

    const editor = page.locator(".launch-brief-editor");
    const material = editor.getByLabel("研究对象", { exact: true });
    const scope = editor.getByLabel("比较范围", { exact: true });
    const open = editor.getByRole("button", { name: "在 DSH 中继续" });
    const dialog = page.getByRole("dialog", { name: "DSH 工具与会话" });
    const draft = dialog.getByRole("region", { name: "DSH 聊天草稿" });
    const copy = draft.getByRole("button", { name: "复制到 DSH 聊天" });
    const materialIssue = draft.getByRole("button", { name: "返回修改研究对象" });
    const scopeIssue = draft.getByRole("button", { name: "返回修改比较范围" });
    await material.fill("材".repeat(301));
    await scope.fill("🧪".repeat(501));
    await editor.getByLabel("研究目标", { exact: true }).fill("相稳定性");
    await open.press("Enter");
    await expect(copy).toBeDisabled();
    await expect(materialIssue).toHaveAccessibleDescription("研究对象 · 已用 301，上限 300");
    await expect(scopeIssue).toHaveAccessibleDescription("比较范围 · 已用 1002，上限 1000");

    await scopeIssue.press("Enter");
    await expect(dialog).toHaveCount(0);
    await expect(scope).toBeFocused();
    await expect(scope).toBeInViewport({ ratio: 1 });
    await expect(scope).toHaveValue("🧪".repeat(501));
    await scope.fill("室温薄膜");
    await open.press("Enter");
    await expect(scopeIssue).toHaveCount(0);
    await expect(copy).toBeDisabled();
    await materialIssue.press("Enter");
    await expect(material).toBeFocused();
    await expect(material).toBeInViewport({ ratio: 1 });
    await expect(material).toHaveValue("材".repeat(301));
    await material.fill("BiFeO₃");

    await open.press("Enter");
    await expect(materialIssue).toHaveCount(0);
    await copy.press("Enter");
    await expect(draft.getByRole("status")).toHaveText("聊天草稿已复制。");
    const message = await page.evaluate(() => navigator.clipboard.readText());
    expect(JSON.parse(message.slice(message.indexOf("{")))).toEqual({ question, material: "BiFeO₃", property: "相稳定性", scope: "室温薄膜" });
    expect(writes).toEqual([]);
  });

  test(`copies the compared materials brief and launch command in place, with keyboard fallback at ${viewport.width}px`, async ({ page, context, baseURL }) => {
    await page.setViewportSize(viewport);
    await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: new URL(baseURL!).origin });
    const writes: string[] = [];
    await page.route("**/api/**", route => {
      const { pathname, port } = new URL(route.request().url());
      if (route.request().method() !== "GET") writes.push(pathname);
      if (pathname === "/api/plugins") return route.fulfill({ json: catalogue });
      if (pathname === "/api/dsh-profile") return route.fulfill({ json: readyProfile(Number(port)), headers: { "X-CosMatter-DSH-Receipts": "per-port-v1" } });
      return route.fulfill({ status: 503, json: {} });
    });
    await page.goto("/?api=local");
    const question = "比较 BaTiO₃ 和 BiFeO₃ 的居里温度，实验判据是否一致？";
    await page.getByLabel("候选航向研究问题").fill(question);
    await page.getByRole("button", { name: /条件分歧/ }).press("Enter");
    const editor = page.locator(".launch-brief-editor");
    const brief = {
      question: await editor.getByLabel("任务简报研究问题").inputValue(),
      material: await editor.getByLabel("研究对象", { exact: true }).inputValue(),
      property: await editor.getByLabel("研究目标", { exact: true }).inputValue(),
      scope: await editor.getByLabel("比较范围").inputValue(),
    };
    expect(brief.material).toBe("BaTiO₃ 和 BiFeO₃");
    expect(brief.property).toBe("居里温度");
    expect(brief.question).toContain(brief.material);
    expect(brief.scope).toContain(question);
    await editor.getByRole("button", { name: "在 DSH 中继续" }).press("Enter");

    const draft = page.getByRole("region", { name: "DSH 聊天草稿" });
    const launch = page.getByRole("region", { name: "打开 DSH 会话" });
    const commandButton = launch.getByRole("button", { name: "复制 DSH 启动命令" });
    const draftButton = draft.getByRole("button", { name: "复制到 DSH 聊天" });
    const preview = draft.locator(".dsh-draft-preview");
    await preview.locator("summary").press("Enter");
    const command = await verifyInPlaceCopy(commandButton, launch.getByRole("status"), preview);
    expect(command).toBe(`cosmatter open-dsh-workbench --port ${new URL(baseURL!).port}`);
    const message = await verifyInPlaceCopy(draftButton, draft.getByRole("status"), preview);
    expect(JSON.parse(message.slice(message.indexOf("{")))).toEqual(brief);
    await expect(preview.locator("pre")).toHaveText(message);

    await page.evaluate(() => {
      Object.defineProperty(navigator.clipboard, "writeText", { value: () => Promise.reject(new Error("Clipboard unavailable")) });
    });
    for (const [button, field, value] of [
      [commandButton, launch.getByRole("textbox", { name: "DSH 命令" }), command],
      [draftButton, draft.getByRole("textbox", { name: "DSH 聊天草稿" }), message],
    ] as const) {
      await button.press("Enter");
      await expect(field).toBeFocused();
      // Textareas normalize LF while the Windows clipboard uses CRLF.
      const fieldValue = value.replace(/\r\n/g, "\n");
      await expect(field).toHaveValue(fieldValue);
      expect(await field.evaluate((input: HTMLTextAreaElement) => [input.selectionStart, input.selectionEnd])).toEqual([0, fieldValue.length]);
      await field.press("ControlOrMeta+c");
      await expect.poll(() => page.evaluate(async () => (await navigator.clipboard.readText()).replace(/\r\n/g, "\n"))).toBe(fieldValue);
    }
    expect(writes).toEqual([]);
  });
}
