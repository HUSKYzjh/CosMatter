import group from "../../plugins/dsh-plugin-group.json" with { type: "json" };
import { expect, test } from "@playwright/test";

const dshToolCount = group.packages.reduce((count, bundle) => count + bundle.tools.length, 0);

test("recovers a catalogue search in place and keeps the filters that still apply", async ({ page, context, baseURL }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: new URL(baseURL!).origin });
  await page.route("**/api/**", route => route.fulfill({ status: 503, json: {} }));
  await page.goto("/?api=local");
  await page.getByRole("button", { name: "DSH 插件", exact: true }).click();
  await page.getByRole("tab", { name: "工具目录" }).click();
  const tools = page.getByRole("tabpanel", { name: "工具目录" });
  const search = tools.getByRole("searchbox");
  const stage = tools.getByLabel("研究阶段");
  const access = tools.getByLabel("授权类型");
  await stage.selectOption("parse");
  await access.selectOption("external");

  await search.fill("nonexistent");
  await expect(tools).toContainText("全部工具中均未找到这个关键词");
  await tools.getByRole("button", { name: "查看当前筛选的 2 个工具" }).press("Enter");
  await expect(search).toBeFocused();
  await expect(search).toHaveValue("");
  await expect(stage).toHaveValue("parse");
  await expect(access).toHaveValue("external");
  await expect(tools.locator(".dsh-tool-item > summary code")).toHaveText(["cosmatter_mineru_source_submit", "cosmatter_mineru_task_poll"]);

  await search.fill("cosmatter_stage_contract");
  await expect(tools).toContainText("当前筛选没有匹配工具（需逐任务授权）");
  await tools.getByRole("button", { name: "查看全部 1 项匹配" }).press("Enter");
  await expect(stage).toHaveValue("parse");
  await expect(access).toHaveValue("all");
  await expect(search).toBeFocused();
  await expect(search).toHaveValue("cosmatter_stage_contract");
  await search.press("Enter");
  const item = tools.locator(".dsh-tool-item");
  await expect(item.locator("summary")).toBeFocused();
  await item.getByRole("button", { name: "复制工具名" }).click();
  await expect(item.getByRole("status")).toHaveText("工具名已复制。");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe("cosmatter_stage_contract");

  await stage.selectOption("report");
  await access.selectOption("external");
  await search.fill("nonexistent");
  await tools.getByRole("button", { name: `查看全部 ${dshToolCount} 个工具` }).press("Enter");
  await expect(search).toBeFocused();
  await expect(search).toHaveValue("");
  await expect(stage).toHaveValue("all");
  await expect(access).toHaveValue("all");
  await expect(tools.locator(".dsh-tool-item")).toHaveCount(dshToolCount);
  await access.selectOption("calculate");
  await expect(tools.locator(".dsh-tool-item > summary code")).toHaveText(["cosmatter_pst_occupancy_count", "cosmatter_md_field_response"]);
});
