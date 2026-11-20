import { expect, test } from "@playwright/test";

for (const width of [320, 1280]) {
  test("keeps edits with their direction and clears them when the research question changes at " + width + "px", async ({ page }) => {
    await page.setViewportSize({ width, height: 720 });
    const writes: string[] = [];
    page.on("request", request => {
      if (request.method() !== "GET") writes.push(request.method() + " " + new URL(request.url()).pathname);
    });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const prompt = page.getByLabel("候选航向研究问题");
    const routes = page.locator(".candidate-orbits").getByRole("button");
    const question = page.getByLabel("任务简报研究问题");
    const material = page.getByLabel("研究对象", { exact: true });
    const scope = page.getByLabel("比较范围", { exact: true });
    const confirm = page.getByRole("button", { name: "确认任务并进入编排" });
    const original = "不同外延应变如何影响 BiFeO₃ 薄膜的相稳定性？";
    await prompt.fill("薄膜中不同退火气氛如何改变载流子迁移率？");
    await prompt.fill(original);
    await expect(routes).toHaveCount(3);
    await routes.first().press("Enter");
    await expect(question).toBeFocused();
    await material.fill("人工选择的 (001) 薄膜 A");
    await scope.fill("仅比较同厚度、同温度的两个应变样品");
    await routes.nth(1).press("Enter");
    await expect(material).not.toHaveValue("人工选择的 (001) 薄膜 A");
    await material.fill("只用于第二航向的对照样品 B");
    await routes.first().press("Enter");
    await expect(question).toBeFocused();
    await expect(material).toHaveValue("人工选择的 (001) 薄膜 A");
    await expect(scope).toHaveValue("仅比较同厚度、同温度的两个应变样品");
    await routes.nth(1).press("Enter");
    await expect(material).toHaveValue("只用于第二航向的对照样品 B");

    await prompt.fill("");
    await expect(routes).toHaveCount(0);
    await expect(question).toHaveCount(0);
    await expect(prompt).toBeFocused();
    await prompt.fill(original);
    await expect(routes).toHaveCount(3);
    await routes.first().press("Enter");
    await expect(material).not.toHaveValue("人工选择的 (001) 薄膜 A");
    await expect(scope).not.toHaveValue("仅比较同厚度、同温度的两个应变样品");
    await prompt.fill("不同氧化气氛如何影响氧化锌薄膜的载流子密度？");
    await expect(routes).toHaveCount(3);
    await routes.first().press("Enter");
    await expect(material).not.toHaveValue("人工选择的 (001) 薄膜 A");
    await expect(scope).not.toHaveValue("仅比较同厚度、同温度的两个应变样品");
    await expect(question).toBeInViewport();
    await question.fill("相同温度下，两种氧化气氛如何影响氧化锌薄膜的载流子密度？");
    await material.fill("氧化锌薄膜");
    await page.getByLabel("研究目标", { exact: true }).fill("载流子密度");
    await scope.fill("比较相同温度下的两种氧化气氛");
    await expect(confirm).toBeEnabled();
    await confirm.press("Enter");
    await expect(page.locator(".view-workflow main h1")).toBeFocused({ timeout: 30_000 });
    expect(writes).toEqual([]);
  });
}

for (const reducedMotion of ["reduce", "no-preference"] as const) {
  test("hands off one authorized brief immediately with " + reducedMotion + " motion", async ({ page }) => {
    await page.emulateMedia({ reducedMotion });
    await page.setViewportSize({ width: reducedMotion === "reduce" ? 320 : 1280, height: 720 });
    const submissions: unknown[] = [];
    await page.route("**/api/**", route => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/api/status") return route.fulfill({ json: {
        api_mode: "loopback_only",
        providers: { deepseek: false, sciverse: false, mineru: false, openalex: false, crossref: true, crossref_polite_contact: false },
        operation_contracts: {
          schema_version: "cosmatter.operation-parameter-contracts/v1", trust_status: "static_parameter_contracts_not_execution_authorization",
          operations: { sciverse_read_content: { type: "object", additionalProperties: false, required: ["offset", "limit"],
            properties: { offset: { type: "integer", minimum: 0, default: 0 }, limit: { type: "integer", minimum: 200, maximum: 4000, default: 2000 } } } },
        },
      } });
      if (path === "/api/missions/auto") submissions.push(route.request().postDataJSON());
      return route.fulfill({ status: 503, json: {} });
    });
    await page.goto("/?api=local", { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: /BFO-01/ }).press("Enter");
    const scope = page.getByLabel("比较范围", { exact: true });
    await scope.fill("仅比较 298 K 和 350 K 的同厚度薄膜");
    const approved = {
      question: await page.getByLabel("任务简报研究问题").inputValue(),
      material: await page.getByLabel("研究对象", { exact: true }).inputValue(),
      property: await page.getByLabel("研究目标", { exact: true }).inputValue(),
      scope: await scope.inputValue(), sources: ["crossref"], consent: true,
    };
    await page.getByLabel(/我确认本次任务可向上列书目服务发送/).press("Space");
    const confirm = page.getByRole("button", { name: "确认并授权元数据检索" });
    await expect(confirm).toBeEnabled();
    await page.clock.install({ time: new Date("2030-01-01T00:00:00Z") });
    await page.clock.pauseAt(new Date("2030-01-01T01:00:00Z"));
    await confirm.press("Enter");
    // Keep the outgoing page mounted until its transition timer runs. Check actual keyboard reachability.
    const stillFocusable = await page.locator(".launchpad").evaluateAll(mains => {
      const controls = mains.flatMap(main => [...main.querySelectorAll<HTMLElement>(
        "[data-mission-field], .launch-auto-consent input, .launch-dsh-entry",
      )]);
      return controls.filter(control => {
        control.focus({ preventScroll: true });
        return document.activeElement === control;
      }).map(control => control.dataset.missionField ?? control.tagName);
    });
    expect(stillFocusable).toEqual([]);
    await expect.poll(() => submissions).toEqual([approved]);
    await page.keyboard.press("Enter");
    await page.clock.runFor(1000);
    await page.clock.resume();
    await expect(page.locator(".view-workflow main h1")).toBeFocused({ timeout: 30_000 });
    expect(submissions).toEqual([approved]);
  });
}
