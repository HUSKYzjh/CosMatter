import { expect, test } from "@playwright/test";

for (const width of [320, 1360]) {
  test(`browses matching DSH tools from the search field at ${width}px`, async ({ page }) => {
    const zh = width === 320;
    await page.setViewportSize({ width, height: zh ? 620 : 850 });
    await page.route("**/api/**", route => route.fulfill({ status: 503, json: {} }));
    await page.goto("/?api=local", { waitUntil: "domcontentloaded" });
    if (!zh) await page.getByRole("button", { name: "Switch to English" }).click();
    const opener = page.getByRole("button", { name: zh ? "DSH 插件" : "DSH plugins", exact: true });
    await opener.press("Enter");
    const tab = zh ? "工具目录" : "Tool catalogue";
    await page.getByRole("tab", { name: tab }).press("Enter");
    const catalogue = page.getByRole("tabpanel", { name: tab });
    const search = catalogue.getByRole("searchbox");
    const stage = catalogue.getByRole("combobox", { name: zh ? "研究阶段" : "Research stage" });
    await stage.selectOption("parse");
    await search.fill("MinerU");
    await expect(search).toHaveAccessibleDescription(zh ? /按向下键进入结果/ : /Press Down Arrow/);
    const submit = catalogue.locator('[data-tool-name="cosmatter_mineru_source_submit"]');
    const poll = catalogue.locator('[data-tool-name="cosmatter_mineru_task_poll"]');

    await search.dispatchEvent("keydown", { key: "ArrowDown", isComposing: true });
    await expect(search).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(search).toBeFocused();
    await page.keyboard.press("ArrowDown");
    await expect(submit.locator("summary")).toBeFocused();
    await page.keyboard.press("ArrowDown");
    await expect(poll.locator("summary")).toBeFocused();
    await expect(poll.locator("summary")).toBeInViewport({ ratio: 1 });
    await page.keyboard.press("ArrowDown");
    await expect(poll.locator("summary")).toBeFocused();
    await expect(catalogue.locator(".dsh-tool-item[open]")).toHaveCount(0);
    await page.keyboard.press("Enter");
    await expect(poll).toHaveAttribute("open", "");
    await page.keyboard.press("Tab");
    await expect(poll.getByRole("button", { name: zh ? "刷新插件状态" : "Refresh bundle status" })).toBeFocused();
    await page.keyboard.press("Shift+Tab");
    await page.keyboard.press("ArrowUp");
    await expect(submit.locator("summary")).toBeFocused();
    await page.keyboard.press("ArrowUp");
    await expect(search).toBeFocused();
    await expect(search).toHaveValue("MinerU");
    await expect(stage).toHaveValue("parse");

    await search.fill("no-such-MinerU-tool");
    await page.keyboard.press("ArrowDown");
    await expect(search).toBeFocused();
    await expect(search).not.toHaveAttribute("aria-describedby");
    await search.fill("cosmatter_mineru_task_poll");
    await page.keyboard.press("Enter");
    await expect(poll.locator("summary")).toBeFocused();
    await expect(poll).toHaveAttribute("open", "");
    await page.keyboard.press("Escape");
    await expect(opener).toBeFocused();
  });
}
