import { expect, test, type Page } from "@playwright/test";
import { resolve } from "node:path";

const routeDiagnosticsExport = resolve(process.cwd(), "..", "examples", "ui-demo", "route_diagnostics.json");
const workspaceLoad = { timeout: 15_000 };
const lazyWorkspaceContentLoad = { timeout: 30_000 };

async function openEditableTaskDefinition(page: Page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /BFO-01/ }).click();
  await page.getByRole("button", { name: "确认任务并进入编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  await page.getByRole("button", { name: /任务定义/ }).first().click();
  await expect(page.locator(".workbench")).toHaveClass(/view-discover/, workspaceLoad);
  await page.locator("details.mission-api > summary").click();
  return page.locator(".import-control input[type=file]");
}

async function openMissionDefinitionWithPendingArtifacts(page: Page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /BFO-01/ }).click();
  await page.getByRole("button", { name: "确认任务并进入编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  await page.getByRole("button", { name: /任务定义/ }).first().click();
  await expect(page.locator(".workbench")).toHaveClass(/view-discover/, workspaceLoad);
}

test("keeps the narrow launch workspace horizontally contained", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const workspace = page.locator(".launch-workspace");
  await expect(workspace).toBeVisible();
  if (process.platform === "win32") {
    await expect(workspace).toHaveScreenshot("launch-workspace-narrow.png", { animations: "disabled" });
  } else {
    const box = await workspace.boundingBox();
    if (!box) throw new Error("launch workspace did not render a layout box");
    expect(Math.ceil(box.x + box.width)).toBeLessThanOrEqual(390);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test("keeps operational labels and evidence copy at a readable scale", async ({ page }) => {
  await page.setViewportSize({ width: 960, height: 900 });
  await page.goto("/", { waitUntil: "domcontentloaded" });

  const fontPixels = (selector: string) => page.locator(selector).first().evaluate((element) => Number.parseFloat(getComputedStyle(element).fontSize));
  expect(await fontPixels(".launch-modes button span")).toBeGreaterThanOrEqual(15);
  expect(await fontPixels(".launch-modes button small")).toBeGreaterThanOrEqual(12);
  expect(await fontPixels(".launch-stage-copy strong")).toBeGreaterThanOrEqual(14);
  expect(await fontPixels(".launch-stage-copy small")).toBeGreaterThanOrEqual(12);

  await page.getByRole("button", { name: "预览：受控编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  expect(await fontPixels(".workflow-artifact-flow h2")).toBeGreaterThanOrEqual(20);
  expect(await fontPixels(".workflow-artifact-flow p")).toBeGreaterThanOrEqual(15);
  expect(await fontPixels(".journey-track button small")).toBeGreaterThanOrEqual(12);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test("turns a typed question into an explicit selectable and confirmable mission path", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByLabel("候选航向研究问题").fill("围绕该研究议题，现有文献的研究对象、报告结论与证据边界分别是什么？");

  const handoff = page.locator(".candidate-handoff");
  await expect(handoff).toContainText("候选已生成；请选择一条航向", { timeout: 4_000 });
  const firstRoute = page.getByRole("button", { name: /全景梳理 点击选择此航向/ });
  await expect(firstRoute).toHaveAttribute("aria-pressed", "false");

  await firstRoute.click();
  await expect(handoff).toContainText("已选择候选航向；请在下方核对并编辑任务边界");
  await expect(page.getByRole("region", { name: "下一步 / 任务简报与可编辑边界" })).toBeVisible();
  const confirm = page.getByRole("button", { name: "确认任务并进入编排" });
  await expect(confirm).toBeDisabled();

  await page.getByLabel("研究对象").fill("BiFeO₃ 外延薄膜");
  await expect(confirm).toBeDisabled();
  await page.getByLabel("任务简报研究问题").fill("BiFeO₃ 外延薄膜的相稳定性在不同应变条件下如何变化？");
  await expect(confirm).toBeEnabled();
  await confirm.click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
});

test("keeps fallback routes tied to the entered material property instead of generic boilerplate", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const input = "BiFeO3的相转变温度是";
  await page.getByLabel("候选航向研究问题").fill(input);

  const routes = page.locator(".candidate-planet");
  await expect(routes).toHaveCount(3, { timeout: 4_000 });
  await expect(routes.nth(0)).toContainText("BiFeO₃");
  await expect(routes.nth(0)).toContainText("转变温区");
  await expect(routes.nth(1)).toContainText("体相、陶瓷与薄膜");
  await expect(routes.nth(2)).toContainText("材料分解与测量伪影");
  await expect(page.getByRole("status", { name: "候选生成来源" })).toContainText("本地问题绑定回退");
  await expect(page.getByRole("status", { name: "候选生成来源" })).toContainText("未连接本机候选生成 API");
  const visibleRoutes = (await routes.allTextContents()).join(" ");
  expect(visibleRoutes).not.toContain("围绕该研究议题");
  expect(visibleRoutes).not.toContain("需要优先核对哪些可定位的原文证据");

  await routes.nth(0).click();
  await expect(page.getByLabel("研究对象")).toHaveValue("BiFeO₃");
  await expect(page.getByLabel("研究目标")).toHaveValue("相转变温度");
  await expect(page.getByRole("button", { name: "确认任务并进入编排" })).toBeEnabled();
});

test("loads an explicitly server-selected UI bundle as a read-only literature map", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => { if (request.url().includes("/api/")) apiRequests.push(request.url()); });
  await page.route("**/ui.json", async (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      schema_version: "1.0",
      generated_at: "2026-09-05T00:00:00Z",
      mission: { mission_id: "mission_server_preview", question: "BiFeO3 的相变温度是多少？", material: "BiFeO3", property_name: "相变温度", scope: "按样品状态与测量条件比较" },
      literature_graph: {
        trust_status: "metadata_only_navigation_not_scientific_evidence",
        nodes: [{ node_id: "paper:bfo", kind: "candidate_paper", label: "Phase transitions in BiFeO3", trust_status: "candidate_metadata_not_scientific_evidence", source: "Sciverse" }],
        edges: [],
      },
    }),
  }));

  await page.goto("/?ui=server&api=local", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".workbench")).toHaveClass(/view-graph/, lazyWorkspaceContentLoad);
  await expect(page.getByText("只读预览：可查看阶段与空态")).toBeVisible();
  await expect(page.locator(".fleet-reading-cards")).toContainText("Phase transitions in BiFeO3");
  await expect(page.locator(".fleet-reading-cards")).toContainText("任务对象与维度双命中");
  expect(apiRequests).toEqual([]);
});

