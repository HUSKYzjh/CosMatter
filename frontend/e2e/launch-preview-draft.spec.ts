import { expect, test, type Page } from "@playwright/test";

const status = {
  api_mode: "loopback_only",
  providers: { deepseek: true, sciverse: false, mineru: false, openalex: false, crossref: true, crossref_polite_contact: false },
  operation_contracts: {
    schema_version: "cosmatter.operation-parameter-contracts/v1",
    trust_status: "static_parameter_contracts_not_execution_authorization",
    operations: { sciverse_read_content: {
      type: "object", additionalProperties: false, required: ["offset", "limit"],
      properties: { offset: { type: "integer", minimum: 0, default: 0 }, limit: { type: "integer", minimum: 200, maximum: 4000, default: 2000 } },
    } },
  },
};

const question = "氧空位如何影响氧化锌薄膜的光学带隙？";
const candidate = {
  id: "oxide-optics", kind: "contrast", question,
  material: "氧化锌薄膜", property: "光学带隙", scope: "比较不同气氛的样品",
};

async function roundTrip(page: Page) {
  await page.getByRole("button", { name: "预览：任务定义" }).click();
  await page.getByRole("region", { name: "只读预览数据边界" }).getByRole("button", { name: "返回起始页" }).click();
}

test("restores edited candidate fields and their source after a preview without reusing consent or an older confirmed brief", async ({ page, context, baseURL }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: new URL(baseURL!).origin });
  const writes: string[] = [];
  await page.route("**/api/**", route => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() !== "GET") writes.push(path);
    if (path === "/api/status") return route.fulfill({ json: status });
    if (path === "/api/question-candidates") return route.fulfill({ json: { candidates: [candidate] } });
    return route.fulfill({ status: 503, json: {} });
  });
  await page.goto("/?api=local");
  const editor = page.locator(".launch-brief-editor");
  await page.getByRole("button", { name: /BFO-01/ }).click();
  await editor.getByRole("button", { name: "仅进入本机编排" }).click();
  await page.getByRole("link", { name: "CosMatter", exact: true }).click();
  const confirmed = page.getByRole("region", { name: "已确认的本地简报" });
  await expect(confirmed).toBeVisible();

  const prompt = page.getByLabel("候选航向研究问题");
  await prompt.fill(question);
  const modelConsent = page.getByLabel(/我同意将上述研究问题发送/);
  await modelConsent.check();
  const origin = page.getByRole("status", { name: "候选生成来源" });
  await expect(origin).toContainText("DeepSeek");
  await page.locator(".candidate-planet").getByText(question, { exact: true }).click();
  const brief = { question: "氧化锌的吸收边随氧空位浓度如何变化？", material: "氧化锌外延薄膜", property: "光学吸收边", scope: "限室温、同一基底、相同厚度" };
  for (const [field, value] of Object.entries(brief)) await editor.locator(`[data-mission-field="${field}"]`).fill(value);
  const retrievalConsent = page.getByLabel(/我确认本次任务可向上列书目服务发送/);
  await retrievalConsent.check();
  await roundTrip(page);
  await expect(prompt).toHaveValue(question);
  for (const [field, value] of Object.entries(brief)) await expect(editor.locator(`[data-mission-field="${field}"]`)).toHaveValue(value);
  await expect(modelConsent).not.toBeChecked();
  await expect(retrievalConsent).not.toBeChecked();
  await expect(editor.getByRole("button", { name: "确认并授权元数据检索" })).toBeDisabled();
  await expect(page.locator(".candidate-planet")).toHaveAttribute("aria-pressed", "true");
  await expect(confirmed).toHaveCount(0);

  await page.getByRole("button", { name: "DSH 插件", exact: true }).click();
  const draft = page.getByRole("region", { name: "DSH 聊天草稿" });
  await draft.getByRole("button", { name: "复制到 DSH 聊天" }).click();
  await expect(draft.getByRole("status")).toContainText("已复制");
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(JSON.parse(copied.slice(copied.search(/^\{/m)))).toEqual(brief);
  await page.keyboard.press("Escape");
  await expect(origin).toContainText("DeepSeek");
  expect(writes).toEqual(["/api/question-candidates"]);

  await editor.getByRole("button", { name: "仅进入本机编排" }).click();
  await page.getByRole("link", { name: "CosMatter", exact: true }).click();
  await expect(confirmed).toContainText(brief.question);
  await expect(prompt).toHaveValue("");
  await expect(editor).toHaveCount(0);
});

test("keeps an unselected question through preview and discards a delayed model result from the old page", async ({ page }) => {
  const writes: string[] = [];
  let release!: () => void;
  const delayed = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() !== "GET") writes.push(path);
    if (path === "/api/status") return route.fulfill({ json: status });
    if (path === "/api/question-candidates") {
      await delayed;
      return route.fulfill({ json: { candidates: [candidate] } });
    }
    return route.fulfill({ status: 503, json: {} });
  });
  await page.goto("/?api=local");
  const prompt = page.getByLabel("候选航向研究问题");
  await prompt.fill(question);
  const requested = page.waitForRequest("**/api/question-candidates");
  await page.getByLabel(/我同意将上述研究问题发送/).check();
  await requested;
  try {
    await roundTrip(page);
    await expect(prompt).toHaveValue(question);
    await expect(page.getByLabel(/我同意将上述研究问题发送/)).not.toBeChecked();
  } finally {
    release();
  }
  await expect(page.locator(".candidate-planet")).toHaveCount(3);
  await expect(page.getByRole("status", { name: "候选生成来源" })).toContainText("本机候选");
  await expect(page.locator(".launch-brief-editor")).toHaveCount(0);
  expect(writes).toEqual(["/api/question-candidates"]);
});
