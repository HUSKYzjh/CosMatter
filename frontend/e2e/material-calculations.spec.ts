import { expect, test } from "@playwright/test";

for (const width of [320, 1280]) {
  test(`calculates exact occupations and MD responses offline at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await page.route("**/api/**", route => route.fulfill({ status: 503, json: {} }));
    await page.goto("/?api=local");
    await page.getByRole("button", { name: "DSH 插件", exact: true }).click();
    await page.getByRole("tab", { name: "工具目录" }).click();
    const tools = page.getByRole("tabpanel", { name: "工具目录" });
    await tools.getByLabel("授权类型").selectOption("calculate");
    const occupation = tools.locator('[data-tool-name="cosmatter_pst_occupancy_count"]');
    await occupation.locator("summary").press("Enter");
    const pst = occupation.getByRole("form", { name: "Pb/Sr 占位计算" });
    const requests: string[] = [];
    page.on("request", request => { if (["fetch", "xhr"].includes(request.resourceType())) requests.push(request.url()); });

    const fraction = pst.getByLabel("Pb 占 A 位的分数 x");
    await fraction.fill("1/3");
    await fraction.press("Enter");
    await expect(pst).toContainText("512 个 A 位无法精确实现这个组分");
    await pst.getByRole("button", { name: /170 Pb/ }).press("Enter");
    await expect(fraction).toHaveValue("0.33203125");
    await expect(fraction).toBeFocused();
    await fraction.fill("1/256");
    await fraction.press("Enter");
    await expect(pst).toContainText("2 Pb · 510 Sr");
    await expect(pst.locator(".material-result code")).toHaveText("130816");
    await fraction.fill("1/2");
    await fraction.press("Enter");
    await expect(pst.locator(".material-result code")).toHaveText(/^\d{153}$/);
    expect(await pst.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBeTruthy();
    await fraction.fill("1/0");
    await fraction.press("Enter");
    await expect(pst.getByRole("alert")).toContainText("分母");
    await expect(pst.locator(".material-result")).toHaveCount(0);
    await occupation.locator("summary").press("Enter");

    const field = tools.locator('[data-tool-name="cosmatter_md_field_response"]');
    await field.locator("summary").press("Enter");
    const md = field.getByRole("form", { name: "MD 电场响应计算" });
    await md.getByLabel("场强幅值").fill("1e6");
    await md.getByLabel("负电场均值").fill("-5e-5");
    await md.getByLabel("正电场均值").fill("5e-5");
    await md.getByRole("button", { name: "计算场响应" }).press("Enter");
    await expect(md).toContainText("d33 = 50 pm/V");
    await md.getByLabel("力学边界").selectOption("fixed_strain");
    await expect(md.locator(".material-result")).toHaveCount(0);
    await md.getByRole("button", { name: "计算场响应" }).click();
    await expect(md.getByRole("alert")).toContainText("固定应力");
    await expect(md.getByLabel("力学边界")).toBeFocused();
    await md.getByLabel("计算目标").selectOption("polarization_C_per_m2");
    await expect(md.getByLabel("负电场均值")).toHaveValue("");
    await md.getByLabel("负电场均值").fill("0");
    await md.getByLabel("正电场均值").fill("0");
    await md.getByLabel("正电场均值").press("Enter");
    await expect(md).toContainText("epsilon_r_33 = 1 （无量纲）");
    expect(await md.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBeTruthy();
    expect(requests).toEqual([]);
  });
}
