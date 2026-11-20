import { expect, test } from "@playwright/test";

const title = "BiFeO₃ · 薄膜相变温度";
const runs = ["annealed", "as_grown"].map((sample, index) => ({
  run_id: "biFeO3_temperature_comparison_shared_prefix_" + sample,
  material: "BiFeO₃", property: "薄膜相变温度",
  updated_at: `2026-11-${17 - index}T09:00:00Z`, stopped: true,
}));

for (const width of [320, 1280]) {
  test.describe(`recent run records at ${width}px`, () => {
    test.use({ viewport: { width, height: 720 }, hasTouch: width === 320, timezoneId: "UTC" });

    test("identifies matching titles and returns to the chosen record", async ({ page }) => {
      const reads: string[] = [];
      await page.route("**/api/**", route => {
        const path = new URL(route.request().url()).pathname;
        if (path === "/api/recent-runs") return route.fulfill({ json: { schema_version: "cosmatter.recent-local-runs/v1", runs } });
        const run = runs.find(row => path.startsWith("/api/runs/" + row.run_id + "/"));
        if (!run) return route.fulfill({ status: 503, json: {} });
        reads.push(route.request().method() + " " + path);
        const identity = { run_id: run.run_id, mission_id: "mission_" + run.run_id };
        if (path.endsWith("/status")) return route.fulfill({ json: { ...identity, state: "CANCELLED" } });
        if (path.endsWith("/artifacts")) return route.fulfill({ json: { ...identity, schema_version: "cosmatter.artifact/v1",
          trust_status: "allowlisted_artifact_index_not_scientific_evidence", artifact_count: 0, artifacts: [] } });
        return route.fulfill({ status: 404 });
      });
      await page.goto("/?api=local");
      await page.getByRole("button", { name: /^续航任务/ }).press("Enter");
      const list = page.getByRole("region", { name: "最近的本机任务" });
      const rows = list.getByRole("listitem");
      await expect(rows).toHaveCount(2);
      const actions = runs.map(run => list.getByRole("button", { name: "查看记录 " + run.run_id, exact: true }));
      for (const [index, action] of actions.entries()) {
        await expect(rows.nth(index).getByText(title, { exact: true })).toBeVisible();
        const updated = await rows.nth(index).locator("time").innerText();
        await expect(action).toHaveAccessibleDescription(title + " " + updated);
      }
      const record = page.getByRole("region", { name: "已停止的任务记录" });
      const close = record.getByRole("button", { name: "关闭记录" });
      const selected = actions[1];
      if (width === 320) {
        await selected.scrollIntoViewIfNeeded();
        const reachable = await selected.evaluate(el => {
          const rect = el.getBoundingClientRect();
          return rect.left >= 0 && rect.right <= innerWidth && el.contains(document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2));
        });
        expect(reachable).toBe(true);
        await selected.tap();
      } else {
        await list.getByRole("button", { name: "刷新列表" }).focus();
        await page.keyboard.press("Tab");
        await expect(actions[0]).toBeFocused();
        await page.keyboard.press("Tab");
        await expect(selected).toBeFocused();
        await page.keyboard.press("Enter");
      }
      await expect(record.getByRole("heading")).toBeFocused();
      await expect(record.locator("header code")).toHaveText(runs[1].run_id);
      await expect(record.getByText("暂无可下载的工件。")).toBeVisible();
      if (width === 320) await close.tap();
      else await close.press("Enter");
      await expect(selected).toBeFocused();
      await expect(selected).toBeInViewport({ ratio: 1 });
      await page.keyboard.press("Shift+Tab");
      await expect(actions[0]).toBeFocused();
      expect(reads).toEqual(["status", "artifacts"].map(resource => "GET /api/runs/" + runs[1].run_id + "/" + resource));
      if (width === 1280) {
        const byId = page.getByRole("textbox", { name: "现有运行 ID" });
        await byId.fill(runs[1].run_id);
        await byId.press("Enter");
        await expect(record.getByRole("heading")).toBeFocused();
        await close.press("Enter");
        await expect(byId).toBeFocused();
      }
    });
  });
}
