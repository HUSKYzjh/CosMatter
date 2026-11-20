import { expect, test } from "@playwright/test";

test("restores the confirmed brief on return home and hands only the current question to DSH", async ({ page, baseURL }) => {
  const writes: string[] = [];
  await page.route("**/api/**", route => {
    if (route.request().method() !== "GET") writes.push(route.request().method());
    return route.fulfill({ status: 503, json: {} });
  });
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"], { origin: new URL(baseURL!).origin });
  await page.goto("/?api=local");
  await page.getByRole("button", { name: /BFO-01/ }).click();
  const question = "How does strain alter the transition in sample " + "BFO".repeat(50) + "?";
  const brief = { question, material: "BiFeO3", property: "Néel temperature", scope: "8 nm films at fixed strain" };
  const editor = page.locator(".launch-brief-editor");
  for (const [key, value] of Object.entries(brief)) {
    await editor.locator(`[data-mission-field="${key}"]`).fill(value);
  }
  await editor.getByRole("button", { name: "确认任务并进入编排" }).click();
  await page.getByRole("link", { name: "CosMatter", exact: true }).click();
  const card = page.getByRole("region", { name: "已确认的本地简报" });
  const restore = card.getByRole("button", { name: "返回已确认简报" });
  for (const width of [320, 1280]) {
    await page.setViewportSize({ width, height: 800 });
    await expect(card).toContainText(question);
    const [rect, copy] = await Promise.all([restore.boundingBox(), card.locator("p").boundingBox()]);
    expect(rect!.height).toBeGreaterThanOrEqual(44);
    expect(rect!.x).toBeGreaterThanOrEqual(0);
    expect(rect!.x + rect!.width).toBeLessThanOrEqual(width);
    expect(copy!.x + copy!.width <= rect!.x || copy!.y + copy!.height <= rect!.y).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
  const homeDsh = page.getByRole("button", { name: /DSH 插件/ });
  const dialog = page.getByRole("dialog");
  async function copyFields() {
    await homeDsh.press("Enter");
    const draft = dialog.getByRole("region", { name: "DSH 聊天草稿" });
    await draft.getByRole("button", { name: "复制到 DSH 聊天" }).click();
    await expect(draft.getByRole("status")).toContainText("已复制");
    const text = await page.evaluate(() => navigator.clipboard.readText());
    await page.keyboard.press("Escape");
    return JSON.parse(text.slice(text.search(/^\{/m)));
  }
  expect(await copyFields()).toEqual(brief);
  const prompt = page.getByLabel("候选航向研究问题");
  await prompt.fill("Ni");
  await expect(card).toHaveCount(0);
  expect(await copyFields()).toEqual({ question: "Ni" });
  await prompt.clear();
  for (const mode of [/文献入港：/, /续航任务：/]) {
    await page.getByRole("button", { name: mode }).click();
    await expect(card).toHaveCount(0);
    await homeDsh.click();
    await expect(dialog.getByRole("region", { name: "DSH 聊天草稿" })).toHaveCount(0);
    await page.keyboard.press("Escape");
  }
  await page.getByRole("button", { name: /问题启航：/ }).click();
  await restore.press("Enter");
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/);
  await expect(page.locator(".rail-run-id")).toHaveCount(0);
  expect(writes).toEqual([]);
});
