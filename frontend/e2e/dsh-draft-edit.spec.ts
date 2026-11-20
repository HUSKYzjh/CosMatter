import { expect, test } from "@playwright/test";

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
}