test("labels a rejected model result and retries without silently presenting it as DeepSeek output", async ({ page }) => {
  let candidateRequests = 0;
  await page.route("**/api/status", async (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ api_mode: "loopback_only", providers: { deepseek: true, sciverse: true, mineru: true, openalex: true, crossref: true, crossref_polite_contact: true } }),
  }));
  await page.route("**/api/question-candidates", async (route) => {
    candidateRequests += 1;
    if (candidateRequests === 1) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ error: "rejected" }) });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        trust_status: "untrusted_question_suggestions",
        candidates: [
          { id: "candidate_1", question: "哪些实验文献直接测定 BiFeO3 相转变温度及其不确定度？", material: "BiFeO3", property: "相转变温度", scope: "实验测量与误差", kind: "survey" },
          { id: "candidate_2", question: "哪些样品、气氛和升温条件解释 BiFeO3 相转变温度的文献分歧？", material: "BiFeO3", property: "相转变温度", scope: "可比条件", kind: "contrast" },
          { id: "candidate_3", question: "哪些原位结构观测可区分 BiFeO3 相转变温度附近的竞争相指派？", material: "BiFeO3", property: "相转变温度", scope: "机制判据", kind: "mechanism" },
        ],
      }),
    });
  });

  await page.goto("/?api=local", { waitUntil: "domcontentloaded" });
  const consent = page.getByLabel(/我同意将上述研究问题发送/);
  await expect(consent).toBeVisible();
  await page.getByLabel("候选航向研究问题").fill("BiFeO3的相转变温度是多少？");
  await consent.check();

  const origin = page.getByRole("status", { name: "候选生成来源" });
  await expect(origin).toContainText("本地问题绑定回退", { timeout: 4_000 });
  await expect(origin).toContainText("模型请求失败或输出未通过相关性校验");
  await page.getByRole("button", { name: "重新请求模型" }).click();
  await expect(origin).toContainText("DeepSeek 候选生成 · 已通过问题锚点校验", { timeout: 4_000 });
  await expect(page.locator(".candidate-planet").first()).toContainText("BiFeO3 相转变温度");
  expect(candidateRequests).toBe(2);
});

