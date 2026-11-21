import { expect, test } from "@playwright/test";

test("opens the research inbox on demand and follows a matching run across pages", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 760 });
  const reads: URL[] = [];
  const records = Array.from({ length: 12 }, (_, i) => ({
    scope: "run", identifier: `bfo_sample_${String(i + 1).padStart(2, "0")}`,
    kind: "human_review_required", status: "open", priority: "review", stage: "plan", action_label: "complete_human_review",
  }));
  await page.route("**/api/**", route => {
    const url = new URL(route.request().url());
    if (url.pathname !== "/api/reminder-board") return route.fulfill({ status: 404, json: {} });
    reads.push(url);
    const id = url.searchParams.get("identifier") ?? "";
    const filtered = records.filter(item => item.identifier.includes(id) && url.searchParams.get("priority") !== "attention");
    const current = Math.min(Number(url.searchParams.get("page")), Math.max(1, Math.ceil(filtered.length / 10)));
    const items = filtered.slice((current - 1) * 10, current * 10);
    return route.fulfill({ json: {
      schema_version: "cosmatter.reminder-page/v1", page: current, page_size: 10, total_count: filtered.length,
      board: { schema_version: "cosmatter.project-reminder-board/v1",
        trust_status: "loopback_operational_reminders_not_schedule_or_execution_authorization",
        scheduler_status: "not_scheduled_local_observation_only", reminder_count: items.length, reminders: items },
    } });
  });
  await page.goto("/?api=local");
  await page.getByRole("button", { name: /^续航任务/ }).press("Enter");
  const inbox = page.locator("details.run-reminder-inbox");
  await expect(inbox.locator("summary")).toHaveText("跨任务待办");
  expect(reads.length).toBe(0);
  await inbox.locator("summary").press("Enter");
  await expect(inbox.getByRole("link")).toHaveCount(10);
  await inbox.getByRole("button", { name: "下一页" }).press("Enter");
  await expect(inbox.getByRole("link")).toHaveCount(2);
  const last = inbox.getByRole("link", { name: /bfo_sample_12/ });
  await expect(last).toHaveAttribute("href", page.url().split("?")[0] + "?api=local#run=bfo_sample_12");
  await expect(last).toHaveAttribute("target", "_blank");
  await inbox.getByLabel("运行或项目条目 ID").fill("_12");
  await inbox.getByRole("button", { name: "查找" }).press("Enter");
  await expect(inbox.getByRole("link")).toHaveCount(1);
  expect(reads.at(-1)?.searchParams.get("page")).toBe("1");
  await inbox.getByLabel("优先级").selectOption("attention");
  await expect(inbox.getByRole("status")).toHaveText("没有符合条件的待办。");
  expect(await inbox.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
});
