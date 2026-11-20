import { expect, test } from "@playwright/test";

for (const locale of ["zh", "en"] as const) {
  test(`finds tools by the authorization label shown in the catalogue (${locale})`, async ({ page }) => {
    const zh = locale === "zh";
    await page.setViewportSize(zh ? { width: 320, height: 620 } : { width: 1360, height: 850 });
    await page.route("**/api/**", route => route.fulfill({ status: 503, json: {} }));
    await page.goto("/?api=local");
    if (!zh) await page.getByRole("button", { name: "Switch to English" }).click();
    await page.getByRole("button", { name: zh ? "DSH 插件" : "DSH plugins", exact: true }).press("Enter");
    const tab = zh ? "工具目录" : "Tool catalogue";
    await page.getByRole("tab", { name: tab }).press("Enter");
    const catalogue = page.getByRole("tabpanel", { name: tab });
    const search = catalogue.getByRole("searchbox");
    const tools = catalogue.locator(".dsh-tool-item");
    const stage = catalogue.getByLabel(zh ? "研究阶段" : "Research stage");
    const access = catalogue.getByLabel(zh ? "授权类型" : "Authorization type");
    const badge = zh ? "需逐任务授权" : "Mission authorization required";
    const visibleLabel = tools.locator("summary").getByText(badge, { exact: true });
    await expect(visibleLabel).toHaveCount(4);

    await search.fill(badge);
    await expect(tools).toHaveCount(4);
    await expect(visibleLabel).toHaveCount(4);
    await expect(access).toHaveValue("all");
    await stage.selectOption("parse");
    const option = (await access.locator('option[value="external"]').innerText()).trim();
    await search.fill(`${option} MinerU`);
    await expect(tools.locator("summary code")).toHaveText(["cosmatter_mineru_source_submit", "cosmatter_mineru_task_poll"]);
    await search.fill(`${option} MinerU source_submit`);
    await search.press("Enter");
    await expect(tools.locator("summary")).toBeFocused();
    await expect(tools).toHaveAttribute("open", "");
    await expect(stage).toHaveValue("parse");

    await stage.selectOption("all");
    await search.fill("mission_scoped_egress_consent");
    await expect(tools).toHaveCount(0);
  });
}

test("updates the command and clipboard of an open tool after switching the session terminal", async ({ page, context, baseURL }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: new URL(baseURL!).origin });
  await page.route("**/api/**", route => route.fulfill({ status: 503, json: {} }));
  await page.goto("/?api=local");
  await page.getByRole("button", { name: "DSH 插件", exact: true }).press("Enter");
  const catalogueTab = page.getByRole("tab", { name: "工具目录" });
  await catalogueTab.press("Enter");
  const catalogue = page.getByRole("tabpanel", { name: "工具目录" });
  const search = catalogue.getByRole("searchbox");
  await search.fill("cosmatter_plugin_catalogue");
  await search.press("Enter");
  const tool = catalogue.locator(".dsh-tool-item");
  const command = tool.locator(".dsh-command-text");
  const suffix = ` dsh-catalogue --port ${new URL(baseURL!).port}`;
  await expect(command).toHaveText("cosmatter" + suffix);
  await tool.getByRole("button", { name: "复制 DSH 命令" }).press("Enter");
  await expect(tool.getByRole("status")).toHaveText("DSH 命令已复制。");

  await page.getByRole("tab", { name: "DSH 会话" }).press("Enter");
  await page.getByLabel("命令运行环境").selectOption("windows-venv");
  await catalogueTab.press("Enter");
  await expect(tool).toHaveAttribute("open", "");
  await expect(tool.getByRole("status")).toHaveCount(0);
  const expected = ".\\.venv\\Scripts\\cosmatter.exe" + suffix;
  await expect(command).toHaveText(expected);
  await tool.getByRole("button", { name: "复制 DSH 命令" }).press("Enter");
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe(expected);
});