test("discloses every available automatic metadata destination before consent", async ({ page }) => {
  await page.route("**/api/status", async (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ api_mode: "loopback_only", providers: { deepseek: false, sciverse: true, mineru: true, openalex: true, crossref: true, crossref_polite_contact: true } }),
  }));

  await page.goto("/?api=local", { waitUntil: "domcontentloaded" });
  await page.getByLabel("候选航向研究问题").fill("BiFeO3的相转变温度是多少？");
  await page.locator(".candidate-planet").first().click();

  const destinations = page.getByRole("status").filter({ hasText: "本次元数据将发送至" });
  await expect(destinations).toContainText("Sciverse、OpenAlex、Crossref");
  await expect(page.getByLabel(/我确认本次任务可向上列书目服务发送/)).toBeVisible();
  await expect(page.getByRole("button", { name: "确认并授权元数据检索" })).toBeDisabled();
});

test("activates a BFO task template through the keyboard with an explicit pressed state", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const bfo = page.getByRole("button", { name: /BFO-01/ });
  await expect(bfo).toHaveAttribute("aria-pressed", "false");
  await bfo.focus();
  await page.keyboard.press("Enter");
  await expect(bfo).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByLabel("研究对象")).toHaveValue("BiFeO₃ 外延薄膜");
  await expect(page.getByRole("button", { name: "预览：任务定义" })).toHaveAttribute("aria-current", "step");
});

test("keeps synthetic launch-preview papers out of the real research route", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "预览：受控编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);

  const bridge = page.locator(".fleet-command-stage");
  await expect(bridge).toContainText("只读预览数据层", lazyWorkspaceContentLoad);
  await expect(bridge.locator(".workflow-next")).toContainText("等待受控检索或导入可审查文献子图");
  await expect(bridge).not.toContainText("20 篇可审查文献");

  await page.getByRole("button", { name: "03 文献星图" }).first().click();
  await expect(page.locator(".workbench")).toHaveClass(/view-graph/, workspaceLoad);
  await expect(page.locator(".graph-empty")).toContainText("仅供导航或演示的论文式节点", lazyWorkspaceContentLoad);
});

test("keeps the bridge artifact flow readable beside its research rail", async ({ page }) => {
  await page.setViewportSize({ width: 960, height: 900 });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "预览：受控编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);

  const flow = page.locator(".workflow-artifact-flow");
  await expect(flow).toBeVisible(lazyWorkspaceContentLoad);
  await expect(flow.locator("article")).toHaveCount(4);
  expect(await flow.evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/))).toHaveLength(2);
  expect(await flow.locator(":scope > i").evaluateAll((arrows) => arrows.every((arrow) => getComputedStyle(arrow).display === "none"))).toBe(true);
});

