import { expect, test } from "@playwright/test";
import { LAUNCH_STAGES } from "../src/launchStages";

for (const width of [320, 390, 1366]) {
  test(`keeps each research stage reachable and contained at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 880 });
    await page.goto("/");
    const question = page.getByLabel("候选航向研究问题");
    await expect(question).toBeVisible();
    const questionBox = await question.boundingBox();
    const templates = await page.getByRole("region", { name: "BiFeO₃ 任务模板" }).boundingBox();
    expect(questionBox && templates && questionBox.y + questionBox.height <= templates.y).toBe(true);
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "跳至任务入口" })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator(".launch-workspace h2").first()).toBeFocused();

    await page.getByRole("button", { name: "预览：任务定义", exact: true }).click();
    const rail = page.getByRole("list", { name: "研究阶段" });
    for (const [index, stage] of LAUNCH_STAGES.entries()) {
      const button = rail.getByRole("button").nth(index);
      await expect(button.locator("strong")).toHaveText(stage.zh);
      if (width <= 420) {
        const lineLengths = await button.locator("strong").evaluate((label) => {
          const text = label.firstChild!;
          const lines = new Map<number, number>();
          const range = document.createRange();
          for (let i = 0; i < (text.textContent?.length ?? 0); i++) {
            range.setStart(text, i);
            range.setEnd(text, i + 1);
            const y = range.getBoundingClientRect().top;
            lines.set(y, (lines.get(y) ?? 0) + 1);
          }
          return [...lines.values()];
        });
        expect(lineLengths).toEqual([2, 2]);
        const bounds = await button.boundingBox();
        expect(bounds?.width).toBeGreaterThanOrEqual(44);
        expect(bounds?.height).toBeGreaterThanOrEqual(44);
      }
      await button.click();
      await expect(button).toHaveAttribute("aria-current", "step");
      await expect(page).toHaveTitle(stage.zh + " · CosMatter");
      await expect(page.locator("main:not(.route-loading) h1").first()).toBeVisible({ timeout: 20_000 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    }
    await page.getByRole("button", { name: "EN", exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await expect(page).toHaveTitle("Research extension · CosMatter");
  });
}
