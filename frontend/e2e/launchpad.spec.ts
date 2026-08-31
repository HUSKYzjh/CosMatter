import { expect, test, type Page } from "@playwright/test";
import { resolve } from "node:path";

const routeDiagnosticsExport = resolve(process.cwd(), "..", "examples", "ui-demo", "route_diagnostics.json");

async function openEditableTaskDefinition(page: Page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /BFO-01/ }).click();
  await page.getByRole("button", { name: "确认任务并进入编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/);
  await page.getByRole("button", { name: /任务定义/ }).first().click();
  await expect(page.locator(".workbench")).toHaveClass(/view-discover/);
  await page.locator("details.mission-api > summary").click();
  return page.locator(".import-control input[type=file]");
}

async function openMissionDefinitionWithPendingArtifacts(page: Page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /BFO-01/ }).click();
  await page.getByRole("button", { name: "确认任务并进入编排" }).click();
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/);
  await page.getByRole("button", { name: /任务定义/ }).first().click();
  await expect(page.locator(".workbench")).toHaveClass(/view-discover/);
}

test("keeps the narrow launch workspace horizontally contained", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".launch-workspace")).toHaveScreenshot("launch-workspace-narrow.png", { animations: "disabled" });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
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

  const bridge = page.locator(".fleet-command-stage");
  await expect(bridge).toContainText("只读预览数据层");
  await expect(bridge.locator(".workflow-next")).toContainText("等待受控检索或导入可审查文献子图");
  await expect(bridge).not.toContainText("20 篇可审查文献");

  await page.getByRole("button", { name: "03 文献星图" }).first().click();
  await expect(page.locator(".graph-empty")).toContainText("仅供导航或演示的论文式节点");
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
  await expect(page.locator(".workbench")).toHaveClass(/view-workflow/);
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
  expect(apiRequests).toEqual([]);
});