test("keeps the evidence proof chain readable beside its research rail", async ({ page }) => {
  await page.setViewportSize({ width: 960, height: 900 });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "预览：受控编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  await page.getByRole("button", { name: "04 证据核对" }).first().click();
  await expect(page.locator(".workbench")).toHaveClass(/view-reader/, workspaceLoad);

  const proofTrack = page.locator(".reader-proof-track");
  await expect(proofTrack).toBeVisible(lazyWorkspaceContentLoad);
  await expect(proofTrack.locator(".reader-proof-station")).toHaveCount(5);
  expect(await proofTrack.evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/))).toHaveLength(3);
  expect(await proofTrack.evaluate((element) => getComputedStyle(element, "::before").display)).toBe("none");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test("keeps an empty task explicit, then renders a redacted exported condition matrix", async ({ page }) => {
  const importInput = await openEditableTaskDefinition(page);

  await expect(page.locator(".mission-preview")).toContainText("尚未导入条件簇");
  await importInput.setInputFiles(routeDiagnosticsExport);

  await expect(page.locator(".rail-status")).toContainText("已导入 route_diagnostics.json");
  await expect(importInput).toHaveValue("");
  await expect(page.locator(".mission-preview")).toContainText("条件簇");
  await expect(page.locator(".mission-preview")).toContainText("1");
  const receipt = page.getByLabel("已导入工件摘要");
  await expect(receipt).toContainText("route_diagnostics.json");
  await expect(receipt).toContainText("工件自述版本");
  await expect(receipt).toContainText("1.0");
  await expect(receipt).toContainText("工件自述生成时间");
  await expect(receipt).toContainText("不会验证完整性、作者身份或科学结论");
  await expect(receipt).toContainText("文件大小");
  await expect(receipt).toContainText("可显示数据项");
  await expect(page.locator("body")).not.toContainText("Synthetic demonstration only; no paper text is included.");

  await page.getByRole("button", { name: "下一步：进入舰桥编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  await expect(page.getByLabel("当前本地工件")).toContainText("route_diagnostics.json");
  await expect(page.getByLabel("当前本地工件")).toContainText("1.0");
  await expect(page.getByLabel("当前本地工件")).toContainText("工件自述版本");
});

test("safely rejects malformed UI JSON without replacing the imported condition artifact", async ({ page }) => {
  const importInput = await openEditableTaskDefinition(page);
  await importInput.setInputFiles(routeDiagnosticsExport);
  await expect(page.locator(".rail-status")).toContainText("已导入 route_diagnostics.json");

  await importInput.setInputFiles({
    name: "malformed-ui.json",
    mimeType: "application/json",
    buffer: Buffer.from('{"mission":'),
  });

  await expect(page.locator(".rail-status")).toContainText("该 UI JSON 未通过格式校验");
  await expect(page.locator(".rail-status")).not.toContainText("SyntaxError");
  await expect(page.locator(".mission-preview")).toContainText("条件簇");
  await expect(page.locator(".mission-preview")).toContainText("1");
  await expect(page.getByLabel("已导入工件摘要")).toContainText("route_diagnostics.json");
});

test("opens the pending-condition navigation card through the keyboard without starting execution", async ({ page }) => {
  await openMissionDefinitionWithPendingArtifacts(page);
  const next = page.getByRole("button", { name: "下一步：导入条件工件" });
  await next.focus();
  await page.keyboard.press("Enter");

  await expect(page.locator("details.mission-api")).toHaveAttribute("open", "");
  await expect(page.locator(".import-control input[type=file]")).toBeVisible();
  await expect(page.locator(".rail-status")).toContainText("已打开高级手动受控执行");
});

test("opens a read-only evaluation audit from frozen-corpus readiness without claiming a metric", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/")) apiRequests.push(request.url());
  });
  const importInput = await openEditableTaskDefinition(page);
  await importInput.setInputFiles({
    name: "frozen-evaluation-readiness.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({
      schema_version: "1.0",
      mission: { mission_id: "frozen-evaluation-demo", question: "Inspect evaluation readiness only.", material: "BiFeO3", property_name: "phase stability", scope: "private review cohort" },
      audit_summary: {
        submission_readiness: {
          question_set: { reviewed_question_count: 8, included_question_count: 7, excluded_question_count: 1, included_evidence_level_counts: { literature_mentioned: 1, data_supported: 4, reproducible: 1, already_reproduced: 1 }, freeze_gate: "ready_for_question_level_evaluation_not_metrics" },
          frozen_corpus: { expected_document_count: 90, frozen_document_count: 90, expected_count_matched: true, document_id_uniqueness_valid: true, doi_present_count: 88, doi_missing_count: 2, authorized_access_boundary_valid: true, evaluation_gate: "ready_for_private_human_annotation" },
        },
      },
    })),
  });

  await expect(page.locator(".rail-status")).toContainText("已导入 frozen-evaluation-readiness.json");
  await page.getByRole("button", { name: "05 研究拓展" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-horizon/, workspaceLoad);
  const audit = page.getByLabel("审计与评测");
  await audit.locator("summary").click();
  await expect(page.getByLabel("评测前置门禁")).toContainText("可开始私有人工标注");
  await expect(audit).toContainText("未生成");
  await expect(page.getByLabel("评测下一步")).toContainText("在私有位置完成相关性金标准标注");
  await expect(audit).toContainText("不代表任何指标已经生成");
  expect(apiRequests).toEqual([]);
});

test("reviews a local question set without network activity or implicit approval", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/")) apiRequests.push(request.url());
  });
  await openMissionDefinitionWithPendingArtifacts(page);
  await expect(page.locator(".workbench")).toHaveClass(/view-discover/, workspaceLoad);

  const desk = page.getByLabel("冻结问题集人工审核台");
  await desk.locator("summary").click();
  await desk.locator("input[type=file]").setInputFiles({
    name: "bfo-question-review.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({
      schema_version: "cosmatter.question-set-review/v1",
      question_set_id: "bfo-ui-review-v1",
      material_family: "BiFeO3",
      trust_status: "blank_human_question_set_review_not_frozen",
      review_instructions: { decision: "Review every question.", checks: "Complete every check.", note: "Record a reason." },
      questions: [1, 2, 3].map((number) => ({
        question_id: `bfo-${number}`,
        question: `Which source-located BiFeO3 phase-transition value is reported for bounded condition ${number}?`,
        material: "BiFeO3",
        target_property: "phase-transition temperature",
        scope: `Condition ${number}; compare source-located reports only.`,
        intended_evidence_level: "data_supported",
        review_decision: "unreviewed",
        review_checks: { answerable_by_literature: null, material_explicit: null, target_property_explicit: null, scope_bounded: null, avoids_assumed_answer: null },
        review_note: "",
      })),
    })),
  });

  await expect(desk).toContainText("0/3");
  const attestation = desk.locator(".question-review-release input[type=checkbox]");
  await expect(attestation).toBeDisabled();
  const items = desk.locator(".question-review-item");
  await expect(items).toHaveCount(3);
  for (let index = 0; index < 3; index += 1) {
    const item = items.nth(index);
    await item.locator("select").first().selectOption("include");
    for (const check of await item.locator("fieldset select").all()) await check.selectOption("true");
    await item.locator("textarea").fill("Independently checked for wording, scope, and a source-locatable answer.");
  }
  await expect(desk).toContainText("3/3");
  await expect(attestation).toBeEnabled();
  await expect(desk.getByRole("button", { name: "导出本地审核草稿" })).toBeVisible();
  await attestation.check();
  await expect(desk.getByRole("button", { name: "导出可冻结审核 JSON" })).toBeVisible();
  await page.getByRole("button", { name: /^02 受控编排/ }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  await page.getByRole("button", { name: /^01 任务定义/ }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-discover/, workspaceLoad);
  await desk.locator("summary").click();
  await expect(desk).toContainText("已恢复本浏览器会话中的审核草稿");
  await expect(desk.locator(".question-review-item").first().locator("select").first()).toHaveValue("include");
  await expect(desk.locator(".question-review-release input[type=checkbox]")).not.toBeChecked();
  await expect(desk.getByRole("button", { name: "导出本地审核草稿" })).toBeVisible();
  await desk.locator("input[type=file]").setInputFiles({ name: "invalid-review.json", mimeType: "application/json", buffer: Buffer.from("{not-json") });
  await expect(desk.getByRole("alert")).toContainText("没有导入任何内容");
  await expect(desk.locator(".question-review-item")).toHaveCount(3);
  await desk.getByRole("button", { name: "清除本会话草稿" }).click();
  await expect(desk.locator(".question-review-item")).toHaveCount(3);
  await desk.getByRole("button", { name: "再次点击确认清除" }).click();
  await expect(desk.locator(".question-review-item")).toHaveCount(0);
  expect(apiRequests).toEqual([]);
});

test("reviews frozen-corpus relevance locally with exact bibliography binding and no implicit attestation", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/")) apiRequests.push(request.url());
  });
  await openMissionDefinitionWithPendingArtifacts(page);

  const instructions = {
    retrieval_relevance: "Mark relevance after reading the authorized paper.",
    evidence_annotations: "Preserve reviewed evidence annotations.",
    material_fact_annotations: "Preserve reviewed material-fact annotations.",
    comparison_annotations: "Preserve reviewed comparisons.",
    gap_annotations: "Preserve reviewed gap annotations.",
  };
  const gold = {
    schema_version: "1.0",
    mission_id: "mission-bfo-corpus-review",
    corpus_id: "bfo-ui-corpus-3",
    trust_status: "blank_human_annotation_template_not_evaluation_result",
    annotation_instructions: instructions,
    documents: [1, 2, 3].map((number) => ({
      document_id: `bfo-paper-${number}`,
      retrieval_relevance: "unreviewed",
      evidence_annotations: number === 1 ? [{ retained: "opaque" }] : [],
      material_fact_annotations: [],
      comparison_annotations: [],
      gap_annotations: [],
    })),
  };
  const manifest = {
    schema_version: "1.0",
    mission_id: gold.mission_id,
    corpus_id: gold.corpus_id,
    material: "BiFeO3",
    trust_status: "human_reviewed_authorized_corpus_manifest_not_evaluation_result",
    access_boundary: "institutional_access_local_review_only_no_fulltext_redistribution",
    documents: [1, 2, 3].map((number) => ({
      document_id: `bfo-paper-${number}`,
      title: `Source-located BiFeO3 transition study ${number}`,
      doi: number === 1 ? "10.1000/bfo.1" : null,
      access_policy: "institutional_access_internal_review_only",
    })),
  };

  const desk = page.getByLabel("冻结语料相关性人工审核台");
  await desk.locator("summary").click();
  const fileInputs = desk.locator("input[type=file]");
  await fileInputs.nth(0).setInputFiles({ name: "bfo-human-gold.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(gold)) });
  await expect(desk).toContainText("0/3");
  await fileInputs.nth(1).setInputFiles({ name: "bfo-corpus-manifest.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(manifest)) });
  await expect(desk).toContainText("Source-located BiFeO3 transition study 1");
  await expect(desk).toContainText("10.1000/bfo.1");

  const attestation = desk.locator(".corpus-review-release input[type=checkbox]");
  await expect(attestation).toBeDisabled();
  const items = desk.locator(".corpus-review-item");
  await expect(items).toHaveCount(3);
  await items.nth(0).locator("select").selectOption("relevant");
  await items.nth(1).locator("select").selectOption("partially_relevant");
  await items.nth(2).locator("select").selectOption("not_relevant");
  await expect(desk).toContainText("3/3");
  await expect(attestation).toBeEnabled();
  await expect(desk.getByRole("button", { name: "导出本地相关性草稿" })).toBeVisible();
  await attestation.check();
  await expect(desk.getByRole("button", { name: "导出可评测金标准" })).toBeVisible();

  await page.getByRole("button", { name: /^02 受控编排/ }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/, workspaceLoad);
  await page.getByRole("button", { name: /^01 任务定义/ }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-discover/, workspaceLoad);
  await desk.locator("summary").click();
  await expect(desk).toContainText("已恢复本浏览器会话中的相关性草稿");
  await expect(desk.locator(".corpus-review-item").first().locator("select")).toHaveValue("relevant");
  await expect(desk.locator(".corpus-review-release input[type=checkbox]")).not.toBeChecked();
  await expect(desk.getByRole("button", { name: "导出本地相关性草稿" })).toBeVisible();

  await desk.locator("input[type=file]").first().setInputFiles({ name: "invalid-human-gold.json", mimeType: "application/json", buffer: Buffer.from("{not-json") });
  await expect(desk.getByRole("alert")).toContainText("当前草稿保持不变");
  await expect(desk.locator(".corpus-review-item")).toHaveCount(3);
  await desk.getByRole("button", { name: "清除本会话草稿" }).click();
  await expect(desk.locator(".corpus-review-item")).toHaveCount(3);
  await desk.getByRole("button", { name: "再次点击确认清除" }).click();
  await expect(desk.locator(".corpus-review-item")).toHaveCount(0);
  expect(apiRequests).toEqual([]);
});

test("renders cross-source reconciliation revisions in the map without calling a local API", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/")) apiRequests.push(request.url());
  });
  const importInput = await openEditableTaskDefinition(page);
  await importInput.setInputFiles({
    name: "reconciliation-summary.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({
      schema_version: "1.0",
      generated_at: "2026-08-31T09:30:00Z",
      mission: { mission_id: "reconciliation-demo", question: "Inspect reviewed bibliography mappings.", material: "BiFeO3", property_name: "phase stability", scope: "synthetic UI fixture" },
      literature_graph: { trust_status: "human_reviewed_graph_projection", nodes: [{ node_id: "paper:demo-paper", kind: "candidate_paper", label: "Reviewable synthetic candidate", trust_status: "candidate_metadata_not_scientific_evidence" }], edges: [] },
      evidence_cards: [{ evidence_id: "evidence-demo", claim: "A reviewer-bound bibliography identity check.", stance: "context", conditions: {}, quote: "Identity mapping recorded for the selected paper.", review_status: "accepted", provenance: { document_id: "demo-paper", locator: "metadata_record:1", source: "human review", access_policy: "authorized" } }],
      relation_reconciliation: {
        trust_status: "human_reviewed_cross_source_identity_not_scientific_evidence",
        source: { evidence_id: "evidence-demo", document_id: "demo-paper" },
        mappings: [{ openalex_work_id: "https://openalex.org/W123", crossref_doi: "10.1000/demo", status: "conflict", basis: "Human review recorded a DOI disagreement." }],
        revision_history: [{ revision: 1, recorded_at: "2026-08-31T09:30:00Z", mapping_count: 1, status_counts: { matched: 0, conflict: 1, unresolved: 0 } }],
      },
      audit_summary: {
        evaluation: {
          evidence_quality: { trust_status: "metrics_from_human_reviewed_evidence_locator_condition_and_contradiction_audit", evidence_count: 8, predicted_contradiction_count: 3, citation_precision: 0.875, condition_completeness: 0.75, contradiction_precision: 2 / 3 },
        },
        submission_readiness: {
          question_set: { reviewed_question_count: 8, included_question_count: 7, excluded_question_count: 1, included_evidence_level_counts: { literature_mentioned: 1, data_supported: 4, reproducible: 1, already_reproduced: 1 }, freeze_gate: "ready_for_question_level_evaluation_not_metrics" },
          frozen_corpus: { expected_document_count: 90, frozen_document_count: 90, expected_count_matched: true, document_id_uniqueness_valid: true, doi_present_count: 88, doi_missing_count: 2, authorized_access_boundary_valid: true, evaluation_gate: "ready_for_private_human_annotation" },
          human_annotation: { frozen_document_count: 90, annotation_file_status: "human_reviewed_gold_standard_for_evaluation", relevance_counts: { unreviewed: 0, relevant: 50, partially_relevant: 20, not_relevant: 20 }, documents_with_evidence_annotations: 30, documents_with_material_fact_annotations: 25, documents_with_comparison_annotations: 18, documents_with_gap_annotations: 5, relevance_evaluation_gate: "ready_for_human_retrieval_evaluation" },
          bibliographic_source: { frozen_document_count: 90, documents_with_reviewed_bibliographic_source: 90, distinct_bibliographic_source_count: 3, bibliographic_source_coverage_gate: "ready_for_source_traceable_evaluation" },
        },
      },
    })),
  });

  await expect(page.locator(".rail-status")).toContainText("已导入 reconciliation-summary.json");
  await page.getByRole("button", { name: "03 文献星图" }).click();
  await expect(page.locator(".frontier-literature-workbench")).toBeVisible({ timeout: 30_000 });
  const route = page.getByLabel("舰队阅读航道");
  await expect(route).toContainText("航线 01");
  await expect(route).toContainText("完成人工筛选");
  expect(await route.locator(".fleet-formation-slot").evaluateAll((slots) => slots.every((slot) => {
    const bounds = slot.getBoundingClientRect();
    return [...slot.children].every((child) => child.getBoundingClientRect().bottom <= bounds.bottom + 1);
  }))).toBe(true);
  const panel = page.getByLabel("跨源标识人工对账");
  await expect(panel).toContainText("冲突，未合并");
  const summary = panel.locator("summary");
  await summary.focus();
  await page.keyboard.press("Enter");
  await expect(panel).toContainText("修订摘要（1 次）");
  await expect(panel).toContainText("映射 1 · 匹配 0 · 冲突 1 · 未决 0");
  await page.getByRole("button", { name: "05 研究拓展" }).click();
  const audit = page.locator("details.evaluation-audit");
  await expect(audit).toBeVisible({ timeout: 30_000 });
  await audit.locator("summary").click();
  await expect(audit).toContainText("引用定位");
  await expect(audit).toContainText("88%");
  await expect(audit).toContainText("已复核证据");
  const readiness = page.getByLabel("评测前置门禁");
  await expect(readiness).toContainText("冻结问题集");
  await expect(readiness).toContainText("纳入 7/8");
  await expect(readiness).toContainText("可开始逐题评测；指标仍未生成");
  await expect(readiness).toContainText("1 / 4 / 1 / 1");
  await expect(readiness).toContainText("90/90");
  await expect(readiness).toContainText("可开始私有人工标注");
  await expect(readiness).toContainText("相关性标注已齐备");
  await expect(readiness).toContainText("书目来源覆盖已齐备");
  await expect(audit).toContainText("不代表任何指标已经生成");
  expect(apiRequests).toEqual([]);
});
